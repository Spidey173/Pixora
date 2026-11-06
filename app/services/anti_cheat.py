"""Anti-Cheat & Cryptographic Proof-of-Gameplay Engine for Pixora 2.0.

Provides:
- Cryptographic session token generation (HMAC-SHA256)
- Authoritative session validation (signature, replay protection)
- Physical game velocity and impossible duration anomaly detection
- Entropy and action heuristics verification

Security & Threat Model Boundaries:
Pixora operates client-side HTML5 canvas games within sandboxed iframes.
1. Mitigated Attacks:
   - Replay attacks across multiple workers or restarts (via distributed Redis single-use sets).
   - Session token forgery and tampering (via HMAC-SHA256 token verification with non-default secrets).
   - Instant velocity jumps (via game-specific score/duration rate curves).
   - Perfectly spaced robotic macros (via input entropy timestamp jitter and variance checks).
2. Fundamental Client-Side Boundary:
   - Because the browser executes JavaScript and canvas game loops, an adversary with full control of
     the client memory space can execute a customized script that satisfies duration and entropy constraints.
   - 100% cheat-proof architectures require authoritative server-side simulation (computing game state
     tick-by-tick on the server). For casual web arcade platforms, Pixora delivers probabilistic,
     heuristic, and cryptographic defense-in-depth.
"""
import hashlib
import hmac
import inspect
import logging
import os
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

    _runtime_ephemeral_secret: Optional[str] = None

    @classmethod
    def _get_secret_key(cls) -> str:
        """Resolve active secret key from Flask context, settings, or shell environment.

        In production, raises RuntimeError if no explicit SECRET_KEY is configured.
        In development/testing, generates a cryptographically secure ephemeral key if unset,
        preventing offline token forgery against hardcoded defaults.
        """
        # 1. Flask current_app configuration
        try:
            from flask import current_app
            if current_app and current_app.config.get('SECRET_KEY'):
                key = current_app.config['SECRET_KEY']
                if key and key not in ('pixora-fallback-secret-key', 'pixora-fallback-dev-secret-key-replace-in-prod'):
                    return key
        except Exception:
            pass

        # 2. Direct Environment Variable
        env_secret = os.environ.get('SECRET_KEY')
        if env_secret and env_secret not in ('pixora-fallback-secret-key', 'pixora-fallback-dev-secret-key-replace-in-prod'):
            return env_secret

        # 3. Settings from app.config
        cfg_secret = getattr(settings, 'SECRET_KEY', None)
        if cfg_secret and cfg_secret not in ('pixora-fallback-secret-key', 'pixora-fallback-dev-secret-key-replace-in-prod'):
            return cfg_secret

        # 4. Enforce strict failure in production
        env_mode = os.environ.get('FLASK_ENV', os.environ.get('ENV', 'development')).lower()
        if env_mode == 'production':
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable is missing in production! "
                "Refusing to fall back to hardcoded secrets."
            )

        # 5. Non-production: Use securely generated process-ephemeral secret
        if not cls._runtime_ephemeral_secret:
            import secrets
            cls._runtime_ephemeral_secret = secrets.token_hex(32)
            logger.warning(
                "No SECRET_KEY configured. Generated ephemeral runtime secret key for current process session."
            )
        return cls._runtime_ephemeral_secret

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
    def create_player_token(cls, player_id: int, username: str) -> str:
        """Create a cryptographically signed Bearer authentication token for a player."""
        from itsdangerous import URLSafeTimedSerializer
        s = URLSafeTimedSerializer(cls._get_secret_key(), salt="pixora-player-auth")
        return s.dumps({"player_id": player_id, "username": username})

    @classmethod
    def verify_player_token(cls, token: str, max_age: int = 86400 * 30) -> Optional[dict]:
        """Verify and decode a player authentication Bearer token."""
        from itsdangerous import URLSafeTimedSerializer
        s = URLSafeTimedSerializer(cls._get_secret_key(), salt="pixora-player-auth")
        try:
            return s.loads(token, max_age=max_age)
        except Exception:
            return None

    @classmethod
    def decode_flask_session(cls, cookie_val: str, max_age: int = 86400 * 31) -> Optional[dict]:
        """Decode and verify a Flask signed session cookie."""
        from itsdangerous import URLSafeTimedSerializer
        s = URLSafeTimedSerializer(cls._get_secret_key(), salt="cookie-session")
        try:
            return s.loads(cookie_val, max_age=max_age)
        except Exception:
            return None

    @classmethod
    def verify_input_entropy(
        cls,
        input_entropy_hash: str,
        action_count: Optional[int],
        start_time_ms: int,
        current_time_ms: int
    ) -> Tuple[bool, str]:
        """Validate format, variance, and temporal consistency of input entropy reports.

        SDK transmits entropy string in format: '<action_count>:<ts_1>,<ts_2>,...'
        Validates:
        1. Non-empty string conforming to structural grammar.
        2. Action count consistency between payload and entropy header.
        3. Monotonic ordering of reported physical input timestamps.
        4. Bounds checking against active session duration.
        """
        if not input_entropy_hash or not isinstance(input_entropy_hash, str):
            return False, "INVALID_ENTROPY_FORMAT"

        parts = input_entropy_hash.split(":", 1)
        if len(parts) != 2:
            return False, "INVALID_ENTROPY_SYNTAX"

        reported_count_str, ts_list_str = parts[0], parts[1]
        if not reported_count_str.isdigit():
            return False, "INVALID_ENTROPY_COUNT"

        reported_count = int(reported_count_str)
        if action_count is not None and reported_count != action_count:
            return False, f"ENTROPY_ACTION_COUNT_MISMATCH (Expected {action_count}, Got {reported_count})"

        # If zero actions were reported, timestamp list must be empty
        if reported_count == 0:
            if ts_list_str.strip():
                return False, "NONZERO_ENTROPY_TIMESTAMPS_FOR_ZERO_ACTIONS"
            return True, "VERIFIED"

        if not ts_list_str.strip():
            # If actions > 0, at least some timestamps must be recorded
            return False, "EMPTY_ENTROPY_TIMESTAMPS"

        try:
            ts_values = [int(t) for t in ts_list_str.split(",") if t.strip()]
        except ValueError:
            return False, "CORRUPTED_ENTROPY_TIMESTAMPS"

        if not ts_values:
            return False, "EMPTY_ENTROPY_TIMESTAMPS"

        # Check monotonic ordering
        for i in range(1, len(ts_values)):
            if ts_values[i] < ts_values[i - 1]:
                return False, "NON_MONOTONIC_ENTROPY_TIMESTAMPS"

        # Check bounds: timestamps must fall between session start (with 5s clock skew buffer) and current time + 5s
        min_allowed = start_time_ms - 5000
        max_allowed = current_time_ms + 5000
        for ts in ts_values:
            if ts < min_allowed or ts > max_allowed:
                return False, "ENTROPY_TIMESTAMP_OUT_OF_BOUNDS"

        # Check statistical variance: detect robotic / synthetic interval scripts (macro bot detection)
        if len(ts_values) >= 5:
            diffs = [ts_values[j] - ts_values[j - 1] for j in range(1, len(ts_values))]
            # If all intervals are perfectly identical, flag synthetic automation
            if len(set(diffs)) == 1 and diffs[0] > 0:
                return False, "SYNTHETIC_INTERVAL_ROBOTIC_ENTROPY"

        return True, "VERIFIED"

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
        """Check whether a session token has already been consumed (Replay Attack Guard).
        Supports sync Redis clients. For async Redis, use async_is_token_replayed.
        """
        if not session_token:
            return True

        if redis_client:
            try:
                key = f"pixora:used_token:{session_token}"
                res = redis_client.exists(key)
                # In case a sync call was made with an object returning int/bool
                return bool(res)
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
    async def async_is_token_replayed(cls, session_token: str, redis_client=None) -> bool:
        """Asynchronously check whether a session token has already been consumed."""
        if not session_token:
            return True

        if redis_client:
            try:
                key = f"pixora:used_token:{session_token}"
                res = redis_client.exists(key)
                if inspect.isawaitable(res):
                    res = await res
                return bool(res)
            except Exception as e:
                logger.warning("Async Redis error checking replayed token: %s", e)

        # In-memory fallback
        with cls._lock:
            now = time.time()
            expired = [t for t, exp in cls._used_tokens_mem.items() if exp < now]
            for t in expired:
                del cls._used_tokens_mem[t]

            return session_token in cls._used_tokens_mem

    @classmethod
    def mark_token_used(cls, session_token: str, ttl: int = 7200, redis_client=None):
        """Mark a session token as consumed (sync)."""
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
    async def async_mark_token_used(cls, session_token: str, ttl: int = 7200, redis_client=None):
        """Mark a session token as consumed (async)."""
        if not session_token:
            return

        if redis_client:
            try:
                key = f"pixora:used_token:{session_token}"
                res = redis_client.set(key, "1", ex=ttl)
                if inspect.isawaitable(res):
                    await res
                return
            except Exception as e:
                logger.warning("Async Redis error marking token used: %s", e)

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

        # 6. Authoritative Input Entropy Validation
        if input_entropy_hash is not None:
            entropy_valid, entropy_reason = cls.verify_input_entropy(
                input_entropy_hash=input_entropy_hash,
                action_count=action_count,
                start_time_ms=start_time_ms,
                current_time_ms=current_time_ms
            )
            if not entropy_valid:
                return False, entropy_reason

        return True, "VERIFIED"

    @classmethod
    async def async_validate_submission(
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
        """Asynchronously validate score submission using async Redis client for replay protection."""
        # 1. Verify cryptographic token authenticity
        expected_token = cls.generate_session_token(player_id, game_slug, start_time_ms)
        if not hmac.compare_digest(expected_token, session_token):
            return False, "INVALID_SESSION_SIGNATURE"

        # 2. Replay attack guard: Ensure session_token can only be used once (async Redis)
        if check_replay and await cls.async_is_token_replayed(session_token, redis_client=redis_client):
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
            if norm_slug == "speedtype" and score > 5 and action_count < score:
                return False, "INSUFFICIENT_KEYSTROKES"

        # 6. Authoritative Input Entropy Validation
        if input_entropy_hash is not None:
            entropy_valid, entropy_reason = cls.verify_input_entropy(
                input_entropy_hash=input_entropy_hash,
                action_count=action_count,
                start_time_ms=start_time_ms,
                current_time_ms=current_time_ms
            )
            if not entropy_valid:
                return False, entropy_reason

        return True, "VERIFIED"

