"""Pytest test fixtures and setup for Pixora (Unified FastAPI Architecture)."""
import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.auth_deps import create_session_cookie, decode_session_cookie
from app.extensions import db
from app.models import User


class ResponseWrapper:
    """Wrapper around httpx.Response for Flask test client API compatibility."""
    def __init__(self, raw):
        self._raw = raw

    @property
    def status_code(self):
        return self._raw.status_code

    @property
    def data(self):
        return self._raw.content

    @property
    def headers(self):
        return self._raw.headers

    def get_json(self, silent=False):
        try:
            return self._raw.json()
        except Exception:
            if silent:
                return None
            raise

    def __getattr__(self, name):
        return getattr(self._raw, name)


class SessionTransaction:
    """Context manager for modifying test client session cookies."""
    def __init__(self, client):
        self.client = client
        self.session_data = {}

    def __enter__(self):
        cookie = self.client.cookies.get("session")
        if cookie:
            self.session_data = decode_session_cookie(cookie) or {}
        else:
            self.session_data = {}
        return self.session_data

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session_data:
            cookie_str = create_session_cookie(self.session_data)
            self.client.cookies.set("session", cookie_str)
        else:
            if "session" in self.client.cookies:
                del self.client.cookies["session"]


class TestClientWrapper(TestClient):
    """FastAPI TestClient with compatibility helpers for existing test suites."""
    def __init__(self, app, **kwargs):
        if 'follow_redirects' not in kwargs:
            kwargs['follow_redirects'] = False
        super().__init__(app, **kwargs)
        self.application = app

    def request(self, *args, **kwargs):
        if 'follow_redirects' not in kwargs:
            kwargs['follow_redirects'] = False
        raw = super().request(*args, **kwargs)
        return ResponseWrapper(raw)

    def session_transaction(self):
        return SessionTransaction(self)


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
        try:
            db.session.rollback()
        except Exception:
            pass
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test HTTP client."""
    return TestClientWrapper(app)


@pytest.fixture
def runner(app):
    """Test CLI runner placeholder."""
    return None


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
