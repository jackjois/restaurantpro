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
from app.models.reservation import Reservation
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

    # Reservaciones pendientes (desde hoy en adelante)
    reservations_pending = Reservation.query.filter(
        Reservation.reservation_time >= today_start_utc,
        Reservation.status != 'cancelled'
    ).order_by(Reservation.reservation_time).all()
    
    reservations_data = []
    for r in reservations_pending:
        res_time_local = r.reservation_time.astimezone(PERU_TZ)
        time_str = res_time_local.strftime('%I:%M %p')
        
        # Siempre agregamos la fecha para claridad
        meses = {1:'Ene',2:'Feb',3:'Mar',4:'Abr',5:'May',6:'Jun',7:'Jul',8:'Ago',9:'Sep',10:'Oct',11:'Nov',12:'Dic'}
        fecha_str = f"{res_time_local.day} {meses[res_time_local.month]}"
        time_str = f"{fecha_str} - {time_str}"
            
        reservations_data.append({
            'id': r.id,
            'table_number': r.table.number if r.table else '-',
            'customer_name': r.customer_name,
            'time': time_str,
            'guests': r.guest_count,
            'status': r.status
        })

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
        'reservations': reservations_data,
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
        
        # Check if it was the last item. If so, cancel the order and free the table
        if len(order.items) <= 1: # <=1 because the item is still in the collection until commit
            order.status = 'cancelled'
            order.notes = (order.notes or '') + ' [Cancelada automáticamente por falta de ítems]'
            if order.table_rel:
                order.table_rel.status = 'free'
                
        db.session.commit()
        AppSignal.emit('floor_item_removed', 'order_items')

        return jsonify({'success': True, 'order': _serialize_order(order)})
    except Exception as e:
        db.session.rollback()
        logger.exception('Error eliminando item %s de orden %s', item_id, order_id)
        return jsonify({'success': False, 'error': 'Error interno.'}), 500


# ───────────────────────────────────────────────
# API: Actualizar cantidad de un item (sin recrearlo)
# ───────────────────────────────────────────────

@floor_bp.route('/api/order/<int:order_id>/item/<int:item_id>/set_qty', methods=['POST'])
@login_required
@role_required('admin', 'cashier', 'waiter')
def api_set_item_qty(order_id, item_id):
    """Actualiza la cantidad de un item existente (mantiene id/estado)."""
    order = db.session.get(Order, order_id, with_for_update=True)
    if not order:
        return jsonify({'success': False, 'error': 'Orden no encontrada.'}), 404
    if order.status in ['paid', 'cancelled']:
        return jsonify({'success': False, 'error': 'Orden cerrada.'}), 400

    item = db.session.get(OrderItem, item_id, with_for_update=True)
    if not item or item.order_id != order.id:
        return jsonify({'success': False, 'error': 'Item no encontrado.'}), 404

    # Para evitar desorden operativo: solo permitir ajuste libre en items en cola
    if item.status != 'pending':
        return jsonify({'success': False, 'error': 'Este item ya fue enviado a cocina. No se puede cambiar la cantidad.'}), 400

    data = request.get_json() or {}
    new_qty = safe_int(data.get('quantity'), default=None)
    if new_qty is None or new_qty < 1 or new_qty > 99:
        return jsonify({'success': False, 'error': 'Cantidad inválida.'}), 400

    old_qty = safe_int(item.quantity, default=1)
    if new_qty == old_qty:
        return jsonify({'success': True, 'order': _serialize_order(order)})

    product = item.product or db.session.get(Product, item.product_id, with_for_update=True)
    if not product or not product.is_available:
        return jsonify({'success': False, 'error': 'Producto no disponible.'}), 400

    try:
        diff_qty = new_qty - old_qty

        # Ajuste de stock por diferencia
        if product.track_stock:
            if diff_qty > 0:
                if product.stock < diff_qty:
                    return jsonify({'success': False, 'error': f'Stock insuficiente. Disponible: {product.stock}'}), 400
                product.stock -= diff_qty
            elif diff_qty < 0:
                product.stock += (-diff_qty)

        old_subtotal = float(item.subtotal or 0)
        new_subtotal = float(item.unit_price) * new_qty

        item.quantity = new_qty
        item.subtotal = new_subtotal

        # Ajustar total de la orden por diferencia
        order.total_amount = max(0, float(order.total_amount or 0) + (new_subtotal - old_subtotal))

        db.session.commit()
        AppSignal.emit('floor_item_qty_updated', 'order_items')

        return jsonify({'success': True, 'order': _serialize_order(order)})
    except Exception:
        db.session.rollback()
        logger.exception('Error actualizando cantidad item %s en orden %s', item_id, order_id)
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
# API: Cancelar orden completa
# ───────────────────────────────────────────────

@floor_bp.route('/api/order/<int:order_id>/cancel', methods=['POST'])
@login_required
@role_required('admin', 'cashier', 'waiter')
def api_cancel_order(order_id):
    """Cancela una orden completa y libera la mesa."""
    order = db.session.get(Order, order_id, with_for_update=True)
    if not order:
        return jsonify({'success': False, 'error': 'Orden no encontrada.'}), 404
    if order.status in ['paid', 'cancelled']:
        return jsonify({'success': False, 'error': 'La orden ya está cerrada o cancelada.'}), 400

    try:
        # Devolver stock de los items que controlan stock
        for item in order.items:
            if item.product and item.product.track_stock:
                item.product.stock += item.quantity
            # Mantener consistencia con el resto del sistema: anular items al anular la orden
            if item.status != 'cancelled':
                item.status = 'cancelled'

        order.status = 'cancelled'
        order.notes = (order.notes or '') + ' [Cancelada manualmente]'
        
        # Liberar la mesa
        if order.table_rel:
            order.table_rel.status = 'free'

        db.session.commit()
        AppSignal.emit('floor_order_cancelled', 'orders')
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.exception('Error cancelando orden %s', order_id)
        return jsonify({'success': False, 'error': 'Error interno al cancelar la orden.'}), 500


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
    """
    Envía/notifica el pedido a cocina (KOT) sin iniciar preparación.
    
    En este sistema, la cocina (KDS) es quien marca el paso 'pending' -> 'preparing'.
    """
    order = Order.query.get_or_404(order_id)

    sent_count = sum(1 for item in order.items if item.status == 'pending')

    if sent_count > 0:
        # Notificación para cocina (sin cambiar estado de items)
        table_num = order.table_rel.number if order.table_rel else 'N/A'
        Notification.create(
            type='system',
            message=f'🔥 Pedido enviado a cocina: {sent_count} item(s) de Mesa {table_num}',
            user_id=None
        )
        AppSignal.emit('floor_kot_sent', 'order_items')
        db.session.commit()

    # No cambiamos estados; cocina decide cuándo pasa a 'preparing'
    return jsonify({'success': True, 'sent_count': sent_count, 'order': _serialize_order(order)})


# ───────────────────────────────────────────────
# API: Reservaciones
# ───────────────────────────────────────────────

@floor_bp.route('/api/reservations', methods=['POST'])
@login_required
@role_required('admin', 'cashier')
def api_create_reservation():
    """Crea una nueva reservación."""
    data = request.get_json() or {}
    table_id = data.get('table_id')
    name = data.get('customer_name')
    phone = data.get('customer_phone', '')
    res_date = data.get('date') # YYYY-MM-DD
    res_time = data.get('time') # HH:MM
    guests = safe_int(data.get('guest_count'), default=1)
    notes = data.get('notes', '')

    if not all([table_id, name, res_date, res_time]):
        return jsonify({'success': False, 'error': 'Faltan datos requeridos.'}), 400

    table = Table.query.get(table_id)
    if not table:
        return jsonify({'success': False, 'error': 'Mesa no encontrada.'}), 404

    try:
        # Parse datetime and convert to UTC
        dt_str = f"{res_date} {res_time}"
        local_dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
        local_dt = local_dt.replace(tzinfo=PERU_TZ)
        utc_dt = local_dt.astimezone(timezone.utc)

        reservation = Reservation(
            table_id=table.id,
            customer_name=name,
            customer_phone=phone,
            reservation_time=utc_dt,
            guest_count=guests,
            notes=notes,
            status='confirmed'
        )
        
        # Marcar la mesa como reservada visualmente si es para hoy
        now = datetime.now(PERU_TZ)
        if local_dt.date() == now.date() and table.status == 'free':
            table.status = 'reserved'

        db.session.add(reservation)
        db.session.commit()
        AppSignal.emit('floor_reservation_created', 'reservations')

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.exception('Error creando reservación')
        return jsonify({'success': False, 'error': 'Error al crear la reservación. Verifique el formato de fecha.'}), 500


@floor_bp.route('/api/reservation/<int:res_id>/cancel', methods=['POST'])
@login_required
@role_required('admin', 'cashier')
def api_cancel_reservation(res_id):
    """Cancela una reservación."""
    reservation = db.session.get(Reservation, res_id, with_for_update=True)
    if not reservation:
        return jsonify({'success': False, 'error': 'Reservación no encontrada.'}), 404

    try:
        reservation.status = 'cancelled'
        
        # Si la mesa está marcada como reservada, la liberamos
        if reservation.table and reservation.table.status == 'reserved':
            reservation.table.status = 'free'

        db.session.commit()
        AppSignal.emit('floor_reservation_cancelled', 'reservations')
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.exception('Error cancelando reservación')
        return jsonify({'success': False, 'error': 'Error interno al cancelar la reservación.'}), 500



# ───────────────────────────────────────────────
# API: Split Bill (Dividir Cuenta / Separar Items)
# ───────────────────────────────────────────────

@floor_bp.route('/api/order/<int:order_id>/split', methods=['POST'])
@login_required
@role_required('admin', 'cashier')
def api_split_order(order_id):
    """Extrae los items especificados y crea una nueva orden para cobrarlos."""
    original_order = db.session.get(Order, order_id, with_for_update=True)
    if not original_order:
        return jsonify({'success': False, 'error': 'Orden original no encontrada.'}), 404
        
    data = request.get_json() or {}
    items_to_split = data.get('items') # List of dicts: [{'item_id': 1, 'qty': 2}]
    
    if not items_to_split or len(items_to_split) == 0:
        return jsonify({'success': False, 'error': 'No se seleccionaron items para separar.'}), 400

    try:
        # Crear nueva orden para los items separados (Sin mesa para evitar colisiones en la vista de piso)
        new_order = Order(
            table_id=None,
            user_id=current_user.id,
            order_number=generate_order_number(),
            order_type='takeaway', # Se marca como takeaway o para llevar
            status='pending',
            total_amount=0,
            notes=f'[SPLIT] Cuenta separada de la orden {original_order.order_number}.'
        )
        db.session.add(new_order)
        db.session.flush() # Para obtener new_order.id
        
        new_total = 0.0
        original_total_reduction = 0.0
        remaining_items_count = len(original_order.items)
        
        for split_req in items_to_split:
            item_id = split_req.get('item_id')
            split_qty = safe_int(split_req.get('qty'), default=0)
            
            if split_qty <= 0:
                continue
                
            orig_item = OrderItem.query.get(item_id)
            if not orig_item or orig_item.order_id != original_order.id:
                continue
                
            if split_qty > orig_item.quantity:
                return jsonify({'success': False, 'error': f'Cantidad a separar mayor a la disponible para {orig_item.product.name}.'}), 400
                
            unit_price = float(orig_item.unit_price)
            split_subtotal = unit_price * split_qty
            
            # Crear el item en la nueva orden
            new_item = OrderItem(
                order_id=new_order.id,
                product_id=orig_item.product_id,
                quantity=split_qty,
                unit_price=unit_price,
                subtotal=split_subtotal,
                status=orig_item.status,
                notes=orig_item.notes
            )
            db.session.add(new_item)
            
            new_total += split_subtotal
            original_total_reduction += split_subtotal
            
            # Reducir el original
            orig_item.quantity -= split_qty
            orig_item.subtotal = float(orig_item.subtotal) - split_subtotal
            
            if orig_item.quantity == 0:
                db.session.delete(orig_item)
                remaining_items_count -= 1
                
        if new_total == 0:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'No se procesó ningún item válido.'}), 400
            
        new_order.total_amount = new_total
        original_order.total_amount = max(0, float(original_order.total_amount or 0) - original_total_reduction)
        
        if remaining_items_count == 0:
            original_order.status = 'cancelled'
            if original_order.table_rel:
                original_order.table_rel.status = 'free'
                
        db.session.commit()
        AppSignal.emit('floor_order_split', 'orders')
        
        return jsonify({'success': True, 'new_order_id': new_order.id})
    except Exception as e:
        db.session.rollback()
        logger.exception('Error haciendo split de orden %s', order_id)
        return jsonify({'success': False, 'error': 'Error interno al procesar el split.'}), 500
