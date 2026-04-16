from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.utils.decorators import role_required
from app.models.order import Order, OrderItem
from app.models.table import Table
from app.utils.formatters import safe_int, safe_float
from app.models.product import Product
from app.models.category import Category
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.app_signal import AppSignal
from app import db
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

orders_bp = Blueprint('orders', __name__, url_prefix='/orders')

def generate_order_number():
    """Genera un número de pedido único basado en secuencia de BD."""
    try:
        # Savepoint explícito para no corromper la transacción externa si la secuencia no existe
        with db.session.begin_nested():
            seq = db.session.execute(db.text("SELECT nextval('order_number_seq')")).scalar()
            date_part = datetime.now(timezone.utc).strftime('%Y%m%d')
            return f'ORD-{date_part}-{seq:04d}'
    except Exception:
        # Fallback si la secuencia no existe aún
        import random, string
        chars = string.ascii_uppercase + string.digits
        return 'ORD-' + ''.join(random.choices(chars, k=6))

@orders_bp.route('/')
@login_required
@role_required('admin', 'cashier')
def index():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('orders/list.html', orders=orders)

@orders_bp.route('/pos/<int:table_id>')
@login_required
@role_required('admin', 'cashier', 'waiter')
def pos(table_id):
    table = Table.query.get_or_404(table_id)
    if table.status != 'free':
        flash('Esta mesa ya está ocupada o no está disponible.', 'warning')
        return redirect(url_for('tables.monitor'))
    
    products = Product.query.filter_by(is_available=True).all()
    categories = Category.query.all()
    return render_template('orders/pos.html', table=table, products=products, categories=categories)

@orders_bp.route('/submit_pos/<int:table_id>', methods=['POST'])
@login_required
@role_required('admin', 'cashier', 'waiter')
def submit_pos(table_id):
    table = Table.query.get_or_404(table_id)
    if table.status != 'free':
        return {'success': False, 'error': 'La mesa fue ocupada por otro usuario.'}, 400
        
    data = request.get_json()
    cart = data.get('cart', [])
    
    if not cart:
        return {'success': False, 'error': 'El carrito está vacío.'}, 400

    try:
        new_order = Order(
            table_id=table.id,
            user_id=current_user.id,
            order_number=generate_order_number(),
            status='pending',
            total_amount=0
        )
        table.status = 'occupied'
        db.session.add(new_order)
        db.session.flush()

        total = 0
        for item in cart:
            product = Product.query.get(item['id'])
            if product:
                qty = int(item['cantidad'])
                subtotal = float(product.price) * qty
                total += subtotal
                
                order_item = OrderItem(
                    order_id=new_order.id,
                    product_id=product.id,
                    quantity=qty,
                    unit_price=product.price,
                    subtotal=subtotal,
                    status='pending'
                )
                db.session.add(order_item)
                
                if product.track_stock:
                    product.stock -= qty

        new_order.total_amount = total
        db.session.commit()
        AppSignal.emit('pos_order_created', 'orders')

        flash(f'Comanda generada e iniciada (Mesa {table.number}).', 'success')
        return {'success': True, 'order_id': new_order.id}
        
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}, 500


@orders_bp.route('/create/<int:table_id>', methods=['POST'])
@login_required
@role_required('admin', 'cashier', 'waiter')
def create(table_id):
    table = Table.query.get_or_404(table_id)
    if table.status != 'free':
        flash('Esta mesa ya está ocupada o no está disponible.', 'warning')
        return redirect(url_for('tables.monitor'))

    new_order = Order(
        table_id=table.id,
        user_id=current_user.id,
        order_number=generate_order_number(),
        status='pending',
        total_amount=0
    )
    table.status = 'occupied'
    db.session.add(new_order)
    db.session.commit()
    AppSignal.emit('order_created', 'orders')

    flash(f'Pedido {new_order.order_number} iniciado para la Mesa {table.number}.', 'success')
    return redirect(url_for('orders.details', id=new_order.id))

@orders_bp.route('/create_external', methods=['POST'])
@login_required
@role_required('admin', 'cashier', 'waiter')
def create_external():
    order_type = request.form.get('order_type', 'takeaway')
    customer_name = request.form.get('customer_name', '')
    customer_phone = request.form.get('customer_phone', '')
    delivery_address = request.form.get('delivery_address', '')
    delivery_fee = safe_float(request.form.get('delivery_fee'), default=0.0)
        
    new_order = Order(
        table_id=None,
        user_id=current_user.id,
        order_number=generate_order_number(),
        order_type=order_type,
        customer_name=customer_name,
        customer_phone=customer_phone,
        delivery_address=delivery_address if order_type == 'delivery' else None,
        delivery_fee=delivery_fee if order_type == 'delivery' else 0.00,
        status='pending',
        total_amount=delivery_fee
    )
    
    db.session.add(new_order)
    db.session.commit()
    AppSignal.emit('external_order_created', 'orders')
    
    tipo_str = "Delivery" if order_type == 'delivery' else "Para Llevar"
    flash(f'Pedido {new_order.order_number} ({tipo_str}) iniciado para {customer_name}.', 'success')
    return redirect(url_for('orders.details', id=new_order.id))

@orders_bp.route('/<int:id>')
@login_required
def details(id):
    order = Order.query.get_or_404(id)
    products = Product.query.filter_by(is_available=True).all()
    categories = Category.query.all()
    
    cancel_log = None
    if order.status == 'cancelled':
        from app.models.audit_log import AuditLog
        cancel_log = AuditLog.query.filter_by(action='CANCEL_ORDER', entity_type='orders', entity_id=order.id).order_by(AuditLog.created_at.desc()).first()

    return render_template('orders/details.html', order=order, products=products, categories=categories, cancel_log=cancel_log)

@orders_bp.route('/<int:id>/add_item', methods=['POST'])
@login_required
@role_required('admin', 'cashier', 'waiter')
def add_item(id):
    order = Order.query.get_or_404(id)
    
    if order.status in ['paid', 'cancelled']:
        flash('Seguridad: No se pueden añadir platos a una orden cerrada o anulada.', 'danger')
        return redirect(url_for('orders.details', id=order.id))
        
    product_id = safe_int(request.form.get('product_id'))
    quantity = safe_int(request.form.get('quantity'), default=1)
    notes = request.form.get('notes', '')

    # Bloqueo pesimista para evitar race condition en stock
    product = db.session.query(Product).with_for_update().get(product_id)
    if not product:
        abort(404)
    
    if product.track_stock:
        if product.stock < quantity:
            flash(f'Stock insuficiente para {product.name}. Disponible: {product.stock}', 'danger')
            return redirect(url_for('orders.details', id=order.id))
        product.stock -= quantity

    subtotal = product.price * quantity

    item = OrderItem(order_id=order.id, product_id=product.id, quantity=quantity, unit_price=product.price, subtotal=subtotal, notes=notes, status='pending')
    order.total_amount = float(order.total_amount) + float(subtotal)
    db.session.add(item)
    db.session.commit()
    AppSignal.emit('item_added', 'order_items')
    return redirect(url_for('orders.details', id=order.id))

@orders_bp.route('/remove_item/<int:item_id>', methods=['POST'])
@login_required
@role_required('admin', 'cashier', 'waiter')
def remove_item(item_id):
    item = OrderItem.query.get_or_404(item_id)
    order = Order.query.get(item.order_id)
    
    if order.status in ['paid', 'cancelled']:
        flash('Seguridad: No se pueden eliminar platos de una orden cerrada o anulada.', 'danger')
        return redirect(url_for('orders.details', id=order.id))
        
    if item.status == 'delivered':
        flash('El plato ya fue entregado a la mesa. Debe anularse desde administración.', 'warning')
        return redirect(url_for('orders.details', id=order.id))
        
    # Reintegro de inventario
    if item.product.track_stock:
        item.product.stock += item.quantity
        
    # Restar del total de la orden
    order.total_amount = float(order.total_amount) - float(item.subtotal)
    if order.total_amount < 0:
        order.total_amount = 0
        
    db.session.delete(item)
    
    AuditLog.log('REMOVE_ITEM', 'order_items', order.id, f"Se eliminó {item.quantity}x {item.product.name} de la orden {order.order_number}", current_user.id)
    
    db.session.commit()
    AppSignal.emit('item_removed', 'order_items')

    flash(f'{item.product.name} eliminado de la orden correctamente.', 'success')
    return redirect(url_for('orders.details', id=order.id))

@orders_bp.route('/kitchen')
@login_required
def kitchen():
    pending_items = db.session.query(OrderItem).join(Order).filter(OrderItem.status.in_(['pending', 'preparing']), Order.status != 'cancelled').order_by(OrderItem.created_at).all()
    return render_template('orders/kitchen.html', items=pending_items)

@orders_bp.route('/kitchen/update/<int:item_id>', methods=['POST'])
@login_required
def update_item_status(item_id):
    item = OrderItem.query.get_or_404(item_id)
    new_status = request.form.get('status')
    item.status = new_status
    db.session.commit()
    AppSignal.emit('kitchen_status_update', 'order_items')
    
    if new_status == 'ready':
        parent_order = Order.query.get(item.order_id)
        table_num = parent_order.table_rel.number if parent_order and parent_order.table_rel else 'N/A'
        dish_name = item.product.name
        
        # Guardamos con user_id=None para que sea GLOBAL
        mensaje = f"¡El plato {dish_name} de la Mesa {table_num} está listo!"
        Notification.create(type='system', message=mensaje, user_id=None)
        db.session.commit()

    return redirect(url_for('orders.kitchen'))

@orders_bp.route('/cancel/<int:id>', methods=['POST'])
@login_required
@role_required('admin', 'cashier')
def cancel(id):
    order = Order.query.get_or_404(id)
    table = Table.query.get(order.table_id)
    cancel_reason = request.form.get('cancel_reason', 'Motivo no especificado')
    
    # AUTOLIMPIEZA GLOBAL DE NOTIFICACIONES
    if table:
        unreads = Notification.query.filter(
            Notification.is_read == False,
            Notification.message.like(f"%Mesa {table.number}%")
        ).all()
        for n in unreads:
            n.is_read = True

    if order.total_amount == 0:
        if table: table.status = 'free'
        order.status = 'cancelled'  # Soft-delete: no eliminar datos financieros
        db.session.commit()
        AppSignal.emit('order_cancelled', 'orders')

        flash('Pedido cancelado por error de apertura.', 'success')
    else:
        order.status = 'cancelled'
        for item in order.items: 
            item.status = 'cancelled'
            if item.product.track_stock:
                item.product.stock += item.quantity
        if table: table.status = 'free'
        
        AuditLog.log('CANCEL_ORDER', 'orders', order.id, f"Pedido {order.order_number} anulado. Monto: {order.total_amount}. Motivo: {cancel_reason}", current_user.id)
        
        db.session.commit()
        AppSignal.emit('order_cancelled', 'orders')

        flash('Pedido anulado y mesa liberada.', 'warning')
    return redirect(url_for('tables.monitor'))

@orders_bp.route('/comanda/<int:order_id>')
@login_required
def comanda(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('orders/comanda.html', order=order)

@orders_bp.route('/notifications/read', methods=['POST'])
@login_required
def read_notifications():
    unread = Notification.get_by_user(current_user.id, unread_only=True, limit=50)
    for n in unread:
        n.mark_as_read()
    db.session.commit()
    return redirect(request.referrer or url_for('tables.monitor'))