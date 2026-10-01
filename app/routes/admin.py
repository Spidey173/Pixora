"""Admin dashboard routes for player and telemetry management."""
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func

from app.extensions import db
from app.forms import AdminLoginForm
from app.models import GameplaySession, GameScore, User

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Decorator to require dedicated admin authentication session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin_authenticated'):
            return redirect(url_for('admin.login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Separate dedicated login portal exclusively for administrators."""
    if session.get('is_admin_authenticated'):
        return redirect(url_for('admin.index'))

    form = AdminLoginForm()
    if form.validate_on_submit():
        user_input = form.username.data.strip()
        pass_input = form.password.data.strip()

        # Check against database User with is_admin=True, or default admin credentials
        admin_user = User.query.filter_by(username=user_input, is_admin=True).first()

        is_valid = False
        if admin_user and admin_user.check_password(pass_input) or user_input == 'admin' and pass_input in ('admin123', 'admin', 'pixora_admin', 'glitch4ce_admin'):
            is_valid = True

        if is_valid:
            session['is_admin_authenticated'] = True
            session['admin_user'] = user_input
            flash('Admin clearance granted. Welcome to Admin Core.', 'success')
            next_url = request.args.get('next') or url_for('admin.index')
            return redirect(next_url)
        else:
            flash('Invalid administrator credentials. Access restricted.', 'danger')

    return render_template('admin/login.html', form=form)


@admin_bp.route('/logout')
def logout():
    """Sign out of admin session."""
    session.pop('is_admin_authenticated', None)
    session.pop('admin_user', None)
    flash('Admin console session terminated.', 'success')
    return redirect(url_for('admin.login'))


@admin_bp.route('')
@admin_bp.route('/')
@admin_required
def index():
    """Admin dashboard overview of all registered players, analytics, catalog, and leaderboards."""
    from app.models import Game
    from app.utils.storage import r2_storage

    players = User.query.order_by(User.created_at.desc()).all()
    total_players = len(players)
    total_sessions = GameplaySession.query.count()
    total_scores = GameScore.query.count()

    # Calculate top 6 most played games
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

    # Calculate top high scores overall for leaderboard inspection
    top_scores = (
        GameScore.query
        .order_by(GameScore.score.desc())
        .limit(25)
        .all()
    )

    # Real-time telemetry feed of recent 10 sessions
    recent_sessions = (
        GameplaySession.query
        .order_by(GameplaySession.started_at.desc())
        .limit(10)
        .all()
    )

    games_list = Game.query.order_by(Game.created_at.desc()).all()
    r2_status = r2_storage.is_configured
    r2_bucket = current_app.config.get('CLOUDFLARE_R2_BUCKET_NAME', 'glitch4ce-games')
    r2_public_url = current_app.config.get('CLOUDFLARE_R2_PUBLIC_URL', 'https://pub-bbadfb1090074e17b2f5293b549ce094.r2.dev')
    total_plays = sum(g.play_count for g in games_list)
    r2_games_count = sum(1 for g in games_list if g.r2_asset_key or (g.play_url and 'r2.dev' in g.play_url))

    from app.utils.telemetry_queue import telemetry_queue
    queue_metrics = telemetry_queue.get_metrics()

    return render_template(
        'admin/index.html',
        players=players,
        total_players=total_players,
        total_sessions=total_sessions,
        total_scores=total_scores,
        total_plays=total_plays,
        top_games=top_games,
        top_scores=top_scores,
        recent_sessions=recent_sessions,
        games_list=games_list,
        r2_status=r2_status,
        r2_bucket=r2_bucket,
        r2_public_url=r2_public_url,
        r2_games_count=r2_games_count,
        queue_metrics=queue_metrics
    )


@admin_bp.route('/player/<string:username>')
@admin_required
def player_detail(username):
    """View detailed gameplay records for a specific player."""
    player = User.query.filter_by(username=username).first_or_404()
    sessions = (
        GameplaySession.query
        .filter_by(player_id=player.id)
        .order_by(GameplaySession.started_at.desc())
        .all()
    )

    return render_template('admin/player_detail.html', player=player, sessions=sessions)


@admin_bp.route('/player/<string:username>/delete', methods=['POST'])
@admin_required
def delete_player(username):
    """Securely delete a player and all associated gameplay logs (POST with CSRF)."""
    player = User.query.filter_by(username=username).first_or_404()
    db.session.delete(player)
    db.session.commit()
    flash(f"Player '{username}' and all associated history have been removed.", "success")
    return redirect(url_for('admin.index'))


@admin_bp.route('/games/upload', methods=['GET', 'POST'])
@admin_required
def upload_game():
    """Upload and deploy a packaged HTML5/WASM game zip archive to Cloudflare R2 or register URL."""
    import os
    import shutil
    import tempfile
    import zipfile

    from werkzeug.utils import secure_filename

    from app.forms import GameUploadForm
    from app.models import Game
    from app.utils.storage import r2_storage

    form = GameUploadForm()
    if form.validate_on_submit():
        file = request.files.get('game_zip')
        direct_url = form.play_url.data.strip() if form.play_url.data else None

        if (not file or not file.filename) and not direct_url:
            flash("Please either choose a .zip game archive or specify a direct web game URL.", "danger")
            return render_template('admin/upload_game.html', form=form)

        slug = secure_filename(form.slug.data.strip().lower().replace('_', '-'))
        existing = Game.query.filter_by(slug=slug).first()
        if existing:
            flash(f"A game with slug '{slug}' already exists. Choose another slug.", "danger")
            return render_template('admin/upload_game.html', form=form)

        play_url = None
        r2_asset_key = None

        if file and file.filename:
            filename = secure_filename(file.filename)
            if not filename.lower().endswith('.zip'):
                flash("Only .zip archives are supported for file packages.", "danger")
                return render_template('admin/upload_game.html', form=form)

            temp_dir = tempfile.mkdtemp()
            try:
                zip_path = os.path.join(temp_dir, filename)
                file.save(zip_path)

                extract_dir = os.path.join(temp_dir, 'extracted')
                os.makedirs(extract_dir, exist_ok=True)

                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    for member in zip_ref.namelist():
                        norm_path = os.path.normpath(os.path.join(extract_dir, member))
                        if not norm_path.startswith(os.path.abspath(extract_dir)):
                            raise Exception("Illegal file path detected in zip archive.")
                    zip_ref.extractall(extract_dir)

                target_dir = extract_dir
                if not os.path.exists(os.path.join(target_dir, 'index.html')):
                    subdirs = [os.path.join(target_dir, d) for d in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, d))]
                    if len(subdirs) == 1 and os.path.exists(os.path.join(subdirs[0], 'index.html')):
                        target_dir = subdirs[0]
                    else:
                        flash("Invalid archive structure: 'index.html' must be present in the game root.", "danger")
                        return render_template('admin/upload_game.html', form=form)

                r2_prefix = f"games/{slug}"
                uploaded = r2_storage.upload_directory(target_dir, r2_prefix)

                if not uploaded:
                    flash("Cloudflare R2 upload failed or is offline. Please check R2 API keys in .env.", "danger")
                    return render_template('admin/upload_game.html', form=form)

                play_url = uploaded.get('index.html', r2_storage.get_public_url(f"{r2_prefix}/index.html"))
                r2_asset_key = f"{r2_prefix}/index.html"

            except Exception as err:
                flash(f"Deployment failed: {err!s}", "danger")
                return render_template('admin/upload_game.html', form=form)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        elif direct_url:
            play_url = direct_url

        new_game = Game(
            slug=slug,
            title=form.title.data.strip(),
            category=form.category.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            controls_guide=form.controls_guide.data.strip() if form.controls_guide.data else None,
            play_url=play_url,
            r2_asset_key=r2_asset_key,
            is_published=True
        )
        db.session.add(new_game)
        db.session.commit()

        deploy_target = "Cloudflare R2 Edge" if r2_asset_key else "Registered WebGL URL"
        flash(f"🎉 Game '{new_game.title}' deployed via {deploy_target}! Playable live at /play/{new_game.slug}", "success")
        return redirect(url_for('admin.index'))

    return render_template('admin/upload_game.html', form=form)


@admin_bp.route('/games/<string:slug>/delete', methods=['POST'])
@admin_required
def delete_game(slug):
    """Remove a game from the platform catalog."""
    from app.models import Game
    game = Game.query.filter_by(slug=slug).first_or_404()
    title = game.title
    db.session.delete(game)
    db.session.commit()
    flash(f"Game '{title}' removed from platform.", "success")
    return redirect(url_for('admin.index'))


@admin_bp.route('/scores/<int:score_id>/delete', methods=['POST'])
@admin_required
def delete_score(score_id):
    """Remove a specific score entry from global leaderboards (POST with CSRF)."""
    score = GameScore.query.get_or_404(score_id)
    game_title = score.game_name
    score_val = score.score
    db.session.delete(score)
    db.session.commit()
    flash(f"Leaderboard entry for '{game_title}' ({score_val} pts) deleted.", "success")
    return redirect(url_for('admin.index'))
