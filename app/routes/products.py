import os
import time
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from app.utils.decorators import role_required
from werkzeug.utils import secure_filename
from app.models.product import Product
from app.models.category import Category
from app import db
from app.utils.supabase_client import get_supabase
from app.utils.formatters import safe_int, safe_float

products_bp = Blueprint('products', __name__, url_prefix='/products')

# Extensiones permitidas para las imágenes
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@products_bp.route('/')
@login_required
@role_required('admin')
def index():
    # Obtenemos todos los productos junto con su categoría
    products = Product.query.outerjoin(Category).order_by(Category.name.asc().nullslast(), Product.name).all()
    categories = Category.query.all()
    return render_template('products/list.html', products=products, categories=categories)

@products_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = safe_float(request.form.get('price'), default=0.0)
        cost = safe_float(request.form.get('cost'), default=0.0)
        category_id = safe_int(request.form.get('category_id'), nullable=True)
        preparation_time = safe_int(request.form.get('preparation_time'), default=0)
        track_stock = 'track_stock' in request.form
        stock = safe_int(request.form.get('stock', 0), default=0)
        
        # Manejo de la imagen
        image_file = request.files.get('image')
        filename = None
        
        if image_file and image_file.filename != '' and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower()
            new_filename = f"prod_{int(time.time())}.{file_ext}"
            file_bytes = image_file.read()
            
            try:
                get_supabase().storage.from_('restaurant_assets').upload(
                    new_filename, 
                    file_bytes,
                    file_options={"content-type": image_file.mimetype}
                )
                public_url = get_supabase().storage.from_('restaurant_assets').get_public_url(new_filename)
                filename = public_url
            except Exception as e:
                flash(f'Error subiendo imagen a Supabase: {str(e)}', 'danger')
                filename = None
            
        new_product = Product(
            name=name,
            description=description,
            price=price,
            cost=cost,
            category_id=category_id,
            preparation_time=preparation_time,
            track_stock=track_stock,
            stock=stock,
            image_url=filename
        )
        
        try:
            db.session.add(new_product)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('Error al crear el producto. Intenta nuevamente.', 'danger')
            return redirect(url_for('products.index'))
        
        flash('Producto agregado correctamente.', 'success')
        return redirect(url_for('products.index'))
        
    categories = Category.query.all()
    return render_template('products/create.html', categories=categories)

@products_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit(id):
    product = Product.query.get_or_404(id)
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = safe_float(request.form.get('price'), default=0.0)
        product.cost = safe_float(request.form.get('cost'), default=0.0)
        product.category_id = safe_int(request.form.get('category_id'), nullable=True)
        product.preparation_time = safe_int(request.form.get('preparation_time'), default=0)
        product.is_available = 'is_available' in request.form
        product.track_stock = 'track_stock' in request.form
        product.stock = safe_int(request.form.get('stock', 0), default=0)
        
        # Manejo de nueva imagen si se sube una
        image_file = request.files.get('image')
        if image_file and image_file.filename != '' and allowed_file(image_file.filename):
            import time
            filename = secure_filename(image_file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower()
            new_filename = f"prod_{int(time.time())}.{file_ext}"
            file_bytes = image_file.read()
            
            try:
                get_supabase().storage.from_('restaurant_assets').upload(
                    new_filename, 
                    file_bytes,
                    file_options={"content-type": image_file.mimetype}
                )
                public_url = get_supabase().storage.from_('restaurant_assets').get_public_url(new_filename)
                product.image_url = public_url
            except Exception as e:
                flash(f'Error subiendo imagen a Supabase: {str(e)}', 'danger')
            
        db.session.commit()
        
        flash('Producto actualizado correctamente.', 'success')
        return redirect(url_for('products.index'))
        
    categories = Category.query.all()
    return render_template('products/edit.html', product=product, categories=categories)

@products_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def delete(id):
    product = Product.query.get_or_404(id)
    try:
        # Soft-delete: desactivar en lugar de eliminar para preservar historial de ventas
        product.is_available = False
        db.session.commit()
        
        flash(f'El producto "{product.name}" ha sido desactivado correctamente. Puedes reactivarlo desde la edición.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al desactivar el producto.', 'danger')
    return redirect(url_for('products.index'))