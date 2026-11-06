"""Integration tests for telemetry and history JSON API endpoints."""
from app.models import GameplaySession


def test_api_history_unauthorized(client):
    """Test /api/history returns 401 when unauthenticated."""
    response = client.get('/api/history')
    assert response.status_code == 401
    data = response.get_json()
    assert data['error'] == 'unauthorized'


def test_api_history_authenticated_empty(auth_client):
    """Test /api/history returns empty list for new user."""
    response = auth_client.get('/api/history')
    assert response.status_code == 200
    data = response.get_json()
    assert data['username'] == 'CyberTester'
    assert data['count'] == 0
    assert data['history'] == []


def test_start_game_and_history(auth_client, app):
    """Test /start_game logs session and updates /api/history."""
    # Launch 2048
    start_resp = auth_client.post('/start_game/2048')
    assert start_resp.status_code == 200
    start_data = start_resp.get_json()
    assert start_data['status'] == 'logged'
    assert start_data['game'] == '2048'

    # Launch Flappy Bird
    start_resp2 = auth_client.post('/start_game/Flappy Bird')
    assert start_resp2.status_code == 200

    # Verify history
    hist_resp = auth_client.get('/api/history')
    assert hist_resp.status_code == 200
    hist_data = hist_resp.get_json()
    assert hist_data['count'] == 2
    assert len(hist_data['history']) == 2
    assert hist_data['history'][0]['game_name'] == 'Flappy Bird'
    assert hist_data['history'][1]['game_name'] == '2048'


def test_end_game_tracking(auth_client, app):
    """Test /end_game calculates session duration properly."""
    # Start game
    auth_client.post('/start_game/Maze')

    # End game
    end_resp = auth_client.post('/end_game/Maze')
    assert end_resp.status_code == 200
    end_data = end_resp.get_json()
    assert end_data['status'] == 'ended'
    assert end_data['game'] == 'Maze'

    with app.app_context():
        session = GameplaySession.query.filter_by(game_name='Maze').first()
        assert session is not None
        assert session.ended_at is not None


def test_submit_score_unauthorized(client):
    """Test /api/score/submit returns 401 when unauthenticated."""
    response = client.post('/api/score/submit', json={'game_name': '2048', 'score': 100})
    assert response.status_code == 401


def test_submit_score_valid_and_leaderboard(auth_client):
    """Test posting valid scores and getting sorted leaderboard."""
    # Submit score 1500 for 2048
    resp1 = auth_client.post('/api/score/submit', json={'game_name': '2048', 'score': 1500})
    assert resp1.status_code == 201
    data1 = resp1.get_json()
    assert data1['status'] == 'success'
    assert data1['score']['score'] == 1500

    # Submit score 3200 for 2048
    resp2 = auth_client.post('/api/score/submit', json={'game_name': '2048', 'score': 3200})
    assert resp2.status_code == 201

    # Check leaderboard — same player appears ONCE with their best score
    lb_resp = auth_client.get('/api/leaderboard/2048')
    assert lb_resp.status_code == 200
    lb_data = lb_resp.get_json()
    assert lb_data['game_name'] == '2048'
    assert len(lb_data['leaderboard']) == 1  # One unique player
    assert lb_data['leaderboard'][0]['score'] == 3200  # Best score kept


def test_submit_score_invalid_payload(auth_client):
    """Test submitting negative or invalid score returns 400."""
    resp_neg = auth_client.post('/api/score/submit', json={'game_name': '2048', 'score': -50})
    assert resp_neg.status_code == 400

    resp_str = auth_client.post('/api/score/submit', json={'game_name': '2048', 'score': 'abc'})
    assert resp_str.status_code == 400

    resp_missing = auth_client.post('/api/score/submit', json={'score': 100})
    assert resp_missing.status_code == 400

