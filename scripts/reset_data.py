"""Safe data reset tool for Pixora.

Dry-run by default. Real deletion requires BOTH `--confirm` and typing the
database host name when prompted. Exports affected tables to `backups/`
before deleting, deletes in a single transaction in FK order, resets ID
sequences, and cleans Redis keys via SCAN (never FLUSHALL/FLUSHDB).
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings  # noqa: E402
from app.database import db  # noqa: E402
from app.models import GameplaySession, GameScore, User  # noqa: E402


def _extract_host(url: str) -> str:
    if not url:
        return "none"
    if url.startswith("sqlite"):
        return "sqlite"
    parsed = urlparse(url)
    return parsed.hostname or "unknown"


def _get_redis_prefixes() -> list[str]:
    prefixes = {
        os.environ.get("REDIS_KEY_PREFIX", "pixora:"),
        "pixora:",
        "glitch4ce:",
    }
    return sorted(p for p in prefixes if p)


def _get_redis_client():
    redis_url = getattr(settings, "REDIS_URL", "") or os.environ.get("REDIS_URL", "")
    if not redis_url or not redis_url.startswith(("redis://", "rediss://", "unix://")):
        return None, "none"
    try:
        import redis
        client = redis.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=3.0)
        client.ping()
        return client, _extract_host(redis_url)
    except Exception:
        return None, _extract_host(redis_url)


def _scan_keys(client, pattern: str) -> list[str]:
    if client is None:
        return []
    keys = []
    cursor = 0
    while True:
        cursor, batch = client.scan(cursor=cursor, match=pattern, count=500)
        keys.extend(batch)
        if cursor == 0:
            break
    return keys


def _export_backups(backup_dir: Path, admin_username: str) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    scores = [
        {
            "id": s.id,
            "player_id": s.player_id,
            "game_name": s.game_name,
            "score": s.score,
            "achieved_at": s.achieved_at.isoformat() if s.achieved_at else None,
        }
        for s in GameScore.query.all()
    ]
    sessions = [
        {
            "id": gs.id,
            "player_id": gs.player_id,
            "game_name": gs.game_name,
            "started_at": gs.started_at.isoformat() if gs.started_at else None,
            "ended_at": gs.ended_at.isoformat() if gs.ended_at else None,
            "duration_seconds": gs.duration_seconds,
        }
        for gs in GameplaySession.query.all()
    ]
    users = [
        {
            "id": u.id,
            "username": u.username,
            "created_at": u.created_at.isoformat() if getattr(u, "created_at", None) else None,
        }
        for u in User.query.filter(User.username != admin_username).all()
    ]
    (backup_dir / "game_scores.json").write_text(json.dumps(scores, indent=2))
    (backup_dir / "gameplay_sessions.json").write_text(json.dumps(sessions, indent=2))
    (backup_dir / "non_admin_users.json").write_text(json.dumps(users, indent=2))


def run_reset(confirm: bool = False, input_fn=input) -> int:
    """Execute dry-run or confirmed reset. Returns exit code (0=ok, 1=aborted/error)."""
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    active_db_url = str(db.engine.url)
    db_host = _extract_host(active_db_url)
    redis_client, redis_host = _get_redis_client()
    prefixes = _get_redis_prefixes()

    score_count = GameScore.query.count()
    session_count = GameplaySession.query.count()
    non_admin_count = User.query.filter(User.username != admin_username).count()

    redis_counts = {}
    for pref in prefixes:
        keys = _scan_keys(redis_client, f"{pref}*")
        redis_counts[f"{pref}*"] = keys

    print(f"Target DB host:    {db_host}")
    print(f"Target Redis host: {redis_host} (prefixes: {', '.join(prefixes)})")
    print(f"Admin preserved:   {admin_username}")
    print("Rows to delete:")
    print(f"  game_scores:       {score_count}")
    print(f"  gameplay_sessions: {session_count}")
    print(f"  users (non-admin): {non_admin_count}")
    print("Redis keys to delete:")
    for pat, keys in redis_counts.items():
        print(f"  {pat:18s} {len(keys)}")

    if not confirm:
        print("\nDRY RUN: No changes made. Pass --confirm to execute reset.")
        return 0

    typed_host = input_fn(f"\nType database host '{db_host}' to confirm deletion: ").strip()
    if typed_host != db_host:
        print("Host mismatch. Aborting without changes.")
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = ROOT_DIR / "backups" / ts
    _export_backups(backup_dir, admin_username)
    print(f"Backups exported to {backup_dir}")

    try:
        db.session.query(GameScore).delete(synchronize_session=False)
        db.session.query(GameplaySession).delete(synchronize_session=False)
        db.session.query(User).filter(User.username != admin_username).delete(synchronize_session=False)

        if active_db_url.startswith("sqlite"):
            try:
                db.session.execute(
                    text("DELETE FROM sqlite_sequence WHERE name IN ('game_scores', 'gameplay_sessions', 'users')")
                )
            except Exception:
                pass
        else:
            for seq in ("game_scores_id_seq", "gameplay_sessions_id_seq", "users_id_seq"):
                db.session.execute(text(f"ALTER SEQUENCE IF EXISTS {seq} RESTART WITH 1"))

        db.session.commit()
        print("Database reset committed.")
    except Exception as exc:
        db.session.rollback()
        print(f"Database reset failed and rolled back: {exc}")
        return 1

    if redis_client is not None:
        deleted_total = 0
        for keys in redis_counts.values():
            for i in range(0, len(keys), 500):
                batch = keys[i : i + 500]
                if batch:
                    deleted_total += redis_client.delete(*batch)
        print(f"Deleted {deleted_total} Redis keys.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe data reset tool for Pixora")
    parser.add_argument("--confirm", action="store_true", help="Actually delete data after host confirmation")
    args = parser.parse_args()
    return run_reset(confirm=args.confirm)


if __name__ == "__main__":
    raise SystemExit(main())
