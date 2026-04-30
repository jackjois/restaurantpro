from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.order import Order, OrderItem # <-- NUEVO: Importamos OrderItem
from app.models.table import Table
from app.models.payment import Payment
from app import db
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from app.utils.decorators import role_required # <-- Candado de seguridad
from app.constants import PERU_TZ

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
    pending_orders = db.session.query(OrderItem).join(Order).filter(
        OrderItem.status.in_(['pending', 'preparing']), 
        Order.status.notin_(['cancelled', 'paid'])
    ).count()
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

    # KPI REALES: Calcular métricas de AYER para comparación real
    yesterday_start_peru = today_start_peru - timedelta(days=1)
    yesterday_start_utc = yesterday_start_peru.astimezone(timezone.utc)
    
    yesterday_sales = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == 'completed',
        Payment.created_at >= yesterday_start_utc,
        Payment.created_at < today_start_utc
    ).scalar() or 0.0
    
    yesterday_orders_count = Order.query.filter(
        Order.created_at >= yesterday_start_utc,
        Order.created_at < today_start_utc,
        Order.status != 'cancelled'
    ).count()
    
    # Calcular porcentajes reales de cambio
    if float(yesterday_sales) > 0:
        sales_change_pct = ((float(today_sales) - float(yesterday_sales)) / float(yesterday_sales)) * 100
    else:
        sales_change_pct = 100.0 if float(today_sales) > 0 else 0.0
    
    if yesterday_orders_count > 0:
        orders_change_pct = ((today_orders_count - yesterday_orders_count) / yesterday_orders_count) * 100
    else:
        orders_change_pct = 100.0 if today_orders_count > 0 else 0.0
    
    total_tables = Table.query.count()

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
                           total_tables=total_tables,
                           today_orders_count=today_orders_count,
                           today_sales=today_sales,
                           sales_change_pct=sales_change_pct,
                           orders_change_pct=orders_change_pct,
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           recent_orders=recent_orders)