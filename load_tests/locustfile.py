"""High-Throughput Load Testing Suite for Pixora 2.0.

Benchmarks:
- 10,000+ requests/second high-throughput telemetry ingestion
- Cryptographic session handshakes (/api/v2/session/start & /api/v2/session/end)
- Sub-millisecond Redis ZSET leaderboard retrieval (/api/leaderboard/<game>)
- Real-time Anti-Cheat velocity rejection under heavy load

Usage:
    pip install locust
    locust -f load_tests/locustfile.py --host=http://127.0.0.1:5000 --users=1000 --spawn-rate=100
"""
import random
import time
from locust import FastHttpUser, task, between


class PixoraArcadePlayer(FastHttpUser):
    """Simulates realistic high-velocity player actions, score submissions, and leaderboard views."""
    wait_time = between(0.01, 0.1)  # High-frequency event simulation

    GAMES = [
        "neon-cyber-racer",
        "flappybird",
        "2048",
        "speedtype",
        "candy-crush",
        "pong"
    ]

    def on_start(self):
        """Initialize session and authenticate player."""
        self.player_id = random.randint(1000, 999999)
        self.username = f"Pilot_{self.player_id}"
        self.active_sessions = {}

        # Log in test user if authentication endpoint is available
        self.client.post("/login", data={
            "username": "CyberTester",
            "password": "SecretPass123!"
        }, catch_response=True)

    @task(5)
    def fetch_live_leaderboard(self):
        """Microsecond Redis ZSET leaderboard query."""
        game = random.choice(self.GAMES)
        with self.client.get(
            f"/api/leaderboard/{game}",
            catch_response=True,
            name="/api/leaderboard/[game]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Leaderboard query failed: HTTP {response.status_code}")

    @task(3)
    def play_and_submit_score_v2(self):
        """Full cryptographic handshake and verified score submission."""
        game = random.choice(self.GAMES)

        # 1. Start Session Handshake
        start_res = self.client.post(
            "/api/v2/session/start",
            json={"game_slug": game},
            catch_response=True,
            name="/api/v2/session/start"
        )
        if start_res.status_code != 200:
            return

        data = start_res.json()
        token = data.get("session_token")

        # 2. Simulate realistic gameplay duration (3 to 10 seconds)
        duration_s = random.uniform(3.0, 10.0)
        max_rates = {"flappybird": 2.0, "2048": 30.0, "speedtype": 10.0, "neon-cyber-racer": 80.0}
        rate = max_rates.get(game, 20.0)
        legit_score = int(duration_s * random.uniform(0.5, rate))

        # Adjust start time to simulate the elapsed gameplay time
        simulated_start_ms = data.get("start_time_ms") or (int(time.time() * 1000) - int(duration_s * 1000))

        # 3. Submit Cryptographically Verified Score
        with self.client.post(
            "/api/v2/session/end",
            json={
                "game_slug": game,
                "score": max(1, legit_score),
                "session_token": token,
                "start_time_ms": simulated_start_ms,
                "action_count": int(duration_s * 4)
            },
            catch_response=True,
            name="/api/v2/session/end [legit]"
        ) as res:
            if res.status_code in (200, 201):
                res.success()
            else:
                res.failure(f"Verified submission failed: HTTP {res.status_code} {res.text}")

    @task(1)
    def attempt_cheat_score_injection(self):
        """Simulate an attacker attempting to submit an impossible score."""
        game = "flappybird"
        # Start valid session
        start_res = self.client.post("/api/v2/session/start", json={"game_slug": game})
        if start_res.status_code != 200:
            return

        token = start_res.json().get("session_token")
        recent_start_ms = int(time.time() * 1000) - 1000  # 1 second ago

        # Attacker injects 99,999,999 points
        with self.client.post(
            "/api/v2/session/end",
            json={
                "game_slug": game,
                "score": 99999999,
                "session_token": token,
                "start_time_ms": recent_start_ms
            },
            catch_response=True,
            name="/api/v2/session/end [cheat attempt]"
        ) as res:
            # Server MUST reject this with 422 Unprocessable Entity
            if res.status_code == 422:
                res.success()
            else:
                res.failure(f"Anti-Cheat failed to catch anomalous score! Received HTTP {res.status_code}")

