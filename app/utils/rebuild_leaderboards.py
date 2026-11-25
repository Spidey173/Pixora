"""Idempotent utility to rebuild Redis leaderboard ZSETs from the database.

Useful after changing REDIS_KEY_PREFIX, migrating from legacy prefixes (e.g.
glitch4ce:*), or recovering from a Redis restart/flush.

Usage:
    python -m app.utils.rebuild_leaderboards
    python -m app.utils.rebuild_leaderboards --purge-legacy
"""
import argparse
import json
import os
import sys

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

from app import create_app
from app.models import GameScore
from app.utils.game_resolver import canonical_game_title
from app.utils.redis_keys import get_redis_key_prefix, redis_key


def rebuild_leaderboards(purge_legacy: bool = False, testing: bool = False) -> dict:
    """Rebuild all Redis leaderboard ZSETs idempotently from relational GameScore rows."""
    if not REDIS_AVAILABLE:
        raise RuntimeError("redis package is not installed.")

    env = "testing" if testing else os.environ.get("FLASK_ENV", "development")
    app = create_app(env)
    redis_url = app.config.get("REDIS_URL", os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"))
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    r.ping()

    prefix = get_redis_key_prefix(testing=testing)

    with app.app_context():
        scores = GameScore.query.order_by(GameScore.score.desc(), GameScore.achieved_at.asc()).all()

        # Clear existing leaderboard keys under the active prefix so stale entries don't linger
        for pattern in (f"{prefix}lb:bests:*", f"{prefix}lb:entries:*", f"{prefix}lb:warmed:*"):
            old_keys = list(r.scan_iter(match=pattern, count=200))
            if old_keys:
                r.delete(*old_keys)

        if purge_legacy:
            legacy_keys = list(r.scan_iter(match="glitch4ce:*", count=200))
            if legacy_keys:
                r.delete(*legacy_keys)

        games_rebuilt = set()
        bests_written = {}  # (game_title, player_id) -> best_score
        pipe = r.pipeline()

        for s in scores:
            game_title = canonical_game_title(s.game_name) or s.game_name
            username = s.player.username if s.player else "Guest"
            entry = {
                "id": s.id,
                "player_id": s.player_id,
                "username": username,
                "game_name": game_title,
                "score": int(s.score),
                "achieved_at": s.achieved_at.isoformat() if s.achieved_at else None,
            }
            pipe.zadd(redis_key(f"lb:entries:{game_title}", testing=testing), {json.dumps(entry): int(s.score)})

            key_pair = (game_title, s.player_id)
            if int(s.score) > bests_written.get(key_pair, -1):
                bests_written[key_pair] = int(s.score)
                pipe.zadd(
                    redis_key(f"lb:bests:{game_title}", testing=testing),
                    {f"{s.player_id}:{username}": int(s.score)},
                    gt=True,
                )
            games_rebuilt.add(game_title)

        for game_title in games_rebuilt:
            pipe.set(redis_key(f"lb:warmed:{game_title}", testing=testing), "1", ex=3600)

        pipe.execute()

    return {
        "prefix": prefix,
        "games_rebuilt": len(games_rebuilt),
        "scores_indexed": len(scores),
        "unique_player_bests": len(bests_written),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild Pixora Redis leaderboard ZSETs from database.")
    parser.add_argument("--purge-legacy", action="store_true", help="Also delete orphaned glitch4ce:* keys.")
    args = parser.parse_args()
    try:
        stats = rebuild_leaderboards(purge_legacy=args.purge_legacy)
        print(
            f"✅ Rebuilt {stats['games_rebuilt']} game leaderboards "
            f"({stats['unique_player_bests']} player bests from {stats['scores_indexed']} scores) "
            f"under prefix '{stats['prefix']}'."
        )
    except Exception as exc:
        print(f"❌ Leaderboard rebuild failed: {exc}", file=sys.stderr)
        sys.exit(1)

