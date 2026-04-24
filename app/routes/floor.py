"""
Floor & Orders — Módulo POS Visual avanzado
Blueprint con vista principal + API JSON para interacción SPA-like.
"""
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from app.utils.decorators import role_required
from app.utils.formatters import safe_int, safe_float
from app.models.order import Order, OrderItem
from app.models.table import Table
from app.models.product import Product
from app.models.category import Category
from app.models.payment import Payment
from app.models.cash_register import CashSession
from app.models.notification import Notification
from app.models.app_signal import AppSignal
from app import db
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

PERU_TZ = timezone(timedelta(hours=-5))

floor_bp = Blueprint('floor', __name__, url_prefix='/floor')


def generate_order_number():
    """Genera un número de pedido único basado en secuencia de BD."""
    try:
        with db.session.begin_nested():
            seq = db.session.execute(db.text("SELECT nextval('order_number_seq')")).scalar()
            date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
            return f'ORD-{date_part}-{seq:04d}'
    except Exception:
        import random, string
        chars = string.ascii_uppercase + string.digits
        return 'ORD-' + ''.join(random.choices(chars, k=6))


# ───────────────────────────────────────────────
# VISTA PRINCIPAL
# ───────────────────────────────────────────────

@floor_bp.route('/')
@login_required
@role_required('admin', 'cashier', 'waiter')
def index():
    """Renderiza la vista Floor & Orders (template standalone dark)."""
    return render_template('floor/floor.html')


# ───────────────────────────────────────────────
# API: Estado completo del piso
# ───────────────────────────────────────────────

@floor_bp.route('/api/status')
@login_required
@role_required('admin', 'cashier', 'waiter')
def api_status():
    """Devuelve JSON con todo el estado actual del restaurante."""
    # --- Mesas con órdenes activas ---
    tables = Table.query.order_by(Table.number).all()
    active_orders = Order.query.filter(
        Order.table_id.isnot(None),
        Order.status.notin_(['paid', 'cancelled'])
    ).all()
    orders_map = {o.table_id: o for o in active_orders}

    tables_data = []
    occupied_count = 0
    occupied_seats = 0
    total_seats = 0

    for t in tables:
        total_seats += t.capacity
        t_data = {
            'id': t.id,
            'number': t.number,
            'capacity': t.capacity,
            'status': t.status or 'free',
            'location': t.location or '',
            'active_order': None
        }
        if t.id in orders_map:
            order = orders_map[t.id]
            occupied_count += 1
            occupied_seats += t.capacity
            t_data['active_order'] = _serialize_order(order)
        elif t.status == 'occupied':
            occupied_count += 1
            occupied_seats += t.capacity

        tables_data.append(t_data)

    # --- KPIs ---
    now_peru = datetime.now(PERU_TZ)
    today_start_peru = now_peru.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start_peru = today_start_peru + timedelta(days=1)
    today_start_utc = today_start_peru.astimezone(timezone.utc)
    tomorrow_start_utc = tomorrow_start_peru.astimezone(timezone.utc)

    today_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'completed',
        Payment.created_at >= today_start_utc,
        Payment.created_at < tomorrow_start_utc
    ).scalar() or 0.0

    today_orders = Order.query.filter(
        Order.created_at >= today_start_utc,
        Order.created_at < tomorrow_start_utc,
        Order.status != 'cancelled'
    ).count()

    # Menu availability
    total_products = Product.query.filter_by(is_available=True).count()
    low_stock_threshold = 10
    low_stock_items = Product.query.filter(
        Product.is_available == True,
        Product.track_stock == True,
        Product.stock <= low_stock_threshold,
        Product.stock > 0
    ).all()
    out_of_stock = Product.query.filter(
        Product.track_stock == True,
        Product.stock <= 0
    ).count()

    total_tables = len(tables)
    occupancy_pct = round((occupied_count / total_tables * 100)) if total_tables > 0 else 0

    # --- Categorías y productos para el menú ---
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    products = Product.query.filter_by(is_available=True).order_by(Product.name).all()

    categories_data = [{'id': c.id, 'name': c.name, 'icon': c.icon, 'color': c.color} for c in categories]
    products_data = []
    for p in products:
        products_data.append({
            'id': p.id,
            'name': p.name,
            'description': p.description or '',
            'price': float(p.price),
            'image_url': p.image_url or '',
            'category_id': p.category_id,
            'track_stock': p.track_stock,
            'stock': p.stock if p.track_stock else None
        })

    return jsonify({
        'tables': tables_data,
        'categories': categories_data,
        'products': products_data,
        'kpis': {
            'revenue_today': float(today_revenue),
            'orders_today': today_orders,
            'occupancy_pct': occupancy_pct,
            'occupied_tables': occupied_count,
            'total_tables': total_tables,
            'total_seats': total_seats,
            'occupied_seats': occupied_seats,
            'menu_available': total_products - out_of_stock,
            'menu_total': total_products,
            'low_stock_items': [{'name': i.name, 'stock': i.stock} for i in low_stock_items]
        }
    })


def _serialize_order(order):
    """Serializa una orden con sus items para JSON."""
    items = []
    subtotal = 0
    for item in order.items:
        if item.status == 'cancelled':
            continue
        item_data = {
            'id': item.id,
            'product_id': item.product_id,
            'name': item.product.name if item.product else 'Producto',
            'quantity': item.quantity,
            'unit_price': float(item.unit_price),
            'subtotal': float(item.subtotal),
            'notes': item.notes or '',
            'status': item.status
        }
        items.append(item_data)
        subtotal += float(item.subtotal)

    discount_pct = float(order.discount_percent or 0)
    tip_val = float(order.tip or 0)
    discount_amount = round(subtotal * discount_pct / 100, 2)
    grand_total = round(subtotal - discount_amount + tip_val, 2)

    waiter_name = ''
    if order.waiter:
        waiter_name = order.waiter.full_name or order.waiter.username

    return {
        'id': order.id,
        'order_number': order.order_number,
        'status': order.status,
        'waiter': waiter_name,
        'items': items,
        'subtotal': subtotal,
        'discount_percent': discount_pct,
        'discount_amount': discount_amount,
        'tip': tip_val,
        'grand_total': grand_total,
        'created_at': order.created_at.isoformat() if order.created_at else ''
    }


# ───────────────────────────────────────────────
# API: Crear orden para una mesa
# ───────────────────────────────────────────────

@floor_bp.route('/api/table/<int:table_id>/order', methods=['POST'])
@login_required
@role_required('admin', 'cashier', 'waiter')
def api_create_order(table_id):
    """Crea una orden nueva para una mesa libre."""
    table = db.session.get(Table, table_id, with_for_update=True)
    if not table:
        return jsonify({'success': False, 'error': 'Mesa no encontrada.'}), 404
    if table.status != 'free':
        return jsonify({'success': False, 'error': 'La mesa ya está ocupada.'}), 400

    try:
        new_order = Order(
            table_id=table.id,
            user_id=current_user.id,
            order_number=generate_order_number(),
            order_type='dine_in',
            status='pending',
            total_amount=0
        )
        table.status = 'occupied'
        db.session.add(new_order)
        db.session.commit()
        AppSignal.emit('floor_order_created', 'orders')

        return jsonify({'success': True, 'order': _serialize_order(new_order)})
    except Exception as e:
        db.session.rollback()
        logger.exception('Error creando orden floor para mesa %s', table_id)
        return jsonify({'success': False, 'error': 'Error interno.'}), 500


# ───────────────────────────────────────────────
# API: Agregar item a orden
# ───────────────────────────────────────────────

@floor_bp.route('/api/order/<int:order_id>/add_item', methods=['POST'])
@login_required
@role_required('admin', 'cashier', 'waiter')
def api_add_item(order_id):
    """Agrega un producto a una orden activa."""
    order = db.session.get(Order, order_id, with_for_update=True)
    if not order:
        return jsonify({'success': False, 'error': 'Orden no encontrada.'}), 404
    if order.status in ['paid', 'cancelled']:
        return jsonify({'success': False, 'error': 'Orden cerrada.'}), 400

    data = request.get_json() or {}
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)
    notes = data.get('notes', '')

    if not product_id or quantity < 1 or quantity > 99:
        return jsonify({'success': False, 'error': 'Datos inválidos.'}), 400

    product = db.session.get(Product, product_id, with_for_update=True)
    if not product or not product.is_available:
        return jsonify({'success': False, 'error': 'Producto no disponible.'}), 400

    if product.track_stock and product.stock < quantity:
        return jsonify({'success': False, 'error': f'Stock insuficiente. Disponible: {product.stock}'}), 400

    try:
        if product.track_stock:
            product.stock -= quantity

        subtotal = float(product.price) * quantity
        item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=product.price,
            subtotal=subtotal,
            notes=notes,
            status='pending'
        )
        db.session.add(item)

        # Recalcular total
        order.total_amount = float(order.total_amount or 0) + subtotal
        db.session.commit()
        AppSignal.emit('floor_item_added', 'order_items')

        return jsonify({'success': True, 'order': _serialize_order(order)})
    except Exception as e:
        db.session.rollback()
        logger.exception('Error agregando item a orden %s', order_id)
        return jsonify({'success': False, 'error': 'Error interno.'}), 500


# ───────────────────────────────────────────────
# API: Eliminar item de orden
# ───────────────────────────────────────────────

@floor_bp.route('/api/order/<int:order_id>/remove_item/<int:item_id>', methods=['POST'])
@login_required
@role_required('admin', 'cashier', 'waiter')
def api_remove_item(order_id, item_id):
    """Elimina un item de la orden."""
    order = db.session.get(Order, order_id, with_for_update=True)
    if not order:
        return jsonify({'success': False, 'error': 'Orden no encontrada.'}), 404
    if order.status in ['paid', 'cancelled']:
        return jsonify({'success': False, 'error': 'Orden cerrada.'}), 400

    item = OrderItem.query.get(item_id)
    if not item or item.order_id != order.id:
        return jsonify({'success': False, 'error': 'Item no encontrado.'}), 404

    if item.status == 'delivered':
        return jsonify({'success': False, 'error': 'Item ya entregado. No se puede eliminar.'}), 400

    try:
        if item.product and item.product.track_stock:
            item.product.stock += item.quantity

        order.total_amount = max(0, float(order.total_amount or 0) - float(item.subtotal or 0))
        db.session.delete(item)
        db.session.commit()
        AppSignal.emit('floor_item_removed', 'order_items')

        return jsonify({'success': True, 'order': _serialize_order(order)})
    except Exception as e:
        db.session.rollback()
        logger.exception('Error eliminando item %s de orden %s', item_id, order_id)
        return jsonify({'success': False, 'error': 'Error interno.'}), 500


# ───────────────────────────────────────────────
# API: Actualizar descuento / propina
# ───────────────────────────────────────────────

@floor_bp.route('/api/order/<int:order_id>/update', methods=['POST'])
@login_required
@role_required('admin', 'cashier', 'waiter')
def api_update_order(order_id):
    """Actualiza discount/tip de una orden."""
    order = db.session.get(Order, order_id, with_for_update=True)
    if not order:
        return jsonify({'success': False, 'error': 'Orden no encontrada.'}), 404

    data = request.get_json() or {}

    if 'discount_percent' in data:
        val = safe_float(data['discount_percent'], default=0.0)
        order.discount_percent = max(0, min(val, 100))

    if 'tip' in data:
        order.tip = max(0, safe_float(data['tip'], default=0.0))

    try:
        db.session.commit()
        return jsonify({'success': True, 'order': _serialize_order(order)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Error interno.'}), 500


# ───────────────────────────────────────────────
# API: Cambiar status de mesa (right-click)
# ───────────────────────────────────────────────

@floor_bp.route('/api/table/<int:table_id>/status', methods=['POST'])
@login_required
@role_required('admin', 'cashier')
def api_table_status(table_id):
    """Cambia el status de una mesa manualmente."""
    table = db.session.get(Table, table_id, with_for_update=True)
    if not table:
        return jsonify({'success': False, 'error': 'Mesa no encontrada.'}), 404

    data = request.get_json() or {}
    new_status = data.get('status')
    allowed = ('free', 'occupied', 'reserved', 'maintenance')
    if new_status not in allowed:
        return jsonify({'success': False, 'error': 'Estado no válido.'}), 400

    table.status = new_status
    db.session.commit()
    AppSignal.emit('floor_table_status', 'tables')

    return jsonify({'success': True, 'status': new_status})


# ───────────────────────────────────────────────
# API: Enviar KOT (Kitchen Order Ticket)
# ───────────────────────────────────────────────

@floor_bp.route('/api/order/<int:order_id>/send_kot', methods=['POST'])
@login_required
@role_required('admin', 'cashier', 'waiter')
def api_send_kot(order_id):
    """Marca items pendientes como 'preparing' (enviados a cocina)."""
    order = Order.query.get_or_404(order_id)

    sent_count = 0
    for item in order.items:
        if item.status == 'pending':
            item.status = 'preparing'
            sent_count += 1

    if sent_count > 0:
        db.session.commit()
        AppSignal.emit('floor_kot_sent', 'order_items')

        # Notificación para cocina
        table_num = order.table_rel.number if order.table_rel else 'N/A'
        Notification.create(
            type='system',
            message=f'🔥 KOT enviado: {sent_count} item(s) de Mesa {table_num}',
            user_id=None
        )
        db.session.commit()

    return jsonify({'success': True, 'sent_count': sent_count, 'order': _serialize_order(order)})
