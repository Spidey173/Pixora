"""Centralized Redis key prefix helpers for Pixora.

All Redis keys across gateway, worker, telemetry queue, anti-cheat, and seeding
must be built through this module so changing REDIS_KEY_PREFIX consistently
updates both write and read paths.
"""
import os
from typing import Optional

from app.config import settings

_DEFAULT_PREFIX = "pixora:"
_DEFAULT_STREAM = "pixora:telemetry"
_DEFAULT_DLQ = "pixora:telemetry:dlq"


def get_redis_key_prefix(testing: Optional[bool] = None) -> str:
    """Return normalized Redis key prefix (always ending with ':')."""
    raw = os.environ.get("REDIS_KEY_PREFIX")
    if raw is None:
        raw = getattr(settings, "REDIS_KEY_PREFIX", _DEFAULT_PREFIX)
    base = (raw or _DEFAULT_PREFIX).strip().rstrip(":")
    if not base:
        base = "pixora"
    if testing is None:
        testing = os.environ.get("FLASK_ENV", "").lower() == "testing"
    return f"{base}:test:" if testing else f"{base}:"


def redis_key(name: str, testing: Optional[bool] = None) -> str:
    """Build a prefixed Redis key from a logical key name."""
    prefix = get_redis_key_prefix(testing=testing)
    clean_name = name.lstrip(":")
    return f"{prefix}{clean_name}"


def get_stream_key(testing: Optional[bool] = None) -> str:
    """Return the Redis telemetry stream key, respecting REDIS_KEY_PREFIX."""
    explicit = os.environ.get("TELEMETRY_STREAM_KEY", "").strip()
    if explicit and explicit != _DEFAULT_STREAM:
        return explicit
    return redis_key("telemetry", testing=testing)


def get_dlq_key(testing: Optional[bool] = None) -> str:
    """Return the Redis telemetry dead-letter queue key, respecting REDIS_KEY_PREFIX."""
    explicit = os.environ.get("TELEMETRY_DLQ_KEY", "").strip()
    if explicit and explicit != _DEFAULT_DLQ:
        return explicit
    return redis_key("telemetry:dlq", testing=testing)


def get_stream_group_name() -> str:
    """Return the Redis Stream consumer group name."""
    return os.environ.get("TELEMETRY_GROUP_NAME", "pixora_telemetry_group").strip() or "pixora_telemetry_group"

