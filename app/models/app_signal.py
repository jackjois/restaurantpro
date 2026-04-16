from app import db
from datetime import datetime, timezone

_now_utc = lambda: datetime.now(timezone.utc)

class AppSignal(db.Model):
    __tablename__ = 'app_signals'
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False)
    entity = db.Column(db.String(50))
    created_at = db.Column(db.DateTime(timezone=True), default=_now_utc)

    @classmethod
    def emit(cls, action, entity=None):
        try:
            signal = cls(action=action, entity=entity)
            db.session.add(signal)
            db.session.flush() # Para forzar que se genere el id pero sin commitear aún (el commit lo hace el route)
        except Exception:
            pass # Si falla por alguna razón no bloquear la transacción principal
