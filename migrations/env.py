import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool, create_engine
from alembic import context

# Ensure application root is in python path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from app.config import Config  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User, GameplaySession, GameScore, Game  # noqa: F401, E402

# Alembic configuration
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None and os.path.isfile(config.config_file_name):
    fileConfig(config.config_file_name)

# Target model metadata for migrations
target_metadata = db.metadata


def get_url():
    """Resolve database URL from environment or Flask Config."""
    url = os.environ.get('DATABASE_URL') or Config.SQLALCHEMY_DATABASE_URI
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    if url.startswith('sqlite:///'):
        db_path = url.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            instance_path = os.path.join(base_dir, 'instance', db_path)
            if os.path.exists(instance_path) or os.path.exists(os.path.join(base_dir, 'instance')):
                url = f"sqlite:///{instance_path}"
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite compatibility for alter/drop columns
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_url()
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite compatibility
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
