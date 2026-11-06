"""Main arcade hub views and gameplay tracking API."""
from datetime import datetime, timezone
import json

from flask import Blueprint, jsonify, redirect, render_template, request, url_for, Response
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import csrf, db
from app.models import Game, GameplaySession, GameScore
from app.services.anti_cheat import AntiCheatValidator
from app.utils.telemetry_queue import telemetry_queue

main_bp = Blueprint('main', __name__)




@main_bp.route('/')
def index():
    """Root homepage redirects unauthenticated visitors to login, or authenticated players to games."""
    if current_user.is_authenticated:
        return redirect(url_for('main.games'))
    return redirect(url_for('auth.login'))


@main_bp.route('/play/<slug>')
def play_game(slug):
    """Render universal Poki-style sandboxed theater player for any registered or Cloudflare-hosted game."""
    game = Game.query.filter_by(slug=slug, is_published=True).first_or_404()
    
    # Increment play count telemetry and auto-log gameplay session via event queue
    try:
        game.play_count += 1
        db.session.commit()
    except Exception:
        db.session.rollback()

    if current_user.is_authenticated:
        telemetry_queue.enqueue_session_start(
            player_id=current_user.id,
            game_name=game.title
        )

    return render_template('player.html', game=game)


def _render_hub_view(active_tab='games'):
    """Render unified gaming platform home with connected games, leaderboard, and infrastructure."""
    user_sessions = []
    username = None
    if current_user.is_authenticated:
        username = current_user.username
        user_sessions = (
            GameplaySession.query
            .filter_by(player_id=current_user.id)
            .order_by(GameplaySession.started_at.desc())
            .all()
        )

    # Format history tuples for template compatibility: (game_name, timestamp_str)
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

    selected_game = request.args.get('game', '').strip()
    active_game_title = 'ALL TITLES (HALL OF FAME)'

    score_query = GameScore.query
    if selected_game and selected_game.lower() not in ('all', ''):
        matched_game = Game.query.filter((Game.title == selected_game) | (Game.slug == selected_game)).first()
        names_to_match = [selected_game]
        if matched_game:
            names_to_match = list(set([matched_game.title, matched_game.slug, selected_game]))
            active_game_title = matched_game.title
        else:
            active_game_title = selected_game
        score_query = score_query.filter(GameScore.game_name.in_(names_to_match))

    all_scores = score_query.order_by(GameScore.score.desc(), GameScore.achieved_at.asc()).all()

    # DEDUPLICATE BY PLAYER: Each unique pilot appears at most ONCE on the championship leaderboard!
    # A single player will NEVER occupy Gold, Silver, and Bronze!
    unique_pilot_scores = []
    seen_players = set()
    for s in all_scores:
        if s.player_id not in seen_players:
            seen_players.add(s.player_id)
            unique_pilot_scores.append(s)

    top_scores = unique_pilot_scores[:30]

    return render_template(
        'Games/game.html',
        username=username or 'Guest Pilot',
        game_count=game_count,
        game_history=game_history,
        games_list=games_list,
        top_scores=top_scores,
        active_tab=active_tab,
        selected_game=selected_game,
        active_game_title=active_game_title
    )


@main_bp.route('/games')
@login_required
def games():
    """Render the AAA gaming platform universe."""
    tab = request.args.get('tab', 'games')
    return _render_hub_view(active_tab=tab)


@main_bp.route('/start_game/<path:game_name>', methods=['POST'])
@csrf.exempt  # Allow beacon and direct AJAX telemetry with current_user session
def start_game(game_name):
    """Log a new game launch event asynchronously via high-throughput event queue."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'unauthorized'}), 401

    clean_game_name = game_name.strip()
    is_dedup, status_code, session_dict = telemetry_queue.enqueue_session_start(
        player_id=current_user.id,
        game_name=clean_game_name
    )
    return jsonify(session_dict)


@main_bp.route('/end_game/<path:game_name>', methods=['POST'])
@csrf.exempt
def end_game(game_name):
    """Log the end of a game session and compute duration asynchronously."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'unauthorized'}), 401

    clean_game_name = game_name.strip()
    result = telemetry_queue.enqueue_session_end(
        player_id=current_user.id,
        game_name=clean_game_name
    )
    return jsonify(result)


@main_bp.route('/api/history')
def api_history():
    """JSON API endpoint returning real-time player history and counts."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'unauthorized', 'history': [], 'count': 0}), 401

    user_sessions = (
        GameplaySession.query
        .filter_by(player_id=current_user.id)
        .order_by(GameplaySession.started_at.desc())
        .limit(100)
        .all()
    )

    history = [s.to_dict() for s in user_sessions]
    return jsonify({
        'username': current_user.username,
        'count': len(history),
        'history': history
    })


GAME_NAME_ALIASES = {
    # 2048
    '2048': '2048',
    '2048 cyber grid': '2048',
    'updown': '2048',
    # Flappy Bird
    'flappy bird': 'flappybird',
    'flappy birds': 'flappybird',
    'flappybird': 'flappybird',
    # Mole
    'mole': 'mole',
    'whack a mole': 'mole',
    'wake a mole': 'mole',
    'mole invasion: whack back!': 'mole',
    'moleeasy': 'mole',
    'molemedium': 'mole',
    'molehard': 'mole',
    # SpeedType
    'speedtype': 'speedtype',
    'speedtype pro': 'speedtype',
    'speedtypepro': 'speedtype',
    # Maze
    'maze': 'maze',
    'cyber labyrinth': 'maze',
    'mazeeasy': 'maze',
    'mazemedium': 'maze',
    'mazehard': 'maze',
    'mazeveasy': 'maze',
    # Pong
    'pong': 'pong',
    'vector pong classic': 'pong',
    'pong easy': 'pong',
    'pongeasy': 'pong',
    'pongmedium': 'pong',
    'ponghard': 'pong',
    'football': 'pong',
    # Candy Crush
    'candy crush': 'candy-crush',
    'candy_crush': 'candy-crush',
    'cyber crush': 'candy-crush',
    # Memory Match
    'memorymatch': 'memorymatch',
    'memory match': 'memorymatch',
    'memory matrix': 'memorymatch',
    'memory match easy': 'memorymatch',
    'matchingeasy': 'memorymatch',
    'matchingmedium': 'memorymatch',
    'matchinghard': 'memorymatch',
    'matchinginsane': 'memorymatch',
    # TicTacToe
    'tictactoe': 'tictactoe',
    'tic-tac-toe': 'tictactoe',
    'quantum tic-tac-toe': 'tictactoe',
    # TowerBlock
    'towerblock': 'towerblock',
    'tower block': 'towerblock',
    'skyline tower block': 'towerblock',
    # Crossword
    'crossword': 'crossword',
    'cross word': 'crossword',
    'neural crossword': 'crossword',
    'animal': 'crossword',
    'anime': 'crossword',
    'cities': 'crossword',
    'movie': 'crossword',
    'sport': 'crossword',
    'state': 'crossword',
    # Quiz
    'quiz': 'quiz',
    'cyber quiz matrix': 'quiz',
    'trivia': 'quiz',
    'trivia madness': 'quiz',
    'aanimal': 'quiz',
    'cartoon': 'quiz',
    'food': 'quiz',
    'gk': 'quiz',
    'history': 'quiz',
    'indiansport': 'quiz',
    'movies': 'quiz',
    'place': 'quiz',
    'riddle': 'quiz',
    # Stone Paper Scissors
    'stonepapersissors': 'stonepapersissors',
    'stone paper scissors': 'stonepapersissors',
    'rock paper scissors': 'stonepapersissors',
    'stonepapersissor': 'stonepapersissors',
    # Tricky
    'tricky': 'tricky',
    'tricky brain quest': 'tricky',
    'trickygame': 'tricky',
    # Relationship
    'relationship': 'relationship',
    'relations': 'relationship',
    'relationshipeasy': 'relationship',
    'relationshiphard': 'relationship',
    'blood relations mystery': 'relationship',
    'blood relations': 'relationship',
    # Sequence
    'sequence': 'sequence',
    'mathsequence': 'sequence',
    'mathsequencegame': 'sequence',
    'sequence number logic': 'sequence',
    # Neon Cyber Racer
    'neon cyber racer': 'neon-cyber-racer',
    'neon-cyber-racer': 'neon-cyber-racer',
}


def _resolve_game(game_name):
    """Resolve any game title, slug, or alias to its canonical Game model instance."""
    if not game_name:
        return None
    clean = game_name.strip()
    norm = clean.lower()

    # Exact or case-insensitive match on title or slug
    matched = Game.query.filter((Game.title.ilike(clean)) | (Game.slug.ilike(clean))).first()
    if matched:
        return matched

    # Lookup alias
    target_slug = GAME_NAME_ALIASES.get(norm)
    if not target_slug:
        for alias_key, alias_slug in GAME_NAME_ALIASES.items():
            if alias_key in norm or norm in alias_key:
                target_slug = alias_slug
                break

    if target_slug:
        return Game.query.filter_by(slug=target_slug).first()

    return None


@main_bp.route('/api/score/submit', methods=['POST'])
@main_bp.route('/api/scores', methods=['POST'])
@csrf.exempt
def submit_score():
    """Submit a high score via asynchronous event queue and live Redis sorted set."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'unauthorized'}), 401

    data = request.get_json(silent=True) or request.form
    game_name = data.get('game_name', '').strip()
    score_val = data.get('score')

    if not game_name or score_val is None:
        return jsonify({'error': 'invalid payload, game_name and score required'}), 400

    try:
        score_int = int(score_val)
        if score_int < 0:
            return jsonify({'error': 'score cannot be negative'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'score must be an integer'}), 400

    matched_game = _resolve_game(game_name)
    canonical_name = matched_game.title if matched_game else game_name

    score_dict = telemetry_queue.enqueue_score(
        player_id=current_user.id,
        username=current_user.username,
        game_name=canonical_name,
        score=score_int
    )

    return jsonify({
        'status': 'success',
        'message': 'Score recorded via high-throughput event queue',
        'score': score_dict
    }), 201


@main_bp.route('/api/v2/session/start', methods=['POST'])
@csrf.exempt
def session_start_v2():
    """Phase 1: Cryptographic session handshake for proof-of-gameplay."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'unauthorized', 'code': 'UNAUTHORIZED'}), 401

    data = request.get_json(silent=True) or request.form
    raw_slug = (data.get('game_slug') or data.get('game_name') or '').strip()
    if not raw_slug:
        return jsonify({'error': 'game_slug or game_name is required', 'code': 'BAD_REQUEST'}), 400

    matched_game = _resolve_game(raw_slug)
    canonical_slug = matched_game.slug if matched_game else raw_slug.lower()
    canonical_title = matched_game.title if matched_game else raw_slug

    start_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    session_token = AntiCheatValidator.generate_session_token(
        player_id=current_user.id,
        game_slug=canonical_slug,
        timestamp_ms=start_time_ms
    )

    # Automatically notify telemetry queue of session initiation
    try:
        telemetry_queue.enqueue_session_start(
            player_id=current_user.id,
            game_name=canonical_title
        )
    except Exception:
        pass

    return jsonify({
        'status': 'success',
        'session_token': session_token,
        'start_time_ms': start_time_ms,
        'game_slug': canonical_slug,
        'game_title': canonical_title,
        'player_id': current_user.id,
        'username': current_user.username
    }), 200


@main_bp.route('/api/v2/session/end', methods=['POST'])
@csrf.exempt
def session_end_v2():
    """Phase 1: Validates cryptographic game session and submits high score."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'unauthorized', 'code': 'UNAUTHORIZED'}), 401

    data = request.get_json(silent=True) or request.form
    game_slug = (data.get('game_slug') or data.get('game_name') or '').strip()
    score_val = data.get('score')
    session_token = data.get('session_token')
    start_time_ms = data.get('start_time_ms')
    action_count = data.get('action_count')
    input_entropy_hash = data.get('input_entropy_hash')

    if not game_slug or score_val is None or not session_token or start_time_ms is None:
        return jsonify({
            'error': 'Missing required fields: game_slug, score, session_token, start_time_ms',
            'code': 'BAD_REQUEST'
        }), 400

    try:
        score_int = int(score_val)
        if score_int < 0:
            return jsonify({'error': 'score cannot be negative', 'code': 'BAD_REQUEST'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'score must be an integer', 'code': 'BAD_REQUEST'}), 400

    try:
        start_time_int = int(start_time_ms)
    except (ValueError, TypeError):
        return jsonify({'error': 'start_time_ms must be an integer timestamp', 'code': 'BAD_REQUEST'}), 400

    action_count_int = None
    if action_count is not None:
        try:
            action_count_int = int(action_count)
        except (ValueError, TypeError):
            pass

    # Resolve matched game for canonical title and slug
    matched_game = _resolve_game(game_slug)
    canonical_slug = matched_game.slug if matched_game else game_slug
    canonical_title = matched_game.title if matched_game else game_slug

    redis_cli = telemetry_queue.redis_client if telemetry_queue.redis_enabled else None

    # Perform Authoritative Anti-Cheat Verification
    is_valid, reason = AntiCheatValidator.validate_submission(
        player_id=current_user.id,
        game_slug=canonical_slug,
        score=score_int,
        start_time_ms=start_time_int,
        session_token=session_token,
        action_count=action_count_int,
        input_entropy_hash=input_entropy_hash,
        redis_client=redis_cli,
        check_replay=True
    )

    if not is_valid:
        if reason == "INVALID_SESSION_SIGNATURE":
            return jsonify({'error': reason, 'code': 'INVALID_SIGNATURE'}), 401
        elif reason == "REPLAY_ATTACK_DETECTED":
            return jsonify({'error': 'Session token has already been consumed', 'code': 'TOKEN_REUSED'}), 401
        elif reason == "SESSION_EXPIRED":
            return jsonify({'error': 'Session token expired', 'code': 'SESSION_EXPIRED'}), 401
        else:
            # Velocity or duration anomalies return 422 Unprocessable Entity
            return jsonify({'error': reason, 'code': 'ANOMALOUS_VELOCITY'}), 422

    # Mark session token as consumed (prevents replay attacks)
    AntiCheatValidator.mark_token_used(session_token, redis_client=redis_cli)

    # Enqueue verified score into live Redis ZSET leaderboard and batch ingestion queue
    score_dict = telemetry_queue.enqueue_score(
        player_id=current_user.id,
        username=current_user.username,
        game_name=canonical_title,
        score=score_int
    )

    return jsonify({
        'status': 'success',
        'message': 'Score cryptographically verified and recorded',
        'verified': True,
        'score': score_dict
    }), 201


@main_bp.route('/api/v2/presence/<path:game_name>')
def get_game_presence(game_name):
    """Phase 3: Retrieve live concurrent player presence."""
    clean_game = game_name.strip()
    matched_game = _resolve_game(clean_game)
    canonical_title = matched_game.title if matched_game else clean_game
    count = telemetry_queue.get_presence(canonical_title)
    return jsonify({
        'status': 'success',
        'game': canonical_title,
        'presence': max(1, count)
    })


@main_bp.route('/api/v2/events/<path:game_name>')
def sse_game_events(game_name):
    """Phase 3: Server-Sent Events (SSE) live broadcast stream for leaderboard overtakes and presence."""
    import queue
    clean_game = game_name.strip()
    matched_game = _resolve_game(clean_game)
    canonical_title = matched_game.title if matched_game else clean_game

    def event_stream():
        q = queue.Queue(maxsize=30)
        with telemetry_queue._lock:
            telemetry_queue._event_listeners[canonical_title].append(q)

        # Increment presence
        telemetry_queue.record_presence(canonical_title, delta=1)
        initial_count = telemetry_queue.get_presence(canonical_title)
        yield f"data: {json.dumps({'type': 'PRESENCE_UPDATE', 'game': canonical_title, 'count': initial_count})}\n\n"

        try:
            while True:
                try:
                    event = q.get(timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
        finally:
            with telemetry_queue._lock:
                if q in telemetry_queue._event_listeners[canonical_title]:
                    telemetry_queue._event_listeners[canonical_title].remove(q)
            telemetry_queue.record_presence(canonical_title, delta=-1)

    return Response(event_stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive'
    })




@main_bp.route('/api/leaderboard/<path:game_name>')
def get_leaderboard(game_name):
    """Retrieve top 10 scores, personal best, and world record with microsecond Redis latency."""
    clean_game_name = game_name.strip()
    matched_game = _resolve_game(clean_game_name)
    canonical_title = matched_game.title if matched_game else clean_game_name
    names_to_match = [clean_game_name]
    if matched_game:
        names_to_match = list(set([matched_game.title, matched_game.slug, clean_game_name]))

    curr_player_id = current_user.id if current_user.is_authenticated else None

    lb_data = telemetry_queue.get_live_leaderboard(
        game_name=canonical_title,
        limit=10,
        current_player_id=curr_player_id,
        names_to_match=names_to_match
    )

    return jsonify({
        'game_name': clean_game_name,
        'canonical_title': canonical_title,
        'leaderboard': lb_data['leaderboard'],
        'user_best': lb_data['user_best'],
        'world_record': lb_data['world_record'],
        'user_rank': lb_data['user_rank'],
        'total_scores_logged': lb_data['total_scores_logged'],
        'queue_mode': telemetry_queue.get_metrics()['mode'],
        'source': lb_data.get('source', 'event_queue')
    })


@main_bp.route('/api/health')
@main_bp.route('/health')
def health_check():
    """Application health check and status telemetry API."""
    try:
        score_count = db.session.query(db.func.count(GameScore.id)).scalar() or 0
        db_status = 'connected'
    except SQLAlchemyError as err:
        score_count = 0
        db_status = f'error: {err!s}'

    q_metrics = telemetry_queue.get_metrics()

    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'scores_logged': score_count,
        'event_queue': q_metrics,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '1.2.0'
    })




@main_bp.route('/profile')
@login_required
def profile():
    """Render player profile overview with statistics and score badges."""
    user_scores = GameScore.query.filter_by(player_id=current_user.id).order_by(GameScore.score.desc()).all()
    user_sessions = GameplaySession.query.filter_by(player_id=current_user.id).order_by(GameplaySession.started_at.desc()).limit(20).all()

    return render_template(
        'profile.html',
        user=current_user,
        scores=user_scores,
        sessions=user_sessions
    )


@main_bp.route('/leaderboard')
def leaderboard_page():
    """Render connected Leaderboard on the unified platform hub."""
    return _render_hub_view(active_tab='leaderboard')


@main_bp.route('/infrastructure')
def infrastructure_page():
    """Render connected Cloudflare Infrastructure architecture on the unified platform hub."""
    return _render_hub_view(active_tab='infrastructure')



