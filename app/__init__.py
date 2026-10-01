"""Application Factory for Pixora Retro Arcade Hub."""
import os

from flask import Flask

from app.config import config_by_name
from app.extensions import csrf, db, limiter, login_manager, migrate
from app.routes.admin import admin_bp
from app.routes.auth import auth_bp
from app.routes.errors import errors_bp
from app.routes.games import register_game_routes
from app.routes.main import main_bp


def create_app(config_name=None):
    """Factory function to create and configure Flask application."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')

    is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
    if is_serverless:
        instance_dir = '/tmp/instance'
        os.makedirs(instance_dir, exist_ok=True)
    else:
        instance_dir = os.path.join(base_dir, 'instance')

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir,
        instance_path=instance_dir
    )

    # Load configuration
    config_class = config_by_name.get(config_name, config_by_name['default'])
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)

    from app.utils.storage import r2_storage
    r2_storage.init_app(app)

    from app.utils.telemetry_queue import telemetry_queue
    telemetry_queue.init_app(app)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(errors_bp)

    # Register all 15+ mini-games and subpage endpoints directly on app
    register_game_routes(app)

    # Add legacy endpoint aliases for backward compatibility with older template calls
    app.add_url_rule('/login', endpoint='login', view_func=app.view_functions['auth.login'], methods=['GET', 'POST'])
    app.add_url_rule('/logout', endpoint='logout', view_func=app.view_functions['auth.logout'])
    app.add_url_rule('/games', endpoint='games', view_func=app.view_functions['main.games'])

    # Security response headers middleware
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    # Auto-create tables in development and serverless environments
    if config_name != 'testing':
        with app.app_context():
            try:
                db.create_all()
            except Exception:
                pass

    return app


def __getattr__(name):
    """Module-level attribute fallback for WSGI servers like Gunicorn (e.g. `gunicorn app:app`)."""
    if name == 'app':
        return create_app(os.environ.get('FLASK_ENV', 'production'))
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
