"""Database migration helper to safely port legacy SQLite records to SQLAlchemy."""
import os
import sqlite3
from datetime import datetime, timezone

from app.extensions import db
from app.models import GameplaySession, User


def migrate_legacy_data(legacy_db_path='game_data.db'):
    """Migrate players and gameplay logs from legacy sqlite3 db."""
    if not os.path.exists(legacy_db_path):
        print(f"No legacy database found at '{legacy_db_path}'. Skipping migration.")
        return

    conn = None
    try:
        conn = sqlite3.connect(legacy_db_path)
        c = conn.cursor()

        # Check if legacy tables exist
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='players'")
        if not c.fetchone():
            print("Legacy 'players' table not found.")
            return

        # Fetch players
        c.execute("SELECT id, username FROM players")
        legacy_players = c.fetchall()
        print(f"Found {len(legacy_players)} legacy players.")

        id_map = {}
        for old_id, username in legacy_players:
            if not username:
                continue
            existing = User.query.filter_by(username=username).first()
            if not existing:
                new_user = User(
                    username=username,
                    is_guest=True,
                    created_at=datetime.now(timezone.utc),
                    last_seen=datetime.now(timezone.utc)
                )
                db.session.add(new_user)
                db.session.flush()
                id_map[old_id] = new_user.id
            else:
                id_map[old_id] = existing.id

        db.session.commit()

        # Fetch gameplay records
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gameplay'")
        if c.fetchone():
            c.execute("SELECT player_id, game_name, timestamp FROM gameplay")
            legacy_gameplay = c.fetchall()
            print(f"Found {len(legacy_gameplay)} legacy gameplay records.")

            for old_player_id, game_name, ts_str in legacy_gameplay:
                new_player_id = id_map.get(old_player_id)
                if not new_player_id or not game_name:
                    continue

                started_at = datetime.now(timezone.utc)
                if ts_str:
                    try:
                        started_at = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass

                # Check if record already migrated
                exists = GameplaySession.query.filter_by(
                    player_id=new_player_id,
                    game_name=game_name,
                    started_at=started_at
                ).first()

                if not exists:
                    session_record = GameplaySession(
                        player_id=new_player_id,
                        game_name=game_name,
                        started_at=started_at
                    )
                    db.session.add(session_record)

            db.session.commit()
            print("Successfully migrated legacy records to SQLAlchemy schema!")

    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        print(f"Error during legacy migration: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        migrate_legacy_data()
