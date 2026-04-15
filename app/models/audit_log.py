from app import db
from datetime import datetime, timezone

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @staticmethod
    def log(action, entity_type=None, entity_id=None, details=None, user_id=None):
        from flask import request
        # En Vercel serverless, remote_addr es el proxy de AWS.
        # X-Forwarded-For contiene la IP real del cliente.
        ip_address = None
        if request:
            ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
            # X-Forwarded-For puede tener múltiples IPs: tomar la primera (cliente real)
            if ip_address and ',' in ip_address:
                ip_address = ip_address.split(',')[0].strip()
        new_log = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            user_id=user_id,
            ip_address=ip_address
        )
        db.session.add(new_log)
        db.session.flush()
