from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User
from app import bcrypt, login_manager, db

# Definimos el Blueprint para la autenticación
auth_bp = Blueprint('auth', __name__)

# Le indicamos a Flask-Login cómo buscar al usuario en la base de datos
@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    if user and not user.is_active:
        return None  # Usuarios desactivados no pueden navegar
    return user

@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Si el usuario ya está autenticado y accede al login por GET, redirigir a su panel
    if request.method == 'GET' and current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('dashboard.index'))
        elif current_user.role == 'cashier':
            return redirect(url_for('cashier.pos'))
        elif current_user.role == 'chef':
            return redirect(url_for('orders.kitchen'))
        else:
            return redirect(url_for('tables.monitor'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, password):
            # Verificar que el usuario esté activo
            if not user.is_active:
                flash('Tu cuenta ha sido desactivada. Contacta al administrador.', 'danger')
                return render_template('login.html')
            
            # Si hay otro usuario logueado, cerrar su sesión primero
            if current_user.is_authenticated:
                logout_user()
            
            # remember=True es CRÍTICO para Vercel serverless:
            # Sin él, la cookie de sesión se pierde entre cold starts
            login_user(user, remember=True)
            
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
                
            # REDIRECCIÓN INTELIGENTE AL INICIAR SESIÓN
            if user.role == 'admin':
                return redirect(url_for('dashboard.index'))
            elif user.role == 'cashier':
                return redirect(url_for('cashier.pos'))
            elif user.role == 'chef':
                return redirect(url_for('orders.kitchen'))
            else:
                return redirect(url_for('tables.monitor'))
        else:
            flash('Usuario o contraseña incorrectos. Intente nuevamente.', 'danger')
            
    return render_template('login.html')

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/switch', methods=['POST'])
@login_required
def switch_user():
    """Cierra la sesión actual y redirige al login para cambiar de usuario."""
    logout_user()
    flash('Sesión cerrada. Ingresa con otro usuario.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    # SEGURIDAD: Solo permitir registro si no hay usuarios (setup inicial)
    if User.query.count() > 0:
        flash('El registro público está deshabilitado. Contacta al administrador.', 'danger')
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not password or len(password.strip()) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.', 'danger')
            return redirect(url_for('auth.register'))
        
        # Revisar duplicados
        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe.', 'danger')
            return redirect(url_for('auth.register'))
            
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(
            full_name=full_name,
            username=username,
            email=email,
            password_hash=hashed_password,
            role='admin'  # El primer usuario siempre es admin (setup inicial)
        )
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Restaurante registrado con éxito. Inicia sesión.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('Error al registrar. Intenta nuevamente.', 'danger')
            
    return render_template('register.html')