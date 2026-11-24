"""Comprehensive behavioral tests for anti-cheat, telemetry queue, auth deps, and storage."""
import time
import pytest

from app.auth_deps import (
    create_session_cookie,
    decode_session_cookie,
)
from app.database import db
from app.models import GameScore, User
from app.services.anti_cheat import AntiCheatValidator
from app.utils.storage import r2_storage
from app.utils.telemetry_queue import telemetry_queue


def test_anti_cheat_player_token_lifecycle():
    """Test generating, verifying, and expiration of anti-cheat player tokens."""
    token = AntiCheatValidator.create_player_token(player_id=42, username="AeroPilot")
    assert token is not None

    decoded = AntiCheatValidator.verify_player_token(token)
    assert decoded is not None
    assert decoded["player_id"] == 42
    assert decoded["username"] == "AeroPilot"

    # Expired token (max_age=-1)
    expired = AntiCheatValidator.verify_player_token(token, max_age=-1)
    assert expired is None

    # Tampered token
    tampered = AntiCheatValidator.verify_player_token(token + "tampered")
    assert tampered is None


def test_anti_cheat_session_token_and_replay_detection():
    """Test session token generation, consumption, and replay rejection."""
    now_ms = int(time.time() * 1000)
    tok = AntiCheatValidator.generate_session_token(player_id=10, game_slug="2048", timestamp_ms=now_ms)
    assert tok is not None

    # Before use, not replayed
    assert AntiCheatValidator.is_token_replayed(tok) is False

    # Mark as consumed
    AntiCheatValidator.mark_token_used(tok, ttl=300)
    assert AntiCheatValidator.is_token_replayed(tok) is True


@pytest.mark.asyncio
async def test_anti_cheat_async_token_replay():
    """Test async token replay check and mark consumed."""
    now_ms = int(time.time() * 1000)
    tok = AntiCheatValidator.generate_session_token(player_id=99, game_slug="flappybird", timestamp_ms=now_ms)

    assert await AntiCheatValidator.async_is_token_replayed(tok) is False
    await AntiCheatValidator.async_mark_token_used(tok, ttl=300)
    assert await AntiCheatValidator.async_is_token_replayed(tok) is True


def test_anti_cheat_input_entropy_verification():
    """Test input entropy parser: valid sequence, format errors, variance, bounds."""
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - 10000

    # Valid human entropy with varied intervals
    ts_list = [start_ms + 1000, start_ms + 2300, start_ms + 3700, start_ms + 5100, start_ms + 7400]
    entropy_str = f"5:{','.join(map(str, ts_list))}"
    valid, reason = AntiCheatValidator.verify_input_entropy(
        input_entropy_hash=entropy_str,
        action_count=5,
        start_time_ms=start_ms,
        current_time_ms=now_ms
    )
    assert valid is True
    assert reason == "VERIFIED"

    # Action count mismatch
    valid, reason = AntiCheatValidator.verify_input_entropy(
        input_entropy_hash=entropy_str,
        action_count=10,
        start_time_ms=start_ms,
        current_time_ms=now_ms
    )
    assert valid is False
    assert "MISMATCH" in reason

    # Invalid syntax (missing colon)
    valid, reason = AntiCheatValidator.verify_input_entropy(
        input_entropy_hash="malformed_string_without_colon",
        action_count=5,
        start_time_ms=start_ms,
        current_time_ms=now_ms
    )
    assert valid is False

    # Non-monotonic timestamps (backwards in time)
    bad_ts = [start_ms + 3000, start_ms + 2000, start_ms + 4000]
    bad_entropy = f"3:{','.join(map(str, bad_ts))}"
    valid, reason = AntiCheatValidator.verify_input_entropy(
        input_entropy_hash=bad_entropy,
        action_count=3,
        start_time_ms=start_ms,
        current_time_ms=now_ms
    )
    assert valid is False
    assert "NON_MONOTONIC" in reason

    # Out of bounds timestamps (before session start)
    oob_ts = [start_ms - 20000, start_ms + 1000]
    oob_entropy = f"2:{','.join(map(str, oob_ts))}"
    valid, reason = AntiCheatValidator.verify_input_entropy(
        input_entropy_hash=oob_entropy,
        action_count=2,
        start_time_ms=start_ms,
        current_time_ms=now_ms
    )
    assert valid is False
    assert "OUT_OF_BOUNDS" in reason

    # Synthetic / robotic intervals (all intervals exactly identical)
    robotic_ts = [start_ms + 1000, start_ms + 2000, start_ms + 3000, start_ms + 4000, start_ms + 5000]
    robotic_entropy = f"5:{','.join(map(str, robotic_ts))}"
    valid, reason = AntiCheatValidator.verify_input_entropy(
        input_entropy_hash=robotic_entropy,
        action_count=5,
        start_time_ms=start_ms,
        current_time_ms=now_ms
    )
    assert valid is False
    assert "SYNTHETIC" in reason


def test_anti_cheat_production_missing_secret_key_fails(monkeypatch):
    """Test AntiCheatValidator raises RuntimeError in production if SECRET_KEY is missing."""
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    from app import config
    monkeypatch.setattr(config.settings, "SECRET_KEY", "")

    with pytest.raises(RuntimeError, match="CRITICAL SECURITY CONFIGURATION ERROR"):
        AntiCheatValidator._get_secret_key()


def test_telemetry_queue_in_memory_lifecycle(app):
    """Test telemetry queue operations: score enqueuing, presence, leaderboard, batch flush."""
    with app.app_context():
        # Clean state
        telemetry_queue.reset()

        # Enqueue scores
        u = User.query.filter_by(username='CyberTester').first()
        if not u:
            u = User(username='CyberTester', is_guest=False)
            db.session.add(u)
            db.session.commit()

        # Enqueue scores for 2048
        score_data = telemetry_queue.enqueue_score(
            player_id=u.id,
            username=u.username,
            game_name='2048',
            score=2048
        )
        assert score_data['score'] == 2048

        # Check live leaderboard
        lb = telemetry_queue.get_live_leaderboard('2048', limit=5, current_player_id=u.id)
        assert lb['world_record']['score'] >= 2048
        assert lb['user_best'] >= 2048

        # Presence increment and decrement
        p1 = telemetry_queue.record_presence('2048', delta=1)
        assert p1 >= 1
        p_read = telemetry_queue.get_presence('2048')
        assert p_read >= 1
        telemetry_queue.record_presence('2048', delta=-1)

        # Session start and deduplication
        is_dedup, status, s_dict = telemetry_queue.enqueue_session_start(player_id=u.id, game_name='2048')
        assert is_dedup is False
        # Immediate second start is deduplicated
        is_dedup2, status2, _ = telemetry_queue.enqueue_session_start(player_id=u.id, game_name='2048')
        assert is_dedup2 is True

        # Session end
        end_res = telemetry_queue.enqueue_session_end(player_id=u.id, game_name='2048')
        assert end_res['status'] == 'ended'

        # Batch flush to relational database
        telemetry_queue.flush()

        # Verify persisted in database
        saved_score = GameScore.query.filter_by(player_id=u.id, game_name='2048').first()
        assert saved_score is not None

        # Metrics check
        metrics = telemetry_queue.get_metrics()
        assert 'mode' in metrics
        assert 'scores_persisted' in metrics
        assert metrics['scores_persisted'] >= 1


def test_auth_deps_session_cookie_helpers():
    """Test auth_deps cookie serialization, deserialization, and tampering detection."""
    data = {"_user_id": 123, "pilot_username": "StarLord"}
    cookie_str = create_session_cookie(data)
    assert cookie_str is not None

    decoded = decode_session_cookie(cookie_str)
    assert decoded["_user_id"] == 123
    assert decoded["pilot_username"] == "StarLord"

    # Tampered cookie returns None
    assert decode_session_cookie("tampered.signature.here") is None
    assert decode_session_cookie("") is None


def test_r2_storage_unconfigured_fallback():
    """Test R2 storage fallback behavior when credentials or boto3 are absent."""
    # When not ready, upload returns None or {}
    assert r2_storage.upload_file("nonexistent.txt", "games/test.txt") is None
    assert r2_storage.upload_directory("/tmp/does_not_exist", "games/dir") == {}

    # Public URL formatting
    url = r2_storage.get_public_url("games/2048/index.html")
    assert url.endswith("games/2048/index.html")


def test_zip_slip_rejection_in_admin_upload(admin_client, tmp_path):
    """Test admin upload game detects and rejects zip-slip directory traversal attacks."""
    import io
    import zipfile

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('../../etc/evil_payload.txt', 'evil data')
    zip_buffer.seek(0)

    resp = admin_client.post(
        '/admin/games/upload',
        data={
            'title': 'Malicious Game',
            'slug': 'malicious-game',
            'category': 'Action',
        },
        files={
            'game_zip': ('malicious.zip', zip_buffer.getvalue(), 'application/zip')
        },
        follow_redirects=True
    )
    # The server catches the exception or returns error
    assert resp.status_code == 400
    assert b'Illegal file path' in resp.data or b'Deployment failed' in resp.data


def test_anti_cheat_validate_submission_all_branches():
    """Test all diagnostic branches in AntiCheatValidator.validate_submission."""
    now_ms = int(time.time() * 1000)

    # 1. Invalid signature
    t1_ms = now_ms - 10000
    ok, reason = AntiCheatValidator.validate_submission(
        player_id=42, game_slug="2048", score=100, session_token="invalid_sig", start_time_ms=t1_ms
    )
    assert ok is False
    assert reason == "INVALID_SESSION_SIGNATURE"

    # 2. Replay attack
    t2_ms = now_ms - 20000
    replayed_token = AntiCheatValidator.generate_session_token(42, "2048", t2_ms)
    AntiCheatValidator.mark_token_used(replayed_token)
    ok, reason = AntiCheatValidator.validate_submission(
        player_id=42, game_slug="2048", score=100, session_token=replayed_token, start_time_ms=t2_ms, check_replay=True
    )
    assert ok is False
    assert reason == "REPLAY_ATTACK_DETECTED"

    # 3. Negative duration anomaly (start time in the future)
    future_ms = now_ms + 100000
    future_token = AntiCheatValidator.generate_session_token(42, "2048", future_ms)
    ok, reason = AntiCheatValidator.validate_submission(
        player_id=42, game_slug="2048", score=100, session_token=future_token, start_time_ms=future_ms
    )
    assert ok is False
    assert reason == "NEGATIVE_DURATION_ANOMALY"

    # 4. Session expired (start time > 7200 seconds ago)
    ancient_ms = now_ms - (8000 * 1000)
    ancient_token = AntiCheatValidator.generate_session_token(42, "2048", ancient_ms)
    ok, reason = AntiCheatValidator.validate_submission(
        player_id=42, game_slug="2048", score=100, session_token=ancient_token, start_time_ms=ancient_ms
    )
    assert ok is False
    assert reason == "SESSION_EXPIRED"

    # 5. Impossible duration (< 2s, score > 10)
    too_fast_ms = now_ms - 500
    too_fast_tok = AntiCheatValidator.generate_session_token(42, "2048", too_fast_ms)
    ok, reason = AntiCheatValidator.validate_submission(
        player_id=42, game_slug="2048", score=50, session_token=too_fast_tok, start_time_ms=too_fast_ms
    )
    assert ok is False
    assert reason == "IMPOSSIBLE_DURATION"

    # 6. Score velocity exceeded
    t6_ms = now_ms - 30000
    high_score_tok = AntiCheatValidator.generate_session_token(42, "2048", t6_ms)
    ok, reason = AntiCheatValidator.validate_submission(
        player_id=42, game_slug="2048", score=999999, session_token=high_score_tok, start_time_ms=t6_ms
    )
    assert ok is False
    assert "SCORE_VELOCITY_EXCEEDED" in reason

    # 7. Zero actions for nonzero score
    t7_ms = now_ms - 40000
    zero_action_tok = AntiCheatValidator.generate_session_token(42, "2048", t7_ms)
    ok, reason = AntiCheatValidator.validate_submission(
        player_id=42, game_slug="2048", score=100, session_token=zero_action_tok, start_time_ms=t7_ms, action_count=0
    )
    assert ok is False
    assert reason == "ZERO_ACTIONS_FOR_NONZERO_SCORE"

    # 8. Speedtype insufficient keystrokes
    t8_ms = now_ms - 50000
    st_tok = AntiCheatValidator.generate_session_token(42, "speedtype", t8_ms)
    ok, reason = AntiCheatValidator.validate_submission(
        player_id=42, game_slug="speedtype", score=20, session_token=st_tok, start_time_ms=t8_ms, action_count=5
    )
    assert ok is False
    assert reason == "INSUFFICIENT_KEYSTROKES"

    # 9. Input entropy failure
    t9_ms = now_ms - 60000
    ent_tok = AntiCheatValidator.generate_session_token(42, "2048", t9_ms)
    ok, reason = AntiCheatValidator.validate_submission(
        player_id=42, game_slug="2048", score=100, session_token=ent_tok, start_time_ms=t9_ms,
        action_count=5, input_entropy_hash="malformed_hash"
    )
    assert ok is False

    # 10. Valid gameplay session
    t10_ms = now_ms - 70000
    valid_token = AntiCheatValidator.generate_session_token(42, "2048", t10_ms)
    ts_list = [t10_ms + 1000, t10_ms + 2500, t10_ms + 4200, t10_ms + 6100, t10_ms + 8000]
    valid_entropy = f"5:{','.join(map(str, ts_list))}"
    ok, reason = AntiCheatValidator.validate_submission(
        player_id=42, game_slug="2048", score=100, session_token=valid_token, start_time_ms=t10_ms,
        action_count=5, input_entropy_hash=valid_entropy
    )
    assert ok is True
    assert reason == "VERIFIED"


@pytest.mark.asyncio
async def test_auth_deps_require_user_and_require_admin():
    """Test require_user and require_admin authorization enforcement."""
    from fastapi import HTTPException
    from unittest.mock import MagicMock
    from app.auth_deps import MockField, MockForm, require_admin, require_user
    from app.models import AnonymousUser, User

    # 1. require_user with JSON request
    req_json = MagicMock()
    req_json.headers = {"accept": "application/json"}
    with pytest.raises(HTTPException) as exc_info:
        await require_user(req_json, user=AnonymousUser())
    assert exc_info.value.status_code == 401

    # 2. require_user with HTML browser request
    req_html = MagicMock()
    req_html.headers = {"accept": "text/html"}
    req_html.url.path = "/protected-portal"
    with pytest.raises(HTTPException) as exc_info:
        await require_user(req_html, user=AnonymousUser())
    assert exc_info.value.status_code == 303
    assert "/login?next=/protected-portal" in exc_info.value.headers["Location"]

    # 3. require_user with authenticated user
    real_user = User(username="ValidPilot", is_guest=False)
    resolved = await require_user(req_html, user=real_user)
    assert resolved == real_user

    # 4. require_admin with valid session cookie
    from app.auth_deps import create_session_cookie
    admin_cookie = create_session_cookie({"is_admin_authenticated": True})
    req_admin = MagicMock()
    req_admin.cookies = {"session": admin_cookie}
    assert await require_admin(req_admin, session=admin_cookie, user=AnonymousUser()) is True

    # 5. require_admin with admin User object
    admin_user = User(username="AdminPilot", is_guest=False)
    admin_user.is_admin = True
    assert await require_admin(req_admin, session=None, user=admin_user) is True

    # 6. require_admin unauthenticated -> 303 redirect
    req_unauth = MagicMock()
    req_unauth.cookies = {}
    req_unauth.url.path = "/admin/secret"
    with pytest.raises(HTTPException) as exc_info:
        await require_admin(req_unauth, session=None, user=AnonymousUser())
    assert exc_info.value.status_code == 303
    assert "/admin/login?next=/admin/secret" in exc_info.value.headers["Location"]

    # 7. MockField and MockForm coverage
    f_check = MockField("remember", True, "checkbox")
    rendered_check = str(f_check(extra="true"))
    assert 'checked' in rendered_check
    assert 'type="checkbox"' in rendered_check

    f_pass = MockField("password", "secret", "password")
    rendered_pass = str(f_pass())
    assert 'type="password"' in rendered_pass

    f_text = MockField("username", "pilot", "text")
    rendered_text = str(f_text())
    assert 'type="text"' in rendered_text
    assert 'value="pilot"' in rendered_text

    form = MockForm(username="test", password="pw", remember_me=True, custom_flag=True)
    assert str(form.hidden_tag()) == ''
    assert form.validate_on_submit() is False
    assert hasattr(form, "custom_flag")


def test_telemetry_queue_redis_mock_pipeline(app):
    """Test telemetry queue methods when Redis client is active."""
    from unittest.mock import MagicMock

    with app.app_context():
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = [True, True]
        mock_redis.get.return_value = "5"
        mock_redis.incrby.return_value = 6
        mock_redis.zcard.return_value = 10
        mock_redis.zrevrange.return_value = [("1:AcePlayer", 5000), ("2:SecondPlayer", 3000)]

        orig_redis = telemetry_queue.redis_client
        orig_enabled = telemetry_queue.redis_enabled
        try:
            telemetry_queue.redis_client = mock_redis
            telemetry_queue.redis_enabled = True

            # Presence operations with Redis
            p = telemetry_queue.record_presence("2048", delta=1)
            assert p == 6

            p_get = telemetry_queue.get_presence("2048")
            assert p_get == 5

            # Score enqueuing with Redis
            score_res = telemetry_queue.enqueue_score(1, "AcePlayer", "2048", 5000)
            assert score_res["score"] == 5000

            # Leaderboard with Redis
            lb = telemetry_queue.get_live_leaderboard("2048", limit=5, current_player_id=1)
            assert lb["source"] == "redis_live"
            assert len(lb["leaderboard"]) == 2
            assert lb["world_record"]["score"] == 5000
            assert lb["user_best"] == 5000
            assert lb["user_rank"] == 1

            # Batch drains
            mock_pipe.execute.return_value = ['{"score": 100, "player_id": 1, "game_name": "2048"}']
            drained_scores = telemetry_queue._drain_scores_batch(1)
            assert len(drained_scores) == 1

            mock_pipe.execute.return_value = ['{"action": "start", "player_id": 1, "game_name": "2048"}']
            drained_sessions = telemetry_queue._drain_sessions_batch(1)
            assert len(drained_sessions) == 1

            # Overtake notification publish
            telemetry_queue.publish_event("2048", {"type": "NEW_RECORD", "score": 9999})
            assert mock_redis.publish.called

            # Session operations with Redis
            mock_redis.get.return_value = '{"session_id": "s123", "started_at": "2026-01-01T12:00:00+00:00"}'
            s_dedup, s_stat, s_info = telemetry_queue.enqueue_session_start(1, "2048")
            assert s_info["game"] == "2048"

            end_res = telemetry_queue.enqueue_session_end(1, "2048")
            assert end_res["status"] == "ended"

            # Leaderboard fallback to database warming
            mock_redis.zrevrange.return_value = []
            mock_redis.exists.return_value = False
            db_lb = telemetry_queue.get_live_leaderboard("2048", limit=5)
            assert db_lb["source"] in ("database_warmed", "db_fallback", "redis_live", "event_queue")

            # Persistence of session end event
            from app.models import GameplaySession
            sess = GameplaySession(player_id=1, game_name="2048")
            db.session.add(sess)
            db.session.commit()
            telemetry_queue._persist_to_database([], [{
                'action': 'end',
                'player_id': 1,
                'game_name': '2048',
                'ended_at': '2026-01-01T12:02:00+00:00',
                'duration_seconds': 120
            }])
            db.session.refresh(sess)
            assert sess.duration_seconds == 120

            # Metrics with Redis online
            mock_redis.llen.return_value = 2
            metrics = telemetry_queue.get_metrics()
            assert metrics["redis_connected"] is True
            assert "ONLINE" in metrics["redis_status"]

        finally:
            telemetry_queue.redis_client = orig_redis
            telemetry_queue.redis_enabled = orig_enabled
