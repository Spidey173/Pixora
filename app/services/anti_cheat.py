"""Anti-Cheat & Cryptographic Proof-of-Gameplay Engine for Pixora 2.0.

Provides:
- Cryptographic session token generation (HMAC-SHA256)
- Authoritative session validation (signature, replay protection)
- Physical game velocity and impossible duration anomaly detection
- Entropy and action heuristics verification
"""
import hashlib
import hmac
import logging
import threading
import time
from typing import Dict, Optional, Tuple

from app.config import settings

logger = logging.getLogger('pixora.anti_cheat')

# Theoretical maximum score rates (points per second)
GAME_VELOCITY_LIMITS: Dict[str, float] = {
    "flappybird": 2.5,     # At most 2.5 pipes per second
    "2048": 40.0,          # At most 40 score points per second
    "speedtype": 15.0,     # Words/characters per second
    "neon-racer": 100.0,   # High-speed distance points per second
    "neon-cyber-racer": 100.0,
    "candy-crush": 20.0,
    "pong": 5.0,
    "towerblock": 10.0,
    "mole": 15.0,
    "tictactoe": 50.0,
    "stonepapersissors": 25.0,
    "maze": 200.0,
}

# Alias mapping for friendly game name normalization
SLUG_ALIASES: Dict[str, str] = {
    "flappy-birds": "flappybird",
    "flappy bird": "flappybird",
    "flappy-bird": "flappybird",
    "flappybirds": "flappybird",
    "neon cyber racer": "neon-racer",
    "neon-cyber-racer": "neon-racer",
    "speedtype pro": "speedtype",
    "speedtype-pro": "speedtype",
    "2048 cyber grid": "2048",
    "whack a mole": "mole",
    "whack-a-mole": "mole",
    "cyber crush": "candy-crush",
    "candy crush": "candy-crush",
    "vector pong classic": "pong",
    "quantum tic-tac-toe": "tictactoe",
    "tic-tac-toe": "tictactoe",
    "cyber labyrinth": "maze",
}


class AntiCheatValidator:
    """Validates game sessions, scores, and detects cheating / anomalies."""

    _used_tokens_mem: Dict[str, float] = {}
    _lock = threading.Lock()

    @classmethod
    def _get_secret_key(cls) -> str:
        """Resolve active secret key from Flask context or app.config settings."""
        try:
            from flask import current_app
            if current_app and current_app.config.get('SECRET_KEY'):
                return current_app.config['SECRET_KEY']
        except Exception:
            pass
        return getattr(settings, 'SECRET_KEY', 'pixora-fallback-secret-key')

    @classmethod
    def normalize_slug(cls, game_slug: str) -> str:
        """Normalize game slugs and titles to canonical velocity lookup keys."""
        if not game_slug:
            return ""
        raw = game_slug.strip().lower()
        if raw in SLUG_ALIASES:
            return SLUG_ALIASES[raw]
        cleaned = raw.replace('_', '-').replace(' ', '-')
        return SLUG_ALIASES.get(cleaned, cleaned)

    @classmethod
    def generate_session_token(cls, player_id: int, game_slug: str, timestamp_ms: int) -> str:
        """Generate a cryptographically signed session token for proof of gameplay."""
        norm_slug = cls.normalize_slug(game_slug)
        payload = f"{player_id}:{norm_slug}:{timestamp_ms}"
        secret = cls._get_secret_key().encode('utf-8')
        return hmac.new(
            secret,
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    @classmethod
    def is_token_replayed(cls, session_token: str, redis_client=None) -> bool:
        """Check whether a session token has already been consumed (Replay Attack Guard)."""
        if not session_token:
            return True

        if redis_client:
            try:
                key = f"pixora:used_token:{session_token}"
                return bool(redis_client.exists(key))
            except Exception as e:
                logger.warning("Redis error checking replayed token: %s", e)

        # In-memory fallback
        with cls._lock:
            now = time.time()
            # Clean expired tokens (> 2 hours old)
            expired = [t for t, exp in cls._used_tokens_mem.items() if exp < now]
            for t in expired:
                del cls._used_tokens_mem[t]

            return session_token in cls._used_tokens_mem

    @classmethod
    def mark_token_used(cls, session_token: str, ttl: int = 7200, redis_client=None):
        """Mark a session token as consumed."""
        if not session_token:
            return

        if redis_client:
            try:
                key = f"pixora:used_token:{session_token}"
                redis_client.set(key, "1", ex=ttl)
                return
            except Exception as e:
                logger.warning("Redis error marking token used: %s", e)

        with cls._lock:
            cls._used_tokens_mem[session_token] = time.time() + ttl

    @classmethod
    def validate_submission(
        cls,
        player_id: int,
        game_slug: str,
        score: int,
        start_time_ms: int,
        session_token: str,
        action_count: Optional[int] = None,
        input_entropy_hash: Optional[str] = None,
        redis_client=None,
        check_replay: bool = True
    ) -> Tuple[bool, str]:
        """Validate score submission against cryptographic proof and physical anomalies.
        
        Returns:
            Tuple[bool, str]: (is_valid, reason_code)
        """
        # 1. Verify cryptographic token authenticity
        expected_token = cls.generate_session_token(player_id, game_slug, start_time_ms)
        if not hmac.compare_digest(expected_token, session_token):
            return False, "INVALID_SESSION_SIGNATURE"

        # 2. Replay attack guard: Ensure session_token can only be used once
        if check_replay and cls.is_token_replayed(session_token, redis_client=redis_client):
            return False, "REPLAY_ATTACK_DETECTED"

        # 3. Verify reasonable elapsed time
        current_time_ms = int(time.time() * 1000)
        elapsed_seconds = (current_time_ms - start_time_ms) / 1000.0

        if elapsed_seconds < 0:
            return False, "NEGATIVE_DURATION_ANOMALY"

        # Token TTL check (2 hours)
        max_session_age = getattr(settings, 'ANTI_CHEAT_TOKEN_TTL', 7200)
        if elapsed_seconds > max_session_age:
            return False, "SESSION_EXPIRED"

        if elapsed_seconds < 2.0 and score > 10:
            return False, "IMPOSSIBLE_DURATION"

        # 4. Verify maximum possible velocity
        norm_slug = cls.normalize_slug(game_slug)
        max_rate = GAME_VELOCITY_LIMITS.get(norm_slug, 50.0)
        calculated_rate = score / max(elapsed_seconds, 1.0)
        if calculated_rate > max_rate:
            return False, f"SCORE_VELOCITY_EXCEEDED (Rate: {calculated_rate:.1f}/s, Max: {max_rate}/s)"

        # 5. Action Entropy & Heuristics Check (if reported by SDK)
        if action_count is not None:
            if score > 0 and action_count <= 0:
                return False, "ZERO_ACTIONS_FOR_NONZERO_SCORE"
            # In speedtype, 1 word requires multiple keystrokes
            if norm_slug == "speedtype" and score > 5 and action_count < score:
                return False, "INSUFFICIENT_KEYSTROKES"

        return True, "VERIFIED"

