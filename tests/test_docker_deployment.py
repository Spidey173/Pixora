"""Automated verification suite for Docker & Docker Compose VPS Deployment.

Ensures that the multi-container architecture (Gateway + Redis + Worker + Postgres + Web)
is correctly configured, valid, and meets continuous WebSocket and Redis Stream execution requirements.
"""
import os


def test_dockerfile_configuration():
    """Verify Dockerfile contains optimal production setup and security layers."""
    dockerfile_path = os.path.join(os.path.dirname(__file__), '..', 'Dockerfile')
    assert os.path.isfile(dockerfile_path), "Dockerfile must exist at repository root."

    with open(dockerfile_path, 'r', encoding='utf-8') as f:
        content = f.read()

    assert "FROM python:3.11-slim" in content, "Should use python:3.11-slim base image."
    assert "WORKDIR /app" in content, "Working directory should be /app."
    assert "COPY requirements.txt" in content, "Must copy requirements.txt before code for caching."
    assert "pip install" in content, "Must install Python dependencies."
    assert "useradd" in content or "USER" in content, "Must configure non-root user."
    assert "EXPOSE 5000 8000" in content or ("5000" in content and "8000" in content), "Must expose web and gateway ports."


def test_dockerignore_configuration():
    """Verify .dockerignore prevents large, temporary, or sensitive files from entering image."""
    dockerignore_path = os.path.join(os.path.dirname(__file__), '..', '.dockerignore')
    assert os.path.isfile(dockerignore_path), ".dockerignore must exist at repository root."

    with open(dockerignore_path, 'r', encoding='utf-8') as f:
        content = f.read()

    critical_ignores = [".venv", "__pycache__", ".git", "*.db", "node_modules"]
    for pattern in critical_ignores:
        assert pattern in content, f".dockerignore must ignore '{pattern}'."


def test_docker_compose_services():
    """Verify docker-compose.yml defines Gateway, Worker, Redis, Postgres, and Web services."""
    compose_path = os.path.join(os.path.dirname(__file__), '..', 'docker-compose.yml')
    assert os.path.isfile(compose_path), "docker-compose.yml must exist at repository root."

    with open(compose_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Required services
    required_services = ["postgres:", "redis:", "gateway:", "worker:", "web:"]
    for srv in required_services:
        assert srv in content, f"docker-compose.yml must define service '{srv}'"

    # Required volumes
    assert "postgres_data:" in content, "docker-compose.yml must have postgres_data volume"
    assert "redis_data:" in content, "docker-compose.yml must have redis_data volume"

    # Continuous running requirements
    assert "uvicorn gateway:app" in content, "Gateway service must launch uvicorn ASGI"
    assert "python worker.py" in content, "Worker service must launch telemetry stream worker"
    assert "redis-server --appendonly yes" in content, "Redis should run with AOF persistence"

    # Healthchecks & Dependencies
    assert "pg_isready" in content, "Postgres service must have a healthcheck"
    assert "redis-cli" in content, "Redis service must have a healthcheck"
    assert "condition: service_healthy" in content, "Services should wait for healthy dependencies"


def test_flask_health_endpoints(client):
    """Verify both /api/health and /health endpoints respond with healthy status."""
    for endpoint in ['/health', '/api/health']:
        response = client.get(endpoint)
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None
        assert data.get('status') == 'healthy'
        assert 'database' in data


def test_gateway_healthcheck_definition():
    """Verify gateway.py defines health endpoints for container liveness probes."""
    gateway_path = os.path.join(os.path.dirname(__file__), '..', 'gateway.py')
    with open(gateway_path, 'r', encoding='utf-8') as f:
        content = f.read()

    assert '@app.get("/health")' in content or "@app.get('/health')" in content, "gateway.py must define /health"
    assert "FastAPI" in content
    assert "WebSocket" in content


def test_worker_telemetry_models_integration(app):
    """Verify worker can access GameScore and GameplaySession models via Flask app context."""
    with app.app_context():
        from app.models import GameScore, GameplaySession, User, Game
        assert hasattr(GameScore, 'player_id')
        assert hasattr(GameScore, 'score')
        assert hasattr(GameplaySession, 'started_at')
        assert hasattr(GameplaySession, 'ended_at')
        assert hasattr(User, 'username')
        assert hasattr(Game, 'play_url')


def test_worker_poison_pill_batch_isolation(app):
    """Verify that a single poison pill message does not dump healthy peer records or strand PEL messages."""
    with app.app_context():
        from app.models import User, GameScore, db
        from worker import TelemetryStreamWorker

        # Create legitimate player
        legit_user = User.query.filter_by(username="batch_hero").first()
        if not legit_user:
            legit_user = User(username="batch_hero")
            legit_user.set_password("securepassword")
            db.session.add(legit_user)
            db.session.commit()

        class MockRedisStream:
            def __init__(self):
                self.dlq = []
                self.acked = []

            def xadd(self, key, fields):
                self.dlq.append((key, fields))

            def xack(self, stream, group, *msg_ids):
                self.acked.extend(msg_ids)

        mock_redis = MockRedisStream()
        worker = TelemetryStreamWorker(redis_client=mock_redis)

        # Batch contains:
        # Message 1: Valid score
        # Message 2: Poison pill (violates non-null foreign key constraint / invalid type)
        # Message 3: Valid score
        batch_messages = [
            ("1001-0", {"type": "score", "player_id": str(legit_user.id), "game_name": "2048", "score": "500"}),
            ("1002-0", {"type": "score", "player_id": "not-an-int-bad-id", "game_name": "2048", "score": "9999"}),
            ("1003-0", {"type": "score", "player_id": str(legit_user.id), "game_name": "flappybird", "score": "45"}),
        ]

        worker.redis_client = mock_redis
        # Mock xreadgroup to return this batch
        worker.redis_client.xreadgroup = lambda *args, **kwargs: [("pixora:telemetry", batch_messages)]

        processed_count = worker.process_batch(app)

        # All 3 messages must be acknowledged so nothing leaks in Redis PEL
        assert processed_count == 3
        assert "1001-0" in mock_redis.acked
        assert "1002-0" in mock_redis.acked
        assert "1003-0" in mock_redis.acked

        # Exactly 1 message routed to DLQ
        assert len(mock_redis.dlq) == 1
        dlq_stream, dlq_data = mock_redis.dlq[0]
        assert "dlq" in dlq_stream
        assert dlq_data["msg_id"] == "1002-0"

        # Valid records persisted in database
        scores = GameScore.query.filter_by(player_id=legit_user.id).all()
        assert len(scores) >= 2

