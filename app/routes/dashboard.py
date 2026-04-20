from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.order import Order, OrderItem # <-- NUEVO: Importamos OrderItem
from app.models.table import Table
from app.models.payment import Payment
from app import db
from sqlalchemy import func
from datetime import date, datetime, timedelta, timezone
from app.utils.decorators import role_required # <-- Candado de seguridad

# Timezone de Perú (UTC-5)
PERU_TZ = timezone(timedelta(hours=-5))

# Definimos el Blueprint para el dashboard
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
@role_required('admin') # <-- Solo Administradores entran aquí
def index():
    # Usar timezone de Perú para contabilizar ventas nocturnas correctamente
    now_peru = datetime.now(PERU_TZ)
    today_peru = now_peru.date()
    
    # Calcular límites UTC del día actual en hora Perú
    today_start_peru = now_peru.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start_peru = today_start_peru + timedelta(days=1)
    today_start_utc = today_start_peru.astimezone(timezone.utc)
    tomorrow_start_utc = tomorrow_start_peru.astimezone(timezone.utc)

    # 1. Tarjetas Rápidas
    # NUEVO: Contamos exactamente los platos que faltan salir de cocina
    pending_orders = OrderItem.query.filter(OrderItem.status.in_(['pending', 'preparing'])).count()
    free_tables = Table.query.filter_by(status='free').count()
    
    # Total de pedidos efectivos generados en el día (excluye anulados)
    today_orders_count = Order.query.filter(
        Order.created_at >= today_start_utc,
        Order.created_at < tomorrow_start_utc,
        Order.status != 'cancelled'
    ).count()

    # Ingresos de Hoy
    today_sales = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'completed',
        Payment.created_at >= today_start_utc,
        Payment.created_at < tomorrow_start_utc
    ).scalar() or 0.0

    # 2. Gráfico: Ingresos de los últimos 7 días (con timezone Perú)
    chart_labels = []
    chart_data = []
    
    # Calcular rango UTC para los últimos 7 días (en hora Perú)
    seven_days_ago_peru = (now_peru - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago_utc = seven_days_ago_peru.astimezone(timezone.utc)
    
    # Traer todos los pagos completados del rango
    recent_payments = Payment.query.filter(
        Payment.status == 'completed',
        Payment.created_at >= seven_days_ago_utc
    ).all()
    
    # Agrupar por fecha en hora Perú (no UTC) para contabilidad correcta
    sales_dict = {}
    for p in recent_payments:
        p_time = p.created_at
        if p_time.tzinfo is None:
            p_time = p_time.replace(tzinfo=timezone.utc)
        peru_date = p_time.astimezone(PERU_TZ).date()
        sales_dict[peru_date] = sales_dict.get(peru_date, 0.0) + float(p.amount)

    # Rellenamos los 7 días
    for i in range(6, -1, -1):
        target_date = today_peru - timedelta(days=i)
        chart_labels.append(target_date.strftime('%d/%m'))
        chart_data.append(sales_dict.get(target_date, 0.0))

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