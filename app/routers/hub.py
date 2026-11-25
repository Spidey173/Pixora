"""Main arcade hub, gameplay, and leaderboard routes."""
import asyncio
from datetime import datetime, timezone
import json
import queue

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy.exc import SQLAlchemyError

from app.auth_deps import get_current_user
from app.extensions import db
from app.models import AnonymousUser, Game, GameplaySession, GameScore, User
from app.templates import templates
from app.utils.game_resolver import (
    build_normalized_all_titles_leaderboard,
    resolve_game,
)
from app.utils.telemetry_queue import telemetry_queue

hub_router = APIRouter(tags=["hub"])


def render_hub_view(request: Request, user: User | AnonymousUser, active_tab: str = 'games'):
    """Render unified gaming platform home with games catalog, leaderboard, and infrastructure."""
    user_sessions = []
    username = None
    if user.is_authenticated:
        username = user.username
        user_sessions = (
            GameplaySession.query
            .filter_by(player_id=user.id)
            .order_by(GameplaySession.started_at.desc())
            .all()
        )

    game_history = [(s.game_name, s.formatted_timestamp) for s in user_sessions]
    game_count = len(game_history)

    games_list = (
        Game.query
        .filter_by(is_published=True)
        .order_by(Game.is_featured.desc(), Game.play_count.desc(), Game.id.asc())
        .all()
    )
    if not games_list:
        try:
            from app.utils.seed_games import seed_catalog
            seed_catalog()
            games_list = (
                Game.query
                .filter_by(is_published=True)
                .order_by(Game.is_featured.desc(), Game.play_count.desc(), Game.id.asc())
                .all()
            )
        except Exception:
            pass

    selected_game = request.query_params.get('game', '').strip()
    active_game_title = 'ALL TITLES (HALL OF FAME)'
    is_all_titles = not selected_game or selected_game.lower() == 'all'

    score_query = GameScore.query
    if not is_all_titles:
        matched_game = resolve_game(selected_game)
        names_to_match = [selected_game]
        if matched_game:
            names_to_match = list(set([matched_game.title, matched_game.slug, selected_game]))
            active_game_title = matched_game.title
        else:
            active_game_title = selected_game
        score_query = score_query.filter(GameScore.game_name.in_(names_to_match))

    all_scores = score_query.order_by(GameScore.score.desc(), GameScore.achieved_at.asc()).all()

    if is_all_titles:
        top_scores = build_normalized_all_titles_leaderboard(all_scores, limit=30)
    else:
        # Keep highest score per player on single-game leaderboard
        unique_pilot_scores = []
        seen_players = set()
        for s in all_scores:
            if s.player_id not in seen_players:
                seen_players.add(s.player_id)
                unique_pilot_scores.append(s)
        top_scores = unique_pilot_scores[:30]

    return templates.TemplateResponse(
        'Games/game.html',
        {
            'request': request,
            'current_user': user,
            'username': username or 'Guest Pilot',
            'game_count': game_count,
            'game_history': game_history,
            'games_list': games_list,
            'top_scores': top_scores,
            'active_tab': active_tab,
            'selected_game': selected_game,
            'active_game_title': active_game_title,
            'is_all_titles': is_all_titles,
        }
    )


@hub_router.get("/")
async def root(
    request: Request,
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Root homepage: redirects unauthenticated visitors to /login, authenticated to /games."""
    if user.is_authenticated:
        return RedirectResponse(url="/games", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@hub_router.get("/games", response_class=HTMLResponse)
async def games(
    request: Request,
    tab: str = "games",
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Render arcade games dashboard and hub."""
    if not user.is_authenticated:
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=status.HTTP_302_FOUND)
    return render_hub_view(request, user, active_tab=tab)


@hub_router.get("/play/{slug}", response_class=HTMLResponse)
async def play_game(
    slug: str,
    request: Request,
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Render sandboxed theater player for any registered game."""
    game = Game.query.filter_by(slug=slug, is_published=True).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    try:
        game.play_count += 1
        db.session.commit()
    except Exception:
        db.session.rollback()

    if user.is_authenticated:
        telemetry_queue.enqueue_session_start(
            player_id=user.id,
            game_name=game.title
        )

    return templates.TemplateResponse(
        "player.html",
        {
            "request": request,
            "game": game,
            "current_user": user
        }
    )


@hub_router.post("/start_game/{game_name:path}")
async def start_game(
    game_name: str,
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Log game launch event asynchronously via event queue."""
    if not user.is_authenticated:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    clean_game_name = game_name.strip()
    is_dedup, status_code, session_dict = telemetry_queue.enqueue_session_start(
        player_id=user.id,
        game_name=clean_game_name
    )
    return JSONResponse(session_dict)


@hub_router.post("/end_game/{game_name:path}")
async def end_game(
    game_name: str,
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Log the end of a game session and compute duration."""
    if not user.is_authenticated:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    clean_game_name = game_name.strip()
    result = telemetry_queue.enqueue_session_end(
        player_id=user.id,
        game_name=clean_game_name
    )
    return JSONResponse(result)


@hub_router.get("/api/history")
async def api_history(user: User | AnonymousUser = Depends(get_current_user)):
    """Return real-time player history and session counts."""
    if not user.is_authenticated:
        return JSONResponse({"error": "unauthorized", "history": [], "count": 0}, status_code=401)

    user_sessions = (
        GameplaySession.query
        .filter_by(player_id=user.id)
        .order_by(GameplaySession.started_at.desc())
        .limit(100)
        .all()
    )
    history = [s.to_dict() for s in user_sessions]
    return JSONResponse({
        "username": user.username,
        "count": len(history),
        "history": history
    })


@hub_router.post("/api/score/submit")
@hub_router.post("/api/scores")
async def submit_score(
    request: Request,
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Submit high score via event queue and live Redis sorted set."""
    if not user.is_authenticated:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        data = await request.json()
    except Exception:
        form = await request.form()
        data = dict(form)

    game_name = (data.get("game_name") or "").strip()
    score_val = data.get("score")

    if not game_name or score_val is None:
        return JSONResponse({"error": "invalid payload, game_name and score required"}, status_code=400)

    try:
        score_int = int(score_val)
        if score_int < 0:
            return JSONResponse({"error": "score cannot be negative"}, status_code=400)
    except (ValueError, TypeError):
        return JSONResponse({"error": "score must be an integer"}, status_code=400)

    matched_game = resolve_game(game_name)
    canonical_name = matched_game.title if matched_game else game_name

    score_dict = telemetry_queue.enqueue_score(
        player_id=user.id,
        username=user.username,
        game_name=canonical_name,
        score=score_int
    )

    return JSONResponse({
        "status": "success",
        "message": "Score recorded via high-throughput event queue",
        "score": score_dict
    }, status_code=201)


@hub_router.get("/api/leaderboard/{game_name:path}")
async def get_leaderboard(
    game_name: str,
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Retrieve top 10 scores, personal best, and world record."""
    clean_game_name = game_name.strip()
    matched_game = resolve_game(clean_game_name)
    canonical_title = matched_game.title if matched_game else clean_game_name
    names_to_match = [clean_game_name]
    if matched_game:
        names_to_match = list(set([matched_game.title, matched_game.slug, clean_game_name]))

    curr_player_id = user.id if user.is_authenticated else None

    lb_data = telemetry_queue.get_live_leaderboard(
        game_name=canonical_title,
        limit=10,
        current_player_id=curr_player_id,
        names_to_match=names_to_match
    )

    return JSONResponse({
        "game_name": clean_game_name,
        "canonical_title": canonical_title,
        "leaderboard": lb_data["leaderboard"],
        "user_best": lb_data["user_best"],
        "world_record": lb_data["world_record"],
        "user_rank": lb_data["user_rank"],
        "total_scores_logged": lb_data["total_scores_logged"],
        "queue_mode": telemetry_queue.get_metrics()["mode"],
        "source": lb_data.get("source", "event_queue")
    })


@hub_router.get("/api/v2/presence/{game_name:path}")
async def get_game_presence(game_name: str):
    """Retrieve live concurrent player presence."""
    clean_game = game_name.strip()
    matched_game = resolve_game(clean_game)
    canonical_title = matched_game.title if matched_game else clean_game
    count = telemetry_queue.get_presence(canonical_title)
    return JSONResponse({
        "status": "success",
        "game": canonical_title,
        "presence": max(1, count)
    })


@hub_router.get("/api/v2/events/{game_name:path}")
async def sse_game_events(game_name: str):
    """Server-Sent Events (SSE) broadcast stream for leaderboard overtakes and presence."""
    clean_game = game_name.strip()
    matched_game = resolve_game(clean_game)
    canonical_title = matched_game.title if matched_game else clean_game

    async def event_generator():
        q = queue.Queue(maxsize=30)
        with telemetry_queue._lock:
            telemetry_queue._event_listeners[canonical_title].append(q)

        telemetry_queue.record_presence(canonical_title, delta=1)
        initial_count = telemetry_queue.get_presence(canonical_title)
        yield f"data: {json.dumps({'type': 'PRESENCE_UPDATE', 'game': canonical_title, 'count': initial_count})}\n\n"

        try:
            while True:
                try:
                    # Poll queue non-blockingly with async sleep
                    try:
                        event = q.get_nowait()
                        yield f"data: {json.dumps(event)}\n\n"
                    except queue.Empty:
                        await asyncio.sleep(1.0)
                        yield ": heartbeat\n\n"
                except asyncio.CancelledError:
                    break
        finally:
            with telemetry_queue._lock:
                if q in telemetry_queue._event_listeners[canonical_title]:
                    telemetry_queue._event_listeners[canonical_title].remove(q)
            telemetry_queue.record_presence(canonical_title, delta=-1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


@hub_router.get("/profile", response_class=HTMLResponse)
async def profile(
    request: Request,
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Render player profile overview with statistics and score badges."""
    if not user.is_authenticated:
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=status.HTTP_302_FOUND)

    user_scores = GameScore.query.filter_by(player_id=user.id).order_by(GameScore.score.desc()).all()
    user_sessions = GameplaySession.query.filter_by(player_id=user.id).order_by(GameplaySession.started_at.desc()).limit(20).all()

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "current_user": user,
            "scores": user_scores,
            "sessions": user_sessions
        }
    )


@hub_router.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(
    request: Request,
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Render connected Leaderboard on the unified platform hub."""
    return render_hub_view(request, user, active_tab="leaderboard")


@hub_router.get("/infrastructure", response_class=HTMLResponse)
async def infrastructure_page(
    request: Request,
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Render connected Cloudflare Infrastructure architecture on the unified platform hub."""
    return render_hub_view(request, user, active_tab="infrastructure")


@hub_router.get("/health")
@hub_router.get("/api/health")
async def health_check():
    """Application health check and telemetry status API."""
    try:
        score_count = db.session.query(db.func.count(GameScore.id)).scalar() or 0
        db_status = "connected"
    except SQLAlchemyError as err:
        score_count = 0
        db_status = f"error: {err!s}"

    q_metrics = telemetry_queue.get_metrics()
    return JSONResponse({
        "status": "healthy",
        "database": db_status,
        "scores_logged": score_count,
        "event_queue": q_metrics,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.2.0"
    })
