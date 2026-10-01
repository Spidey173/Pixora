"""Integration tests for authentication, login, registration, and logout."""
from app.models import User


def test_login_page_renders(client):
    """Test that login page loads successfully."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'PLAYER ACCESS' in response.data
    assert b'PIXORA' in response.data or b'GLITCH4CE' in response.data


def test_guest_login_auto_registers(client, app):
    """Test that entering a codename without password logs in as guest."""
    response = client.post('/login', data={'username': 'GuestPilot'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'Arcade Hub' in response.data

    with app.app_context():
        user = User.query.filter_by(username='GuestPilot').first()
        assert user is not None
        assert user.is_guest is True
        assert user.password_hash is None


def test_registered_user_login_success(client, test_user):
    """Test successful login with registered credentials."""
    response = client.post('/login', data={
        'username': 'CyberTester',
        'password': 'SecretPass123!'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Arcade Hub' in response.data
    assert b'CyberTester' in response.data


def test_registered_user_login_wrong_password(client, test_user):
    """Test that invalid password fails authentication."""
    response = client.post('/login', data={
        'username': 'CyberTester',
        'password': 'IncorrectPassword'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid passcode' in response.data


def test_logout(auth_client):
    """Test that logout terminates session and redirects to login."""
    response = auth_client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b'PLAYER ACCESS' in response.data

    # Attempt to access protected /games
    protected_resp = auth_client.get('/games', follow_redirects=False)
    assert protected_resp.status_code == 302
    assert '/login' in protected_resp.headers['Location']
