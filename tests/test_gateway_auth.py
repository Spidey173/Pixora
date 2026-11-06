"""Tests verifying authentication and identity spoofing prevention in gateway.py."""
import time
import pytest

from gateway import app, FASTAPI_AVAILABLE
from app.services.anti_cheat import AntiCheatValidator

try:
    from fastapi.testclient import TestClient
    TESTCLIENT_AVAILABLE = True
except (ImportError, RuntimeError):
    TestClient = None
    TESTCLIENT_AVAILABLE = False


@pytest.fixture
def gateway_client():
    """Create a fresh FastAPI test client for gateway.py."""
    if not FASTAPI_AVAILABLE or not TESTCLIENT_AVAILABLE:
        pytest.skip("FastAPI or httpx/TestClient is not installed.")
    with TestClient(app) as client:
        yield client


def test_unauthenticated_session_start_rejected(gateway_client):
    """Verify that unauthenticated session start returns 401 Unauthorized."""
    res = gateway_client.post("/api/v2/session/start", json={"game_slug": "flappybird"})
    assert res.status_code == 401
    data = res.json()
    assert data["detail"]["code"] == "UNAUTHORIZED"


def test_unauthenticated_session_end_rejected(gateway_client):
    """Verify that unauthenticated score submission returns 401 Unauthorized."""
    res = gateway_client.post("/api/v2/session/end", json={
        "game_slug": "flappybird",
        "score": 100,
        "session_token": "fake-token",
        "start_time_ms": int(time.time() * 1000)
    })
    assert res.status_code == 401
    data = res.json()
    assert data["detail"]["code"] == "UNAUTHORIZED"


def test_authenticated_session_start_via_bearer_token(gateway_client):
    """Verify authenticated session start issues a token signed for the authenticated player."""
    player_id = 42
    username = "AcePilot"
    auth_token = AntiCheatValidator.create_player_token(player_id, username)

    res = gateway_client.post(
        "/api/v2/session/start",
        json={"game_slug": "flappybird"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["player_id"] == player_id
    assert data["username"] == username
    assert "session_token" in data

    # Verify session_token signature belongs specifically to player 42
    expected_token = AntiCheatValidator.generate_session_token(
        player_id=player_id,
        game_slug="flappybird",
        timestamp_ms=data["start_time_ms"]
    )
    assert data["session_token"] == expected_token


def test_identity_spoofing_in_session_start_is_blocked(gateway_client):
    """Verify that attempting to self-report a different player_id is rejected with 403 Forbidden."""
    # Authenticated as player 10
    auth_token = AntiCheatValidator.create_player_token(10, "Attacker")

    # Attacker attempts to request session token for player 9999 ("TopPlayer")
    res = gateway_client.post(
        "/api/v2/session/start",
        json={
            "game_slug": "flappybird",
            "player_id": 9999,
            "username": "TopPlayer"
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert res.status_code == 403
    data = res.json()
    assert data["detail"]["code"] == "FORBIDDEN"
    assert "Identity spoofing detected" in data["detail"]["error"]


def test_authenticated_session_start_via_flask_cookie(gateway_client):
    """Verify that gateway authenticates players using the Flask signed session cookie."""
    from itsdangerous import URLSafeTimedSerializer
    secret = AntiCheatValidator._get_secret_key()
    serializer = URLSafeTimedSerializer(secret, salt="cookie-session")
    cookie_val = serializer.dumps({"_user_id": "7", "pilot_username": "CookieAce"})

    gateway_client.cookies.set("session", cookie_val)
    res = gateway_client.post("/api/v2/session/start", json={"game_slug": "2048"})
    assert res.status_code == 200
    data = res.json()
    assert data["player_id"] == 7
    assert data["username"] == "CookieAce"


def test_identity_spoofing_in_score_submission_is_blocked(gateway_client):
    """Verify that score submission with a mismatched/spoofed player_id is rejected with 403 Forbidden."""
    auth_token = AntiCheatValidator.create_player_token(15, "Cheater")
    start_time_ms = int(time.time() * 1000) - 10000

    token = AntiCheatValidator.generate_session_token(15, "2048", start_time_ms)

    # Cheater tries to claim score for player 9999
    res = gateway_client.post(
        "/api/v2/session/end",
        json={
            "game_slug": "2048",
            "score": 50,
            "session_token": token,
            "start_time_ms": start_time_ms,
            "player_id": 9999,
            "username": "LegitLeader"
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert res.status_code == 403
    data = res.json()
    assert data["detail"]["code"] == "FORBIDDEN"
    assert "Identity spoofing detected" in data["detail"]["error"]


def test_valid_score_submission_with_authenticated_player(gateway_client):
    """Verify legitimate score submission completes and binds to authenticated identity."""
    player_id = 88
    username = "SpeedDemon"
    auth_token = AntiCheatValidator.create_player_token(player_id, username)

    # 10 seconds ago to satisfy anti-cheat velocity checks
    start_time_ms = int(time.time() * 1000) - 10000
    session_token = AntiCheatValidator.generate_session_token(player_id, "2048", start_time_ms)

    res = gateway_client.post(
        "/api/v2/session/end",
        json={
            "game_slug": "2048",
            "score": 80,
            "session_token": session_token,
            "start_time_ms": start_time_ms,
            "action_count": 20
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["verified"] is True


def test_tampered_bearer_token_rejected(gateway_client):
    """Verify tampered or invalid bearer tokens are rejected with 401."""
    res = gateway_client.post(
        "/api/v2/session/start",
        json={"game_slug": "flappybird"},
        headers={"Authorization": "Bearer totally-invalid-and-tampered-token"}
    )
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "UNAUTHORIZED"


def test_issue_auth_token_endpoint(gateway_client):
    """Verify /api/v2/auth/token generates a verified Bearer token for an authenticated user."""
    from itsdangerous import URLSafeTimedSerializer
    secret = AntiCheatValidator._get_secret_key()
    serializer = URLSafeTimedSerializer(secret, salt="cookie-session")
    cookie_val = serializer.dumps({"_user_id": "55", "pilot_username": "RocketPilot"})

    gateway_client.cookies.set("session", cookie_val)
    res = gateway_client.post("/api/v2/auth/token")
    assert res.status_code == 200
    data = res.json()
    assert data["player_id"] == 55
    assert data["username"] == "RocketPilot"
    assert data["token_type"] == "bearer"
    assert "access_token" in data

    # Verify the issued token can now be used for session start
    token_res = gateway_client.post(
        "/api/v2/session/start",
        json={"game_slug": "neon-racer"},
        headers={"Authorization": f"Bearer {data['access_token']}"}
    )
    assert token_res.status_code == 200
    assert token_res.json()["player_id"] == 55

