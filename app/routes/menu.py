from flask import Blueprint, render_template, request, jsonify
from app.models.table import Table
from app.models.product import Product
from app.models.category import Category
from app.models.order import Order, OrderItem
from app.models.notification import Notification
from app.models.app_signal import AppSignal
from app import db, csrf
import random
import string
import time
from datetime import datetime, timezone, timedelta

menu_bp = Blueprint('menu', __name__, url_prefix='/menu')

def get_now_utc():
    return datetime.now(timezone.utc)

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
    table = Table.query.filter_by(qr_code=qr_code).first_or_404()
    
    # RATE LIMITING CON BASE DE DATOS (SERVERLESS SAFE)
    one_min_ago = get_now_utc() - timedelta(minutes=1)
    
    # Limitar 2 pedidos web por minuto POR MESA
    table_orders_count = Order.query.filter(
        Order.user_id == None,
        Order.table_id == table.id,
        Order.created_at >= one_min_ago
    ).count()
    if table_orders_count >= 2:
        return jsonify({'error': 'Acabas de hacer un pedido. Espera 1 minuto.'}), 429
        
    # Limitar a 30 pedidos web por minuto GLOBALES en el restaurante (anti botnet DDoS)
    global_orders_count = Order.query.filter(
        Order.user_id == None,
        Order.created_at >= one_min_ago
    ).count()
    if global_orders_count >= 30:
        return jsonify({'error': 'El sistema está recibiendo muchos pedidos en este momento.'}), 429
    
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

    AppSignal.emit('digital_menu_order', 'orders')
    db.session.commit()

    return jsonify({'success': True, 'message': 'Pedido enviado a cocina'})