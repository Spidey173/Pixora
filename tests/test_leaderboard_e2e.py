"""End-to-end tests for Pixora leaderboard, identity propagation, Redis prefixing, and normalized ranking."""
import time
from datetime import datetime, timezone

from app.extensions import db
from app.models import GameScore, User
from app.services.anti_cheat import AntiCheatValidator
from app.utils.game_resolver import build_normalized_all_titles_leaderboard
from app.utils.redis_keys import get_dlq_key, get_redis_key_prefix, get_stream_key, redis_key
from app.utils.telemetry_queue import telemetry_queue
from worker import TelemetryStreamWorker


class InMemoryFakeRedis:
    """Minimal sync+async compatible fake Redis supporting ZSETs, Streams, Strings, and Hashes."""

    def __init__(self):
        self.strings: dict[str, str] = {}
        self.zsets: dict[str, dict[str, float]] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.streams: dict[str, list[tuple[str, dict]]] = {}
        self.published: list[tuple[str, str]] = []
        self._seq = 0

    def ping(self):
        return True

    def exists(self, key):
        return 1 if (key in self.strings or key in self.zsets or key in self.streams or key in self.hashes) else 0

    def get(self, key):
        return self.strings.get(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.strings:
            return False
        self.strings[key] = str(value)
        return True

    def delete(self, *keys):
        removed = 0
        for k in keys:
            for store in (self.strings, self.zsets, self.hashes, self.streams):
                if k in store:
                    del store[k]
                    removed += 1
        return removed

    def scan_iter(self, match="*", count=100):
        import fnmatch
        all_keys = set(self.strings) | set(self.zsets) | set(self.hashes) | set(self.streams)
        for k in list(all_keys):
            if fnmatch.fnmatch(k, match):
                yield k

    def zadd(self, key, mapping, gt=False):
        z = self.zsets.setdefault(key, {})
        added = 0
        for member, score in mapping.items():
            score_f = float(score)
            if member not in z:
                z[member] = score_f
                added += 1
            elif not gt or score_f > z[member]:
                z[member] = score_f
        return added

    def zrevrank(self, key, member):
        z = self.zsets.get(key, {})
        if member not in z:
            return None
        ordered = sorted(z.items(), key=lambda kv: (-kv[1], kv[0]))
        for idx, (m, _) in enumerate(ordered):
            if m == member:
                return idx
        return None

    def zrevrange(self, key, start, end, withscores=False):
        z = self.zsets.get(key, {})
        ordered = sorted(z.items(), key=lambda kv: (-kv[1], kv[0]))
        stop = None if end == -1 else end + 1
        sliced = ordered[start:stop]
        if withscores:
            return sliced
        return [m for m, _ in sliced]

    def zcard(self, key):
        return len(self.zsets.get(key, {}))

    def xadd(self, key, fields):
        self._seq += 1
        msg_id = f"{int(time.time() * 1000)}-{self._seq}"
        self.streams.setdefault(key, []).append((msg_id, dict(fields)))
        return msg_id

    def xreadgroup(self, group, consumer, streams, count=50, block=None):
        res = []
        for s_key, _ in streams.items():
            msgs = self.streams.get(s_key, [])[:count]
            if msgs:
                res.append((s_key, msgs))
        return res

    def xack(self, stream, group, *msg_ids):
        if stream in self.streams:
            id_set = set(msg_ids)
            self.streams[stream] = [(mid, p) for mid, p in self.streams[stream] if mid not in id_set]
        return len(msg_ids)

    def publish(self, channel, msg):
        self.published.append((channel, msg))
        return 1

    def pipeline(self):
        outer = self

        class _SyncPipe:
            def __init__(self):
                self._ops = []

            def zadd(self, key, mapping, gt=False):
                self._ops.append(("zadd", (key, mapping, gt)))
                return self

            def zrevrank(self, key, member):
                self._ops.append(("zrevrank", (key, member)))
                return self

            def xadd(self, key, fields):
                self._ops.append(("xadd", (key, fields)))
                return self

            def set(self, key, value, nx=False, ex=None):
                self._ops.append(("set", (key, value, nx, ex)))
                return self

            def execute(self):
                results = []
                for op, args in self._ops:
                    if op == "zadd":
                        results.append(outer.zadd(*args))
                    elif op == "zrevrank":
                        results.append(outer.zrevrank(*args))
                    elif op == "xadd":
                        results.append(outer.xadd(*args))
                    elif op == "set":
                        results.append(outer.set(*args))
                self._ops.clear()
                return results

        return _SyncPipe()


class AsyncFakeRedisAdapter:
    """Async wrapper over InMemoryFakeRedis for gateway.py endpoints."""

    def __init__(self, sync_redis: InMemoryFakeRedis):
        self.sync = sync_redis

    async def exists(self, key):
        return self.sync.exists(key)

    async def get(self, key):
        return self.sync.get(key)

    async def set(self, key, value, nx=False, ex=None):
        return self.sync.set(key, value, nx=nx, ex=ex)

    async def zrevrange(self, key, start, end, withscores=False):
        return self.sync.zrevrange(key, start, end, withscores=withscores)

    async def publish(self, channel, msg):
        return self.sync.publish(channel, msg)

    def pipeline(self):
        sync_pipe = self.sync.pipeline()

        class _AsyncPipe:
            def zadd(self, key, mapping, gt=False):
                sync_pipe.zadd(key, mapping, gt=gt)
                return self

            def zrevrank(self, key, member):
                sync_pipe.zrevrank(key, member)
                return self

            def xadd(self, key, fields):
                sync_pipe.xadd(key, fields)
                return self

            async def execute(self):
                return sync_pipe.execute()

        return _AsyncPipe()


def test_end_to_end_session_submit_worker_and_leaderboard_api(client, app, monkeypatch):
    """E2E: login -> session/start -> session/end -> worker stream flush -> leaderboard & PB update."""
    import gateway

    fake_sync = InMemoryFakeRedis()
    fake_async = AsyncFakeRedisAdapter(fake_sync)
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("REDIS_KEY_PREFIX", "e2e:")
    monkeypatch.setattr(gateway, "redis_client", fake_async)

    orig_redis = telemetry_queue.redis_client
    orig_enabled = telemetry_queue.redis_enabled
    orig_testing = telemetry_queue.is_testing
    telemetry_queue.redis_client = fake_sync
    telemetry_queue.redis_enabled = True
    telemetry_queue.is_testing = False

    try:
        # Simulate an active worker heartbeat so worker.py owns DB persistence from Redis stream
        worker = TelemetryStreamWorker(worker_name="test-worker", redis_client=fake_sync)
        worker._refresh_heartbeat()

        with app.app_context():
            rival = User(username="RivalAce", is_guest=False)
            rival.set_password("RivalPass123!")
            db.session.add(rival)
            db.session.commit()
            db.session.add(GameScore(player_id=rival.id, game_name="2048 Cyber Grid", score=500))
            db.session.commit()

        # 1. Login as Pilot_7255 (guest codename login)
        login_res = client.post("/login", data={"username": "Pilot_7255"}, follow_redirects=False)
        assert login_res.status_code == 302

        # 2. Start v2 session
        start_res = client.post("/api/v2/session/start", json={"game_slug": "2048"})
        assert start_res.status_code == 200
        sess_data = start_res.get_json()
        assert sess_data["username"] == "Pilot_7255"

        # Backdate start_time_ms by 30s to satisfy anti-cheat duration & velocity rules
        valid_start_ms = int(time.time() * 1000) - 30000
        token = AntiCheatValidator.generate_session_token(
            player_id=sess_data["player_id"],
            game_slug="2048",
            timestamp_ms=valid_start_ms,
        )

        # 3. Submit valid score higher than RivalAce (750 > 500)
        end_res = client.post(
            "/api/v2/session/end",
            json={
                "game_slug": "2048",
                "score": 750,
                "session_token": token,
                "start_time_ms": valid_start_ms,
                "action_count": 25,
            },
        )
        assert end_res.status_code == 201
        assert end_res.get_json()["verified"] is True

        # Stream should contain 1 unconsumed message for worker
        stream_key = get_stream_key(testing=False)
        assert len(fake_sync.streams.get(stream_key, [])) == 1

        # 4. Process via worker
        processed = worker.process_batch(app)
        assert processed == 1
        assert len(fake_sync.streams.get(stream_key, [])) == 0

        # Verify persisted in DB under canonical title
        with app.app_context():
            pilot = User.query.filter_by(username="Pilot_7255").first()
            saved = GameScore.query.filter_by(player_id=pilot.id, game_name="2048 Cyber Grid").all()
            assert len(saved) == 1
            assert saved[0].score == 750

        # 5. Query leaderboard API (warmed from DB -> merged with ZSET) and verify rank + personal best
        lb_res = client.get("/api/leaderboard/2048")
        assert lb_res.status_code == 200
        lb = lb_res.get_json()
        assert lb["canonical_title"] == "2048 Cyber Grid"
        assert lb["user_best"] == 750
        assert lb["user_rank"] == 1
        assert lb["leaderboard"][0]["username"] == "Pilot_7255"
        assert lb["leaderboard"][0]["score"] == 750
        assert lb["leaderboard"][1]["username"] == "RivalAce"
        assert lb["leaderboard"][1]["score"] == 500

        # Also check /api/v2/leaderboard/2048 reads the exact same canonical ZSET
        v2_res = client.get("/api/v2/leaderboard/2048")
        assert v2_res.status_code == 200
        v2_data = v2_res.get_json()
        assert v2_data["leaderboard"][0]["username"] == "Pilot_7255"
        assert v2_data["leaderboard"][0]["score"] == 750
    finally:
        telemetry_queue.redis_client = orig_redis
        telemetry_queue.redis_enabled = orig_enabled
        telemetry_queue.is_testing = orig_testing


def test_logged_in_user_not_shown_as_guest_and_spoofed_username_ignored(client, app):
    """Logged-in pilot appears on /play/<slug> and spoofed username in payload is ignored."""
    client.post("/login", data={"username": "Pilot_7255"}, follow_redirects=False)

    # Hub and play page must both show Pilot_7255, never Guest
    hub_resp = client.get("/games")
    assert hub_resp.status_code == 200
    assert b"Pilot_7255" in hub_resp.data

    play_resp = client.get("/play/2048")
    assert play_resp.status_code == 200
    assert b"Pilot_7255" in play_resp.data
    assert b"Pilot: Guest" not in play_resp.data

    # Start session as Pilot_7255 while trying to spoof username='VortexAce'
    start_res = client.post("/api/v2/session/start", json={"game_slug": "2048", "username": "VortexAce"})
    assert start_res.status_code == 200
    sess = start_res.get_json()
    assert sess["username"] == "Pilot_7255"

    valid_start_ms = int(time.time() * 1000) - 20000
    token = AntiCheatValidator.generate_session_token(sess["player_id"], "2048", valid_start_ms)

    # Submit score with spoofed username='VortexAce' in payload
    end_res = client.post(
        "/api/v2/session/end",
        json={
            "game_slug": "2048",
            "score": 128,
            "session_token": token,
            "start_time_ms": valid_start_ms,
            "action_count": 10,
            "username": "VortexAce",
        },
    )
    assert end_res.status_code == 201
    score_payload = end_res.get_json()["score"]
    assert score_payload["username"] == "Pilot_7255"

    # Also test v1 /api/score/submit ignores spoofed username
    v1_res = client.post(
        "/api/score/submit",
        json={"game_name": "2048", "score": 256, "username": "VortexAce"},
    )
    assert v1_res.status_code == 201
    assert v1_res.get_json()["score"]["username"] == "Pilot_7255"

    with app.app_context():
        pilot = User.query.filter_by(username="Pilot_7255").first()
        scores = GameScore.query.filter_by(player_id=pilot.id).all()
        assert len(scores) >= 2
        assert User.query.filter_by(username="VortexAce").first() is None


def test_redis_key_prefix_helper_controls_write_and_read_paths(client, app, monkeypatch):
    """Changing REDIS_KEY_PREFIX dynamically updates anti-cheat, gateway, worker, and queue keys."""
    import gateway

    fake_sync = InMemoryFakeRedis()
    fake_async = AsyncFakeRedisAdapter(fake_sync)

    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("REDIS_KEY_PREFIX", "custom_arcade:")
    monkeypatch.delenv("TELEMETRY_STREAM_KEY", raising=False)
    monkeypatch.delenv("TELEMETRY_DLQ_KEY", raising=False)
    monkeypatch.setattr(gateway, "redis_client", fake_async)

    orig_redis = telemetry_queue.redis_client
    orig_enabled = telemetry_queue.redis_enabled
    orig_testing = telemetry_queue.is_testing
    telemetry_queue.redis_client = fake_sync
    telemetry_queue.redis_enabled = True
    telemetry_queue.is_testing = False

    try:
        assert get_redis_key_prefix() == "custom_arcade:"
        assert redis_key("lb:bests:2048") == "custom_arcade:lb:bests:2048"
        assert get_stream_key() == "custom_arcade:telemetry"
        assert get_dlq_key() == "custom_arcade:telemetry:dlq"

        client.post("/login", data={"username": "PrefixPilot"}, follow_redirects=False)
        start_res = client.post("/api/v2/session/start", json={"game_slug": "2048"}).get_json()
        start_ms = int(time.time() * 1000) - 20000
        token = AntiCheatValidator.generate_session_token(start_res["player_id"], "2048", start_ms)

        end_res = client.post(
            "/api/v2/session/end",
            json={
                "game_slug": "2048",
                "score": 320,
                "session_token": token,
                "start_time_ms": start_ms,
                "action_count": 12,
            },
        )
        assert end_res.status_code == 201

        # All written keys must live under custom_arcade:, and none under pixora:
        all_keys = set(fake_sync.strings) | set(fake_sync.zsets) | set(fake_sync.streams)
        assert any(k.startswith("custom_arcade:") for k in all_keys)
        assert not any(k.startswith("pixora:") for k in all_keys)
        assert f"custom_arcade:used_token:{token}" in fake_sync.strings
        assert "custom_arcade:lb:bests:2048 Cyber Grid" in fake_sync.zsets
        assert "custom_arcade:telemetry" in fake_sync.streams

        # Read path under custom_arcade: finds the score
        lb_res = client.get("/api/v2/leaderboard/2048")
        assert lb_res.status_code == 200
        assert lb_res.get_json()["leaderboard"][0]["score"] == 320
    finally:
        telemetry_queue.redis_client = orig_redis
        telemetry_queue.redis_enabled = orig_enabled
        telemetry_queue.is_testing = orig_testing


def test_all_titles_normalized_leaderboard_ordering(auth_client, app):
    """All Titles board ranks by normalized % of game world record instead of raw score."""
    with app.app_context():
        flappy_champ = User(username="FlappyAce", is_guest=False)
        pinball_mid = User(username="PinballCasual", is_guest=False)
        pinball_wr = User(username="PinballKing", is_guest=False)
        db.session.add_all([flappy_champ, pinball_mid, pinball_wr])
        db.session.commit()

        now = datetime.now(timezone.utc)
        # Flappy Birds WR = 100 (FlappyAce has 100 -> 100.0% WR)
        # Synthwave Pinball WR = 20000 (PinballKing has 20000 -> 100.0% WR, PinballCasual has 10000 -> 50.0% WR)
        db.session.add_all([
            GameScore(player_id=flappy_champ.id, game_name="Flappy Birds", score=100, achieved_at=now),
            GameScore(player_id=pinball_wr.id, game_name="Synthwave Pinball", score=20000, achieved_at=now),
            GameScore(player_id=pinball_mid.id, game_name="Synthwave Pinball", score=10000, achieved_at=now),
        ])
        db.session.commit()

        ranked = build_normalized_all_titles_leaderboard(GameScore.query.all(), limit=10)
        usernames = [r.player.username for r in ranked]
        # FlappyAce (100.0% WR) MUST rank above PinballCasual (50.0% WR), even though 100 < 10,000!
        assert usernames.index("FlappyAce") < usernames.index("PinballCasual")
        flappy_row = next(r for r in ranked if r.player.username == "FlappyAce")
        casual_row = next(r for r in ranked if r.player.username == "PinballCasual")
        assert flappy_row.normalized_pct == 100.0
        assert casual_row.normalized_pct == 50.0

    # Verify rendered /leaderboard page displays normalized % WR label and FlappyAce above PinballCasual
    resp = auth_client.get("/leaderboard")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "NORMALIZED (% WR)" in body
    assert "100.0% WR" in body
    assert body.index("FlappyAce") < body.index("PinballCasual")


def test_rebuild_leaderboards_is_idempotent(app, monkeypatch):
    """rebuild_leaderboards rebuilds ZSETs from DB cleanly and is safe to run repeatedly."""
    from app.utils import rebuild_leaderboards as rb_mod

    fake_sync = InMemoryFakeRedis()
    fake_sync.zsets["glitch4ce:lb:bests:2048 Cyber Grid"] = {"1:Old": 999}
    fake_sync.zsets["rebuilt:lb:bests:Stale Game"] = {"99:Ghost": 99999}

    monkeypatch.setenv("REDIS_KEY_PREFIX", "rebuilt:")
    monkeypatch.setattr(rb_mod.redis.Redis, "from_url", staticmethod(lambda *a, **kw: fake_sync))
    monkeypatch.setattr(rb_mod, "create_app", lambda *a, **kw: app)

    with app.app_context():
        u = User(username="RebuildPilot", is_guest=False)
        db.session.add(u)
        db.session.commit()
        db.session.add(GameScore(player_id=u.id, game_name="2048", score=2048))
        db.session.commit()

    res1 = rb_mod.rebuild_leaderboards(purge_legacy=True, testing=False)
    res2 = rb_mod.rebuild_leaderboards(purge_legacy=True, testing=False)

    assert res1 == res2
    assert "glitch4ce:lb:bests:2048 Cyber Grid" not in fake_sync.zsets
    assert "rebuilt:lb:bests:Stale Game" not in fake_sync.zsets
    assert "rebuilt:lb:bests:2048 Cyber Grid" in fake_sync.zsets
    assert fake_sync.zrevrange("rebuilt:lb:bests:2048 Cyber Grid", 0, -1, withscores=True) == [
        (f"{u.id}:RebuildPilot", 2048.0)
    ]

