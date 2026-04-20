from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.user import User
from app import db, bcrypt
from app.utils.decorators import role_required

users_bp = Blueprint('users', __name__, url_prefix='/users')

@users_bp.route('/')
@login_required
@role_required('admin') # ¡Solo los administradores entran aquí!
def index():
    users = User.query.all()
    return render_template('users/list.html', users=users)

@users_bp.route('/create', methods=['POST'])
@login_required
@role_required('admin')
def create():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    full_name = request.form.get('full_name')
    role = request.form.get('role')
    
    if not password or len(password.strip()) < 8:
        flash('La contraseña debe tener al menos 8 caracteres.', 'danger')
        return redirect(url_for('users.index'))
    
    # Verificamos que el usuario no exista
    if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
        flash('Error: El nombre de usuario o el correo electrónico ya están en uso.', 'danger')
        return redirect(url_for('users.index'))
        
    # Encriptamos la contraseña de forma segura
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    new_user = User(
        username=username,
        email=email,
        password_hash=hashed_password,
        full_name=full_name,
        role=role
    )
    
    db.session.add(new_user)
    db.session.commit()
    flash(f'El usuario {username} ha sido creado exitosamente.', 'success')
    return redirect(url_for('users.index'))

@users_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def edit(id):
    user = User.query.get_or_404(id)
    
    new_username = request.form.get('username')
    new_email = request.form.get('email')
    
    # Validar duplicados de username y email con otros usuarios
    if new_username != user.username:
        existing = User.query.filter(User.username == new_username, User.id != id).first()
        if existing:
            flash(f'El nombre de usuario "{new_username}" ya está en uso por otro usuario.', 'danger')
            return redirect(url_for('users.index'))
    
    if new_email and new_email != user.email:
        existing = User.query.filter(User.email == new_email, User.id != id).first()
        if existing:
            flash(f'El correo "{new_email}" ya está en uso por otro usuario.', 'danger')
            return redirect(url_for('users.index'))
    
    user.username = new_username
    user.email = new_email
    user.full_name = request.form.get('full_name')
    user.role = request.form.get('role')
    user.is_active = 'is_active' in request.form
    
    # Si el administrador escribió una nueva contraseña, la actualizamos
    new_password = request.form.get('password')
    if new_password and new_password.strip() != '':
        user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        
    db.session.commit()
    flash(f'Los datos del usuario {user.username} fueron actualizados.', 'success')
    return redirect(url_for('users.index'))

@users_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def delete(id):
    if current_user.id == id:
        flash('No puedes eliminar tu propia cuenta de administrador.', 'danger')
        return redirect(url_for('users.index'))
        
    user = User.query.get_or_404(id)
    user.is_active = False
    db.session.commit()
    flash(f'El usuario "{user.username}" ha sido desactivado. Puede reactivarse desde la edición.', 'success')
        
    return redirect(url_for('users.index'))