import os
import ssl
import certifi
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'), override=True)

is_production = bool(os.environ.get("VERCEL"))

ssl_ctx = ssl.create_default_context(cafile=certifi.where())
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_REQUIRED

_db_url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DATABASE_URL')
if not _db_url:
    raise ValueError("FALTA DATABASE_URL en variables de entorno.")
_db_url = _db_url.strip()
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+pg8000://", 1)
elif _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+pg8000://", 1)

if is_production:
    from sqlalchemy.pool import NullPool
    _engine_opts = {
        "poolclass": NullPool,
        "connect_args": {"ssl_context": ssl_ctx}
    }
else:
    _engine_opts = {
        "pool_size": 2,
        "max_overflow": 2,
        "pool_recycle": 280,
        "pool_pre_ping": True,
        "connect_args": {"ssl_context": ssl_ctx}
    }


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("FALTA SECRET_KEY en variables de entorno. Genera una con: python -c \"import secrets; print(secrets.token_hex(32))\"")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = 2592000

    _is_vercel = is_production
    SESSION_COOKIE_SECURE = _is_vercel
    REMEMBER_COOKIE_SECURE = _is_vercel

    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_ENGINE_OPTIONS = _engine_opts
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

    RATELIMIT_STORAGE_URI = os.environ.get("REDIS_URL", "memory://")

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
