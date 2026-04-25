from flask import Blueprint, render_template, send_file, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.utils.decorators import role_required
from app.models.payment import Payment
from app.models.order import OrderItem, Order
from app.models.product import Product
from app.models.category import Category # <-- IMPORTANTE: Añadimos Category
from app import db
from sqlalchemy import func, desc, cast, Date
from app.utils.excel_generator import generate_sales_excel
from app.utils.pdf_generator import generate_sales_pdf
from app.constants import PERU_TZ
import collections
from datetime import datetime, timezone, timedelta

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/sales')
@login_required
@role_required('admin')
def sales():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = Payment.query.filter_by(status='completed')
    
    if start_date:
        try:
            sd_peru = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=PERU_TZ)
            sd_utc = sd_peru.astimezone(timezone.utc)
            query = query.filter(Payment.created_at >= sd_utc)
        except ValueError:
            pass
            
    if end_date:
        try:
            ed_peru = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=PERU_TZ)
            ed_utc = ed_peru.astimezone(timezone.utc)
            query = query.filter(Payment.created_at <= ed_utc)
        except ValueError:
            pass
        
    payments = query.order_by(Payment.created_at.asc()).all()
    
    # === CÁLCULAR EGRESOS ===
    from app.models.cash_expense import CashExpense
    expense_query = CashExpense.query
    if start_date:
        try:
            sd_peru = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=PERU_TZ)
            sd_utc = sd_peru.astimezone(timezone.utc)
            expense_query = expense_query.filter(CashExpense.created_at >= sd_utc)
        except ValueError:
            pass
    if end_date:
        try:
            ed_peru = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=PERU_TZ)
            ed_utc = ed_peru.astimezone(timezone.utc)
            expense_query = expense_query.filter(CashExpense.created_at <= ed_utc)
        except ValueError:
            pass
    expenses = expense_query.order_by(CashExpense.created_at.desc()).all()
    total_expenses = sum(float(e.amount) for e in expenses)
    
    # === CÁLCULOS GERENCIALES (KPIs) ===
    total_sales = 0
    total_costs = 0
    total_orders = len(payments)
    
    # === AGRUPACIONES PARA GRÁFICOS ===
    # 1. Ventas por Día (Gráfico de Líneas)
    sales_by_date = collections.defaultdict(float)
    # 2. Ventas por Método de Pago (Gráfico de Dona)
    sales_by_method = collections.defaultdict(float)
    
    for p in payments:
        p_time = p.created_at
        if p_time.tzinfo is None:
            p_time = p_time.replace(tzinfo=timezone.utc)
        peru_date = p_time.astimezone(PERU_TZ)
        date_str = peru_date.strftime('%Y-%m-%d')
        
        amount = float(p.amount)
        method = p.payment_method.upper()
        
        sales_by_date[date_str] += amount
        sales_by_method[method] += amount
        total_sales += amount
        
        # Calcular costos fijos del pedido correspondiente
        if p.order and p.order.items:
            for item in p.order.items:
                if item.status != 'cancelled' and item.product:
                    total_costs += float(item.product.cost or 0) * int(item.quantity)

    avg_ticket = total_sales / total_orders if total_orders > 0 else 0
    gross_profit = total_sales - total_costs
    margin_percentage = (gross_profit / total_sales * 100) if total_sales > 0 else 0

    # Preparamos los datos para Chart.js
    chart_dates = list(sales_by_date.keys())
    chart_sales_values = list(sales_by_date.values())
    
    chart_methods = list(sales_by_method.keys())
    chart_method_values = list(sales_by_method.values())
    
    # Invertimos la lista solo para la tabla (para ver los más recientes primero)
    payments.reverse()

    return render_template('reports/sales.html', 
                           payments=payments, 
                           expenses=expenses,
                           total_expenses=total_expenses,
                           total_sales=total_sales,
                           total_costs=total_costs,
                           gross_profit=gross_profit,
                           margin_percentage=margin_percentage,
                           total_orders=total_orders,
                           avg_ticket=avg_ticket,
                           chart_dates=chart_dates,
                           chart_sales_values=chart_sales_values,
                           chart_methods=chart_methods,
                           chart_method_values=chart_method_values,
                           start_date=start_date,
                           end_date=end_date)

@reports_bp.route('/sales/export/<format>')
@login_required
@role_required('admin')
def export_sales(format):
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = Payment.query.filter_by(status='completed')
    
    if start_date:
        try:
            sd_peru = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=PERU_TZ)
            sd_utc = sd_peru.astimezone(timezone.utc)
            query = query.filter(Payment.created_at >= sd_utc)
        except ValueError:
            pass
    if end_date:
        try:
            ed_peru = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=PERU_TZ)
            ed_utc = ed_peru.astimezone(timezone.utc)
            query = query.filter(Payment.created_at <= ed_utc)
        except ValueError:
            pass
        
    payments = query.order_by(Payment.created_at.desc()).all()
    
    if format == 'excel':
        file_data = generate_sales_excel(payments)
        return send_file(file_data, download_name='reporte_ventas.xlsx', as_attachment=True)
    elif format == 'pdf':
        file_data = generate_sales_pdf(payments)
        return send_file(file_data, download_name='reporte_ventas.pdf', as_attachment=True, mimetype='application/pdf')
    
    return "Formato no soportado", 400

@reports_bp.route('/products')
@login_required
@role_required('admin')
def products():
    # 1. Los 10 platos más vendidos (sólo pedidos pagados)
    top_products = db.session.query(
        Product.name, 
        func.sum(OrderItem.quantity).label('total_sold'),
        func.sum(OrderItem.subtotal).label('total_revenue')
    ).select_from(Product).join(OrderItem).join(Order).filter(Order.status == 'paid') \
     .group_by(Product.id).order_by(desc('total_sold')).limit(10).all()
     
    # 2. Rendimiento por Categorías (Gráfico de Dona - sólo pedidos pagados)
    category_stats = db.session.query(
        Category.name,
        func.sum(OrderItem.subtotal).label('total_revenue')
    ).select_from(OrderItem).join(Order).join(Product).join(Category) \
     .filter(Order.status == 'paid') \
     .group_by(Category.id).all()
     
    # Preparar datos para gráficos
    chart_product_names = [p.name for p in top_products]
    chart_product_qty = [float(p.total_sold) for p in top_products]
    
    chart_cat_names = [c.name for c in category_stats]
    chart_cat_revenue = [float(c.total_revenue) for c in category_stats]

    return render_template('reports/products.html', 
                           products=top_products,
                           chart_product_names=chart_product_names,
                           chart_product_qty=chart_product_qty,
                           chart_cat_names=chart_cat_names,
                           chart_cat_revenue=chart_cat_revenue)

@reports_bp.route('/shifts')
@login_required
@role_required('admin')
def shifts():
    from app.models.cash_register import CashSession
    page = request.args.get('page', 1, type=int)
    shifts = CashSession.query.order_by(CashSession.opening_time.desc()).paginate(page=page, per_page=15)
    return render_template('reports/shifts.html', shifts=shifts)

@reports_bp.route('/shift_ticket/<int:session_id>')
@login_required
def shift_ticket(session_id):
    from app.models.cash_register import CashSession
    from app.models.cash_expense import CashExpense
    
    session = CashSession.query.get_or_404(session_id)
    
    # Validar acceso
    if current_user.role != 'admin' and session.user_id != current_user.id:
        flash('No tienes permiso para ver este ticket.', 'danger')
        return redirect(url_for('dashboard.index'))
        
    # Calcular número de turno secuencial real (ignorando IDs saltados)
    num_turno = CashSession.query.filter(CashSession.id <= session.id).count()
    
    payments = Payment.query.filter_by(cash_session_id=session.id, status='completed').all()
    expenses = CashExpense.query.filter_by(cash_session_id=session.id).all()
    
    total_sales = sum(float(p.amount) for p in payments)
    total_expenses = sum(float(e.amount) for e in expenses)
    cash_sales = sum(float(p.amount) for p in payments if p.payment_method == 'cash')
    digital_sales = sum(float(p.amount) for p in payments if p.payment_method != 'cash')
    
    return render_template('reports/shift_ticket.html', 
                           session=session, 
                           payments=payments, 
                           expenses=expenses,
                           total_sales=total_sales,
                           total_expenses=total_expenses,
                           cash_sales=cash_sales,
                           digital_sales=digital_sales,
                           num_turno=num_turno)