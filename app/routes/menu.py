from flask import Blueprint, render_template, request, jsonify
from app.models.table import Table
from app.models.product import Product
from app.models.category import Category
from app.models.order import Order, OrderItem
from app.models.notification import Notification
from app import db, csrf
import random
import string
import time

# Rate limiting en memoria (se resetea con cold starts, pero funciona durante instancias calientes)
_rate_limit_store = {}

menu_bp = Blueprint('menu', __name__, url_prefix='/menu')

# 1. RUTA PARA MOSTRAR LA CARTA (No requiere login)
@menu_bp.route('/<qr_code>')
def view_menu(qr_code):
    # Buscamos la mesa por su código secreto
    table = Table.query.filter_by(qr_code=qr_code).first_or_404()
    categories = Category.query.filter_by(is_active=True).all()
    products = Product.query.filter_by(is_available=True).all()
    
    return render_template('carta-digital.html', table=table, categories=categories, products=products)

# 2. RUTA PARA RECIBIR EL PEDIDO DESDE EL CELULAR DEL CLIENTE
@csrf.exempt  # API JSON pública, no usa sesiones de Flask
@menu_bp.route('/<qr_code>/order', methods=['POST'])
def place_order(qr_code):
    # Rate limiting por IP real (máx 5 pedidos por minuto)
    # Usar X-Forwarded-For para obtener la IP real en Vercel/proxies
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr) or 'unknown'
    if ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()
    rate_key = f'menu_rate_{client_ip}'
    now = time.time()
    recent_orders = _rate_limit_store.get(rate_key, [])
    recent_orders = [t for t in recent_orders if now - t < 60]  # Último minuto
    if len(recent_orders) >= 5:
        return jsonify({'error': 'Demasiados pedidos. Espera un momento.'}), 429
    
    table = Table.query.filter_by(qr_code=qr_code).first_or_404()
    data = request.json
    
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'Datos inválidos'}), 400
        
    cart = data.get('cart', [])

    if not cart or not isinstance(cart, list):
        return jsonify({'error': 'El carrito está vacío'}), 400
    
    if len(cart) > 30:
        return jsonify({'error': 'Demasiados items en el pedido'}), 400

    # Verificamos si la mesa ya tiene una cuenta abierta para sumarle los platos, o si creamos una nueva
    active_order = Order.query.filter_by(table_id=table.id).filter(Order.status.in_(['pending', 'preparing', 'ready', 'served'])).first()

    if not active_order:
        chars = string.ascii_uppercase + string.digits
        order_num = 'WEB-' + ''.join(random.choices(chars, k=5))
        active_order = Order(
            table_id=table.id,
            user_id=None, # Pedido Web (Sin mozo)
            order_number=order_num,
            status='pending',
            total_amount=0
        )
        table.status = 'occupied'
        db.session.add(active_order)
        db.session.flush()

    total_added = 0
    items_added = 0
    for item in cart:
        # Validación estricta de cada item
        if not isinstance(item.get('id'), int) or not isinstance(item.get('cantidad'), int):
            continue
        if item['cantidad'] < 1 or item['cantidad'] > 50:
            continue
            
        product = Product.query.get(item['id'])
        if not product or not product.is_available:
            continue
            
        qty = item['cantidad']
        
        # Validar stock si se trackea
        if product.track_stock and product.stock < qty:
            continue
        if product.track_stock:
            product.stock -= qty
            
        subtotal = float(product.price) * qty
        total_added += subtotal
        items_added += 1
        new_item = OrderItem(
            order_id=active_order.id,
            product_id=product.id,
            quantity=qty,
            unit_price=product.price,
            subtotal=subtotal,
            status='pending',
            notes=str(item.get('notas', ''))[:200]  # Limitar notas a 200 chars
        )
        db.session.add(new_item)
    
    if items_added == 0:
        return jsonify({'error': 'No se pudo agregar ningún producto válido'}), 400

    active_order.total_amount = float(active_order.total_amount) + total_added

    # Notificamos al sistema interno
    Notification.create(
        type='system', 
        message=f"¡Nuevo pedido WEB recibido en la Mesa {table.number}!", 
        user_id=None
    )

    db.session.commit()
    
    # Registrar para rate limiting
    recent_orders.append(now)
    _rate_limit_store[rate_key] = recent_orders
    
    # Limpiar entradas viejas del store cada 100 pedidos para evitar memory leak
    if len(_rate_limit_store) > 100:
        cutoff = now - 120
        _rate_limit_store.clear()

    return jsonify({'success': True, 'message': 'Pedido enviado a cocina'})