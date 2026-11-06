"""Pixora 2.0 Real-Time FastAPI Gateway & WebSocket Engine.

Fulfills Phase 2 & Phase 3 of the Tier S Architecture:
- Sub-5ms Async IO REST Endpoints
- WebSockets for Live Rank Overtake Tickers & Player Presence
- Direct integration with Redis Streams and Redis ZSET Leaderboards
- Standalone ASGI execution via Uvicorn

Run:
    uvicorn gateway:app --host 0.0.0.0 --port 8000 --reload
"""
import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Optional

try:
    from fastapi import (
        FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status,
        Request, Depends, Header, Cookie
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("pixora.gateway")

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
STREAM_KEY = os.environ.get("TELEMETRY_STREAM_KEY", "pixora:telemetry")
KEY_PREFIX = "pixora:"

if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Pixora 2.0 Real-Time Gateway",
        description="High-Throughput Gaming Engine with Cryptographic Anti-Cheat & Sub-Millisecond Leaderboards",
        version="2.0.0"
    )

    # Allowed Origins for CORS & Cross-Site WebSocket Hijacking (CSWSH) Protection
    DEFAULT_ALLOWED_ORIGINS = [
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "https://pixora-17.vercel.app",
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

    # ─────────────────────────────────────────────────────────────
    # DISTRIBUTED WEBSOCKET & PRESENCE MANAGER (REDIS PUB/SUB)
    # ─────────────────────────────────────────────────────────────

    class WebSocketManager:
        """Manages local WebSocket connections with Redis Pub/Sub multi-worker distribution."""

        def __init__(self):
            # game_slug -> list of WebSockets connected to this local worker process
            self.active_connections: Dict[str, List[WebSocket]] = {}
            self._lock = asyncio.Lock()

        async def connect(self, game_slug: str, websocket: WebSocket):
            await websocket.accept()
            async with self._lock:
                if game_slug not in self.active_connections:
                    self.active_connections[game_slug] = []
                self.active_connections[game_slug].append(websocket)
            logger.info("Local WebSocket connected for '%s' (Worker local total: %d)", game_slug, len(self.active_connections[game_slug]))

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
            """Publish event to Redis so ALL Uvicorn worker processes broadcast to their clients."""
            if redis:
                try:
                    await redis.publish(f"{KEY_PREFIX}events:{game_slug}", json.dumps(message))
                    return
                except Exception as err:
                    logger.warning("Redis Pub/Sub broadcast error: %s; falling back to local fanout", err)
            await self.broadcast_local(game_slug, message)

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
                    count = await redis.hincrby(f"{KEY_PREFIX}presence", game_slug, 1)
                    return max(1, int(count))
                except Exception as err:
                    logger.warning("Redis presence increment warning: %s", err)
            return max(1, self.get_local_presence(game_slug))

        async def update_presence_disconnect(self, game_slug: str, redis=None) -> int:
            """Decrement distributed presence in Redis across all workers."""
            if redis:
                try:
                    count = await redis.hincrby(f"{KEY_PREFIX}presence", game_slug, -1)
                    if count < 0:
                        await redis.hset(f"{KEY_PREFIX}presence", game_slug, 0)
                        count = 0
                    return count
                except Exception as err:
                    logger.warning("Redis presence decrement warning: %s", err)
            return self.get_local_presence(game_slug)

        async def get_global_presence(self, game_slug: str, redis=None) -> int:
            """Fetch authoritative presence across all worker instances."""
            if redis:
                try:
                    val = await redis.hget(f"{KEY_PREFIX}presence", game_slug)
                    if val is not None:
                        return max(1, int(val))
                except Exception as err:
                    logger.warning("Redis presence fetch warning: %s", err)
            return max(1, self.get_local_presence(game_slug))

    ws_manager = WebSocketManager()

    # ─────────────────────────────────────────────────────────────
    # PYDANTIC DATA SCHEMAS & CRYPTOGRAPHIC AUTH DEPENDENCIES
    # ─────────────────────────────────────────────────────────────

    class AuthenticatedPlayer(BaseModel):
        id: int
        username: str

    async def get_current_player(
        request: Request,
        authorization: Optional[str] = Header(None),
        session: Optional[str] = Cookie(None)
    ) -> AuthenticatedPlayer:
        """Authenticate caller via Bearer token or signed session cookie.

        Eliminates identity spoofing: player identity is established exclusively by
        verified cryptographic credentials, never self-reported by untrusted clients.
        """
        # 1. Bearer Token Authentication
        if authorization:
            parts = authorization.strip().split(" ", 1)
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token_data = AntiCheatValidator.verify_player_token(parts[1])
                if token_data and "player_id" in token_data:
                    return AuthenticatedPlayer(
                        id=int(token_data["player_id"]),
                        username=str(token_data.get("username", "Player"))
                    )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "Invalid or expired authorization token", "code": "UNAUTHORIZED"}
            )

        # 2. Flask Signed Session Cookie Authentication
        cookie_val = session or request.cookies.get("session")
        if cookie_val:
            sess_data = AntiCheatValidator.decode_flask_session(cookie_val)
            if sess_data and "_user_id" in sess_data:
                return AuthenticatedPlayer(
                    id=int(sess_data["_user_id"]),
                    username=str(sess_data.get("pilot_username", "Player"))
                )

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

    # ─────────────────────────────────────────────────────────────
    # REDIS CLIENT LIFECYCLE & BACKGROUND PUB/SUB LISTENER
    # ─────────────────────────────────────────────────────────────

    redis_client = None

    @app.on_event("startup")
    async def startup_event():
        global redis_client
        if AIOREDIS_AVAILABLE and os.environ.get("FLASK_ENV") != "testing":
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
                    await redis_client.ping()
                    logger.info("Connected to Redis at %s", REDIS_URL)
                    # Launch Redis Pub/Sub listener task
                    asyncio.create_task(redis_pubsub_listener())
                    break
                except Exception as e:
                    logger.warning("Redis async connection attempt %d/%d failed: %s", attempt, max_attempts, e)
                    if attempt < max_attempts:
                        await asyncio.sleep(0.5)
                    else:
                        logger.warning("Redis async connection could not be established; continuing in fallback mode")

    @app.on_event("shutdown")
    async def shutdown_event():
        if redis_client:
            await redis_client.close()

    async def redis_pubsub_listener():
        """Listen to Redis Pub/Sub events and broadcast via WebSockets in real time."""
        if not redis_client:
            return
        try:
            pubsub = redis_client.pubsub()
            await pubsub.psubscribe(f"{KEY_PREFIX}events:*")
            logger.info("Subscribed to Redis Pub/Sub channel '%sevents:*'", KEY_PREFIX)
            async for msg in pubsub.listen():
                if msg and msg["type"] == "pmessage":
                    channel = msg["channel"]
                    game_slug = channel.split(":")[-1]
                    try:
                        event_data = json.loads(msg["data"])
                        await ws_manager.broadcast_local(game_slug, event_data)
                    except Exception as err:
                        logger.error("PubSub broadcast error: %s", err)
        except Exception as e:
            logger.warning("PubSub listener stopped: %s", e)

    # ─────────────────────────────────────────────────────────────
    # ASYNC REST ENDPOINTS & HEALTH
    # ─────────────────────────────────────────────────────────────

    @app.get("/")
    @app.get("/health")
    @app.get("/api/health")
    async def health_check():
        redis_ok = False
        if redis_client:
            try:
                await redis_client.ping()
                redis_ok = True
            except Exception:
                pass
        return {
            "status": "healthy",
            "service": "pixora-fastapi-gateway",
            "redis": "connected" if redis_ok else "offline",
            "version": "2.0.0"
        }

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

        if not is_valid:
            if reason in ("INVALID_SESSION_SIGNATURE", "REPLAY_ATTACK_DETECTED", "SESSION_EXPIRED"):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": reason, "code": "AUTH_FAILED"})
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"error": reason, "code": "ANOMALOUS_VELOCITY"})

        await AntiCheatValidator.async_mark_token_used(req.session_token, redis_client=redis_client)

        rank = None
        # 2. Redis Operations (Sorted Sets & Streams) strictly bound to verified player
        if redis_client:
            try:
                # Update Redis ZSET
                pipe = redis_client.pipeline()
                pipe.zadd(f"{KEY_PREFIX}lb:bests:{req.game_slug}", {f"{player.id}:{player.username}": req.score}, gt=True)
                pipe.zrevrank(f"{KEY_PREFIX}lb:bests:{req.game_slug}", f"{player.id}:{player.username}")
                # Push to Redis Streams
                pipe.xadd(STREAM_KEY, {
                    "type": "score",
                    "player_id": str(player.id),
                    "username": player.username,
                    "game_name": req.game_slug,
                    "score": str(req.score),
                    "ts": str(time.time())
                })
                res = await pipe.execute()
                rank_idx = res[1]
                if rank_idx is not None:
                    rank = rank_idx + 1

                # If reached Top 10, publish real-time overtake event
                if rank is not None and rank <= 10:
                    overtake_event = {
                        "type": "LEADERBOARD_OVERTAKE",
                        "game": req.game_slug,
                        "player": player.username,
                        "rank": rank,
                        "score": req.score,
                        "timestamp": time.time()
                    }
                    await redis_client.publish(f"{KEY_PREFIX}events:{req.game_slug}", json.dumps(overtake_event))
                    # Also broadcast directly to connected WebSockets
                    await ws_manager.broadcast_to_game(req.game_slug, overtake_event)
            except Exception as e:
                logger.warning("Redis operation warning: %s", e)

        return ScoreSubmissionResponse(
            verified=True,
            rank=rank,
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

    @app.get("/api/v2/leaderboard/{game_slug}")
    async def get_live_leaderboard(game_slug: str, limit: int = 10):
        top_list = []
        if redis_client:
            try:
                bests = await redis_client.zrevrange(
                    f"{KEY_PREFIX}lb:bests:{game_slug}", 0, limit - 1, withscores=True
                )
                for member, score in bests:
                    parts = member.split(":", 1)
                    pid = int(parts[0]) if parts[0].isdigit() else 0
                    uname = parts[1] if len(parts) > 1 else "Champion"
                    top_list.append({"player_id": pid, "username": uname, "score": int(score)})
            except Exception as e:
                logger.warning("Leaderboard fetch error: %s", e)

        return {"game_slug": game_slug, "leaderboard": top_list, "source": "redis_zset"}

    @app.get("/api/v2/presence/{game_slug}")
    async def get_game_presence(game_slug: str):
        count = await ws_manager.get_global_presence(game_slug, redis=redis_client)
        return {"game_slug": game_slug, "presence": count}

    # ─────────────────────────────────────────────────────────────
    # WEBSOCKET REAL-TIME ENDPOINT WITH CSWSH & DISTRIBUTED PRESENCE
    # ─────────────────────────────────────────────────────────────

    @app.websocket("/ws/live/{game_slug}")
    async def live_game_websocket(websocket: WebSocket, game_slug: str):
        # 1. Cross-Site WebSocket Hijacking (CSWSH) Validation
        origin = websocket.headers.get("origin")
        if origin and os.environ.get("FLASK_ENV") != "testing":
            # Strip trailing slash for exact matching
            clean_origin = origin.rstrip("/")
            is_allowed = any(
                clean_origin == allowed.rstrip("/")
                or clean_origin.endswith(".vercel.app")
                for allowed in ALLOWED_ORIGINS
            )
            if not is_allowed:
                logger.warning("Rejected unauthorized WebSocket connection from origin '%s'", origin)
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

        await ws_manager.connect(game_slug, websocket)
        # Update and broadcast distributed presence to ALL worker instances
        curr_presence = await ws_manager.update_presence_connect(game_slug, redis=redis_client)
        await ws_manager.broadcast_distributed(game_slug, {
            "type": "PRESENCE_UPDATE",
            "game": game_slug,
            "count": curr_presence
        }, redis=redis_client)

        # Heartbeat timeout: reap connection if no ping/data received within 45 seconds
        HEARTBEAT_TIMEOUT_SECONDS = 45.0

        try:
            while True:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=HEARTBEAT_TIMEOUT_SECONDS)
                # Respond to client heartbeats
                if data == "ping":
                    await websocket.send_text("pong")
        except (asyncio.TimeoutError, WebSocketDisconnect):
            pass
        except Exception as ws_err:
            logger.debug("WebSocket terminated: %s", ws_err)
        finally:
            await ws_manager.disconnect(game_slug, websocket)
            # Decrement and broadcast updated distributed presence across all workers
            updated_presence = await ws_manager.update_presence_disconnect(game_slug, redis=redis_client)
            await ws_manager.broadcast_distributed(game_slug, {
                "type": "PRESENCE_UPDATE",
                "game": game_slug,
                "count": updated_presence
            }, redis=redis_client)

    # ─────────────────────────────────────────────────────────────
    # UNIFIED TIER S BACKEND: MOUNT FLASK AS ASGI MIDDLEWARE
    # ─────────────────────────────────────────────────────────────
    try:
        from a2wsgi import WSGIMiddleware
        from app import create_app
        flask_app = create_app(os.environ.get('FLASK_ENV', 'production'))
        app.mount("/", WSGIMiddleware(flask_app))
        logger.info("🚀 Unified Tier S Backend Active: Full platform & WebSockets on single ASGI engine")
    except Exception as e:
        logger.error("Could not mount Flask app into FastAPI: %s", e)

else:
    logger.info("FastAPI not installed in current environment. Install via pip install fastapi uvicorn.")

