"""Integration tests for arcade routes, game templates, and admin views."""


def test_root_redirect_unauthenticated(client):
    """Test unauthenticated user visiting / is redirected to /login."""
    response = client.get('/', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_root_redirect_authenticated(auth_client):
    """Test authenticated user visiting / is redirected to /games."""
    response = auth_client.get('/', follow_redirects=False)
    assert response.status_code == 302
    assert '/games' in response.headers['Location']


def test_games_dashboard_renders(auth_client):
    """Test that main arcade hub dashboard renders properly with games."""
    response = auth_client.get('/games')
    assert response.status_code == 200
    assert b'Arcade Hub' in response.data
    assert b'2048' in response.data
    assert b'Flappy Bird' in response.data
    assert b'Whack a Mole' in response.data
    assert b'SpeedType Pro' in response.data


def test_game_templates_render(client):
    """Test that direct game routes render valid HTML."""
    routes_to_test = [
        '/2048',
        '/FlappyBird',
        '/Maze',
        '/mazeeasy',
        '/pong',
        '/memorymatch',
        '/quiz',
        '/stonepapersissors',
        '/tictactoe',
        '/TowerBlock',
        '/tricky',
        '/mole',
        '/Candy_Crush',
        '/speedtype',
        '/speedtypepro'
    ]
    for route in routes_to_test:
        response = client.get(route)
        assert response.status_code == 200, f"Route {route} returned status {response.status_code}"



def test_404_error_page(client):
    """Test custom 404 error page."""
    response = client.get('/non-existent-sector')
    assert response.status_code == 404
    assert b'404' in response.data
    assert b'SECTOR NOT FOUND' in response.data


def test_api_health_endpoint(client):
    """Test /api/health returns healthy JSON status."""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert data['database'] == 'connected'
    assert data['version'] == '1.2.0'


def test_security_response_headers(client):
    """Test security response headers are present on responses."""
    response = client.get('/api/health')
    assert response.headers.get('X-Content-Type-Options') == 'nosniff'
    assert response.headers.get('X-Frame-Options') == 'SAMEORIGIN'


def test_profile_unauthorized(client):
    """Test /profile redirects unauthenticated user to login."""
    response = client.get('/profile')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_profile_authenticated(auth_client):
    """Test /profile renders player username and metrics."""
    response = auth_client.get('/profile')
    assert response.status_code == 200
    assert b'CyberTester' in response.data
    assert b'TOTAL GAMES PLAYED' in response.data


def test_play_game_theater_route(client, app):
    """Test /play/<slug> dynamic theater player loads game."""
    from app.extensions import db
    from app.models import Game

    with app.app_context():
        test_game = Game(
            slug='test-racer',
            title='Test Cyber Racer',
            category='Arcade',
            play_url='https://pub-test.r2.dev/games/test/index.html',
            is_published=True
        )
        db.session.add(test_game)
        db.session.commit()

    response = client.get('/play/test-racer')
    assert response.status_code == 200
    assert b'Test Cyber Racer' in response.data
    assert b'https://pub-test.r2.dev/games/test/index.html' in response.data


def test_admin_upload_game_page(admin_client):
    """Test that admin upload game page loads properly for authorized admin."""
    response = admin_client.get('/admin/games/upload')
    assert response.status_code == 200
    assert b'Deploy Game' in response.data


def test_admin_dashboard_unauthorized(client):
    """Test that unauthorized user visiting /admin is redirected to separate /admin/login."""
    response = client.get('/admin', follow_redirects=False)
    assert response.status_code == 302
    assert '/admin/login' in response.headers['Location']


def test_admin_dashboard_authorized(admin_client):
    """Test that authenticated admin sees catalog, leaderboards, and analytics."""
    response = admin_client.get('/admin')
    assert response.status_code == 200
    assert b'ADMIN CORE' in response.data
    assert b'CATALOG & CLOUDFLARE R2 EDGE ASSETS' in response.data
    assert b'VERIFIED HIGH SCORES LEADERBOARD' in response.data
    assert b'POPULARITY TELEMETRY' in response.data


def test_admin_separate_login_flow(client):
    """Test separate login flow for admin only."""
    # GET dedicated admin login page
    get_resp = client.get('/admin/login')
    assert get_resp.status_code == 200
    assert b'ADMIN CORE' in get_resp.data

    # POST invalid credentials
    fail_resp = client.post('/admin/login', data={
        'username': 'fake_admin',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    assert fail_resp.status_code == 200
    assert b'Invalid administrator credentials' in fail_resp.data

    # POST valid master credentials
    login_resp = client.post('/admin/login', data={
        'username': 'admin',
        'password': 'admin123'
    }, follow_redirects=False)
    assert login_resp.status_code == 302
    assert '/admin' in login_resp.headers['Location']


def test_user_screens_have_logout_action(auth_client):
    """Verify that user screens have a convenient logout action for players."""
    # Hub screen
    resp_games = auth_client.get('/games')
    assert resp_games.status_code == 200
    assert b'href="/logout"' in resp_games.data
    assert b'Logout' in resp_games.data

    # Leaderboard screen
    resp_lb = auth_client.get('/leaderboard')
    assert resp_lb.status_code == 200
    assert b'href="/logout"' in resp_lb.data

    # Infrastructure screen
    resp_infra = auth_client.get('/infrastructure')
    assert resp_infra.status_code == 200
    assert b'href="/logout"' in resp_infra.data


def test_admin_delete_game(admin_client, app):
    """Test that admin can remove games from catalog."""
    from app.extensions import db
    from app.models import Game

    with app.app_context():
        g = Game(
            slug='disposable-game',
            title='Disposable Game',
            category='Arcade',
            play_url='/play/disposable-game',
            is_published=True
        )
        db.session.add(g)
        db.session.commit()

    del_resp = admin_client.post('/admin/games/disposable-game/delete', follow_redirects=True)
    assert del_resp.status_code == 200
    assert b"Disposable Game" in del_resp.data
    assert b"removed from platform" in del_resp.data

    with app.app_context():
        assert Game.query.filter_by(slug='disposable-game').first() is None



