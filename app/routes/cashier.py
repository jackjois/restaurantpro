from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.utils.decorators import role_required
from app.models.order import Order
from app.models.table import Table
from app.models.payment import Payment, Invoice
from app.models.notification import Notification 
from app.models.cash_register import CashSession
from app.models.cash_expense import CashExpense
from app.models.audit_log import AuditLog
from app.models.app_signal import AppSignal
from datetime import datetime, timezone, timedelta
from app import db
from app.utils.formatters import safe_float
import logging

logger = logging.getLogger(__name__)

cashier_bp = Blueprint('cashier', __name__, url_prefix='/cashier')

@cashier_bp.route('/')
@login_required
@role_required('admin', 'cashier')
def pos():
    active_orders = Order.query.filter(Order.status.notin_(['paid', 'cancelled'])).order_by(Order.created_at.desc()).all()
    current_session = CashSession.query.filter_by(status='open').first()
    
    # Convertir hora de apertura a Perú para mostrar correctamente
    opening_time_peru = None
    if current_session and current_session.opening_time:
        PERU_TZ = timezone(timedelta(hours=-5))
        ot = current_session.opening_time
        if ot.tzinfo is None:
            ot = ot.replace(tzinfo=timezone.utc)
        opening_time_peru = ot.astimezone(PERU_TZ)
    
    return render_template('cashier/pos.html', orders=active_orders, current_session=current_session, opening_time_peru=opening_time_peru)

@cashier_bp.route('/open_session', methods=['POST'])
@login_required
@role_required('admin')
def open_session():
    existing = CashSession.query.filter_by(status='open').first()
    if existing:
        flash('Ya existe una caja abierta.', 'warning')
        return redirect(url_for('cashier.pos'))
        
    opening_amount = safe_float(request.form.get('opening_amount'), default=0.0)
    
    new_session = CashSession(
        user_id=current_user.id,
        opening_amount=opening_amount,
        status='open'
    )
    db.session.add(new_session)
    db.session.flush()
    
    AuditLog.log('OPEN_SESSION', 'cash_sessions', new_session.id, f"Caja abierta con monto inicial de S/ {opening_amount}", current_user.id)
    db.session.commit()
    
    flash('Caja abierta exitosamente.', 'success')
    return redirect(url_for('cashier.pos'))

@cashier_bp.route('/close_session', methods=['POST'])
@login_required
@role_required('admin')
def close_session():
    current_session = CashSession.query.filter_by(status='open').first()
    if not current_session:
        flash('No hay ninguna caja abierta para cerrar.', 'warning')
        return redirect(url_for('cashier.pos'))
        
    payments = Payment.query.filter_by(cash_session_id=current_session.id, status='completed').all()
    expenses = CashExpense.query.filter_by(cash_session_id=current_session.id).all()
    
    total_sales = sum(float(p.amount) for p in payments)
    cash_sales = sum(float(p.amount) for p in payments if p.payment_method == 'cash')
    total_expenses = sum(float(e.amount) for e in expenses)
    expected_amount = float(current_session.opening_amount) + cash_sales - total_expenses
    
    closing_amount = safe_float(request.form.get('closing_amount'), default=expected_amount)
    
    current_session.closing_time = datetime.now(timezone.utc)
    current_session.closing_amount = closing_amount
    current_session.expected_amount = expected_amount
    current_session.status = 'closed'
    
    AuditLog.log('CLOSE_SESSION', 'cash_sessions', current_session.id, f"Caja cerrada. Monto Esperado: S/ {expected_amount}, Ingresado: S/ {closing_amount}", current_user.id)
    db.session.commit()
    
    flash(f'Caja cerrada. Ventas puras: S/ {total_sales} | Egresos: S/ {total_expenses}. Tu Ticket Z se abrirá en instantes.', 'success')
    return redirect(url_for('cashier.pos', popup_shift=current_session.id))

@cashier_bp.route('/add_expense', methods=['POST'])
@login_required
@role_required('admin', 'cashier')
def add_expense():
    current_session = CashSession.query.filter_by(status='open').first()
    if not current_session:
        flash('No hay ninguna caja abierta para registrar egresos.', 'danger')
        return redirect(url_for('cashier.pos'))
        
    amount = safe_float(request.form.get('amount'), default=0.0)
    reason = request.form.get('reason')
    
    try:
        expense = CashExpense(
            cash_session_id=current_session.id,
            user_id=current_user.id,
            amount=float(amount),
            reason=reason
        )
        db.session.add(expense)
        
        AuditLog.log('CASH_EXPENSE', 'cash_expenses', current_session.id, f"Egreso de caja: S/ {amount} por {reason}", current_user.id)
        
        db.session.commit()
        flash(f'Se registró con éxito el egreso por S/ {amount}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Hubo un error al registrar el egreso.', 'danger')
        
    return redirect(url_for('cashier.pos'))

@cashier_bp.route('/checkout/<int:order_id>')
@login_required
@role_required('admin', 'cashier')
def checkout(order_id):
    current_session = CashSession.query.filter_by(status='open').first()
    if not current_session:
        flash('Es necesario que un Administrador abra la caja antes de cobrar.', 'danger')
        return redirect(url_for('cashier.pos'))

    order = Order.query.get_or_404(order_id)
    if order.status == 'paid':
        flash('Este pedido ya fue pagado.', 'warning')
        return redirect(url_for('cashier.pos'))
        
    return render_template('cashier/payments.html', order=order)

@cashier_bp.route('/pay/<int:order_id>', methods=['POST'])
@login_required
@role_required('admin', 'cashier')
def pay(order_id):
    current_session = CashSession.query.filter_by(status='open').first()
    if not current_session:
        flash('No hay caja abierta. Es necesario que un Administrador abra la caja antes de poder cobrar.', 'danger')
        return redirect(url_for('cashier.pos'))

    # Bloqueo pesimista: Evitar cobros dobles con concurrencia real
    order = db.session.get(Order, order_id, with_for_update=True)
    if not order:
        abort(404)
    
    if order.status == 'paid':
        flash('Seguridad: Esta orden ya fue cobrada previamente.', 'warning')
        return redirect(url_for('cashier.pos'))
    
    amount = safe_float(request.form.get('amount'), default=0.0)
    payment_method = request.form.get('payment_method')
    reference_code = request.form.get('reference_code', '')
    invoice_type = request.form.get('invoice_type')
    customer_name = request.form.get('customer_name', 'Cliente Varios')
    customer_document = request.form.get('customer_document', '00000000')
    
    # === VALIDACIONES DE SEGURIDAD ===
    allowed_methods = ('cash', 'card', 'yape', 'plin', 'transfer')
    if payment_method not in allowed_methods:
        flash('Método de pago no válido.', 'danger')
        return redirect(url_for('cashier.checkout', order_id=order_id))
    
    allowed_invoice_types = ('boleta', 'factura')
    if invoice_type not in allowed_invoice_types:
        flash('Tipo de comprobante no válido.', 'danger')
        return redirect(url_for('cashier.checkout', order_id=order_id))
    
    if amount < float(order.total_amount):
        flash(f'El monto (S/ {amount:.2f}) no puede ser menor al total de la orden (S/ {order.total_amount}).', 'danger')
        return redirect(url_for('cashier.checkout', order_id=order_id))
    
    try:
        payment = Payment(
            order_id=order.id, amount=amount, payment_method=payment_method,
            reference_code=reference_code, status='completed', created_by=current_user.id,
            cash_session_id=current_session.id
        )
        db.session.add(payment)
        db.session.flush() 
        
        # Secuencia atómica de facturación (evita duplicados por concurrencia)
        prefix = 'B001' if invoice_type == 'boleta' else 'F001'
        try:
            seq_name = 'boleta_seq' if invoice_type == 'boleta' else 'factura_seq'
            next_num = db.session.execute(db.text(f"SELECT nextval('{seq_name}')")).scalar()
        except Exception:
            # Fallback si las secuencias no existen aún
            last_invoice = Invoice.query.filter(Invoice.document_number.like(f"{prefix}-%")).order_by(Invoice.id.desc()).first()
            next_num = 1
            if last_invoice:
                try:
                    next_num = int(last_invoice.document_number.split('-')[1]) + 1
                except (ValueError, IndexError):
                    db.session.rollback()
                    flash('Error crítico: No se pudo generar el número de comprobante. Contacta al administrador del sistema.', 'danger')
                    logger.error('Fallo generando número de comprobante: secuencia inexistente y parse fallido para prefix %s', prefix)
                    return redirect(url_for('cashier.checkout', order_id=order_id))
        doc_number = f"{prefix}-{next_num:06d}"
        
        total = float(amount)
        # IGV 18% (Perú): El total ya incluye impuesto, se desglosa para el comprobante
        tax_rate = 0.18
        subtotal = round(total / (1 + tax_rate), 2)
        tax_amount = round(total - subtotal, 2)
        
        invoice = Invoice(
            payment_id=payment.id, invoice_type=invoice_type, document_number=doc_number,
            customer_name=customer_name, customer_document=customer_document,
            subtotal=subtotal, tax_amount=tax_amount, total_amount=total
        )
        db.session.add(invoice)
        
        order.status = 'paid'
        # Auto-marcar todos los items como entregados al cobrar
        # (si el cliente pagó, la comida ya fue servida)
        for item in order.items:
            if item.status != 'cancelled':
                item.status = 'delivered'
        table = Table.query.get(order.table_id)
        
        if table:
            unreads = Notification.query.filter(
                Notification.is_read == False,
                Notification.message.like(f"%Mesa {table.number}%")
            ).all()
            for n in unreads:
                n.is_read = True
            
            table.status = 'free'
            
        AppSignal.emit('payment_completed', 'orders')
        db.session.commit()
        # (Supabase Realtime)
        if table:
            msg = f'¡Cobro exitoso! Se generó la {invoice_type.capitalize()} {doc_number}. La Mesa {table.number} ahora está libre.'
        else:
            tipo = 'Delivery' if order.order_type == 'delivery' else 'Para Llevar'
            msg = f'¡Cobro exitoso! Se generó la {invoice_type.capitalize()} {doc_number} para la orden tipo {tipo}.'
        flash(msg, 'success')
        # UX: Redirigir al POS y abrir el ticket como ventana emergente automática
        return redirect(url_for('cashier.pos', popup_ticket=order.id))
        
        
    except Exception as e:
        db.session.rollback()
        flash('Ocurrió un error al procesar el pago.', 'danger')
        logger.exception("Error procesando pago para orden %s", order_id)
        
    return redirect(url_for('cashier.pos'))

@cashier_bp.route('/ticket/<int:order_id>')
@login_required
@role_required('admin', 'cashier')
def ticket(order_id):
    order = Order.query.get_or_404(order_id)
    payment = Payment.query.filter_by(order_id=order.id).first()
    invoice = Invoice.query.filter_by(payment_id=payment.id).first() if payment else None
    
    # Convertir fechas a hora Perú para el ticket impreso
    PERU_TZ = timezone(timedelta(hours=-5))
    order_time_peru = order.created_at
    if order_time_peru:
        if order_time_peru.tzinfo is None:
            order_time_peru = order_time_peru.replace(tzinfo=timezone.utc)
        order_time_peru = order_time_peru.astimezone(PERU_TZ)
    
    return render_template('cashier/ticket.html', order=order, payment=payment, invoice=invoice, order_time_peru=order_time_peru)