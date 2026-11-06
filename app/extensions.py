"""Native extensions and compatibility proxies for Pixora (Flask-Free Architecture)."""
from app.database import db

__all__ = ["db", "csrf", "limiter", "login_manager", "migrate"]


class NoOpDecorator:
    """Pass-through decorator for retired Flask extension wrappers."""
    def __call__(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]):
            return args[0]
        def decorator(f):
            return f
        return decorator

    def exempt(self, f):
        return f

    def limit(self, *args, **kwargs):
        def decorator(f):
            return f
        return decorator

    def init_app(self, *args, **kwargs):
        pass


csrf = NoOpDecorator()
limiter = NoOpDecorator()
login_manager = NoOpDecorator()
migrate = NoOpDecorator()

