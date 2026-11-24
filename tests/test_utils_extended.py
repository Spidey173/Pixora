"""Tests for utility modules: seeding, data migration, and bundle downloading."""
import sqlite3

from app.models import Game, GameplaySession, User
from app.utils.bundle_packager import _clean_and_transform_html, _generate_embedded_sdk_script
from app.utils.download_bundles import download_bundle_if_missing
from app.utils.migrate_data import migrate_legacy_data
from app.utils.seed_games import seed_catalog


def test_seed_catalog_populates_games(app):
    """Test seed_catalog populates catalog games idempotently."""
    with app.app_context():
        seed_catalog()
        count = Game.query.count()
        assert count >= 17

        # Second call does not duplicate
        seed_catalog()
        assert Game.query.count() == count


def test_migrate_legacy_data(app, tmp_path):
    """Test migrating SQLite database records into SQLAlchemy models."""
    legacy_db_file = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(legacy_db_file))
    cur = conn.cursor()
    cur.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, username TEXT)")
    cur.execute("CREATE TABLE gameplay (id INTEGER PRIMARY KEY, player_id INTEGER, game_name TEXT, timestamp TEXT)")
    cur.execute("INSERT INTO players (id, username) VALUES (1, 'LegacyRetroPilot')")
    cur.execute("INSERT INTO gameplay (id, player_id, game_name, timestamp) VALUES (1, 1, '2048', '2026-01-01 12:00:00')")
    conn.commit()
    conn.close()

    with app.app_context():
        migrate_legacy_data(str(legacy_db_file))
        migrated_user = User.query.filter_by(username='LegacyRetroPilot').first()
        assert migrated_user is not None
        assert migrated_user.is_guest is True

        migrated_session = GameplaySession.query.filter_by(player_id=migrated_user.id).first()
        assert migrated_session is not None
        assert migrated_session.game_name == '2048'


def test_migrate_legacy_data_handles_missing_file():
    """Test migrate_legacy_data skips cleanly if file doesn't exist."""
    # Should not raise exception
    migrate_legacy_data("/nonexistent/path/db.sqlite")


def test_bundle_packager_sdk_injection():
    """Test bundle packager creates SDK injection snippet and transforms HTML."""
    sdk_script = _generate_embedded_sdk_script(slug="test-slug", title="Test Title")
    assert "PIXORA_GAME_CLIENT" in sdk_script
    assert "test-slug" in sdk_script

    html_in = "<html><head><title>Game</title></head><body><h1>Play</h1></body></html>"
    html_out = _clean_and_transform_html(html_in, slug="test-slug", title="Test Title")
    assert "PIXORA_GAME_CLIENT" in html_out
    assert "Play" in html_out


def test_download_bundle_already_cached(tmp_path, monkeypatch):
    """Test download_bundle_if_missing recognizes existing local bundle."""
    from app.utils import download_bundles
    monkeypatch.setattr(download_bundles, "base_dir", str(tmp_path))

    game_dir = tmp_path / "public" / "games" / "test-game"
    game_dir.mkdir(parents=True)
    index_file = game_dir / "index.html"
    index_file.write_text("<html>Cached Game</html>")

    result = download_bundle_if_missing("test-game")
    assert result is True
