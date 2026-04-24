from app import db
from datetime import datetime, timezone

_now_utc = lambda: datetime.now(timezone.utc)

class Reservation(db.Model):
    __tablename__ = 'reservations'
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('tables.id', ondelete='CASCADE'), nullable=False)
    customer_name = db.Column(db.String(150), nullable=False)
    customer_phone = db.Column(db.String(50))
    reservation_time = db.Column(db.DateTime(timezone=True), nullable=False)
    guest_count = db.Column(db.Integer, default=1)
    status = db.Column(db.String(50), default='pending') # pending, confirmed, cancelled, completed
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=_now_utc)

    # Relationships
    table = db.relationship('Table', backref=db.backref('reservations', lazy=True, cascade="all, delete"))
