from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.models.setting import Setting # <-- Importamos las configuraciones
from app.constants import PERU_TZ
import io
from datetime import timezone, timedelta

def generate_sales_pdf(payments):
    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=letter)
    
    # Consultamos el nombre del restaurante dinámicamente
    setting = Setting.query.first()
    rest_name = setting.name if setting else "RestaurantPro"
    
    # Título
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, f"Reporte de Ventas Detallado - {rest_name}")
    
    y = 710
    total = 0
    
    for p in payments:
        if p.status == 'completed':
            if y < 120:
                c.showPage()
                y = 750

            o = p.order
            
            p_time = p.created_at
            if p_time.tzinfo is None:
                p_time = p_time.replace(tzinfo=timezone.utc)
            fecha = p_time.astimezone(PERU_TZ).strftime('%d/%m/%Y %H:%M')
            
            metodo = p.payment_method.upper()
            monto_total = float(p.amount)
            monto_envio = float(o.delivery_fee) if o.order_type == 'delivery' else 0.00
            
            # Encabezado de la Ficha de Venta
            if o.order_type == 'delivery':
                modalidad = f"DELIVERY - {o.customer_name}"
            elif o.order_type == 'takeaway':
                modalidad = f"PARA LLEVAR - {o.customer_name}"
            else:
                modalidad = f"Mesa {o.table_rel.number if o.table_rel else 'N/A'}"

            c.setFont("Helvetica-Bold", 11)
            c.setFillColorRGB(0.1, 0.15, 0.3) # Azul oscuro
            c.drawString(50, y, f"Venta #{p.id} | {modalidad}")
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica", 10)
            c.drawString(450, y, f"Total: S/ {monto_total:.2f}")
            
            y -= 15
            c.setFont("Helvetica-Oblique", 9)
            info_line = f"Fecha: {fecha} | Pago: {metodo}"
            if o.order_type == 'delivery':
                info_line += f" | Envío: S/ {monto_envio:.2f}"
            c.drawString(50, y, info_line)
            
            if o.order_type == 'delivery' and o.delivery_address:
                y -= 12
                c.setFont("Helvetica-Bold", 9)
                c.drawString(50, y, f"Dirección: {o.delivery_address}")

            y -= 15
            
            c.setFont("Helvetica", 9)
            c.setFillColorRGB(0.2, 0.2, 0.2) 
            
            platos_validos = [item for item in o.items if item.status != 'cancelled']
            if platos_validos:
                for item in platos_validos:
                    if y < 50:
                        c.showPage()
                        y = 750
                        c.setFont("Helvetica", 9)
                    
                    nombre_plato = item.product.name if item.product else '[Producto eliminado]'
                    c.drawString(70, y, f"• {item.quantity}x {nombre_plato} (S/ {item.subtotal})")
                    y -= 12
            else:
                c.drawString(70, y, "- Sin platos registrados.")
                y -= 12
            
            c.setFillColorRGB(0, 0, 0)
            y -= 5
            c.setDash(1, 2)
            c.line(50, y, 550, y)
            c.setDash()
            y -= 20
            
            total += monto_total
            
    if y < 80:
        c.showPage()
        y = 750
        
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y, "TOTAL INGRESOS DEL PERIODO:")
    c.drawString(540, y, f"S/ {total:.2f}")
    
    c.save()
    output.seek(0)
    return output