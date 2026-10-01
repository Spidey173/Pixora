import os
import sys

# Ensure root directory is on python path so `app` package is importable
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import create_app  # noqa: E402

app = create_app(os.environ.get('FLASK_ENV', 'production'))
application = app
