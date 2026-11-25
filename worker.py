"""Background worker that reads game scores from Redis and writes them to the database.

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

from app.utils.game_resolver import canonical_game_title
from app.utils.redis_keys import get_dlq_key, get_stream_group_name, get_stream_key, redis_key

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
)
logger = logging.getLogger('pixora.worker')

REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')


class TelemetryStreamWorker:
    def __init__(self, worker_name="worker-1", batch_size=50, poll_timeout_ms=2000, redis_client=None):
        self.worker_name = worker_name
        self.batch_size = batch_size
        self.poll_timeout_ms = poll_timeout_ms
        self.running = True
        self.redis_client = redis_client

        if self.redis_client is None:
            if not REDIS_AVAILABLE:
                logger.error("Redis library is not installed. Worker cannot start.")
                sys.exit(1)

            self.redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            self._ensure_stream_and_group()

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    @property
    def stream_key(self) -> str:
        return get_stream_key()

    @property
    def group_name(self) -> str:
        return get_stream_group_name()

    @property
    def dlq_key(self) -> str:
        return get_dlq_key()

    def _handle_shutdown(self, signum, frame):
        logger.info("Shutdown signal received (%s). Draining and stopping worker...", signum)
        self.running = False

    def _refresh_heartbeat(self):
        """Publish short-lived heartbeat so gateway knows a stream consumer is active."""
        try:
            if self.redis_client and hasattr(self.redis_client, "set"):
                self.redis_client.set(redis_key("worker:active"), self.worker_name, ex=15)
        except Exception:
            pass

    def _ensure_stream_and_group(self, max_retries: int = 15, retry_delay: float = 2.0):
        """Ensure Redis stream and consumer group exist, retrying on startup if Redis is initializing."""
        stream_key = self.stream_key
        group_name = self.group_name
        for attempt in range(1, max_retries + 1):
            try:
                self.redis_client.ping()
                try:
                    self.redis_client.xgroup_create(stream_key, group_name, id="0", mkstream=True)
                    logger.info("Created Consumer Group '%s' on Stream '%s'", group_name, stream_key)
                except redis.exceptions.ResponseError as e:
                    if "BUSYGROUP" in str(e):
                        logger.info("Consumer Group '%s' already exists on Stream '%s'", group_name, stream_key)
                    else:
                        logger.error("Error creating consumer group: %s", e)
                        raise
                self._refresh_heartbeat()
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

        stream_key = self.stream_key
        group_name = self.group_name
        dlq_key = self.dlq_key

        self._refresh_heartbeat()

        # Read pending messages using consumer group
        try:
            entries = self.redis_client.xreadgroup(
                group_name,
                self.worker_name,
                {stream_key: ">"},
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
        parsed_entries = []  # List of tuples: (msg_id, payload, record)
        dlq_records = []

        with app.app_context():
            for msg_id, payload in messages:
                try:
                    # Skip DB write if gateway already persisted synchronously in fallback mode
                    if str(payload.get("db_persisted", "0")) == "1":
                        acked_ids.append(msg_id)
                        continue

                    event_type = payload.get("type", "score")
                    player_id = int(payload.get("player_id"))
                    raw_game = payload.get("game_name", "").strip()
                    game_name = canonical_game_title(raw_game) or raw_game

                    if event_type == "score":
                        score_val = int(payload.get("score", 0))
                        ts_str = payload.get("achieved_at")
                        try:
                            achieved_dt = datetime.fromisoformat(ts_str) if ts_str else datetime.now(timezone.utc)
                        except Exception:
                            achieved_dt = datetime.now(timezone.utc)

                        record = GameScore(
                            player_id=player_id,
                            game_name=game_name,
                            score=score_val,
                            achieved_at=achieved_dt
                        )
                        parsed_entries.append((msg_id, payload, record))
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

                        record = GameplaySession(
                            player_id=player_id,
                            game_name=game_name,
                            started_at=started_dt,
                            ended_at=ended_dt,
                            duration_seconds=duration_sec
                        )
                        parsed_entries.append((msg_id, payload, record))
                    else:
                        # Unknown event type, acknowledge message
                        acked_ids.append(msg_id)

                except Exception as ex:
                    logger.error("Failed to parse event %s: %s", msg_id, ex)
                    dlq_records.append((msg_id, payload, str(ex)))

            # Save records in batch; if an error occurs, save each valid record individually
            committed_records = []
            if parsed_entries:
                try:
                    for _, _, rec in parsed_entries:
                        db.session.add(rec)
                    db.session.commit()
                    acked_ids.extend([m_id for m_id, _, _ in parsed_entries])
                    committed_records.extend(parsed_entries)
                    logger.info("Committed batch (%d events) successfully", len(parsed_entries))
                except Exception as batch_err:
                    db.session.rollback()
                    logger.warning("Batch commit failed: %s. Saving records individually...", batch_err)

                    for m_id, m_payload, rec in parsed_entries:
                        try:
                            db.session.add(rec)
                            db.session.commit()
                            acked_ids.append(m_id)
                            committed_records.append((m_id, m_payload, rec))
                        except Exception as item_err:
                            db.session.rollback()
                            logger.error("Failed to save msg %s: %s", m_id, item_err)
                            dlq_records.append((m_id, m_payload, str(item_err)))

            # Ensure Redis ZSETs reflect committed score records
            if committed_records and hasattr(self.redis_client, "pipeline"):
                try:
                    pipe = self.redis_client.pipeline()
                    for _, m_payload, rec in committed_records:
                        if isinstance(rec, GameScore):
                            uname = m_payload.get("username") or (rec.player.username if rec.player else "Guest")
                            pipe.zadd(redis_key(f"lb:bests:{rec.game_name}"), {f"{rec.player_id}:{uname}": rec.score}, gt=True)
                    pipe.execute()
                except Exception as z_err:
                    logger.debug("Worker Redis ZSET sync skipped: %s", z_err)

            # Send failed messages to dead-letter queue
            for msg_id, payload, err_msg in dlq_records:
                try:
                    self.redis_client.xadd(dlq_key, {"msg_id": str(msg_id), "payload": json.dumps(payload), "error": str(err_msg)})
                except Exception as q_err:
                    logger.error("Failed to write to DLQ for msg %s: %s", msg_id, q_err)
                acked_ids.append(msg_id)

            # Acknowledge processed messages in Redis
            if acked_ids:
                try:
                    self.redis_client.xack(stream_key, group_name, *acked_ids)
                except Exception as ack_err:
                    logger.error("Error executing xack on stream: %s", ack_err)

        return len(acked_ids)

    def run(self):
        """Main worker execution loop."""
        from app import create_app
        env = os.environ.get('FLASK_ENV', 'production')
        app = create_app(env)

        logger.info("Telemetry worker '%s' started on stream '%s'", self.worker_name, self.stream_key)

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
