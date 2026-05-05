import time
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.utils.decorators import role_required
from werkzeug.utils import secure_filename
from app.models.product import Product
from app.models.category import Category
from app import db
from app.utils.supabase_client import get_supabase
from app.utils.formatters import safe_int, safe_float
import logging

logger = logging.getLogger(__name__)

products_bp = Blueprint('products', __name__, url_prefix='/products')

# Extensiones permitidas para las imágenes
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

MAGIC_BYTES = {
    b'\xff\xd8\xff': 'image/jpeg',
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
    b'RIFF': None,
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_image_bytes(file_bytes, declared_ext):
    ext = declared_ext.lower()
    if ext in ('jpg', 'jpeg'):
        return file_bytes[:3] == b'\xff\xd8\xff'
    if ext == 'png':
        return file_bytes[:8] == b'\x89PNG\r\n\x1a\n'
    if ext == 'gif':
        return file_bytes[:6] in (b'GIF87a', b'GIF89a')
    if ext == 'webp':
        return file_bytes[:4] == b'RIFF' and file_bytes[8:12] == b'WEBP'
    return False

def safe_content_type(ext):
    mapping = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
    return mapping.get(ext.lower(), 'application/octet-stream')

@products_bp.route('/')
@login_required
@role_required('admin')
def index():
    # Obtenemos todos los productos junto con su categoría
    products = Product.query.outerjoin(Category).order_by(Category.name.asc().nullslast(), Product.name).all()
    categories = Category.query.all()
    return render_template('products/list.html', products=products, categories=categories)

@products_bp.route('/create', methods=['POST'])
@login_required
@role_required('admin')
def create():
    name = request.form.get('name')
    if not name or not name.strip():
        flash('El nombre del producto es obligatorio.', 'danger')
        return redirect(url_for('products.index'))
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

        if not validate_image_bytes(file_bytes, file_ext):
            flash('El archivo no es una imagen válida.', 'danger')
            return redirect(url_for('products.index'))

        try:
            get_supabase().storage.from_('restaurant_assets').upload(
                new_filename,
                file_bytes,
                file_options={"content-type": safe_content_type(file_ext)}
            )
            public_url = get_supabase().storage.from_('restaurant_assets').get_public_url(new_filename)
            filename = public_url
        except Exception as e:
                logger.exception('Error subiendo imagen de producto')
                flash('Error al subir la imagen. Intenta nuevamente.', 'danger')
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

@products_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def edit(id):
    product = Product.query.get_or_404(id)

    new_name = request.form.get('name')
    if not new_name or not new_name.strip():
        flash('El nombre del producto es obligatorio.', 'danger')
        return redirect(url_for('products.index'))
    product.name = new_name
    product.description = request.form.get('description')
    product.price = safe_float(request.form.get('price'), default=0.0)
    product.cost = safe_float(request.form.get('cost'), default=0.0)
    product.category_id = safe_int(request.form.get('category_id'), nullable=True)
    product.preparation_time = safe_int(request.form.get('preparation_time'), default=0)
    product.is_available = 'is_available' in request.form
    product.track_stock = 'track_stock' in request.form
    product.stock = safe_int(request.form.get('stock', 0), default=0)

    image_file = request.files.get('image')
    if image_file and image_file.filename != '' and allowed_file(image_file.filename):
        filename = secure_filename(image_file.filename)
        file_ext = filename.rsplit('.', 1)[1].lower()
        new_filename = f"prod_{int(time.time())}.{file_ext}"
        file_bytes = image_file.read()

        if not validate_image_bytes(file_bytes, file_ext):
            flash('El archivo no es una imagen válida.', 'danger')
            return redirect(url_for('products.index'))

        try:
            if product.image_url and 'supabase' in product.image_url:
                try:
                    old_file = product.image_url.split('/')[-1].split('?')[0]
                    get_supabase().storage.from_('restaurant_assets').remove([old_file])
                except Exception:
                    pass

            get_supabase().storage.from_('restaurant_assets').upload(
                new_filename,
                file_bytes,
                file_options={"content-type": safe_content_type(file_ext)}
            )
            public_url = get_supabase().storage.from_('restaurant_assets').get_public_url(new_filename)
            product.image_url = public_url
        except Exception as e:
            logger.exception('Error subiendo imagen de producto')
            flash('Error al subir la imagen. Intenta nuevamente.', 'danger')

    try:
        db.session.commit()
        flash('Producto actualizado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception('Error actualizando producto %s', id)
        flash('Error al actualizar el producto. Intenta nuevamente.', 'danger')

    return redirect(url_for('products.index'))

@products_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin')
def delete(id):
    product = Product.query.get_or_404(id)
    try:
        # Eliminar imagen de Supabase Storage si existe
        if product.image_url and 'supabase' in product.image_url:
            try:
                old_file = product.image_url.split('/')[-1].split('?')[0]
                get_supabase().storage.from_('restaurant_assets').remove([old_file])
            except Exception:
                logger.exception('Error eliminando imagen de producto en Storage')
                pass

        # Desenlazar el producto de los items de orden para preservar historial de ventas
        from app.models.order import OrderItem
        OrderItem.query.filter_by(product_id=id).update({'product_id': None})

        # Eliminar el producto de la base de datos (Hard delete)
        db.session.delete(product)
        db.session.commit()
        
        flash(f'El producto "{product.name}" ha sido eliminado correctamente de la base de datos.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.exception(f'Error al eliminar el producto {id}')
        flash('Error al eliminar el producto. Verifica que no tenga dependencias.', 'danger')
    return redirect(url_for('products.index'))