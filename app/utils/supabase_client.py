import os
import logging
from supabase import create_client, Client

_client = None

def get_supabase() -> Client:
    """Obtiene el cliente de Supabase con lazy initialization.
    
    Usa SUPABASE_SERVICE_ROLE_KEY si está disponible (para operaciones de backend
    como Storage que necesitan permisos completos), sino fallback a SUPABASE_KEY.
    NUNCA uses este cliente en el frontend — para eso está SUPABASE_ANON_KEY.
    """
    global _client
    if _client is None:
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Faltan las credenciales de Supabase en el entorno.")
        if key and '"service_role"' not in key:
            logging.getLogger(__name__).warning(
                "Supabase client usando anon key — operaciones de Storage pueden fallar por permisos RLS. "
                "Configura SUPABASE_SERVICE_ROLE_KEY para backend."
            )
        _client = create_client(url, key)
    return _client
