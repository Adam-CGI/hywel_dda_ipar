"""Root-level WSGI entrypoint for Azure App Service.

This shim ensures `az webapp up` (which scans the repository root) detects
the Flask application. It delegates to the real factory in `flask_app/app.py`.

Low-risk structural improvement: keeps all implementation inside `flask_app/`
while exposing a top-level `app` object for Gunicorn/App Service autodiscovery.
"""
from flask_app.app import create_app

# Azure / Gunicorn looks for a module attribute named `app` or `application`
app = create_app()
application = app  # alias for compatibility

if __name__ == "__main__":
    # Local dev convenience: `python app.py`
    app.run(host="0.0.0.0", port=8000)
