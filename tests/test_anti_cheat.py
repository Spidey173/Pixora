"""Security and concurrency test suite for Anti-Cheat & Proof-of-Gameplay engine."""
import concurrent.futures
import time
from app.services.anti_cheat import AntiCheatValidator
from app.utils.telemetry_queue import telemetry_queue


def test_anti_cheat_validator_token_generation_and_validation(app):
    """Test generating cryptographic tokens and validating them."""
    with app.app_context():
        player_id = 42
        game_slug = "flappybird"
        now_ms = int(time.time() * 1000) - 10000  # 10 seconds ago

        token = AntiCheatValidator.generate_session_token(player_id, game_slug, now_ms)
        assert token is not None
        assert len(token) == 64  # SHA256 hex string

        # Valid score: 10 points in 10 seconds (1.0 points/sec, max 2.5)
        is_valid, reason = AntiCheatValidator.validate_submission(
            player_id=player_id,
            game_slug=game_slug,
            score=10,
            start_time_ms=now_ms,
            session_token=token,
            check_replay=False
        )
        assert is_valid is True
        assert reason == "VERIFIED"


def test_api_v2_session_start_unauthorized(client):
    """Test /api/v2/session/start returns 401 when user is not logged in."""
    res = client.post('/api/v2/session/start', json={'game_slug': 'flappybird'})
    assert res.status_code == 401
    data = res.get_json()
    assert data['code'] == 'UNAUTHORIZED'


def test_api_v2_session_start_authenticated(auth_client):
    """Test /api/v2/session/start returns a cryptographic token and metadata."""
    res = auth_client.post('/api/v2/session/start', json={'game_slug': 'flappybird'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'success'
    assert 'session_token' in data
    assert 'start_time_ms' in data
    assert data['game_slug'] == 'flappybird'
    assert data['username'] == 'CyberTester'


def test_api_v2_session_end_valid(auth_client):
    """Test end session with valid gameplay score submission."""
    # Start session 15 seconds in the past to allow realistic gameplay
    now_ms = int(time.time() * 1000) - 15000
    with auth_client.application.app_context():
        # Create token for player
        token = AntiCheatValidator.generate_session_token(1, 'flappybird', now_ms)

    res = auth_client.post('/api/v2/session/end', json={
        'game_slug': 'flappybird',
        'score': 20,
        'session_token': token,
        'start_time_ms': now_ms,
        'action_count': 25
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data['status'] == 'success'
    assert data['verified'] is True
    assert data['score']['score'] == 20

    # Verify score is reflected in leaderboard
    lb_res = auth_client.get('/api/leaderboard/flappybird')
    assert lb_res.status_code == 200
    lb_data = lb_res.get_json()
    assert len(lb_data['leaderboard']) >= 1
    assert lb_data['leaderboard'][0]['score'] == 20


def test_impossible_score_anomalous_velocity(auth_client):
    """Test that submitting an impossible score (10,000 score in 2 seconds) returns HTTP 422 with ANOMALOUS_VELOCITY."""
    start_ms = int(time.time() * 1000) - 2000  # 2 seconds ago
    with auth_client.application.app_context():
        token = AntiCheatValidator.generate_session_token(1, 'flappybird', start_ms)

    # Submitting 10,000 pipes in 2 seconds is physically impossible (rate 5000/s > max 2.5/s)
    res = auth_client.post('/api/v2/session/end', json={
        'game_slug': 'flappybird',
        'score': 10000,
        'session_token': token,
        'start_time_ms': start_ms,
        'action_count': 10000
    })
    assert res.status_code == 422
    data = res.get_json()
    assert data['code'] == 'ANOMALOUS_VELOCITY'
    assert 'SCORE_VELOCITY_EXCEEDED' in data['error']


def test_impossible_duration_rejection(auth_client):
    """Test that score > 10 in < 2.0s returns HTTP 422 with ANOMALOUS_VELOCITY."""
    start_ms = int(time.time() * 1000) - 500  # 0.5s ago
    with auth_client.application.app_context():
        token = AntiCheatValidator.generate_session_token(1, '2048', start_ms)

    res = auth_client.post('/api/v2/session/end', json={
        'game_slug': '2048',
        'score': 500,
        'session_token': token,
        'start_time_ms': start_ms
    })
    assert res.status_code == 422
    data = res.get_json()
    assert data['code'] == 'ANOMALOUS_VELOCITY'
    assert 'IMPOSSIBLE_DURATION' in data['error']


def test_replayed_session_token_rejection(auth_client):
    """Test that reusing a session_token returns HTTP 401 Unauthorized with TOKEN_REUSED."""
    start_ms = int(time.time() * 1000) - 10000
    with auth_client.application.app_context():
        token = AntiCheatValidator.generate_session_token(1, 'flappybird', start_ms)

    # 1. First submission succeeds
    res1 = auth_client.post('/api/v2/session/end', json={
        'game_slug': 'flappybird',
        'score': 12,
        'session_token': token,
        'start_time_ms': start_ms
    })
    assert res1.status_code == 201

    # 2. Replay the same submission: Must be blocked
    res2 = auth_client.post('/api/v2/session/end', json={
        'game_slug': 'flappybird',
        'score': 15,
        'session_token': token,
        'start_time_ms': start_ms
    })
    assert res2.status_code == 401
    data2 = res2.get_json()
    assert data2['code'] == 'TOKEN_REUSED'


def test_invalid_session_signature_rejection(auth_client):
    """Test that submitting a forged or tampered session_token returns HTTP 401 with INVALID_SIGNATURE."""
    start_ms = int(time.time() * 1000) - 5000
    fake_token = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    res = auth_client.post('/api/v2/session/end', json={
        'game_slug': 'flappybird',
        'score': 5,
        'session_token': fake_token,
        'start_time_ms': start_ms
    })
    assert res.status_code == 401
    data = res.get_json()
    assert data['code'] == 'INVALID_SIGNATURE'


def test_expired_session_token_rejection(auth_client):
    """Test that submitting an expired token (> 2 hours old) returns 401 with SESSION_EXPIRED."""
    old_start_ms = int(time.time() * 1000) - (8000 * 1000)  # > 2 hours ago
    with auth_client.application.app_context():
        token = AntiCheatValidator.generate_session_token(1, 'flappybird', old_start_ms)

    res = auth_client.post('/api/v2/session/end', json={
        'game_slug': 'flappybird',
        'score': 10,
        'session_token': token,
        'start_time_ms': old_start_ms
    })
    assert res.status_code == 401
    data = res.get_json()
    assert data['code'] == 'SESSION_EXPIRED'


def test_concurrency_stress_telemetry_queue(app):
    """Simulate concurrent score submissions and verify zero dropped events and exact ranking."""
    num_submissions = 500
    telemetry_queue.reset()

    def submit_worker(i):
        return telemetry_queue.enqueue_score(
            player_id=i,
            username=f"Player_{i}",
            game_name="Neon Cyber Racer",
            score=i * 10
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(submit_worker, range(num_submissions)))

    assert len(results) == num_submissions
    assert telemetry_queue.scores_ingested == num_submissions

    # Check leaderboard top rank
    lb = telemetry_queue.get_live_leaderboard("Neon Cyber Racer", limit=5)
    assert len(lb['leaderboard']) == 5
    # The highest score should be (num_submissions - 1) * 10
    top_score = (num_submissions - 1) * 10
    assert lb['leaderboard'][0]['score'] == top_score
    assert lb['leaderboard'][0]['username'] == f"Player_{num_submissions - 1}"


def test_input_entropy_validation_heuristics(app):
    """Verify input entropy format, monotonicity, and bounds enforcement."""
    with app.app_context():
        start_ms = int(time.time() * 1000) - 5000
        curr_ms = int(time.time() * 1000)

        # 1. Valid entropy string
        valid_entropy = f"3:{start_ms + 1000},{start_ms + 2000},{start_ms + 3000}"
        valid, reason = AntiCheatValidator.verify_input_entropy(
            input_entropy_hash=valid_entropy,
            action_count=3,
            start_time_ms=start_ms,
            current_time_ms=curr_ms
        )
        assert valid is True
        assert reason == "VERIFIED"

        # 2. Syntax/Format Error: Missing colon
        valid, reason = AntiCheatValidator.verify_input_entropy(
            input_entropy_hash="malformed_gibberish",
            action_count=3,
            start_time_ms=start_ms,
            current_time_ms=curr_ms
        )
        assert valid is False
        assert reason == "INVALID_ENTROPY_SYNTAX"

        # 3. Action count mismatch
        valid, reason = AntiCheatValidator.verify_input_entropy(
            input_entropy_hash=valid_entropy,
            action_count=10,  # mismatch with 3
            start_time_ms=start_ms,
            current_time_ms=curr_ms
        )
        assert valid is False
        assert "ENTROPY_ACTION_COUNT_MISMATCH" in reason

        # 4. Non-monotonic timestamp anomaly (e.g. spoofed back in time)
        non_monotonic = f"3:{start_ms + 2000},{start_ms + 1000},{start_ms + 3000}"
        valid, reason = AntiCheatValidator.verify_input_entropy(
            input_entropy_hash=non_monotonic,
            action_count=3,
            start_time_ms=start_ms,
            current_time_ms=curr_ms
        )
        assert valid is False
        assert reason == "NON_MONOTONIC_ENTROPY_TIMESTAMPS"

        # 5. Out of bounds timestamp (future or far in the past)
        out_of_bounds = f"1:{start_ms - 100000}"
        valid, reason = AntiCheatValidator.verify_input_entropy(
            input_entropy_hash=out_of_bounds,
            action_count=1,
            start_time_ms=start_ms,
            current_time_ms=curr_ms
        )
        assert valid is False
        assert reason == "ENTROPY_TIMESTAMP_OUT_OF_BOUNDS"

        # 6. Robotic / synthetic macro script (zero-variance intervals)
        robotic_intervals = f"5:{start_ms + 500},{start_ms + 1000},{start_ms + 1500},{start_ms + 2000},{start_ms + 2500}"
        valid, reason = AntiCheatValidator.verify_input_entropy(
            input_entropy_hash=robotic_intervals,
            action_count=5,
            start_time_ms=start_ms,
            current_time_ms=curr_ms
        )
        assert valid is False
        assert reason == "SYNTHETIC_INTERVAL_ROBOTIC_ENTROPY"


def test_production_secret_key_hardcoded_fallback_rejection(monkeypatch):
    """Verify that in production mode, missing or default SECRET_KEY raises a critical error."""
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    from app.config import settings
    monkeypatch.setattr(settings, "SECRET_KEY", "pixora-fallback-secret-key")

    import pytest
    with pytest.raises(RuntimeError, match="CRITICAL SECURITY CONFIGURATION ERROR"):
        AntiCheatValidator._get_secret_key()


