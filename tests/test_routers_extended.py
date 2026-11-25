"""Tests for router endpoints: admin views, authentication workflows, and hub routes."""
import io
import zipfile

from app.database import db
from app.models import Game, GameplaySession, User


def test_register_page_renders(client):
    """Test that register page loads successfully."""
    response = client.get('/register')
    assert response.status_code == 200
    assert b'PLAYER' in response.data or b'CODENAME' in response.data or b'PIXORA' in response.data


def test_register_empty_fields_fails(client):
    """Test that submitting empty username or password in registration returns 400."""
    response = client.post('/register', data={'username': '', 'password': ''})
    assert response.status_code == 400
    assert b'required' in response.data.lower()


def test_register_new_user_success(client, app):
    """Test registering a brand new user creates account and logs in."""
    response = client.post('/register', data={
        'username': 'NewCadetPilot',
        'password': 'SecureCadetPassword2026!'
    }, follow_redirects=False)
    assert response.status_code == 302
    assert '/games' in response.headers['Location']

    with app.app_context():
        user = User.query.filter_by(username='NewCadetPilot').first()
        assert user is not None
        assert user.is_guest is False
        assert user.check_password('SecureCadetPassword2026!') is True


def test_register_existing_user_with_password_warns(client, app):
    """Test registering an existing user who already has a password flashes warning."""
    with app.app_context():
        u = User(username='ExistingPilot', is_guest=False)
        u.set_password('Pass123456789!')
        db.session.add(u)
        db.session.commit()

    response = client.post('/register', data={
        'username': 'ExistingPilot',
        'password': 'NewPassword1234!'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'already registered' in response.data.lower()


def test_register_upgrade_guest_to_registered(client, app):
    """Test registering an existing guest user upgrades them with password."""
    with app.app_context():
        guest = User(username='GuestToUpgrade', is_guest=True)
        db.session.add(guest)
        db.session.commit()

    response = client.post('/register', data={
        'username': 'GuestToUpgrade',
        'password': 'NewUpgradedPass123!'
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        upgraded = User.query.filter_by(username='GuestToUpgrade').first()
        assert upgraded.is_guest is False
        assert upgraded.check_password('NewUpgradedPass123!') is True


def test_login_empty_username_returns_400(client):
    """Test login with empty username returns 400."""
    resp = client.post('/login', data={'username': ''})
    assert resp.status_code == 400
    assert b'cannot be empty' in resp.data.lower()


def test_login_missing_password_for_protected_account(client, app):
    """Test login without password on password-protected account prompts for password."""
    with app.app_context():
        u = User(username='ProtectedUser', is_guest=False)
        u.set_password('SecretPass123456!')
        db.session.add(u)
        db.session.commit()

    resp = client.post('/login', data={'username': 'ProtectedUser', 'password': ''}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'protected with a password' in resp.data.lower()


def test_admin_login_redirects_if_already_authenticated(admin_client):
    """Test authenticated admin accessing /admin/login is redirected to /admin."""
    resp = admin_client.get('/admin/login', follow_redirects=False)
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']


def test_admin_logout_clears_session(admin_client):
    """Test admin logout terminates admin session and redirects to /admin/login."""
    resp = admin_client.get('/admin/logout', follow_redirects=False)
    assert resp.status_code == 302
    assert '/admin/login' in resp.headers['Location']


def test_admin_player_detail_view(admin_client, app):
    """Test admin can view player details and session history."""
    with app.app_context():
        u = User(username='TrackedPlayer', is_guest=False)
        db.session.add(u)
        db.session.flush()
        sess = GameplaySession(player_id=u.id, game_name='2048')
        db.session.add(sess)
        db.session.commit()

    resp = admin_client.get('/admin/player/TrackedPlayer')
    assert resp.status_code == 200
    assert b'TrackedPlayer' in resp.data
    assert b'2048' in resp.data


def test_admin_player_detail_nonexistent_returns_404(admin_client):
    """Test viewing non-existent player detail returns 404."""
    resp = admin_client.get('/admin/player/NoSuchPlayer')
    assert resp.status_code == 404


def test_admin_player_detail_unauthorized_redirects(client):
    """Test unauthenticated user accessing player detail is redirected."""
    resp = client.get('/admin/player/SomePlayer', follow_redirects=False)
    assert resp.status_code == 302
    assert '/admin/login' in resp.headers['Location']


def test_admin_delete_player(admin_client, app):
    """Test admin can delete player and their sessions."""
    with app.app_context():
        u = User(username='PlayerToDelete', is_guest=False)
        db.session.add(u)
        db.session.commit()

    resp = admin_client.post('/admin/player/PlayerToDelete/delete', follow_redirects=False)
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']

    with app.app_context():
        assert User.query.filter_by(username='PlayerToDelete').first() is None


def test_admin_delete_nonexistent_player_returns_404(admin_client):
    """Test deleting non-existent player returns 404."""
    resp = admin_client.post('/admin/player/NonExistentUser/delete')
    assert resp.status_code == 404


def test_admin_upload_game_validation_missing_fields(admin_client):
    """Test upload game requires title and slug."""
    resp = admin_client.post('/admin/games/upload', data={'title': '', 'slug': ''})
    assert resp.status_code == 400
    assert b'required' in resp.data.lower()


def test_admin_upload_game_validation_existing_slug(admin_client):
    """Test upload game with existing slug rejects."""
    resp = admin_client.post('/admin/games/upload', data={
        'title': 'Duplicate 2048',
        'slug': '2048'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'already exists' in resp.data.lower()


def test_admin_upload_game_missing_zip_and_url(admin_client):
    """Test upload game without zip or direct url warns user."""
    resp = admin_client.post('/admin/games/upload', data={
        'title': 'New Unique Game',
        'slug': 'new-unique-game',
        'category': 'Arcade'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'choose a .zip' in resp.data.lower() or b'direct web game url' in resp.data.lower()


def test_admin_upload_game_with_direct_url(admin_client, app):
    """Test uploading game with direct web URL succeeds and creates Game entry."""
    resp = admin_client.post('/admin/games/upload', data={
        'title': 'Direct URL Game',
        'slug': 'direct-url-game',
        'category': 'Puzzle',
        'description': 'A great web puzzle game.',
        'controls_guide': 'Mouse click',
        'play_url': 'https://example.com/games/direct-puzzle/index.html'
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']

    with app.app_context():
        game = Game.query.filter_by(slug='direct-url-game').first()
        assert game is not None
        assert game.title == 'Direct URL Game'
        assert game.play_url == 'https://example.com/games/direct-puzzle/index.html'


def test_admin_upload_game_with_zip_file(admin_client, app):
    """Test uploading game with a mock zip file extracts and deploys."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('index.html', '<html><body>Game Content</body></html>')
        zf.writestr('game.js', 'console.log("running");')
    zip_buffer.seek(0)

    resp = admin_client.post(
        '/admin/games/upload',
        data={
            'title': 'Packaged Zip Game',
            'slug': 'packaged-zip-game',
            'category': 'Action',
            'description': 'A packaged test game.',
            'controls_guide': 'Arrow keys',
        },
        files={
            'game_zip': ('packaged-game.zip', zip_buffer.getvalue(), 'application/zip')
        },
        follow_redirects=False
    )
    assert resp.status_code == 302

    with app.app_context():
        game = Game.query.filter_by(slug='packaged-zip-game').first()
        assert game is not None
        assert 'packaged-zip-game' in game.play_url


def test_hub_play_nonexistent_game_returns_404(client):
    """Test playing non-existent game returns 404."""
    resp = client.get('/play/completely-unknown-game')
    assert resp.status_code == 404


def test_player_profile_detail_view(admin_client, app):
    """Test admin player detail view for existing player and 404 for missing player."""
    with app.app_context():
        u = User(username='StarPilot', is_guest=False)
        db.session.add(u)
        db.session.commit()

    resp = admin_client.get('/admin/player/StarPilot')
    assert resp.status_code == 200
    assert b'StarPilot' in resp.data

    resp_404 = admin_client.get('/admin/player/GhostPilotNobody')
    assert resp_404.status_code == 404


def test_hub_api_scores_validation(auth_client):
    """Test /api/scores payload validation."""
    # Empty payload
    resp = auth_client.post('/api/scores', json={})
    assert resp.status_code == 400

    # Negative score
    resp = auth_client.post('/api/scores', json={'game_name': '2048', 'score': -50})
    assert resp.status_code == 400

    # Non-integer score
    resp = auth_client.post('/api/scores', json={'game_name': '2048', 'score': 'notanumber'})
    assert resp.status_code == 400

    # Valid score submission
    resp = auth_client.post('/api/scores', json={'game_name': '2048', 'score': 1024})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['status'] == 'success'


def test_hub_api_history_unauthenticated(client):
    """Test /api/history endpoint returns 401 when not authenticated."""
    resp = client.get('/api/history')
    assert resp.status_code == 401


def test_hub_api_history_authenticated(auth_client):
    """Test /api/history endpoint returns player session history."""
    resp = auth_client.get('/api/history')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'history' in data
    assert 'count' in data


def test_hub_start_and_end_game_unauthenticated(client):
    """Test /start_game and /end_game return 401 when unauthenticated."""
    resp_start = client.post('/start_game/2048')
    assert resp_start.status_code == 401

    resp_end = client.post('/end_game/2048')
    assert resp_end.status_code == 401


def test_hub_api_scores_form_data_submission(auth_client):
    """Test /api/scores endpoint accepts multipart/urlencoded form data."""
    resp = auth_client.post('/api/scores', data={'game_name': '2048', 'score': '256'})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['status'] == 'success'


def test_hub_start_and_end_game_authenticated(auth_client):
    """Test /start_game and /end_game endpoints when authenticated."""
    resp = auth_client.post('/start_game/2048')
    assert resp.status_code == 200

    resp = auth_client.post('/end_game/2048')
    assert resp.status_code == 200


def test_hub_presence_endpoint(client):
    """Test /api/v2/presence/<game> returns presence count."""
    resp = client.get('/api/v2/presence/2048')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'presence' in data
    assert data['presence'] >= 0


def test_resolve_game_aliases_and_fallbacks(app):
    """Test resolve_game function with exact, case-insensitive, alias, and none."""
    with app.app_context():
        from app.routers.hub import resolve_game

        # None / empty input
        assert resolve_game("") is None
        assert resolve_game("   ") is None

        # Canonical slug / title
        g = resolve_game("2048")
        assert g is not None
        assert g.slug == "2048"

        # Alias resolution
        g_alias = resolve_game("whack a mole")
        assert g_alias is not None
        assert g_alias.slug == "mole"

        # Unknown game
        assert resolve_game("nonexistent_galaxy_game_xyz") is None


def test_hub_view_filtered_by_game(auth_client):
    """Test hub view with ?game query parameter for filtering."""
    resp = auth_client.get('/games?game=2048')
    assert resp.status_code == 200

    resp_all = auth_client.get('/games?game=all')
    assert resp_all.status_code == 200


def test_profile_endpoint_unauthenticated(client):
    """Test /profile redirects when unauthenticated."""
    resp = client.get('/profile', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_profile_endpoint_authenticated(auth_client):
    """Test /profile renders when authenticated."""
    resp_auth = auth_client.get('/profile')
    assert resp_auth.status_code == 200
    assert b'CyberTester' in resp_auth.data


def test_infrastructure_page(client):
    """Test /infrastructure page renders successfully."""
    resp_infra = client.get('/infrastructure')
    assert resp_infra.status_code == 200


def test_health_check_endpoints(client):
    """Test /health and /api/health endpoints."""
    for path in ('/health', '/api/health'):
        resp = client.get(path)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'healthy'
        assert data['database'] == 'connected'
        assert 'scores_logged' in data


def test_game_definitions_helpers():
    """Test games router helper functions."""
    from app.routers.games import (
        get_all_game_definitions,
        get_game_categories,
        get_game_definition_by_path,
        get_game_definitions_by_slug,
    )
    all_defs = get_all_game_definitions()
    assert len(all_defs) > 0

    g_path = get_game_definition_by_path("/2048")
    assert g_path is not None
    assert g_path.slug == "2048"

    g_slugs = get_game_definitions_by_slug("2048")
    assert len(g_slugs) >= 1

    cats = get_game_categories()
    assert isinstance(cats, dict)
    assert len(cats) > 0
