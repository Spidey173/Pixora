"""Pixora FastAPI server and WebSocket gateway."""
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

try:
    from fastapi import (
        FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status,
        Request, Response, Depends, Header, Cookie
    )
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

try:
    import redis.asyncio as aioredis
    AIOREDIS_AVAILABLE = True
except ImportError:
    aioredis = None
    AIOREDIS_AVAILABLE = False

from app.services.anti_cheat import AntiCheatValidator
from app.utils.game_resolver import canonical_game_title
from app.utils.redis_keys import get_stream_key, redis_key

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("pixora.gateway")

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Pixora",
        description="Arcade gaming platform API and WebSockets",
        version="1.0.0",
        lifespan=lambda app_instance: lifespan(app_instance)
    )

    # Allowed origins for CORS and WebSockets
    DEFAULT_ALLOWED_ORIGINS = [
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://pub-bbadfb1090074e17b2f5293b549ce094.r2.dev"
    ]
    custom_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    ALLOWED_ORIGINS = list(set(DEFAULT_ALLOWED_ORIGINS + custom_origins))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS if os.environ.get("FLASK_ENV") != "testing" else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # WebSocket and presence manager
    class WebSocketManager:
        """Tracks active WebSockets and broadcasts game events."""

        def __init__(self):
            # Map of game_slug -> list of connected WebSockets
            self.active_connections: Dict[str, List[WebSocket]] = {}
            self._lock = asyncio.Lock()

        async def connect(self, game_slug: str, websocket: WebSocket):
            await websocket.accept()
            async with self._lock:
                if game_slug not in self.active_connections:
                    self.active_connections[game_slug] = []
                self.active_connections[game_slug].append(websocket)
            logger.info("WebSocket connected for '%s' (total: %d)", game_slug, len(self.active_connections[game_slug]))

        async def disconnect(self, game_slug: str, websocket: WebSocket):
            async with self._lock:
                if game_slug in self.active_connections:
                    if websocket in self.active_connections[game_slug]:
                        self.active_connections[game_slug].remove(websocket)
                    if not self.active_connections[game_slug]:
                        del self.active_connections[game_slug]

        async def broadcast_local(self, game_slug: str, message: dict):
            """Fan out message to WebSockets connected to this specific worker process."""
            payload = json.dumps(message)
            async with self._lock:
                connections = list(self.active_connections.get(game_slug, []))
            for ws in connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    pass

        async def broadcast_distributed(self, game_slug: str, message: dict, redis=None):
            """Publish event to Redis Pub/Sub so ALL Uvicorn worker processes broadcast to their clients."""
            payload = dict(message)
            if "game" not in payload:
                payload["game"] = game_slug
            if redis:
                try:
                    payload_json = json.dumps(payload)
                    await redis.publish(redis_key("ws:broadcast"), payload_json)
                    await redis.publish(redis_key(f"events:{game_slug}"), payload_json)
                    return
                except Exception as err:
                    logger.warning("Redis Pub/Sub broadcast error: %s; falling back to local fanout", err)
            await self.broadcast_local(game_slug, payload)

        # Multi-worker local broadcast alias
        local_broadcast = broadcast_local

        # Backward compatibility alias
        async def broadcast_to_game(self, game_slug: str, message: dict):
            await self.broadcast_local(game_slug, message)

        def get_local_presence(self, game_slug: str) -> int:
            return len(self.active_connections.get(game_slug, []))

        # Backward compatibility alias
        def get_presence(self, game_slug: str) -> int:
            return self.get_local_presence(game_slug)

        async def update_presence_connect(self, game_slug: str, redis=None) -> int:
            """Increment distributed presence in Redis across all workers."""
            if redis:
                try:
                    count = await redis.hincrby(redis_key("presence"), game_slug, 1)
                    return max(1, int(count))
                except Exception as err:
                    logger.warning("Redis presence increment warning: %s", err)
            return max(1, self.get_local_presence(game_slug))

        async def update_presence_disconnect(self, game_slug: str, redis=None) -> int:
            """Decrement distributed presence in Redis across all workers."""
            if redis:
                try:
                    presence_key = redis_key("presence")
                    count = await redis.hincrby(presence_key, game_slug, -1)
                    if count < 0:
                        await redis.hset(presence_key, game_slug, 0)
                        count = 0
                    return count
                except Exception as err:
                    logger.warning("Redis presence decrement warning: %s", err)
            return self.get_local_presence(game_slug)

        async def get_global_presence(self, game_slug: str, redis=None) -> int:
            """Fetch authoritative presence across all worker instances."""
            if redis:
                try:
                    val = await redis.hget(redis_key("presence"), game_slug)
                    if val is not None:
                        return max(1, int(val))
                except Exception as err:
                    logger.warning("Redis presence fetch warning: %s", err)
            return max(1, self.get_local_presence(game_slug))

    ws_manager = WebSocketManager()

    # Request schemas and authentication
    class AuthenticatedPlayer(BaseModel):
        id: int
        username: str

    async def get_current_player(
        request: Request,
        authorization: Optional[str] = Header(None),
        session: Optional[str] = Cookie(None)
    ) -> AuthenticatedPlayer:
        """Authenticate player using Bearer token or session cookie."""
        # 1. Bearer Token Authentication
        if authorization:
            parts = authorization.strip().split(" ", 1)
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token_data = AntiCheatValidator.verify_player_token(parts[1])
                if token_data and "player_id" in token_data:
                    pid = int(token_data["player_id"])
                    uname = str(token_data.get("username", "Player"))
                    try:
                        from app.extensions import db
                        from app.models import User
                        db_user = db.session.get(User, pid)
                        if db_user and db_user.username:
                            uname = db_user.username
                    except Exception:
                        pass
                    return AuthenticatedPlayer(id=pid, username=uname)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "Invalid or expired authorization token", "code": "UNAUTHORIZED"}
            )

        # 2. Flask Signed Session Cookie Authentication
        cookie_val = session or request.cookies.get("session")
        if cookie_val:
            sess_data = AntiCheatValidator.decode_flask_session(cookie_val)
            if sess_data and "_user_id" in sess_data:
                pid = int(sess_data["_user_id"])
                uname = str(sess_data.get("pilot_username", "Player"))
                try:
                    from app.extensions import db
                    from app.models import User
                    db_user = db.session.get(User, pid)
                    if db_user and db_user.username:
                        uname = db_user.username
                except Exception:
                    pass
                return AuthenticatedPlayer(id=pid, username=uname)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "code": "UNAUTHORIZED"}
        )

    class SessionStartRequest(BaseModel):
        game_slug: str
        player_id: Optional[int] = None   # Validated against authenticated token to prevent spoofing
        username: Optional[str] = None

    class SessionStartResponse(BaseModel):
        status: str = "success"
        session_token: str
        start_time_ms: int
        game_slug: str
        player_id: int
        username: str

    class ScoreSubmissionRequest(BaseModel):
        game_slug: str
        score: int
        session_token: str
        start_time_ms: int
        duration_ms: Optional[int] = None
        action_count: Optional[int] = None
        input_entropy_hash: Optional[str] = None
        player_id: Optional[int] = None   # Validated against authenticated token to prevent spoofing
        username: Optional[str] = None

    class ScoreSubmissionResponse(BaseModel):
        status: str = "success"
        verified: bool = True
        rank: Optional[int] = None
        message: str
        score: Optional[dict] = None

    # Redis setup and background listener
    redis_client = None

    async def redis_pubsub_listener():
        """Listen to Redis Pub/Sub events and broadcast via WebSockets across all Uvicorn workers."""
        if not redis_client:
            return
        try:
            pubsub = redis_client.pubsub()
            ws_channel = redis_key("ws:broadcast")
            events_pattern = redis_key("events:*")
            await pubsub.subscribe(ws_channel)
            await pubsub.psubscribe(events_pattern)
            logger.info("Subscribed to Redis Pub/Sub channels '%s' and '%s'", ws_channel, events_pattern)
            async for msg in pubsub.listen():
                if not msg:
                    continue
                if msg["type"] == "message" and msg.get("data"):
                    try:
                        event_data = json.loads(msg["data"])
                        game_slug = event_data.get("game") or event_data.get("game_slug") or "all"
                        await ws_manager.local_broadcast(game_slug, event_data)
                    except Exception as err:
                        logger.error("PubSub message error: %s", err)
                elif msg["type"] == "pmessage" and msg.get("data"):
                    channel = msg.get("channel", "")
                    game_slug = channel.split(":")[-1]
                    try:
                        event_data = json.loads(msg["data"])
                        await ws_manager.local_broadcast(game_slug, event_data)
                    except Exception as err:
                        logger.error("PubSub pmessage error: %s", err)
        except Exception as e:
            logger.warning("PubSub listener stopped: %s", e)

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        global redis_client
        from app.config import settings, validate_secrets
        from app.utils.telemetry_queue import telemetry_queue

        validate_secrets(settings)
        is_pytest = "PYTEST_CURRENT_TEST" in os.environ or os.environ.get("FLASK_ENV") == "testing"
        if not hasattr(app_instance, "config"):
            app_instance.config = {
                k: getattr(settings, k)
                for k in dir(settings)
                if not k.startswith("_")
            }
        if is_pytest:
            app_instance.config["TESTING"] = True
        telemetry_queue.init_app(app_instance)

        pubsub_task = None
        if AIOREDIS_AVAILABLE and os.environ.get("FLASK_ENV") != "testing":
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
                    await redis_client.ping()
                    logger.info("Connected to Redis at %s", REDIS_URL)
                    pubsub_task = asyncio.create_task(redis_pubsub_listener())
                    break
                except Exception as e:
                    logger.warning("Redis async connection attempt %d/%d failed: %s", attempt, max_attempts, e)
                    if attempt < max_attempts:
                        await asyncio.sleep(0.5)
                    else:
                        logger.warning("Redis async connection could not be established; continuing in fallback mode")
        yield
        if pubsub_task and not pubsub_task.done():
            pubsub_task.cancel()
            try:
                await pubsub_task
            except asyncio.CancelledError:
                pass
        if redis_client:
            try:
                if hasattr(redis_client, "aclose"):
                    await redis_client.aclose()
                elif hasattr(redis_client, "close"):
                    await redis_client.close()
            except Exception:
                pass

    # REST API endpoints
    @app.get("/health")
    async def gateway_health_check():
        from app.routers.hub import deep_health_check
        return await deep_health_check()

    @app.post("/api/v2/session/start", response_model=SessionStartResponse)
    async def session_start(
        req: SessionStartRequest,
        player: AuthenticatedPlayer = Depends(get_current_player)
    ):
        # Prevent identity spoofing: reject if client attempts to impersonate another player
        if req.player_id is not None and req.player_id != player.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": f"Identity spoofing detected: token belongs to player {player.id}, cannot start session for player {req.player_id}",
                    "code": "FORBIDDEN"
                }
            )

        start_time_ms = int(time.time() * 1000)
        token = AntiCheatValidator.generate_session_token(
            player_id=player.id,
            game_slug=req.game_slug,
            timestamp_ms=start_time_ms
        )
        return SessionStartResponse(
            session_token=token,
            start_time_ms=start_time_ms,
            game_slug=req.game_slug,
            player_id=player.id,
            username=player.username
        )

    @app.post("/api/v2/session/end", response_model=ScoreSubmissionResponse)
    async def session_end(
        req: ScoreSubmissionRequest,
        request: Request,
        response: Response,
        player: AuthenticatedPlayer = Depends(get_current_player)
    ):
        # Prevent identity spoofing: reject if client attempts to claim another player's score
        if req.player_id is not None and req.player_id != player.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": f"Identity spoofing detected: token belongs to player {player.id}, cannot submit score for player {req.player_id}",
                    "code": "FORBIDDEN"
                }
            )

        # 1. Authoritative Anti-Cheat Verification using verified player identity & multi-worker Redis replay protection
        is_valid, reason = await AntiCheatValidator.async_validate_submission(
            player_id=player.id,
            game_slug=req.game_slug,
            score=req.score,
            start_time_ms=req.start_time_ms,
            session_token=req.session_token,
            action_count=req.action_count,
            input_entropy_hash=req.input_entropy_hash,
            redis_client=redis_client,
            check_replay=True
        )

        is_bearer = bool(request.headers.get("authorization"))
        if not is_valid:
            if reason in ("INVALID_SESSION_SIGNATURE", "REPLAY_ATTACK_DETECTED", "SESSION_EXPIRED"):
                code = "AUTH_FAILED" if is_bearer else {
                    "INVALID_SESSION_SIGNATURE": "INVALID_SIGNATURE",
                    "REPLAY_ATTACK_DETECTED": "TOKEN_REUSED",
                    "SESSION_EXPIRED": "SESSION_EXPIRED"
                }.get(reason, "AUTH_FAILED")
                error_msg = reason if is_bearer else {
                    "REPLAY_ATTACK_DETECTED": "Session token has already been consumed",
                    "SESSION_EXPIRED": "Session token expired",
                    "INVALID_SESSION_SIGNATURE": reason
                }.get(reason, reason)
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": error_msg, "code": code})
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"error": reason, "code": "ANOMALOUS_VELOCITY"})

        await AntiCheatValidator.async_mark_token_used(req.session_token, redis_client=redis_client)

        if not is_bearer:
            response.status_code = status.HTTP_201_CREATED

        clean_game_name = canonical_game_title(req.game_slug) or req.game_slug
        now_iso = datetime.now(timezone.utc).isoformat()
        worker_active = False
        if redis_client:
            try:
                worker_active = bool(await redis_client.exists(redis_key("worker:active")))
            except Exception:
                worker_active = False

        rank = None
        # 2. Redis Operations (Sorted Sets & Streams) strictly bound to verified player
        if redis_client:
            try:
                bests_key = redis_key(f"lb:bests:{clean_game_name}")
                entries_key = redis_key(f"lb:entries:{clean_game_name}")
                score_entry = {
                    "id": uuid.uuid4().hex[:10],
                    "player_id": player.id,
                    "username": player.username,
                    "game_name": clean_game_name,
                    "score": int(req.score),
                    "achieved_at": now_iso,
                }
                # Update Redis ZSET
                pipe = redis_client.pipeline()
                pipe.zadd(bests_key, {f"{player.id}:{player.username}": req.score}, gt=True)
                pipe.zrevrank(bests_key, f"{player.id}:{player.username}")
                # Push to Redis Streams
                pipe.xadd(get_stream_key(), {
                    "type": "score",
                    "player_id": str(player.id),
                    "username": player.username,
                    "game_name": clean_game_name,
                    "score": str(req.score),
                    "achieved_at": now_iso,
                    "ts": str(time.time()),
                    "db_persisted": "0" if worker_active else "1",
                })
                pipe.zadd(entries_key, {json.dumps(score_entry): int(req.score)})
                res = await pipe.execute()
                rank_idx = res[1]
                if rank_idx is not None:
                    rank = rank_idx + 1

                # If reached Top 10, publish real-time overtake event
                if rank is not None and rank <= 10:
                    overtake_event = {
                        "type": "SCORE_UPDATE",
                        "game": clean_game_name,
                        "game_slug": req.game_slug,
                        "player": player.username,
                        "rank": rank,
                        "score": req.score,
                        "timestamp": time.time()
                    }
                    # Broadcast to all workers via Redis Pub/Sub (and local fallback)
                    await ws_manager.broadcast_distributed(req.game_slug, overtake_event, redis=redis_client)
                    from app.utils.telemetry_queue import telemetry_queue
                    telemetry_queue.publish_event(clean_game_name, overtake_event)
            except Exception as e:
                logger.warning("Redis operation warning: %s", e)

        from app.utils.telemetry_queue import telemetry_queue
        if worker_active:
            score_dict = {
                "id": uuid.uuid4().hex[:10],
                "player_id": player.id,
                "username": player.username,
                "game_name": clean_game_name,
                "score": int(req.score),
                "achieved_at": now_iso,
            }
        else:
            score_dict = telemetry_queue.enqueue_score(
                player_id=player.id,
                username=player.username,
                game_name=clean_game_name,
                score=req.score,
                push_stream=False,
            )

        return ScoreSubmissionResponse(
            verified=True,
            rank=rank,
            score=score_dict,
            message="Score cryptographically validated and queued for ingestion"
        )

    @app.post("/api/v2/auth/token")
    async def issue_auth_token(player: AuthenticatedPlayer = Depends(get_current_player)):
        """Issue a Bearer authentication token for an authenticated player."""
        token = AntiCheatValidator.create_player_token(player.id, player.username)
        return {
            "access_token": token,
            "token_type": "bearer",
            "player_id": player.id,
            "username": player.username
        }

    @app.get("/api/v2/presence/{game_slug}")
    async def get_game_presence(game_slug: str):
        count = await ws_manager.get_global_presence(game_slug, redis=redis_client)
        return {"game_slug": game_slug, "presence": count}

    # WebSocket endpoint for real-time presence
    @app.websocket("/ws/live/{game_slug}")
    async def live_game_websocket(websocket: WebSocket, game_slug: str):
        # Validate WebSocket origin
        origin = websocket.headers.get("origin")
        if origin and os.environ.get("FLASK_ENV") != "testing":
            clean_origin = origin.rstrip("/")
            is_allowed = any(
                clean_origin == allowed.rstrip("/")
                for allowed in ALLOWED_ORIGINS
            )
            if not is_allowed:
                logger.warning("Rejected unauthorized WebSocket connection from origin '%s'", origin)
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

        await ws_manager.connect(game_slug, websocket)
        curr_presence = await ws_manager.update_presence_connect(game_slug, redis=redis_client)
        await ws_manager.broadcast_distributed(game_slug, {
            "type": "PRESENCE_UPDATE",
            "game": game_slug,
            "count": curr_presence
        }, redis=redis_client)

        HEARTBEAT_TIMEOUT_SECONDS = 45.0

        try:
            while True:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=HEARTBEAT_TIMEOUT_SECONDS)
                if data == "ping":
                    await websocket.send_text("pong")
        except (asyncio.TimeoutError, WebSocketDisconnect):
            pass
        except Exception as ws_err:
            logger.debug("WebSocket terminated: %s", ws_err)
        finally:
            await ws_manager.disconnect(game_slug, websocket)
            updated_presence = await ws_manager.update_presence_disconnect(game_slug, redis=redis_client)
            await ws_manager.broadcast_distributed(game_slug, {
                "type": "PRESENCE_UPDATE",
                "game": game_slug,
                "count": updated_presence
            }, redis=redis_client)

    # Static files and application routers
    from fastapi.staticfiles import StaticFiles

    class CachedStaticFiles(StaticFiles):
        """Serve static assets with long-lived immutable cache headers."""

        async def get_response(self, path: str, scope):
            response = await super().get_response(path, scope)
            if response.status_code == 200 and path.lower().endswith(
                (".webp", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff2", ".css", ".js")
            ):
                response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
            return response

    base_dir = os.path.abspath(os.path.dirname(__file__))
    static_dir = os.path.join(base_dir, "static")
    public_dir = os.path.join(base_dir, "public")

    if os.path.exists(static_dir):
        app.mount("/static", CachedStaticFiles(directory=static_dir), name="static")
    if os.path.exists(public_dir):
        app.mount("/public", CachedStaticFiles(directory=public_dir), name="public")

    # Security & timing headers middleware
    @app.middleware("http")
    async def set_security_headers(request: Request, call_next):
        import time as _time
        t0 = _time.perf_counter()
        response = await call_next(request)
        dur_ms = (_time.perf_counter() - t0) * 1000
        response.headers["Server-Timing"] = f"app;dur={dur_ms:.1f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # Scoped database session cleanup middleware
    @app.middleware("http")
    async def db_session_lifecycle(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            try:
                from app.extensions import db
                db.session.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                from app.extensions import db
                db.session.remove()
            except Exception:
                pass

    # Include routers
    from app.routers.auth import auth_router
    from app.routers.hub import hub_router
    from app.routers.admin import admin_router
    from app.routers.games import register_game_routes
    from app.routers.errors import register_error_handlers

    app.include_router(auth_router)
    app.include_router(hub_router)
    app.include_router(admin_router)
    register_game_routes(app)
    register_error_handlers(app)

    class _AppContext:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    app.app_context = lambda: _AppContext()

    logger.info("Pixora application started on port 8000")

else:
    logger.info("FastAPI not installed in current environment. Install via pip install fastapi uvicorn.")

