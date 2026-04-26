from app import db
from datetime import datetime, timezone

_now_utc = lambda: datetime.now(timezone.utc)

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    reference_code = db.Column(db.String(100))
    status = db.Column(db.String(50), default='pending')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    cash_session_id = db.Column(db.Integer, db.ForeignKey('cash_sessions.id'), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_now_utc)
    
    order = db.relationship('Order', backref=db.backref('payment_info', uselist=False))
    invoice = db.relationship('Invoice', backref=db.backref('payment_rel', lazy=True, uselist=False))
    order_items = db.relationship('OrderItem', backref='payment_rel_item', lazy=True)

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'))
    invoice_type = db.Column(db.String(50), nullable=False)
    document_number = db.Column(db.String(50), unique=True, nullable=True)
    customer_name = db.Column(db.String(150))
    customer_document = db.Column(db.String(50))
    customer_address = db.Column(db.Text)
    subtotal = db.Column(db.Numeric(10, 2))
    tax_amount = db.Column(db.Numeric(10, 2))
    total_amount = db.Column(db.Numeric(10, 2))
    pdf_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), default=_now_utc)
