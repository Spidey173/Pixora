"""Application configuration classes for Pixora."""
import os
from datetime import timedelta
from typing import ClassVar

from dotenv import load_dotenv

# Load environment variables from .env if present
basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    """Base configuration."""
    APP_NAME = 'Pixora'
    APP_VERSION = '2.0.0'
    SECRET_KEY = os.environ.get('SECRET_KEY', 'pixora-fallback-dev-secret-key-replace-in-prod')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max payload size
    
    # Database (On Vercel serverless, root filesystem is read-only, writable dir is /tmp/instance)
    if os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
        _default_db_dir = '/tmp/instance'
        os.makedirs(_default_db_dir, exist_ok=True)
    else:
        _default_db_dir = basedir
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(_default_db_dir, 'game_data.db')}"
    )
    # Fix Render's postgres:// prefix to postgresql:// if needed
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
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '200/hour')
    RATELIMIT_AUTH = os.environ.get('RATELIMIT_AUTH', '20/minute')

    # WTForms / CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

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
    # Background worker threads are not supported in serverless lambdas (Vercel)
    _is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
    TELEMETRY_QUEUE_ENABLED = os.environ.get('TELEMETRY_QUEUE_ENABLED', 'False' if _is_serverless else 'True').lower() in ('true', '1')
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

