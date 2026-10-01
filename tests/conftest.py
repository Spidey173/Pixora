"""Pytest test fixtures and setup for Pixora."""
import pytest

from app import create_app
from app.extensions import db
from app.models import User


@pytest.fixture
def app():
    """Create test application configured for testing."""
    test_app = create_app('testing')

    with test_app.app_context():
        db.create_all()
        from app.models import Game
        from app.utils.seed_games import CATALOG_GAMES
        for item in CATALOG_GAMES:
            game = Game(
                slug=item['slug'],
                title=item['title'],
                category=item['category'],
                description=item['description'],
                thumbnail_url=item['thumbnail_url'],
                play_url=item['play_url'],
                controls_guide=item['controls_guide'],
                is_featured=item.get('is_featured', False),
                is_published=True
            )
            db.session.add(game)
        db.session.commit()

        from app.utils.telemetry_queue import telemetry_queue
        telemetry_queue.reset()

        yield test_app
        telemetry_queue.reset()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test HTTP client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def test_user(app):
    """Create a sample registered user in test db."""
    with app.app_context():
        user = User(username='CyberTester', is_guest=False)
        user.set_password('SecretPass123!')
        db.session.add(user)
        db.session.commit()
        return db.session.get(User, user.id)


@pytest.fixture
def auth_client(client, test_user):
    """Test HTTP client logged in as test_user."""
    client.post('/login', data={
        'username': 'CyberTester',
        'password': 'SecretPass123!'
    }, follow_redirects=True)
    return client


@pytest.fixture
def admin_client(client):
    """Test HTTP client authenticated into the separate admin console."""
    with client.session_transaction() as sess:
        sess['is_admin_authenticated'] = True
        sess['admin_user'] = 'admin'
    return client

