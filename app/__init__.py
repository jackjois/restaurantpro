import os
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicie sesión.'
    login_manager.login_message_category = 'warning'

    # os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) # Removido para Vercel Serverless
    # Registro de Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.products import products_bp
    from app.routes.tables import tables_bp
    from app.routes.orders import orders_bp
    from app.routes.cashier import cashier_bp
    from app.routes.reports import reports_bp
    from app.routes.users import users_bp
    from app.routes.settings import settings_bp
    from app.routes.menu import menu_bp # <-- NUEVO: Importamos el menú digital
    from app.routes.categories import categories_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(tables_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(cashier_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(menu_bp) # <-- NUEVO: Lo registramos
    app.register_blueprint(categories_bp)
    
    @app.context_processor
    def inject_notifications():
        from flask_login import current_user
        from app.models.notification import Notification
        
        # Obtenemos las vars de Entorno de Supabase (las ANÓNIMAS son públicas y seguras de exponer en HTML/JS)
        supa_url = os.environ.get("SUPABASE_URL", "")
        supa_key = os.environ.get("SUPABASE_KEY", "")
        
        if current_user.is_authenticated:
            try:
                unread_count = Notification.get_unread_count(current_user.id)
                unread_list = Notification.get_by_user(current_user.id, unread_only=True, limit=5)
                return dict(unread_count=unread_count, unread_notifications=unread_list, supabase_url=supa_url, supabase_key=supa_key)
            except Exception as e:
                pass
        return dict(unread_count=0, unread_notifications=[], supabase_url=supa_url, supabase_key=supa_key)

    @app.context_processor
    def inject_settings():
        from app.models.setting import Setting
        try:
            restaurant = Setting.query.first()
            return dict(restaurant=restaurant)
        except Exception as e:
            return dict(restaurant=None)

    @app.route('/manifest.json')
    def manifest():
        return send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.json')

    @app.route('/sw.js')
    def service_worker():
        return send_from_directory(os.path.join(app.root_path, 'static'), 'sw.js')
    
    @app.template_filter('resolve_url')
    def resolve_url(path, folder='uploads/products/'):
        if not path:
            return ""
        if path.startswith('http://') or path.startswith('https://'):
            return path
        return url_for('static', filename=folder + path)

    return app