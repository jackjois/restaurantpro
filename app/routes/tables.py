import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.models.table import Table
from app.models.order import Order
from app import db
from app.utils.decorators import role_required
from app.utils.formatters import safe_int
import logging

logger = logging.getLogger(__name__)

tables_bp = Blueprint('tables', __name__, url_prefix='/tables')

@tables_bp.route('/')
@login_required
@role_required('admin')
def index():
    tables = Table.query.order_by(Table.number).all()
    return render_template('tables/list.html', tables=tables)

@tables_bp.route('/monitor')
@login_required
def monitor():
    tables = Table.query.order_by(Table.number).all()
    
    # Construir mapa de pedidos activos por mesa para link directo
    active_orders = Order.query.filter(
        Order.table_id.isnot(None),
        Order.status.notin_(['paid', 'cancelled'])
    ).all()
    active_orders_map = {o.table_id: o.id for o in active_orders}
    
    return render_template('tables/monitor.html', tables=tables, active_orders_map=active_orders_map)

@tables_bp.route('/create', methods=['POST'])
@login_required
@role_required('admin')
def create():
    number = safe_int(request.form.get('number'), default=1)
    capacity = safe_int(request.form.get('capacity'), default=4)
    location = request.form.get('location')
    
    existing_table = Table.query.filter_by(number=number).first()
    if existing_table:
        flash(f'La mesa número {number} ya existe.', 'danger')
        return redirect(url_for('tables.index'))
        
    # NUEVO: Generamos un código único para el QR de la carta digital
    token = uuid.uuid4().hex[:10]
    
    new_table = Table(number=number, capacity=capacity, location=location, qr_code=token)
    db.session.add(new_table)
    db.session.commit()
    
    # (Supabase Realtime)
    flash('Mesa creada correctamente.', 'success')
    return redirect(url_for('tables.index'))

@tables_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def edit(id):
    table = Table.query.get_or_404(id)
    new_number = safe_int(request.form.get('number'), default=table.number)
    existing = Table.query.filter(Table.number == new_number, Table.id != id).first()
    
    if existing:
        flash(f'El número de mesa {new_number} ya está en uso.', 'danger')
    else:
        table.number = new_number
        table.capacity = safe_int(request.form.get('capacity'), default=4)
        table.location = request.form.get('location')
        
        # Validar status permitido (prevenir inyección de estados arbitrarios)
        new_status = request.form.get('status')
        allowed_statuses = ('free', 'occupied', 'reserved', 'maintenance')
        if new_status not in allowed_statuses:
            flash('Estado de mesa no válido.', 'danger')
            return redirect(url_for('tables.index'))
        table.status = new_status
        
        # Si la mesa no tiene token (porque es antigua), le generamos uno
        if not table.qr_code:
            table.qr_code = uuid.uuid4().hex[:10]
            
        db.session.commit()
        # (Supabase Realtime)
        flash('Mesa actualizada correctamente.', 'success')
        
    return redirect(url_for('tables.index'))

@tables_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def delete(id):
    table = Table.query.get_or_404(id)
    try:
        db.session.delete(table)
        db.session.commit()
        # (Supabase Realtime)
        flash('Mesa eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception("Error al eliminar la mesa")
        flash('No se puede eliminar la mesa porque tiene pedidos asociados.', 'danger')
        
    return redirect(url_for('tables.index'))

# Ruta de atajo para abrir la Carta de una Mesa y probarla (pública)
@tables_bp.route('/qr/<int:id>')
def view_qr_link(id):
    table = Table.query.get_or_404(id)
    if not table.qr_code:
        table.qr_code = uuid.uuid4().hex[:10]
        db.session.commit()
    # Redirigimos al menú público
    return redirect(url_for('menu.view_menu', qr_code=table.qr_code))