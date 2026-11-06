import os
import sys

# Ensure root directory is on python path so `app` and `gateway` are importable
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    # Tier S Architecture: Serve via Unified FastAPI ASGI engine
    from gateway import app
    application = app
except Exception:
    # Graceful fallback to WSGI app
    from app import create_app
    app = create_app(os.environ.get('FLASK_ENV', 'production'))
    application = app
