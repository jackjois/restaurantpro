from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def role_required(*roles):
    """
    Decorador para restringir el acceso a ciertas rutas basándose en el rol del usuario.
    Ejemplo de uso: @role_required('admin', 'cashier')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Verificamos autenticación antes de leer current_user.role (evita fallos con AnonymousUser)
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))

            # Verificamos si su rol está en la lista permitida
            if current_user.role not in roles:
                flash('Acceso denegado. No tienes los permisos necesarios para ver esta sección.', 'danger')
                # Si no tiene permiso, lo devolvemos a una ruta segura (ej. historial de pedidos o monitor)
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