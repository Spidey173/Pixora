"""Route blueprints package for Pixora."""
from app.routes.admin import admin_bp
from app.routes.auth import auth_bp
from app.routes.errors import errors_bp
from app.routes.games import games_bp
from app.routes.main import main_bp

__all__ = ['admin_bp', 'auth_bp', 'errors_bp', 'games_bp', 'main_bp']
