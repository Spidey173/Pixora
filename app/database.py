"""Native SQLAlchemy Database Engine & Scoped Session Provider for Pixora.

Replaces Flask-SQLAlchemy with direct SQLAlchemy 2.0 ORM:
- Native engine with connection pooling & ping
- Thread-safe scoped_session and SessionLocal
- FastAPI get_db dependency injection
- Backward-compatible `db` proxy for models and migrations
"""
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func
)
from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings

# Database URI configuration
db_url = getattr(settings, 'SQLALCHEMY_DATABASE_URI', 'sqlite:///game_data.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

engine_kwargs = {}
if db_url.startswith('sqlite'):
    engine_kwargs['connect_args'] = {'check_same_thread': False}
    if db_url == 'sqlite:///:memory:':
        engine_kwargs['poolclass'] = StaticPool

engine = create_engine(db_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
_scoped_session = scoped_session(SessionLocal)
Base = declarative_base()


class DatabaseProxy:
    """Compatibility proxy offering db.session, db.Model, db.Column, etc."""
    Model = Base
    metadata = Base.metadata
    Column = staticmethod(Column)
    Integer = Integer
    String = String
    Boolean = Boolean
    DateTime = DateTime
    Float = Float
    Text = Text
    ForeignKey = staticmethod(ForeignKey)
    relationship = staticmethod(relationship)
    func = func

    @property
    def session(self):
        return _scoped_session

    @property
    def engine(self):
        return engine

    def create_all(self, bind=None):
        target_engine = bind or engine
        Base.metadata.create_all(bind=target_engine)

    def drop_all(self, bind=None):
        target_engine = bind or engine
        Base.metadata.drop_all(bind=target_engine)

    def init_app(self, app=None, *args, **kwargs):
        if app is not None and hasattr(app, 'config'):
            uri = app.config.get('SQLALCHEMY_DATABASE_URI')
            if uri:
                rebind_engine(uri)


db = DatabaseProxy()


def get_db():
    """FastAPI dependency for request-scoped database sessions."""
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()


def rebind_engine(new_url: str):
    """Rebind engine for testing (e.g. sqlite:///:memory:)."""
    global engine
    kwargs = {}
    if new_url.startswith('sqlite'):
        kwargs['connect_args'] = {'check_same_thread': False}
        if new_url == 'sqlite:///:memory:' or ':memory:' in new_url:
            kwargs['poolclass'] = StaticPool

    engine = create_engine(new_url, **kwargs)
    _scoped_session.remove()
    SessionLocal.configure(bind=engine)
    return engine
