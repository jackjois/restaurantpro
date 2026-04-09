from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.utils.decorators import role_required
from app.models.category import Category
from app import db
from sqlalchemy.exc import IntegrityError

categories_bp = Blueprint('categories', __name__, url_prefix='/categories')

@categories_bp.route('/')
@login_required
@role_required('admin')
def index():
    categories = Category.query.order_by(Category.name).all()
    return render_template('categories/list.html', categories=categories)

@categories_bp.route('/create', methods=['POST'])
@login_required
@role_required('admin')
def create():
    name = request.form.get('name')
    description = request.form.get('description', '')
    color = request.form.get('color', '#007bff')
    
    existing = Category.query.filter_by(name=name).first()
    if existing:
        flash(f'La categoría {name} ya existe.', 'warning')
        return redirect(url_for('categories.index'))
        
    new_cat = Category(
        name=name,
        description=description,
        color=color,
        is_active=True
    )
    db.session.add(new_cat)
    db.session.commit()
    
    flash('Categoría creada exitosamente.', 'success')
    return redirect(url_for('categories.index'))

@categories_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def edit(id):
    category = Category.query.get_or_404(id)
    new_name = request.form.get('name')
    
    existing = Category.query.filter(Category.name == new_name, Category.id != id).first()
    if existing:
        flash(f'El nombre de categoría {new_name} ya está en uso.', 'danger')
    else:
        category.name = new_name
        category.description = request.form.get('description', '')
        category.color = request.form.get('color', category.color)
        db.session.commit()
        flash('Categoría actualizada correctamente.', 'success')
        
    return redirect(url_for('categories.index'))

@categories_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def delete(id):
    category = Category.query.get_or_404(id)
    try:
        db.session.delete(category)
        db.session.commit()
        flash('Categoría eliminada satisfactoriamente.', 'success')
    except IntegrityError as e:
        db.session.rollback()
        flash('¡Operación denegada! No puedes eliminar esta categoría porque ya tiene Productos asignados. Por favor remueve los productos asociados primero para evitar inconsistencias en la base de datos.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'No se pudo eliminar la categoría. Error: {str(e)}', 'danger')
        
    return redirect(url_for('categories.index'))
