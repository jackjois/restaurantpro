from app import db
from datetime import datetime, timezone

class CashExpense(db.Model):
    __tablename__ = 'cash_expenses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    cash_session_id = db.Column(db.Integer, db.ForeignKey('cash_sessions.id'))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='cash_expenses', lazy=True)
