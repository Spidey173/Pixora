"""Admin Dashboard Router for Pixora."""
import json
import os
import shutil
import tempfile
import zipfile
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from werkzeug.utils import secure_filename

from app.auth_deps import (
    MockForm,
    decode_session_cookie,
    get_current_user,
    parse_form_or_json,
    set_flash,
)
from app.config import settings
from app.extensions import db
from app.models import AnonymousUser, Game, GameplaySession, GameScore, User
from app.templates import templates
from app.utils.storage import r2_storage
from app.utils.telemetry_queue import telemetry_queue

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("", response_class=HTMLResponse)
@admin_router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    session: Optional[str] = Cookie(None),
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Admin dashboard overview of registered players, catalog, analytics, and leaderboards."""
    sess_data = decode_session_cookie(session) if session else {}
    if not sess_data.get("is_admin_authenticated") and not getattr(user, "is_admin", False):
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=status.HTTP_302_FOUND)

    players = User.query.order_by(User.created_at.desc()).all()
    total_players = len(players)
    total_sessions = GameplaySession.query.count()
    total_scores = GameScore.query.count()

    top_games = (
        db.session.query(
            GameplaySession.game_name,
            func.count(GameplaySession.id).label('play_count')
        )
        .group_by(GameplaySession.game_name)
        .order_by(func.count(GameplaySession.id).desc())
        .limit(6)
        .all()
    )

    top_scores = (
        GameScore.query
        .order_by(GameScore.score.desc())
        .limit(25)
        .all()
    )

    recent_sessions = (
        GameplaySession.query
        .order_by(GameplaySession.started_at.desc())
        .limit(10)
        .all()
    )

    games_list = Game.query.order_by(Game.created_at.desc()).all()
    r2_status = r2_storage.is_configured
    r2_bucket = getattr(settings, 'CLOUDFLARE_R2_BUCKET_NAME', 'glitch4ce-games')
    r2_public_url = getattr(settings, 'CLOUDFLARE_R2_PUBLIC_URL', 'https://pub-bbadfb1090074e17b2f5293b549ce094.r2.dev')
    total_plays = sum(g.play_count for g in games_list)
    r2_games_count = sum(1 for g in games_list if g.r2_asset_key or (g.play_url and 'r2.dev' in g.play_url))

    queue_metrics = telemetry_queue.get_metrics()

    flashes = []
    if "_flashes" in request.cookies:
        try:
            flashes = json.loads(request.cookies["_flashes"])
        except Exception:
            pass

    response = templates.TemplateResponse(
        "admin/index.html",
        {
            "request": request,
            "current_user": user,
            "players": players,
            "total_players": total_players,
            "total_sessions": total_sessions,
            "total_scores": total_scores,
            "total_plays": total_plays,
            "top_games": top_games,
            "top_scores": top_scores,
            "recent_sessions": recent_sessions,
            "games_list": games_list,
            "r2_status": r2_status,
            "r2_bucket": r2_bucket,
            "r2_public_url": r2_public_url,
            "r2_games_count": r2_games_count,
            "queue_metrics": queue_metrics,
            "flashes": flashes
        }
    )
    if "_flashes" in request.cookies:
        response.delete_cookie("_flashes", path="/")
    return response


@admin_router.get("/player/{username}", response_class=HTMLResponse)
async def player_detail(
    username: str,
    request: Request,
    session: Optional[str] = Cookie(None),
    user: User | AnonymousUser = Depends(get_current_user)
):
    """View detailed gameplay records for a specific player."""
    sess_data = decode_session_cookie(session) if session else {}
    if not sess_data.get("is_admin_authenticated") and not getattr(user, "is_admin", False):
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=status.HTTP_302_FOUND)

    player = User.query.filter_by(username=username).first()
    if not player:
        raise HTTPException(status_code=404, detail=f"Player '{username}' not found")

    sessions = (
        GameplaySession.query
        .filter_by(player_id=player.id)
        .order_by(GameplaySession.started_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "admin/player_detail.html",
        {
            "request": request,
            "current_user": user,
            "player": player,
            "sessions": sessions
        }
    )


@admin_router.post("/player/{username}/delete")
async def delete_player(
    username: str,
    request: Request,
    session: Optional[str] = Cookie(None),
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Securely delete player and all associated gameplay logs."""
    sess_data = decode_session_cookie(session) if session else {}
    if not sess_data.get("is_admin_authenticated") and not getattr(user, "is_admin", False):
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=status.HTTP_302_FOUND)

    player = User.query.filter_by(username=username).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    db.session.delete(player)
    db.session.commit()

    response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    set_flash(response, f"Player '{username}' and all associated history have been removed.", "success")
    return response


@admin_router.get("/games/upload", response_class=HTMLResponse)
async def upload_game_page(
    request: Request,
    session: Optional[str] = Cookie(None),
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Render game upload and deployment portal."""
    sess_data = decode_session_cookie(session) if session else {}
    if not sess_data.get("is_admin_authenticated") and not getattr(user, "is_admin", False):
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=status.HTTP_302_FOUND)

    form = MockForm()
    return templates.TemplateResponse(
        "admin/upload_game.html",
        {
            "request": request,
            "current_user": user,
            "form": form,
            "flashes": []
        }
    )


@admin_router.post("/games/upload")
async def upload_game_submit(
    request: Request,
    session: Optional[str] = Cookie(None),
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Deploy packaged HTML5/WASM game archive to Cloudflare R2 or register URL."""
    sess_data = decode_session_cookie(session) if session else {}
    if not sess_data.get("is_admin_authenticated") and not getattr(user, "is_admin", False):
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=status.HTTP_302_FOUND)

    form_data = await parse_form_or_json(request)
    title_val = (form_data.get("title") or "").strip()
    slug_val = secure_filename((form_data.get("slug") or "").strip().lower().replace("_", "-"))
    category_val = (form_data.get("category") or "Arcade").strip()
    desc_val = (form_data.get("description") or "").strip() or None
    controls_val = (form_data.get("controls_guide") or "").strip() or None
    direct_url = (form_data.get("play_url") or "").strip() or None

    form = MockForm()
    if not slug_val or not title_val:
        return templates.TemplateResponse(
            "admin/upload_game.html",
            {
                "request": request,
                "current_user": user,
                "form": form,
                "flashes": [("danger", "Game title and slug are required.")]
            },
            status_code=400
        )

    existing = Game.query.filter_by(slug=slug_val).first()
    if existing:
        return templates.TemplateResponse(
            "admin/upload_game.html",
            {
                "request": request,
                "current_user": user,
                "form": form,
                "flashes": [("danger", f"A game with slug '{slug_val}' already exists. Choose another slug.")]
            }
        )

    game_zip = None
    try:
        req_form = await request.form()
        game_zip = req_form.get("game_zip")
    except Exception:
        game_zip = None

    resolved_play_url = None
    r2_asset_key = None

    if (not game_zip or not getattr(game_zip, "filename", None)) and not direct_url:
        return templates.TemplateResponse(
            "admin/upload_game.html",
            {
                "request": request,
                "current_user": user,
                "form": form,
                "flashes": [("danger", "Please either choose a .zip game archive or specify a direct web game URL.")]
            }
        )

    if game_zip and getattr(game_zip, "filename", None):
        filename = secure_filename(game_zip.filename)
        if not filename.lower().endswith(".zip"):
            return templates.TemplateResponse(
                "admin/upload_game.html",
                {
                    "request": request,
                    "current_user": user,
                    "form": form,
                    "flashes": [("danger", "Only .zip archives are supported for game packages.")]
                }
            )

        temp_dir = tempfile.mkdtemp()
        try:
            zip_path = os.path.join(temp_dir, filename)
            contents = await game_zip.read()
            with open(zip_path, "wb") as f:
                f.write(contents)

            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                for member in zip_ref.namelist():
                    norm_path = os.path.normpath(os.path.join(extract_dir, member))
                    if not norm_path.startswith(os.path.abspath(extract_dir)):
                        raise Exception("Illegal file path detected in zip archive.")
                zip_ref.extractall(extract_dir)

            target_dir = extract_dir
            if not os.path.exists(os.path.join(target_dir, "index.html")):
                subdirs = [os.path.join(target_dir, d) for d in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, d))]
                if len(subdirs) == 1 and os.path.exists(os.path.join(subdirs[0], "index.html")):
                    target_dir = subdirs[0]
                else:
                    return templates.TemplateResponse(
                        "admin/upload_game.html",
                        {
                            "request": request,
                            "current_user": user,
                            "form": form,
                            "flashes": [("danger", "Invalid archive structure: 'index.html' must be present in root.")]
                        }
                    )

            r2_prefix = f"games/{slug_val}"
            uploaded = r2_storage.upload_directory(target_dir, r2_prefix)
            if not uploaded:
                return templates.TemplateResponse(
                    "admin/upload_game.html",
                    {
                        "request": request,
                        "current_user": user,
                        "form": form,
                        "flashes": [("danger", "Cloudflare R2 upload failed or is offline. Please check R2 API keys.")]
                    }
                )

            resolved_play_url = uploaded.get("index.html", r2_storage.get_public_url(f"{r2_prefix}/index.html"))
            r2_asset_key = f"{r2_prefix}/index.html"
        except Exception as err:
            return templates.TemplateResponse(
                "admin/upload_game.html",
                {
                    "request": request,
                    "current_user": user,
                    "form": form,
                    "flashes": [("danger", f"Deployment failed: {err!s}")]
                }
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    elif direct_url:
        resolved_play_url = direct_url

    new_game = Game(
        slug=slug_val,
        title=title_val,
        category=category_val,
        description=desc_val,
        controls_guide=controls_val,
        play_url=resolved_play_url,
        r2_asset_key=r2_asset_key,
        is_published=True
    )
    db.session.add(new_game)
    db.session.commit()

    deploy_target = "Cloudflare R2 Edge" if r2_asset_key else "Registered WebGL URL"
    response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    set_flash(response, f"🎉 Game '{new_game.title}' deployed via {deploy_target}! Playable live at /play/{new_game.slug}", "success")
    return response


@admin_router.post("/games/{slug}/delete")
async def delete_game(
    slug: str,
    request: Request,
    session: Optional[str] = Cookie(None),
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Remove a game from platform catalog."""
    sess_data = decode_session_cookie(session) if session else {}
    if not sess_data.get("is_admin_authenticated") and not getattr(user, "is_admin", False):
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=status.HTTP_302_FOUND)

    game = Game.query.filter_by(slug=slug).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    title = game.title
    db.session.delete(game)
    db.session.commit()

    response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    set_flash(response, f"Game '{title}' removed from platform.", "success")
    return response


@admin_router.post("/scores/{score_id}/delete")
async def delete_score(
    score_id: int,
    request: Request,
    session: Optional[str] = Cookie(None),
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Remove specific score entry from global leaderboards."""
    sess_data = decode_session_cookie(session) if session else {}
    if not sess_data.get("is_admin_authenticated") and not getattr(user, "is_admin", False):
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=status.HTTP_302_FOUND)

    score = GameScore.query.get(score_id)
    if not score:
        raise HTTPException(status_code=404, detail="Score not found")

    game_title = score.game_name
    score_val = score.score
    db.session.delete(score)
    db.session.commit()

    response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    set_flash(response, f"Leaderboard entry for '{game_title}' ({score_val} pts) deleted.", "success")
    return response
