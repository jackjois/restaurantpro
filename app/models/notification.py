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
        if not self.created_at:
            return ''
        from app.constants import PERU_TZ
        dt = self.created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(PERU_TZ).strftime('%H:%M')
        
    @classmethod
    def get_unread_count(cls, user_id):
        """Cuenta notificaciones no leídas del usuario."""
        return cls.query.filter(
            cls.user_id == user_id,
            cls.is_read == False
        ).count()
        
    @classmethod
    def get_by_user(cls, user_id, limit=20, unread_only=False):
        """Obtiene notificaciones del usuario."""
        query = cls.query.filter(cls.user_id == user_id)
        if unread_only:
            query = query.filter_by(is_read=False)
        return query.order_by(cls.created_at.desc()).limit(limit).all()
        
    @classmethod
    def create(cls, message, type='system', user_id=None):
        """Crea una notificación. Si user_id=None (global), se duplica para cada usuario activo.
        El caller debe hacer db.session.commit() cuando la transacción esté completa."""
        if user_id is not None:
            # Notificación individual
            n = cls(message=message, type=type, user_id=user_id)
            db.session.add(n)
            db.session.flush()
            return n
        else:
            # Notificación global: crear una copia por cada usuario activo
            from app.models.user import User
            active_users = User.query.filter_by(is_active=True).all()
            created = []
            for user in active_users:
                n = cls(message=message, type=type, user_id=user.id)
                db.session.add(n)
                created.append(n)
            db.session.flush()
            return created[0] if created else None
        
    def mark_as_read(self):
        self.is_read = True
        db.session.flush()

