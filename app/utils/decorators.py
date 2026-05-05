from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user, logout_user

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))

            if not getattr(current_user, 'is_active', True):
                logout_user()
                flash('Tu cuenta ha sido desactivada. Contacta al administrador.', 'danger')
                return redirect(url_for('auth.login'))

            if current_user.role not in roles:
                flash('Acceso denegado. No tienes los permisos necesarios para ver esta sección.', 'danger')
                if current_user.role == 'waiter':
                    return redirect(url_for('tables.monitor'))
                elif current_user.role == 'cashier':
                    return redirect(url_for('cashier.pos'))
                elif current_user.role == 'chef':
                    return redirect(url_for('orders.kitchen'))
                else:
                    return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator