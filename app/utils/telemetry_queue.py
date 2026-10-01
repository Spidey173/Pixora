"""High-throughput asynchronous telemetry event queue and microsecond live leaderboards.

Architectural highlights:
- Ingestion Queue (Redis List / In-Memory Fallback):
  High scores and session telemetry are enqueued instantly (< 5ms) without waiting
  for relational database write locks (SQLite/PostgreSQL lock contention eliminated).
- Live Leaderboard Engine (Redis Sorted Sets ZSET):
  Instant O(log N) score insertion, top-N range queries (ZREVRANGE), and rank
  calculation (ZREVRANK) with automatic fallback and cache-warming from SQL.
- Asynchronous Daemon Worker:
  Batches incoming events (micro-batching) and commits in bulk transactions,
  minimizing connection thrashing and write amplification.
"""
import collections
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone

logger = logging.getLogger('pixora.telemetry_queue')

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False


class TelemetryQueueManager:
    """Enterprise-grade event queue manager for telemetry and gaming leaderboards."""

    def __init__(self, app=None):
        self.app = app
        self.redis_client = None
        self.redis_enabled = False
        self.is_testing = False
        self.batch_size = 25
        self.flush_interval = 0.5  # seconds
        self.worker_thread = None
        self.running = False
        self._lock = threading.RLock()

        # In-memory fallbacks when Redis is not available or disabled
        self._memory_score_queue = collections.deque()
        self._memory_session_queue = collections.deque()
        self._memory_leaderboards = collections.defaultdict(list)  # game -> list of score dicts
        self._memory_bests = collections.defaultdict(dict)  # game -> {player_id: max_score}
        self._memory_active_sessions = {}  # (player_id, game) -> {session_id, started_at}
        self._memory_dedup_starts = {}  # (player_id, game) -> timestamp

        # Telemetry metrics counters
        self.scores_ingested = 0
        self.sessions_ingested = 0
        self.scores_persisted = 0
        self.sessions_persisted = 0
        self.last_flush_time = None

        if app is not None:
            self.init_app(app)

    @property
    def key_prefix(self) -> str:
        """Namespace key prefix to isolate testing from runtime data."""
        return 'pixora:test:' if self.is_testing else 'pixora:'

    def init_app(self, app):
        """Initialize telemetry queue extension with Flask application."""
        self.app = app
        self.is_testing = app.config.get('TESTING', False)
        self.batch_size = app.config.get('TELEMETRY_BATCH_SIZE', 25)
        self.flush_interval = app.config.get('TELEMETRY_FLUSH_INTERVAL', 0.5)

        redis_url = app.config.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
        queue_enabled = app.config.get('TELEMETRY_QUEUE_ENABLED', True)

        if queue_enabled and REDIS_AVAILABLE:
            try:
                client = redis.Redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                    socket_timeout=2.0
                )
                if client.ping():
                    self.redis_client = client
                    self.redis_enabled = True
                    logger.info("⚡ TelemetryQueue: Connected to Redis at %s", redis_url)
                else:
                    self.redis_enabled = False
                    logger.warning("⚠️ TelemetryQueue: Redis ping failed; using in-memory queue fallback.")
            except Exception as err:
                self.redis_enabled = False
                logger.warning("⚠️ TelemetryQueue: Redis connection error (%s); using in-memory queue fallback.", err)
        else:
            self.redis_enabled = False
            logger.info("ℹ️ TelemetryQueue: Operating in in-memory event queue mode.")

        # Start asynchronous worker daemon (only if not already running and not purely synchronous in unit tests)
        if not self.running and not self.is_testing:
            self.running = True
            self.worker_thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="PixoraTelemetryWorker"
            )
            self.worker_thread.start()
            logger.info("🚀 TelemetryQueue: Daemon worker thread started (batch_size=%d, interval=%.2fs)",
                        self.batch_size, self.flush_interval)

    def reset(self):
        """Reset all in-memory queues and clean Redis test keys (guarantees test isolation)."""
        with self._lock:
            self._memory_score_queue.clear()
            self._memory_session_queue.clear()
            self._memory_leaderboards.clear()
            self._memory_bests.clear()
            self._memory_active_sessions.clear()
            self._memory_dedup_starts.clear()
            self.scores_ingested = 0
            self.sessions_ingested = 0
            self.scores_persisted = 0
            self.sessions_persisted = 0

        if self.redis_enabled and self.redis_client:
            try:
                pattern = f"{self.key_prefix}*"
                keys = list(self.redis_client.scan_iter(match=pattern, count=100))
                if keys:
                    self.redis_client.delete(*keys)
            except Exception as err:
                logger.warning("Redis reset keys error: %s", err)

    # ─────────────────────────────────────────────────────────────
    # INGESTION API: HIGH SCORES
    # ─────────────────────────────────────────────────────────────

    def enqueue_score(self, player_id: int, username: str, game_name: str, score: int) -> dict:
        """Enqueue high score submission into event queue and live sorted set."""
        now_utc = datetime.now(timezone.utc)
        clean_game = game_name.strip()
        event_id = uuid.uuid4().hex[:10]

        score_data = {
            'id': event_id,
            'player_id': player_id,
            'username': username or 'Guest',
            'game_name': clean_game,
            'score': int(score),
            'achieved_at': now_utc.isoformat()
        }

        # 1. Update Live Microsecond Leaderboard (Redis ZSET or in-memory)
        self._update_live_leaderboard(clean_game, player_id, username, int(score), score_data)

        # 2. Push to asynchronous ingestion queue
        with self._lock:
            self.scores_ingested += 1

        if self.redis_enabled and self.redis_client:
            try:
                self.redis_client.lpush(f'{self.key_prefix}queue:scores', json.dumps(score_data))
            except Exception as err:
                logger.error("Redis queue push failed: %s; falling back to memory queue", err)
                with self._lock:
                    self._memory_score_queue.append(score_data)
        else:
            with self._lock:
                self._memory_score_queue.append(score_data)

        # In testing mode, flush immediately to satisfy synchronous test assertions
        if self.is_testing:
            self.flush()

        return score_data

    def _update_live_leaderboard(self, game_name: str, player_id: int, username: str, score: int, entry_dict: dict):
        """Update live sorted sets in Redis or in-memory structures."""
        if self.redis_enabled and self.redis_client:
            try:
                pipe = self.redis_client.pipeline()
                pipe.zadd(f'{self.key_prefix}lb:entries:{game_name}', {json.dumps(entry_dict): score})
                pipe.zadd(f'{self.key_prefix}lb:bests:{game_name}', {f'{player_id}:{username}': score}, gt=True)
                pipe.execute()
                return
            except Exception as err:
                logger.warning("Redis leaderboard update failed: %s", err)

        # In-memory fallback
        with self._lock:
            entries = self._memory_leaderboards[game_name]
            entries.append(entry_dict)
            entries.sort(key=lambda x: x['score'], reverse=True)
            if len(entries) > 100:
                self._memory_leaderboards[game_name] = entries[:100]

            curr_best = self._memory_bests[game_name].get(player_id, 0)
            if score > curr_best:
                self._memory_bests[game_name][player_id] = score

    # ─────────────────────────────────────────────────────────────
    # INGESTION API: SESSION TELEMETRY
    # ─────────────────────────────────────────────────────────────

    def enqueue_session_start(self, player_id: int, game_name: str) -> tuple[bool, str, dict]:
        """Enqueue game session start event with high-speed sub-millisecond deduplication."""
        now_utc = datetime.now(timezone.utc)
        clean_game = game_name.strip()
        now_ts = now_utc.timestamp()

        # Check deduplication (within 2.0s)
        if self.redis_enabled and self.redis_client:
            try:
                dedup_key = f'{self.key_prefix}dedup:start:{player_id}:{clean_game}'
                is_fresh = self.redis_client.set(dedup_key, '1', nx=True, ex=2)
                if not is_fresh:
                    return True, 'deduped', {'status': 'deduped', 'game': clean_game}
            except Exception as err:
                logger.warning("Redis dedup check error: %s", err)
        else:
            with self._lock:
                last_start = self._memory_dedup_starts.get((player_id, clean_game), 0)
                if (now_ts - last_start) < 2.0:
                    return True, 'deduped', {'status': 'deduped', 'game': clean_game}
                self._memory_dedup_starts[(player_id, clean_game)] = now_ts

        session_id = uuid.uuid4().hex[:12]
        session_event = {
            'action': 'start',
            'session_id': session_id,
            'player_id': player_id,
            'game_name': clean_game,
            'started_at': now_utc.isoformat()
        }

        # Track active session
        if self.redis_enabled and self.redis_client:
            try:
                active_key = f'{self.key_prefix}session:active:{player_id}:{clean_game}'
                self.redis_client.set(active_key, json.dumps(session_event), ex=86400)
                self.redis_client.lpush(f'{self.key_prefix}queue:sessions', json.dumps(session_event))
            except Exception as err:
                logger.error("Redis session start push failed: %s", err)
                with self._lock:
                    self._memory_active_sessions[(player_id, clean_game)] = session_event
                    self._memory_session_queue.append(session_event)
        else:
            with self._lock:
                self._memory_active_sessions[(player_id, clean_game)] = session_event
                self._memory_session_queue.append(session_event)

        with self._lock:
            self.sessions_ingested += 1

        if self.is_testing:
            self.flush()

        return False, 'logged', {'status': 'logged', 'game': clean_game, 'session_id': session_id}

    def enqueue_session_end(self, player_id: int, game_name: str) -> dict:
        """Enqueue game session end event and compute duration without DB write lock."""
        now_utc = datetime.now(timezone.utc)
        clean_game = game_name.strip()
        started_at = None
        duration_seconds = 0

        # Retrieve active session
        if self.redis_enabled and self.redis_client:
            try:
                active_key = f'{self.key_prefix}session:active:{player_id}:{clean_game}'
                raw_active = self.redis_client.get(active_key)
                if raw_active:
                    active_data = json.loads(raw_active)
                    started_str = active_data.get('started_at')
                    if started_str:
                        started_at = datetime.fromisoformat(started_str)
                    self.redis_client.delete(active_key)
            except Exception as err:
                logger.warning("Redis session end check failed: %s", err)
        else:
            with self._lock:
                active_data = self._memory_active_sessions.pop((player_id, clean_game), None)
                if active_data and active_data.get('started_at'):
                    started_at = datetime.fromisoformat(active_data['started_at'])

        if started_at:
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            duration_seconds = max(0, int((now_utc - started_at).total_seconds()))

        session_event = {
            'action': 'end',
            'player_id': player_id,
            'game_name': clean_game,
            'ended_at': now_utc.isoformat(),
            'duration_seconds': duration_seconds
        }

        if self.redis_enabled and self.redis_client:
            try:
                self.redis_client.lpush(f'{self.key_prefix}queue:sessions', json.dumps(session_event))
            except Exception:
                with self._lock:
                    self._memory_session_queue.append(session_event)
        else:
            with self._lock:
                self._memory_session_queue.append(session_event)

        with self._lock:
            self.sessions_ingested += 1

        if self.is_testing:
            self.flush()

        return {'status': 'ended', 'game': clean_game, 'duration_seconds': duration_seconds}

    # ─────────────────────────────────────────────────────────────
    # REAL-TIME LEADERBOARD RETRIEVAL (MICROSECOND LATENCY)
    # ─────────────────────────────────────────────────────────────

    def get_live_leaderboard(
        self,
        game_name: str,
        limit: int = 10,
        current_player_id: int | None = None,
        names_to_match: list[str] | None = None
    ) -> dict:
        """Fetch ultra-fast live leaderboard rankings with Redis Sorted Sets or SQL fallback."""
        clean_game = game_name.strip()
        names = names_to_match or [clean_game]

        # 1. Try Redis Sorted Sets — use lb:bests (one entry per player) for leaderboard
        if self.redis_enabled and self.redis_client:
            try:
                # lb:bests stores "player_id:username" → best_score (unique per player)
                bests_raw = self.redis_client.zrevrange(
                    f'{self.key_prefix}lb:bests:{clean_game}', 0, limit - 1, withscores=True
                )
                if bests_raw:
                    top_list = []
                    for member_key, best_score in bests_raw:
                        parts = member_key.split(':', 1)
                        pid = int(parts[0]) if parts[0].isdigit() else 0
                        uname = parts[1] if len(parts) > 1 else 'Champion'
                        top_list.append({
                            'username': uname,
                            'score': int(best_score),
                            'player_id': pid
                        })

                    # World record is simply the #1 entry
                    world_record = {
                        'score': top_list[0]['score'],
                        'username': top_list[0]['username'],
                        'achieved_at': None
                    }

                    user_best = None
                    user_rank = None
                    if current_player_id:
                        # Walk the full bests list to find current player's rank
                        all_bests = self.redis_client.zrevrange(
                            f'{self.key_prefix}lb:bests:{clean_game}', 0, -1, withscores=True
                        )
                        for r_idx, (m_key, m_score) in enumerate(all_bests):
                            if m_key.startswith(f"{current_player_id}:"):
                                user_best = int(m_score)
                                user_rank = r_idx + 1
                                break

                    total_scores = self.redis_client.zcard(f'{self.key_prefix}lb:entries:{clean_game}')

                    return {
                        'game_name': clean_game,
                        'leaderboard': top_list,
                        'user_best': user_best,
                        'world_record': world_record,
                        'user_rank': user_rank,
                        'total_scores_logged': total_scores,
                        'source': 'redis_live'
                    }
            except Exception as err:
                logger.warning("Redis get_live_leaderboard error: %s; falling back to DB", err)

        # 2. Database Fallback & Cache Warming
        return self._fetch_and_warm_db_leaderboard(clean_game, names, limit, current_player_id)

    def _fetch_and_warm_db_leaderboard(
        self,
        clean_game: str,
        names_to_match: list[str],
        limit: int,
        current_player_id: int | None
    ) -> dict:
        """Query relational database and warm Redis sorted sets for zero-latency future hits."""
        from app.models import GameScore

        all_scores = (
            GameScore.query
            .filter(GameScore.game_name.in_(names_to_match))
            .order_by(GameScore.score.desc(), GameScore.achieved_at.asc())
            .all()
        )

        # DEDUPLICATE: keep only the best score per player
        seen_players = set()
        unique_best_scores = []
        for s in all_scores:
            if s.player_id not in seen_players:
                seen_players.add(s.player_id)
                unique_best_scores.append(s)

        top_scores = unique_best_scores[:limit]
        top_list = [s.to_dict() for s in top_scores]

        world_record = None
        if unique_best_scores:
            top_s = unique_best_scores[0]
            world_record = {
                'score': top_s.score,
                'username': top_s.player.username if top_s.player else 'Guest',
                'achieved_at': top_s.achieved_at.strftime('%Y-%m-%d %H:%M') if top_s.achieved_at else None
            }

        user_best = None
        user_rank = None
        if current_player_id:
            for rank_idx, s in enumerate(unique_best_scores):
                if s.player_id == current_player_id:
                    user_best = s.score
                    user_rank = rank_idx + 1
                    break

        # Warm Redis cache with top 50 scores if Redis is alive
        if self.redis_enabled and self.redis_client and all_scores:
            try:
                pipe = self.redis_client.pipeline()
                for s in all_scores[:50]:
                    s_dict = s.to_dict()
                    pipe.zadd(f'{self.key_prefix}lb:entries:{clean_game}', {json.dumps(s_dict): s.score})
                    username = s.player.username if s.player else 'Guest'
                    pipe.zadd(f'{self.key_prefix}lb:bests:{clean_game}', {f'{s.player_id}:{username}': s.score}, gt=True)
                pipe.execute()
            except Exception as err:
                logger.warning("Failed to warm Redis leaderboard: %s", err)

        return {
            'game_name': clean_game,
            'leaderboard': top_list,
            'user_best': user_best,
            'world_record': world_record,
            'user_rank': user_rank,
            'total_scores_logged': len(all_scores),
            'source': 'database_warmed'
        }

    # ─────────────────────────────────────────────────────────────
    # ASYNCHRONOUS BACKGROUND WORKER (MICRO-BATCH COMMITS)
    # ─────────────────────────────────────────────────────────────

    def _worker_loop(self):
        """Continuous background worker draining event queues and committing batches to database."""
        while self.running:
            try:
                self.flush()
                time.sleep(self.flush_interval)
            except Exception as err:
                logger.error("Telemetry worker iteration error: %s", err)
                time.sleep(1.0)

    def flush(self):
        """Drain queues in micro-batches and persist to database atomically."""
        scores_batch = self._drain_scores_batch(self.batch_size)
        sessions_batch = self._drain_sessions_batch(self.batch_size)

        if not scores_batch and not sessions_batch:
            return

        app_context = self.app.app_context() if self.app else None
        if app_context:
            with app_context:
                self._persist_to_database(scores_batch, sessions_batch)
        else:
            self._persist_to_database(scores_batch, sessions_batch)

    def _drain_scores_batch(self, max_items: int) -> list[dict]:
        """Fetch up to max_items from score queue."""
        batch = []
        if self.redis_enabled and self.redis_client:
            try:
                pipe = self.redis_client.pipeline()
                for _ in range(max_items):
                    pipe.rpop(f'{self.key_prefix}queue:scores')
                results = pipe.execute()
                for raw in results:
                    if raw:
                        try:
                            batch.append(json.loads(raw))
                        except Exception:
                            continue
            except Exception as err:
                logger.error("Error popping from Redis score queue: %s", err)

        if len(batch) < max_items:
            with self._lock:
                while self._memory_score_queue and len(batch) < max_items:
                    batch.append(self._memory_score_queue.popleft())

        return batch

    def _drain_sessions_batch(self, max_items: int) -> list[dict]:
        """Fetch up to max_items from session queue."""
        batch = []
        if self.redis_enabled and self.redis_client:
            try:
                pipe = self.redis_client.pipeline()
                for _ in range(max_items):
                    pipe.rpop(f'{self.key_prefix}queue:sessions')
                results = pipe.execute()
                for raw in results:
                    if raw:
                        try:
                            batch.append(json.loads(raw))
                        except Exception:
                            continue
            except Exception as err:
                logger.error("Error popping from Redis session queue: %s", err)

        if len(batch) < max_items:
            with self._lock:
                while self._memory_session_queue and len(batch) < max_items:
                    batch.append(self._memory_session_queue.popleft())

        return batch

    def _persist_to_database(self, scores_batch: list[dict], sessions_batch: list[dict]):
        """Persist drained batches to SQLite/PostgreSQL in a single atomic transaction."""
        from app.extensions import db
        from app.models import GameplaySession, GameScore

        try:
            # 1. Persist Scores
            if scores_batch:
                score_objs = []
                for s in scores_batch:
                    achieved = s.get('achieved_at')
                    if isinstance(achieved, str):
                        try:
                            dt = datetime.fromisoformat(achieved)
                        except Exception:
                            dt = datetime.now(timezone.utc)
                    else:
                        dt = datetime.now(timezone.utc)

                    score_objs.append(
                        GameScore(
                            player_id=s['player_id'],
                            game_name=s['game_name'],
                            score=s['score'],
                            achieved_at=dt
                        )
                    )
                db.session.add_all(score_objs)
                with self._lock:
                    self.scores_persisted += len(score_objs)

            # 2. Persist Sessions
            if sessions_batch:
                for sess in sessions_batch:
                    action = sess.get('action')
                    player_id = sess.get('player_id')
                    game_name = sess.get('game_name')

                    if action == 'start':
                        started_str = sess.get('started_at')
                        try:
                            started_dt = datetime.fromisoformat(started_str) if started_str else datetime.now(timezone.utc)
                        except Exception:
                            started_dt = datetime.now(timezone.utc)

                        db_session = GameplaySession(
                            player_id=player_id,
                            game_name=game_name,
                            started_at=started_dt
                        )
                        db.session.add(db_session)
                        with self._lock:
                            self.sessions_persisted += 1

                    elif action == 'end':
                        # Match with active session record in DB
                        active_rec = (
                            GameplaySession.query
                            .filter_by(player_id=player_id, game_name=game_name)
                            .filter(GameplaySession.ended_at.is_(None))
                            .order_by(GameplaySession.id.desc())
                            .first()
                        )
                        ended_str = sess.get('ended_at')
                        try:
                            ended_dt = datetime.fromisoformat(ended_str) if ended_str else datetime.now(timezone.utc)
                        except Exception:
                            ended_dt = datetime.now(timezone.utc)

                        if active_rec:
                            active_rec.ended_at = ended_dt
                            duration = sess.get('duration_seconds')
                            if duration is not None:
                                active_rec.duration_seconds = duration
                            elif active_rec.started_at:
                                sat = active_rec.started_at
                                if sat.tzinfo is None:
                                    sat = sat.replace(tzinfo=timezone.utc)
                                eat = active_rec.ended_at
                                if eat.tzinfo is None:
                                    eat = eat.replace(tzinfo=timezone.utc)
                                active_rec.duration_seconds = max(0, int((eat - sat).total_seconds()))
                        else:
                            fallback_sess = GameplaySession(
                                player_id=player_id,
                                game_name=game_name,
                                started_at=ended_dt,
                                ended_at=ended_dt,
                                duration_seconds=sess.get('duration_seconds', 0)
                            )
                            db.session.add(fallback_sess)

                        with self._lock:
                            self.sessions_persisted += 1

            db.session.commit()
            self.last_flush_time = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
            logger.debug("TelemetryQueue: Flushed %d scores, %d sessions to database",
                         len(scores_batch), len(sessions_batch))
        except Exception as err:
            db.session.rollback()
            logger.error("TelemetryQueue: Database commit error: %s", err)
            with self._lock:
                for s in scores_batch:
                    self._memory_score_queue.append(s)
                for sess in sessions_batch:
                    self._memory_session_queue.append(sess)

    # ─────────────────────────────────────────────────────────────
    # TELEMETRY STATUS & HEALTH METRICS
    # ─────────────────────────────────────────────────────────────

    def get_metrics(self) -> dict:
        """Return operational telemetry metrics for Admin Mission Control Dashboard."""
        score_q_len = 0
        session_q_len = 0
        redis_status = "OFFLINE (Using In-Memory Fallback)"

        if self.redis_enabled and self.redis_client:
            try:
                score_q_len = self.redis_client.llen(f'{self.key_prefix}queue:scores')
                session_q_len = self.redis_client.llen(f'{self.key_prefix}queue:sessions')
                redis_status = "ONLINE (Cluster Active)"
            except Exception:
                redis_status = "DEGRADED (Redis Unreachable)"

        with self._lock:
            score_q_len += len(self._memory_score_queue)
            session_q_len += len(self._memory_session_queue)

            return {
                'mode': 'REDIS + IN-MEMORY' if self.redis_enabled else 'IN-MEMORY EVENT QUEUE',
                'redis_status': redis_status,
                'redis_connected': self.redis_enabled,
                'queue_depth_scores': score_q_len,
                'queue_depth_sessions': session_q_len,
                'total_queue_depth': score_q_len + session_q_len,
                'scores_ingested': self.scores_ingested,
                'sessions_ingested': self.sessions_ingested,
                'scores_persisted': self.scores_persisted,
                'sessions_persisted': self.sessions_persisted,
                'batch_size': self.batch_size,
                'flush_interval': self.flush_interval,
                'worker_alive': self.worker_thread.is_alive() if self.worker_thread else False,
                'last_flush_time': self.last_flush_time or 'Pending First Batch'
            }


telemetry_queue = TelemetryQueueManager()
