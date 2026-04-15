from app import db
from datetime import datetime, timezone
from sqlalchemy import or_

_now_utc = lambda: datetime.now(timezone.utc)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    type = db.Column(db.String(50), default='system')
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_now_utc)
    
    @property
    def time(self):
        return self.created_at.strftime('%H:%M') if self.created_at else ''
        
    @classmethod
    def get_unread_count(cls, user_id):
        """Cuenta notificaciones no leídas: las del usuario + las globales (user_id=None)."""
        return cls.query.filter(
            or_(cls.user_id == user_id, cls.user_id.is_(None)),
            cls.is_read == False
        ).count()
        
    @classmethod
    def get_by_user(cls, user_id, limit=20, unread_only=False):
        """Obtiene notificaciones del usuario + las globales (user_id=None)."""
        query = cls.query.filter(or_(cls.user_id == user_id, cls.user_id.is_(None)))
        if unread_only:
            query = query.filter_by(is_read=False)
        return query.order_by(cls.created_at.desc()).limit(limit).all()
        
    @classmethod
    def create(cls, message, type='system', user_id=None):
        """Crea una notificación y la agrega a la sesión (sin commit).
        El caller debe hacer db.session.commit() cuando la transacción esté completa."""
        n = cls(message=message, type=type, user_id=user_id)
        db.session.add(n)
        db.session.flush()  # Genera el ID sin cerrar la transacción
        return n
        
    def mark_as_read(self):
        self.is_read = True
        db.session.flush()
