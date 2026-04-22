import os
import time
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from app.models.setting import Setting
from app import db
from app.utils.supabase_client import get_supabase
from app.utils.decorators import role_required
import logging

logger = logging.getLogger(__name__)

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

# Extensiones de imagen permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def index():
    setting = Setting.query.first()
    
    if not setting:
        setting = Setting(name='Mi Restaurante')
        db.session.add(setting)
        db.session.commit()

    if request.method == 'POST':
        setting.name = request.form.get('name', '')
        setting.subtitle = request.form.get('subtitle', '')
        setting.ruc = request.form.get('ruc', '')
        setting.address = request.form.get('address', '')
        setting.phone = request.form.get('phone', '')
        setting.thank_you_message = request.form.get('thank_you_message', '')
        
        # LOGICA PARA SUBIR EL LOGO
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '' and allowed_file(file.filename):
                # Limpiamos el nombre del archivo por seguridad
                filename = secure_filename(file.filename)
                
                # Subir archivo al Storage de Supabase (asumimos el bucket "restaurant_assets")
                file_ext = filename.rsplit('.', 1)[1].lower()
                new_filename = f"logo_{int(time.time())}.{file_ext}"
                file_bytes = file.read()
                
                try:
                    get_supabase().storage.from_('restaurant_assets').upload(
                        new_filename, 
                        file_bytes,
                        file_options={"content-type": file.mimetype}
                    )
                    public_url = get_supabase().storage.from_('restaurant_assets').get_public_url(new_filename)
                    setting.logo_url = public_url
                except Exception as e:
                    logger.exception('Error subiendo logo a Supabase')
                    flash('Error al subir el logo. Intenta nuevamente.', 'danger')

        db.session.commit()
        flash('Datos de la empresa y logo actualizados exitosamente.', 'success')
        return redirect(url_for('settings.index'))

    return render_template('settings/index.html', setting=setting)