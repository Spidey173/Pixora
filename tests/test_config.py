"""Unit tests for configuration validation, fail-fast checks, and secrets hygiene."""
import pytest

from app.config import ConfigurationError, validate_secrets


def test_validate_secrets_fails_missing_secret_key(monkeypatch):
    """Test startup fails when SECRET_KEY is missing or empty."""
    monkeypatch.delenv("FLASK_ENV", raising=False)
    cfg = {
        "TESTING": False,
        "SECRET_KEY": "",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///game_data.db",
        "CLOUDFLARE_R2_ENABLED": False,
    }
    with pytest.raises(ConfigurationError, match="SECRET_KEY is missing or set to a placeholder"):
        validate_secrets(cfg)


def test_validate_secrets_fails_placeholder_secret_key(monkeypatch):
    """Test startup fails when SECRET_KEY contains placeholder text."""
    monkeypatch.delenv("FLASK_ENV", raising=False)
    cfg = {
        "TESTING": False,
        "SECRET_KEY": "CHANGE_ME_NOW",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///game_data.db",
        "CLOUDFLARE_R2_ENABLED": False,
    }
    with pytest.raises(ConfigurationError, match="SECRET_KEY is missing or set to a placeholder"):
        validate_secrets(cfg)


def test_validate_secrets_fails_missing_or_placeholder_db_url(monkeypatch):
    """Test startup fails when database URL is missing or set to placeholder."""
    monkeypatch.delenv("FLASK_ENV", raising=False)
    cfg_empty = {
        "TESTING": False,
        "SECRET_KEY": "super-secure-production-secret-key-123",
        "SQLALCHEMY_DATABASE_URI": "",
        "CLOUDFLARE_R2_ENABLED": False,
    }
    with pytest.raises(ConfigurationError, match="Database URL"):
        validate_secrets(cfg_empty)

    cfg_placeholder = {
        "TESTING": False,
        "SECRET_KEY": "super-secure-production-secret-key-123",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///CHANGE_ME.db",
        "CLOUDFLARE_R2_ENABLED": False,
    }
    with pytest.raises(ConfigurationError, match="Database URL"):
        validate_secrets(cfg_placeholder)


def test_validate_secrets_fails_r2_enabled_missing_credentials(monkeypatch):
    """Test startup fails when R2 storage is enabled but credentials are missing."""
    monkeypatch.delenv("FLASK_ENV", raising=False)
    cfg = {
        "TESTING": False,
        "SECRET_KEY": "super-secure-production-secret-key-123",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///game_data.db",
        "CLOUDFLARE_R2_ENABLED": True,
        "CLOUDFLARE_R2_ACCESS_KEY_ID": "",
        "CLOUDFLARE_R2_SECRET_ACCESS_KEY": "",
        "CLOUDFLARE_R2_ENDPOINT_URL": "",
    }
    with pytest.raises(ConfigurationError, match="CLOUDFLARE_R2_ACCESS_KEY_ID is missing"):
        validate_secrets(cfg)


def test_validate_secrets_fails_r2_enabled_placeholder_credentials(monkeypatch):
    """Test startup fails when R2 storage credentials contain placeholders."""
    monkeypatch.delenv("FLASK_ENV", raising=False)
    cfg = {
        "TESTING": False,
        "SECRET_KEY": "super-secure-production-secret-key-123",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///game_data.db",
        "CLOUDFLARE_R2_ENABLED": True,
        "CLOUDFLARE_R2_ACCESS_KEY_ID": "CHANGE_ME",
        "CLOUDFLARE_R2_SECRET_ACCESS_KEY": "CHANGE_ME",
        "CLOUDFLARE_R2_ENDPOINT_URL": "https://CHANGE_ME.r2.cloudflarestorage.com",
    }
    with pytest.raises(ConfigurationError) as exc_info:
        validate_secrets(cfg)
    err_str = str(exc_info.value)
    assert "CLOUDFLARE_R2_ACCESS_KEY_ID" in err_str
    assert "CLOUDFLARE_R2_SECRET_ACCESS_KEY" in err_str
    assert "CLOUDFLARE_R2_ENDPOINT_URL" in err_str


def test_validate_secrets_success_with_valid_config(monkeypatch):
    """Test validation succeeds when valid production secrets are supplied."""
    monkeypatch.delenv("FLASK_ENV", raising=False)
    cfg = {
        "TESTING": False,
        "SECRET_KEY": "a-genuinely-random-and-secure-secret-key-value",
        "SQLALCHEMY_DATABASE_URI": "postgresql://pixora:realpass@localhost:5432/pixora",
        "CLOUDFLARE_R2_ENABLED": True,
        "CLOUDFLARE_R2_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
        "CLOUDFLARE_R2_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "CLOUDFLARE_R2_ENDPOINT_URL": "https://accountid.r2.cloudflarestorage.com",
    }
    # Should not raise
    validate_secrets(cfg)


def test_validate_secrets_testing_mode_allows_test_secrets():
    """Test testing mode permits testing secrets and disabled R2."""
    cfg = {
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "CLOUDFLARE_R2_ENABLED": False,
    }
    validate_secrets(cfg)


def test_serverless_sqlite_tmp_fallback(monkeypatch):
    """Test that serverless execution on Vercel falls back to /tmp/game_data.db."""
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app.config import get_default_database_uri
    assert "/tmp/game_data.db" in get_default_database_uri()


def test_database_proxy_rollback_and_remove():
    """Test DatabaseProxy rollback and remove helper methods."""
    from app.extensions import db
    # Should execute without error
    db.rollback()
    db.remove()


