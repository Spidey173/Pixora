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
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ─────────────────────────────────────────────────────────────
    # WEBSOCKET CONNECTION & PRESENCE MANAGER
    # ─────────────────────────────────────────────────────────────

    class WebSocketManager:
        def __init__(self):
            # game_slug -> list of WebSockets
            self.active_connections: Dict[str, List[WebSocket]] = {}
            self._lock = asyncio.Lock()

        async def connect(self, game_slug: str, websocket: WebSocket):
            await websocket.accept()
            async with self._lock:
                if game_slug not in self.active_connections:
                    self.active_connections[game_slug] = []
                self.active_connections[game_slug].append(websocket)
            logger.info("WebSocket connected for '%s' (Total: %d)", game_slug, len(self.active_connections[game_slug]))

        async def disconnect(self, game_slug: str, websocket: WebSocket):
            async with self._lock:
                if game_slug in self.active_connections:
                    if websocket in self.active_connections[game_slug]:
                        self.active_connections[game_slug].remove(websocket)
                    if not self.active_connections[game_slug]:
                        del self.active_connections[game_slug]

        async def broadcast_to_game(self, game_slug: str, message: dict):
            payload = json.dumps(message)
            async with self._lock:
                connections = list(self.active_connections.get(game_slug, []))
            for ws in connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    pass

        def get_presence(self, game_slug: str) -> int:
            return len(self.active_connections.get(game_slug, []))

    ws_manager = WebSocketManager()

    # ─────────────────────────────────────────────────────────────
    # PYDANTIC DATA SCHEMAS
    # ─────────────────────────────────────────────────────────────

    class SessionStartRequest(BaseModel):
        game_slug: str
        player_id: int = 1
        username: str = "Player"

    class SessionStartResponse(BaseModel):
        status: str = "success"
        session_token: str
        start_time_ms: int
        game_slug: str
        player_id: int

    class ScoreSubmissionRequest(BaseModel):
        game_slug: str
        player_id: int = 1
        username: str = "Player"
        score: int
        session_token: str
        start_time_ms: int
        duration_ms: Optional[int] = None
        action_count: Optional[int] = None
        input_entropy_hash: Optional[str] = None

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
        if AIOREDIS_AVAILABLE:
            for attempt in range(1, 11):
                try:
                    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
                    await redis_client.ping()
                    logger.info("Connected to Redis at %s", REDIS_URL)
                    # Launch Redis Pub/Sub listener task
                    asyncio.create_task(redis_pubsub_listener())
                    break
                except Exception as e:
                    logger.warning("Redis async connection attempt %d/10 failed: %s", attempt, e)
                    if attempt < 10:
                        await asyncio.sleep(1.5)
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
                        await ws_manager.broadcast_to_game(game_slug, event_data)
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
    async def session_start(req: SessionStartRequest):
        start_time_ms = int(time.time() * 1000)
        token = AntiCheatValidator.generate_session_token(
            player_id=req.player_id,
            game_slug=req.game_slug,
            timestamp_ms=start_time_ms
        )
        return SessionStartResponse(
            session_token=token,
            start_time_ms=start_time_ms,
            game_slug=req.game_slug,
            player_id=req.player_id
        )

    @app.post("/api/v2/session/end", response_model=ScoreSubmissionResponse)
    async def session_end(req: ScoreSubmissionRequest):
        # 1. Anti-Cheat Verification
        is_valid, reason = AntiCheatValidator.validate_submission(
            player_id=req.player_id,
            game_slug=req.game_slug,
            score=req.score,
            start_time_ms=req.start_time_ms,
            session_token=req.session_token,
            action_count=req.action_count,
            input_entropy_hash=req.input_entropy_hash,
            check_replay=True
        )

        if not is_valid:
            if reason in ("INVALID_SESSION_SIGNATURE", "REPLAY_ATTACK_DETECTED", "SESSION_EXPIRED"):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": reason, "code": "AUTH_FAILED"})
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"error": reason, "code": "ANOMALOUS_VELOCITY"})

        AntiCheatValidator.mark_token_used(req.session_token)

        rank = None
        # 2. Redis Operations (Sorted Sets & Streams)
        if redis_client:
            try:
                # Update Redis ZSET
                pipe = redis_client.pipeline()
                pipe.zadd(f"{KEY_PREFIX}lb:bests:{req.game_slug}", {f"{req.player_id}:{req.username}": req.score}, gt=True)
                pipe.zrevrank(f"{KEY_PREFIX}lb:bests:{req.game_slug}", f"{req.player_id}:{req.username}")
                # Push to Redis Streams
                pipe.xadd(STREAM_KEY, {
                    "type": "score",
                    "player_id": str(req.player_id),
                    "username": req.username,
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
                        "player": req.username,
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
        count = ws_manager.get_presence(game_slug)
        return {"game_slug": game_slug, "presence": max(1, count)}

    # ─────────────────────────────────────────────────────────────
    # WEBSOCKET REAL-TIME ENDPOINT
    # ─────────────────────────────────────────────────────────────

    @app.websocket("/ws/live/{game_slug}")
    async def live_game_websocket(websocket: WebSocket, game_slug: str):
        await ws_manager.connect(game_slug, websocket)
        # Broadcast presence count
        curr_presence = ws_manager.get_presence(game_slug)
        await ws_manager.broadcast_to_game(game_slug, {
            "type": "PRESENCE_UPDATE",
            "game": game_slug,
            "count": curr_presence
        })

        try:
            while True:
                data = await websocket.receive_text()
                # Respond to client heartbeats
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            await ws_manager.disconnect(game_slug, websocket)
            # Broadcast updated presence
            updated_presence = ws_manager.get_presence(game_slug)
            await ws_manager.broadcast_to_game(game_slug, {
                "type": "PRESENCE_UPDATE",
                "game": game_slug,
                "count": updated_presence
            })

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

