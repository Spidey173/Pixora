"""Application Factory for Pixora (Unified ASGI FastAPI Architecture)."""
import os

from app.config import config_by_name
from app.database import db, rebind_engine
from app.utils.storage import r2_storage
from app.utils.telemetry_queue import telemetry_queue

__all__ = ["create_app", "db", "rebind_engine", "r2_storage", "telemetry_queue"]


class AppContext:
    """Compatibility app_context manager for database operations."""
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def create_app(config_name=None):
    """Factory function returning the unified FastAPI ASGI application."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    from gateway import app

    config_class = config_by_name.get(config_name, config_by_name['default'])
    db_uri = getattr(config_class, 'SQLALCHEMY_DATABASE_URI', None)
    if db_uri:
        rebind_engine(db_uri)

    app.config = {
        k: getattr(config_class, k)
        for k in dir(config_class)
        if not k.startswith('_')
    }
    app.app_context = lambda: AppContext()

    # Auto-seed in development or serverless environments
    if config_name != 'testing':
        try:
            db.create_all()
            from app.models import Game, GameScore
            if Game.query.count() == 0 or GameScore.query.count() == 0:
                from app.utils.seed_games import seed_catalog
                seed_catalog()
        except Exception:
            pass

    return app


def __getattr__(name):
    """Module-level attribute fallback (e.g. `uvicorn app:app` or `gunicorn app:app`)."""
    if name == 'app':
        return create_app(os.environ.get('FLASK_ENV', 'production'))
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
