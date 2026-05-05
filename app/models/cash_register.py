from app import db
from datetime import datetime, timezone

_now_utc = lambda: datetime.now(timezone.utc)

class CashSession(db.Model):
    __tablename__ = 'cash_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    opening_time = db.Column(db.DateTime(timezone=True), nullable=False, default=_now_utc)
    closing_time = db.Column(db.DateTime(timezone=True), nullable=True)
    opening_amount = db.Column(db.Numeric(10, 2), nullable=False)
    closing_amount = db.Column(db.Numeric(10, 2), nullable=True)
    expected_amount = db.Column(db.Numeric(10, 2), nullable=True)
    status = db.Column(db.String(50), default='open')
    created_at = db.Column(db.DateTime(timezone=True), default=_now_utc)

    user = db.relationship('User', backref='cash_sessions', lazy=True)
