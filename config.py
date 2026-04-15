import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'), override=True)

class Config:
    # Clave secreta para proteger formularios y sesiones
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("FALTA SECRET_KEY en variables de entorno. Genera una con: python -c \"import secrets; print(secrets.token_hex(32))\"")
    
    # Configuración de sesiones para Vercel Serverless
    # remember=True en login_user() usa cookies persistentes que sobreviven cold starts
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = 2592000  # 30 días en segundos
    
    # En producción (Vercel/HTTPS), las cookies deben ser Secure
    SESSION_COOKIE_SECURE = os.environ.get('VERCEL', False) != False
    REMEMBER_COOKIE_SECURE = os.environ.get('VERCEL', False) != False
    
    # Configuración de la base de datos (PostgreSQL en Supabase vía pg8000)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI:
        if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql+pg8000://", 1)
        elif SQLALCHEMY_DATABASE_URI.startswith("postgresql://"):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgresql://", "postgresql+pg8000://", 1)
            
    import ssl
    ssl_ctx = ssl.create_default_context()
    # SSL cifrado + verificación de certificado, pero sin check de hostname
    # El pooler de Supabase (pooler.supabase.com) puede presentar un cert
    # con CN/SAN que no coincide exactamente con el hostname de conexión
    ssl_ctx.check_hostname = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 1,
        "max_overflow": 2,
        "pool_recycle": 280,
        "pool_pre_ping": True,
        "connect_args": {
            "ssl_context": ssl_ctx
        }
    }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuración de Supabase
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    
    # Límite de subida de archivos (16 MB)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024