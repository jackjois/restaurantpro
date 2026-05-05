from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User
from app import bcrypt, login_manager, db, limiter
import logging
import re

auth_bp = Blueprint('auth', __name__)


@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    if user and not user.is_active:
        return None
    return user


@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'GET' and current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('dashboard.index'))
        elif current_user.role == 'cashier':
            return redirect(url_for('cashier.pos'))
        elif current_user.role == 'chef':
            return redirect(url_for('orders.kitchen'))
        else:
            return redirect(url_for('floor.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Ingresa usuario y contrasena.', 'danger')
            return render_template('login.html')

        try:
            user = User.query.filter_by(username=username).first()
            password_matches = user and bcrypt.check_password_hash(user.password_hash, password)
        except Exception as e:
            logging.getLogger(__name__).exception('Error al autenticar usuario')
            flash('No se pudo procesar la autenticacion. Verifica la conexion al servidor.', 'danger')
            return render_template('login.html')

        if password_matches:
            if not user.is_active:
                flash('Tu cuenta ha sido desactivada. Contacta al administrador.', 'danger')
                return render_template('login.html')

            if current_user.is_authenticated:
                logout_user()

            old_data = dict(session)
            session.clear()
            session.update(old_data)
            session.modified = True

            login_user(user, remember=True)

            next_page = request.args.get('next')
            if next_page:
                from urllib.parse import urlparse
                parsed_next = urlparse(next_page)
                if not parsed_next.netloc and not parsed_next.scheme and next_page.startswith('/'):
                    return redirect(next_page)

            if user.role == 'admin':
                return redirect(url_for('dashboard.index'))
            elif user.role == 'cashier':
                return redirect(url_for('cashier.pos'))
            elif user.role == 'chef':
                return redirect(url_for('orders.kitchen'))
            else:
                return redirect(url_for('floor.index'))
        else:
            flash('Usuario o contrasena incorrectos. Intente nuevamente.', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/switch', methods=['POST'])
@login_required
def switch_user():
    logout_user()
    flash('Sesion cerrada. Ingresa con otro usuario.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per minute")
def register():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('floor.index'))

    if User.query.count() > 0:
        flash('El registro publico esta deshabilitado. Contacta al administrador.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if email and not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('El formato del correo electronico no es valido.', 'danger')
            return redirect(url_for('auth.register'))

        if not password:
            flash('La contrasena es requerida.', 'danger')
            return redirect(url_for('auth.register'))

        if len(password) < 12:
            flash('La contrasena debe tener al menos 12 caracteres.', 'danger')
            return redirect(url_for('auth.register'))

        if not re.search(r'[A-Z]', password):
            flash('La contrasena debe contener al menos una mayuscula.', 'danger')
            return redirect(url_for('auth.register'))

        if not re.search(r'[a-z]', password):
            flash('La contrasena debe contener al menos una minuscula.', 'danger')
            return redirect(url_for('auth.register'))

        if not re.search(r'[0-9]', password):
            flash('La contrasena debe contener al menos un numero.', 'danger')
            return redirect(url_for('auth.register'))

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            flash('La contrasena debe contener al menos un caracter especial.', 'danger')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe.', 'danger')
            return redirect(url_for('auth.register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(
            full_name=full_name,
            username=username,
            email=email,
            password_hash=hashed_password,
            role='admin'
        )
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Restaurante registrado con exito. Inicia sesion.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('Error al registrar. Intenta nuevamente.', 'danger')

    return render_template('register.html')
