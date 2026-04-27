from app import db
from datetime import datetime, timezone

_now_utc = lambda: datetime.now(timezone.utc)

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('tables.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    waiter = db.relationship('User', backref='orders', lazy=True)
    order_type = db.Column(db.String(50), default='dine_in')
    customer_name = db.Column(db.String(100))
    customer_phone = db.Column(db.String(50))
    delivery_address = db.Column(db.Text)
    delivery_fee = db.Column(db.Numeric(10, 2), default=0.0)
    order_number = db.Column(db.String(50), nullable=True, unique=True)
    status = db.Column(db.String(50), default='pending')
    total_amount = db.Column(db.Numeric(10, 2), default=0.0)
    notes = db.Column(db.Text)
    discount_percent = db.Column(db.Numeric(5, 2), default=0)
    tip = db.Column(db.Numeric(10, 2), default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=_now_utc)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)
    
    items = db.relationship('OrderItem', backref='order_rel', cascade='all, delete-orphan', lazy=True)

    @staticmethod
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

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'))
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2))
    subtotal = db.Column(db.Numeric(10, 2))
    status = db.Column(db.String(50), default='pending')
    is_printed = db.Column(db.Boolean, default=False)
    is_paid = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=_now_utc)

    @property
    def kitchen_verb(self):
        if self.product and self.product.category:
            cat_name = self.product.category.name.lower()
            if any(x in cat_name for x in ('bebida', 'refresco', 'jugo', 'cerveza', 'vino', 'liquido')):
                return 'Servir'
            if any(x in cat_name for x in ('postre', 'dulce', 'helado', 'snack')):
                return 'Emplatar'
        return 'Cocinar'
