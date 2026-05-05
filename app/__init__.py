import os
from datetime import timezone
from flask import Flask, send_from_directory, url_for, render_template
import logging
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from app.constants import PERU_TZ

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicie sesion.'
    login_manager.login_message_category = 'warning'

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.products import products_bp
    from app.routes.tables import tables_bp
    from app.routes.orders import orders_bp
    from app.routes.cashier import cashier_bp
    from app.routes.reports import reports_bp
    from app.routes.users import users_bp
    from app.routes.settings import settings_bp
    from app.routes.menu import menu_bp
    from app.routes.categories import categories_bp
    from app.routes.floor import floor_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(tables_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(cashier_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(menu_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(floor_bp)

    @app.context_processor
    def inject_notifications():
        from flask_login import current_user
        from app.models.notification import Notification

        supa_url = app.config.get("SUPABASE_URL", "")
        supa_key = app.config.get("SUPABASE_ANON_KEY", "") or app.config.get("SUPABASE_KEY", "")
        if supa_key and '"service_role"' in supa_key:
            logging.getLogger(__name__).critical(
                "SUPABASE_SERVICE_ROLE_KEY detectada en contexto de template - NO exponer al frontend"
            )
            supa_key = ""

        if current_user.is_authenticated:
            try:
                unread_count = Notification.get_unread_count(current_user.id)
                unread_list = Notification.get_by_user(current_user.id, unread_only=True, limit=5)
                return dict(unread_count=unread_count, unread_notifications=unread_list, supabase_url=supa_url, supabase_key=supa_key)
            except Exception as e:
                logging.getLogger(__name__).warning(f"Error cargando notificaciones: {e}")
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

    from sqlalchemy import text

    @app.route('/health')
    def health_check():
        try:
            db.session.execute(text('SELECT 1'))
            return {'status': 'ok', 'app': 'RestaurantPro'}, 200
        except Exception:
            db.session.rollback()
            return {'status': 'error', 'app': 'RestaurantPro'}, 500

    csrf.exempt(health_check)

    @app.errorhandler(404)
    def not_found_error(error):
        from flask_login import current_user
        if current_user.is_authenticated:
            return render_template('errors/404.html'), 404
        return render_template('errors/404_public.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logging.getLogger(__name__).exception('Error 500 no controlado')
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @app.template_filter('resolve_url')
    def resolve_url(path, folder='uploads/products/'):
        if not path:
            return ""
        if path.startswith('http://') or path.startswith('https://'):
            return path
        return url_for('static', filename=folder + path)

    @app.template_filter('peru_time')
    def peru_time(dt, fmt=None):
        if not dt:
            return dt
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        result = dt.astimezone(PERU_TZ)
        if fmt:
            return result.strftime(fmt)
        return result

    @app.template_filter('format_payment_method')
    def filter_format_payment_method(val):
        from app.utils.formatters import format_payment_method
        return format_payment_method(val)

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if bool(os.environ.get("VERCEL")):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        supabase_host = os.environ.get("SUPABASE_URL", "").replace("https://", "")
        img_src = "'self' data: https://*.supabase.co"
        if supabase_host:
            img_src += f" https://{supabase_host}"
        response.headers['Content-Security-Policy'] = (
            f"default-src 'self'; "
            f"script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            f"style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            f"img-src {img_src}; "
            f"font-src 'self' cdn.jsdelivr.net; "
            f"connect-src 'self' https://*.supabase.co wss://*.supabase.co; "
            f"frame-ancestors 'none'"
        )
        return response

    return app
