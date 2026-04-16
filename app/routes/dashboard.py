from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.order import Order, OrderItem # <-- NUEVO: Importamos OrderItem
from app.models.table import Table
from app.models.payment import Payment
from app import db
from sqlalchemy import func
from datetime import date, timedelta
from app.utils.decorators import role_required # <-- Candado de seguridad

# Definimos el Blueprint para el dashboard
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
@role_required('admin') # <-- Solo Administradores entran aquí
def index():
    today = date.today()

    # 1. Tarjetas Rápidas
    # NUEVO: Contamos exactamente los platos que faltan salir de cocina
    pending_orders = OrderItem.query.filter(OrderItem.status.in_(['pending', 'preparing'])).count()
    free_tables = Table.query.filter_by(status='free').count()
    
    # Total de pedidos efectivos generados en el día (excluye anulados)
    today_orders_count = Order.query.filter(
        func.date(Order.created_at) == today,
        Order.status != 'cancelled'
    ).count()

    # Ingresos de Hoy
    today_sales = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'completed',
        func.date(Payment.created_at) == today
    ).scalar() or 0.0

    # 2. Gráfico: Ingresos de los últimos 7 días
    chart_labels = []
    chart_data = []
    
    seven_days_ago = today - timedelta(days=6)
    
    # Única consulta para traer todas las ventas completadas de los últimos 7 días agrupadas por fecha
    daily_sales_query = db.session.query(
        func.date(Payment.created_at).label('fecha'),
        func.sum(Payment.amount).label('total')
    ).filter(
        Payment.status == 'completed',
        func.date(Payment.created_at) >= seven_days_ago
    ).group_by(func.date(Payment.created_at)).all()
    
    # Convertimos a diccionario para aceso rápido: { date(year, month, day): total }
    sales_dict = { row.fecha: float(row.total or 0.0) for row in daily_sales_query }

    # Rellenamos los 7 días
    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        
        # Formato de fecha para la etiqueta (Ej: 26/03)
        label = target_date.strftime('%d/%m')
        chart_labels.append(label)
        
        # Recuperamos la suma del diccionario, o 0.0 si no hubo ventas ese día
        daily_total = sales_dict.get(target_date, 0.0)
        chart_data.append(daily_total)

    # 3. NUEVO: Últimos 5 pedidos para el panel lateral rápido
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()

    return render_template('dashboard.html', 
                           pending_orders=pending_orders,
                           free_tables=free_tables,
                           today_orders_count=today_orders_count,
                           today_sales=today_sales,
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           recent_orders=recent_orders)