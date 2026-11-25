"""Tests for scripts/reset_data.py and empty-database rendering."""
from app.extensions import db
from app.models import Game, GameplaySession, GameScore, User
from scripts.reset_data import run_reset


def _seed_sample_data():
    GameScore.query.delete()
    GameplaySession.query.delete()
    User.query.delete()
    admin = User(username="admin", password_hash="hash")
    pilot = User(username="VortexAce", password_hash="hash")
    db.session.add_all([admin, pilot])
    db.session.flush()
    db.session.add(GameScore(player_id=pilot.id, game_name="2048", score=2048))
    db.session.add(GameplaySession(player_id=pilot.id, game_name="2048", duration_seconds=60))
    db.session.commit()
    return Game.query.count()


def test_reset_dry_run_deletes_nothing(app, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    with app.app_context():
        game_count = _seed_sample_data()
        rc = run_reset(confirm=False)
        assert rc == 0
        assert GameScore.query.count() == 1
        assert GameplaySession.query.count() == 1
        assert User.query.count() == 2
        assert Game.query.count() == game_count


def test_reset_wrong_host_aborts(app, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    with app.app_context():
        _seed_sample_data()
        rc = run_reset(confirm=True, input_fn=lambda _: "wrong-host")
        assert rc == 1
        assert GameScore.query.count() == 1
        assert User.query.count() == 2


def test_reset_confirmed_deletes_non_admin_and_keeps_games_and_admin(app, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    with app.app_context():
        game_count = _seed_sample_data()
        rc = run_reset(confirm=True, input_fn=lambda _: "sqlite")
        assert rc == 0
        assert GameScore.query.count() == 0
        assert GameplaySession.query.count() == 0
        assert User.query.count() == 1
        assert User.query.first().username == "admin"
        assert Game.query.count() == game_count


def test_empty_database_routes_render_cleanly(client, app):
    with app.app_context():
        GameScore.query.delete()
        GameplaySession.query.delete()
        db.session.commit()

    for path in ("/leaderboard", "/api/leaderboard/2048", "/play/2048"):
        resp = client.get(path, follow_redirects=True)
        assert resp.status_code == 200
