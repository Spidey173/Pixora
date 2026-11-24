"""Vercel Serverless Entrypoint for Pixora FastAPI Application."""
import os
import shutil

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
tmp_db = "/tmp/game_data.db"
bundled_db = os.path.join(basedir, "game_data.db")

# In Vercel serverless environment, ensure SQLite uses writable /tmp directory
if not os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL", "").startswith("sqlite"):
    if os.path.exists(bundled_db) and not os.path.exists(tmp_db):
        try:
            shutil.copy2(bundled_db, tmp_db)
        except Exception:
            pass
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db}"

from gateway import app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Game  # noqa: E402
from app.utils.seed_games import seed_catalog  # noqa: E402
from app.utils.seed_admin import seed_admin  # noqa: E402

# Ensure database tables and catalog are initialized in /tmp on cold boot
try:
    db.create_all()
    if Game.query.count() == 0:
        seed_catalog()
    seed_admin()
except Exception:
    try:
        db.session.rollback()
    except Exception:
        pass

# Expose ASGI application
app = app


