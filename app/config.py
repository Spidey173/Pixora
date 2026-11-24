"""Application configuration classes for Pixora."""
import os
from datetime import timedelta
from typing import ClassVar, Optional

from dotenv import load_dotenv

# Load environment variables from .env if present
basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(basedir, '.env'))


class ConfigurationError(ValueError):
    """Raised when critical configuration or secrets are missing or invalid."""
    pass


PLACEHOLDER_MARKERS = (
    "CHANGE_ME",
    "CHANGE_THIS",
    "REPLACE_ME",
    "YOUR_SECRET",
    "GENERATE_A_SECURE",
    "PIXORA-FALLBACK-DEV-SECRET-KEY-REPLACE-IN-PROD",
)


def is_placeholder(val: Optional[str]) -> bool:
    """Check if a secret value is empty or matches known placeholder patterns."""
    if not val or not str(val).strip():
        return True
    val_upper = str(val).strip().upper()
    return any(marker in val_upper for marker in PLACEHOLDER_MARKERS)


def validate_secrets(config) -> None:
    """Validate that required secrets are present and not left as placeholders.

    Fails fast at startup with a clear ConfigurationError if required secrets
    (SECRET_KEY, DB URL, R2 credentials if storage is enabled) are missing
    or still set to placeholders.
    """
    if isinstance(config, dict):
        is_testing = config.get("TESTING", False) or os.environ.get("FLASK_ENV") == "testing"
    else:
        is_testing = getattr(config, "TESTING", False) or os.environ.get("FLASK_ENV") == "testing"

    def get_val(key: str) -> Optional[str]:
        if isinstance(config, dict):
            return config.get(key)
        val = getattr(config, key, None)
        return val if val is not None else os.environ.get(key)

    errors = []

    # 1. SECRET_KEY
    secret_key = get_val("SECRET_KEY")
    if is_testing:
        if not secret_key:
            errors.append("SECRET_KEY is missing.")
    else:
        if is_placeholder(secret_key):
            errors.append("SECRET_KEY is missing or set to a placeholder.")

    # 2. Database URL
    db_uri = get_val("SQLALCHEMY_DATABASE_URI") or get_val("DATABASE_URL")
    if is_placeholder(db_uri):
        errors.append("Database URL (DATABASE_URL / SQLALCHEMY_DATABASE_URI) is missing or set to a placeholder.")

    # 3. R2 Credentials (if storage is enabled)
    r2_enabled = get_val("CLOUDFLARE_R2_ENABLED")
    if isinstance(r2_enabled, str):
        r2_enabled = r2_enabled.lower() in ("true", "1")
    elif not isinstance(r2_enabled, bool):
        r2_enabled = bool(r2_enabled)

    if r2_enabled and not is_testing:
        r2_key_id = get_val("CLOUDFLARE_R2_ACCESS_KEY_ID")
        r2_secret = get_val("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
        r2_endpoint = get_val("CLOUDFLARE_R2_ENDPOINT_URL")

        if is_placeholder(r2_key_id):
            errors.append("CLOUDFLARE_R2_ACCESS_KEY_ID is missing or set to a placeholder while storage is enabled.")
        if is_placeholder(r2_secret):
            errors.append("CLOUDFLARE_R2_SECRET_ACCESS_KEY is missing or set to a placeholder while storage is enabled.")
        if is_placeholder(r2_endpoint):
            errors.append("CLOUDFLARE_R2_ENDPOINT_URL is missing or set to a placeholder while storage is enabled.")

    if errors:
        error_msg = "Startup configuration validation failed:\n  - " + "\n  - ".join(errors)
        raise ConfigurationError(error_msg)


class Config:
    """Base configuration."""
    APP_NAME = 'Pixora'
    APP_VERSION = '2.0.0'
    SECRET_KEY = os.environ.get('SECRET_KEY', '')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max payload size
    
    # Database
    _default_db_dir = basedir
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(_default_db_dir, 'game_data.db')}"
    )
    # Fix Render/VPS postgres:// prefix to postgresql:// if needed
    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS: ClassVar[dict] = {
        "pool_pre_ping": True,
    }

    # Session & Security
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1')
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    SECURITY_PASSWORD_SALT = os.environ.get('SECURITY_PASSWORD_SALT', 'pixora-password-salt')

    # Rate Limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_SWALLOW_ERRORS = True
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '200/hour')
    RATELIMIT_AUTH = os.environ.get('RATELIMIT_AUTH', '20/minute')

    # WTForms / CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Anti-Cheat & Proof-of-Gameplay
    ANTI_CHEAT_ENABLED = os.environ.get('ANTI_CHEAT_ENABLED', 'True').lower() in ('true', '1')
    ANTI_CHEAT_TOKEN_TTL = int(os.environ.get('ANTI_CHEAT_TOKEN_TTL', '3600'))  # 1 hour validity

    # Cloudflare R2 Edge Storage
    CLOUDFLARE_R2_ENABLED = os.environ.get('CLOUDFLARE_R2_ENABLED', 'True').lower() in ('true', '1')
    CLOUDFLARE_R2_ACCOUNT_ID = os.environ.get('CLOUDFLARE_R2_ACCOUNT_ID', '')
    CLOUDFLARE_R2_ACCESS_KEY_ID = os.environ.get('CLOUDFLARE_R2_ACCESS_KEY_ID', '')
    CLOUDFLARE_R2_SECRET_ACCESS_KEY = os.environ.get('CLOUDFLARE_R2_SECRET_ACCESS_KEY', '')
    CLOUDFLARE_R2_BUCKET_NAME = os.environ.get('CLOUDFLARE_R2_BUCKET_NAME', 'glitch4ce-games')
    CLOUDFLARE_R2_ENDPOINT_URL = os.environ.get('CLOUDFLARE_R2_ENDPOINT_URL', '')
    CLOUDFLARE_R2_PUBLIC_URL = os.environ.get('CLOUDFLARE_R2_PUBLIC_URL', 'https://pub-bbadfb1090074e17b2f5293b549ce094.r2.dev')

    # Redis & Asynchronous High-Throughput Telemetry Queue
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
    TELEMETRY_QUEUE_ENABLED = os.environ.get('TELEMETRY_QUEUE_ENABLED', 'True').lower() in ('true', '1')
    TELEMETRY_BATCH_SIZE = int(os.environ.get('TELEMETRY_BATCH_SIZE', '25'))
    TELEMETRY_FLUSH_INTERVAL = float(os.environ.get('TELEMETRY_FLUSH_INTERVAL', '0.5'))  # seconds


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration with in-memory SQLite and disabled CSRF."""
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SECRET_KEY = 'test-secret-key'
    TELEMETRY_FLUSH_INTERVAL = 0.01


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}

# Settings alias for clean modular imports (e.g. from app.config import settings)
env_mode = os.environ.get('FLASK_ENV', os.environ.get('ENV', 'development')).lower()
settings = config_by_name.get(env_mode, DevelopmentConfig)


