from app import create_app
import os

# Crear la instancia de la aplicación
app = create_app()

if __name__ == '__main__':
    # Ejecutar en todas las interfaces de red locales (0.0.0.0)
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes", "on")
    app.run(host=host, port=port, debug=debug)