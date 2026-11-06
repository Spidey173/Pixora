"""Distributed Telemetry Ingestion Worker for Pixora 2.0.

Solves Fatal Flaw #2 (Daemon threading under multi-process Gunicorn) by running
as an independent background worker decoupled from the web application.

Architecture:
- Redis Streams: 'pixora:telemetry'
- Consumer Group: 'pixora_telemetry_group'
- Reliable Delivery: Consumer-group read (XREADGROUP) + explicit ACK (XACK)
- Dead Letter Queue: 'pixora:telemetry:dlq' for malformed or failed writes
- Micro-batch Bulk Writes into PostgreSQL / SQLite

Usage:
    python worker.py --worker-name=worker-1 --batch-size=50
"""
import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
)
logger = logging.getLogger('pixora.worker')

STREAM_KEY = os.environ.get('TELEMETRY_STREAM_KEY', 'pixora:telemetry')
GROUP_NAME = os.environ.get('TELEMETRY_GROUP_NAME', 'pixora_telemetry_group')
DLQ_KEY = os.environ.get('TELEMETRY_DLQ_KEY', 'pixora:telemetry:dlq')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')


class TelemetryStreamWorker:
    def __init__(self, worker_name="worker-1", batch_size=50, poll_timeout_ms=2000):
        self.worker_name = worker_name
        self.batch_size = batch_size
        self.poll_timeout_ms = poll_timeout_ms
        self.running = True
        self.redis_client = None

        if not REDIS_AVAILABLE:
            logger.error("Redis library is not installed. Worker cannot start.")
            sys.exit(1)

        self.redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        self._ensure_stream_and_group()

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info("Shutdown signal received (%s). Draining and stopping worker...", signum)
        self.running = False

    def _ensure_stream_and_group(self, max_retries: int = 15, retry_delay: float = 2.0):
        """Ensure Redis stream and consumer group exist, retrying on startup if Redis is initializing."""
        for attempt in range(1, max_retries + 1):
            try:
                self.redis_client.ping()
                try:
                    self.redis_client.xgroup_create(STREAM_KEY, GROUP_NAME, id="0", mkstream=True)
                    logger.info("Created Consumer Group '%s' on Stream '%s'", GROUP_NAME, STREAM_KEY)
                except redis.exceptions.ResponseError as e:
                    if "BUSYGROUP" in str(e):
                        logger.info("Consumer Group '%s' already exists on Stream '%s'", GROUP_NAME, STREAM_KEY)
                    else:
                        logger.error("Error creating consumer group: %s", e)
                        raise
                return
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as conn_err:
                if attempt == max_retries:
                    logger.critical("Failed to connect to Redis at %s after %d attempts: %s", REDIS_URL, max_retries, conn_err)
                    raise
                logger.warning("Redis connection attempt %d/%d failed: %s. Retrying in %.1fs...", attempt, max_retries, conn_err, retry_delay)
                time.sleep(retry_delay)

    def process_batch(self, app):
        """Read and process a batch of telemetry events."""
        from app.extensions import db
        from app.models import GameScore, GameplaySession

        # Read pending messages using consumer group
        try:
            entries = self.redis_client.xreadgroup(
                GROUP_NAME,
                self.worker_name,
                {STREAM_KEY: ">"},
                count=self.batch_size,
                block=self.poll_timeout_ms
            )
        except Exception as err:
            logger.error("Error reading from Redis Stream: %s", err)
            time.sleep(1)
            return 0

        if not entries:
            return 0

        stream_name, messages = entries[0]
        if not messages:
            return 0

        acked_ids = []
        score_records = []
        session_records = []
        dlq_records = []

        with app.app_context():
            for msg_id, payload in messages:
                try:
                    event_type = payload.get("type", "score")
                    player_id = int(payload.get("player_id"))
                    game_name = payload.get("game_name", "").strip()

                    if event_type == "score":
                        score_val = int(payload.get("score", 0))
                        ts_str = payload.get("achieved_at")
                        try:
                            achieved_dt = datetime.fromisoformat(ts_str) if ts_str else datetime.now(timezone.utc)
                        except Exception:
                            achieved_dt = datetime.now(timezone.utc)

                        score_records.append(GameScore(
                            player_id=player_id,
                            game_name=game_name,
                            score=score_val,
                            achieved_at=achieved_dt
                        ))
                    elif event_type in ("session", "gameplay", "session_end"):
                        started_str = payload.get("started_at")
                        ended_str = payload.get("ended_at")
                        duration_sec = int(payload.get("duration_seconds", 0))
                        try:
                            started_dt = datetime.fromisoformat(started_str) if started_str else datetime.now(timezone.utc)
                        except Exception:
                            started_dt = datetime.now(timezone.utc)
                        try:
                            ended_dt = datetime.fromisoformat(ended_str) if ended_str else datetime.now(timezone.utc)
                        except Exception:
                            ended_dt = datetime.now(timezone.utc)

                        session_records.append(GameplaySession(
                            player_id=player_id,
                            game_name=game_name,
                            started_at=started_dt,
                            ended_at=ended_dt,
                            duration_seconds=duration_sec
                        ))
                    acked_ids.append(msg_id)

                except Exception as ex:
                    logger.error("Failed to parse event %s: %s", msg_id, ex)
                    dlq_records.append((msg_id, payload, str(ex)))

            # Batch insert to DB
            if score_records or session_records:
                try:
                    if score_records:
                        db.session.add_all(score_records)
                    if session_records:
                        db.session.add_all(session_records)
                    db.session.commit()
                    logger.info("Committed batch (%d scores, %d sessions) to database", len(score_records), len(session_records))
                except Exception as db_err:
                    db.session.rollback()
                    logger.critical("Database batch commit failed: %s", db_err)
                    # Route to DLQ
                    for msg_id, payload in messages:
                        self.redis_client.xadd(DLQ_KEY, {"payload": json.dumps(payload), "error": str(db_err)})
                    return 0

            # Route individual bad payloads to DLQ
            for msg_id, payload, err_msg in dlq_records:
                self.redis_client.xadd(DLQ_KEY, {"msg_id": msg_id, "payload": json.dumps(payload), "error": err_msg})
                acked_ids.append(msg_id)

            # Acknowledge processed messages
            if acked_ids:
                self.redis_client.xack(STREAM_KEY, GROUP_NAME, *acked_ids)

        return len(acked_ids)

    def run(self):
        """Main worker execution loop."""
        from app import create_app
        env = os.environ.get('FLASK_ENV', 'production')
        app = create_app(env)

        logger.info("🚀 Telemetry Worker '%s' running on Stream '%s'", self.worker_name, STREAM_KEY)

        while self.running:
            try:
                processed = self.process_batch(app)
                if processed == 0:
                    time.sleep(0.1)
            except Exception as e:
                logger.error("Worker unhandled exception: %s", e)
                time.sleep(1.0)

        logger.info("Telemetry Worker '%s' stopped cleanly.", self.worker_name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Pixora Telemetry Stream Worker")
    parser.add_argument("--worker-name", default=f"worker-{os.getpid()}", help="Consumer worker unique name")
    parser.add_argument("--batch-size", type=int, default=50, help="Max batch size to read")
    args = parser.parse_args()

    worker = TelemetryStreamWorker(worker_name=args.worker_name, batch_size=args.batch_size)
    worker.run()

