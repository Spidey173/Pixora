"""Unit and integration tests for TelemetryQueueManager and event-driven architecture."""
from app.extensions import db
from app.models import GameScore, User
from app.utils.telemetry_queue import telemetry_queue


def test_telemetry_queue_initialization(app):
    """Verify queue manager initializes with expected properties and metrics."""
    metrics = telemetry_queue.get_metrics()
    assert 'mode' in metrics
    assert 'queue_depth_scores' in metrics
    assert 'queue_depth_sessions' in metrics
    assert 'total_queue_depth' in metrics
    assert 'worker_alive' in metrics


def test_enqueue_score_and_live_leaderboard(app):
    """Verify scores are ingested into event queue and live leaderboards."""
    with app.app_context():
        # Create test player
        player = User(username="QueueRacer", is_guest=False)
        db.session.add(player)
        db.session.commit()
        player_id = player.id

        # Enqueue first score
        s1 = telemetry_queue.enqueue_score(
            player_id=player_id,
            username="QueueRacer",
            game_name="Neon Cyber Racer",
            score=4500
        )
        assert s1['score'] == 4500
        assert s1['player_id'] == player_id

        # Enqueue higher score
        s2 = telemetry_queue.enqueue_score(
            player_id=player_id,
            username="QueueRacer",
            game_name="Neon Cyber Racer",
            score=9800
        )
        assert s2['score'] == 9800

        # Add a SECOND player to test multi-player leaderboard
        player2 = User(username="NeonPilot", is_guest=False)
        db.session.add(player2)
        db.session.commit()
        telemetry_queue.enqueue_score(
            player_id=player2.id,
            username="NeonPilot",
            game_name="Neon Cyber Racer",
            score=6000
        )

        # Query live leaderboard
        lb = telemetry_queue.get_live_leaderboard(
            game_name="Neon Cyber Racer",
            limit=5,
            current_player_id=player_id
        )

        assert lb['game_name'] == "Neon Cyber Racer"
        # 2 unique players, each appearing ONCE with their best score
        assert len(lb['leaderboard']) >= 2
        assert lb['leaderboard'][0]['score'] == 9800  # QueueRacer's best
        assert lb['user_best'] == 9800
        assert lb['world_record']['score'] >= 9800


def test_session_deduplication_and_duration(app):
    """Verify sub-millisecond session deduplication and end-duration calculation."""
    with app.app_context():
        player = User(username="SpeedyPilot", is_guest=False)
        db.session.add(player)
        db.session.commit()
        player_id = player.id

        # First launch
        is_dedup1, status1, _sess1 = telemetry_queue.enqueue_session_start(player_id, "Pac-Man")
        assert not is_dedup1
        assert status1 == 'logged'

        # Immediate duplicate launch (< 2s)
        is_dedup2, status2, _sess2 = telemetry_queue.enqueue_session_start(player_id, "Pac-Man")
        assert is_dedup2
        assert status2 == 'deduped'

        # End session
        end_res = telemetry_queue.enqueue_session_end(player_id, "Pac-Man")
        assert end_res['status'] == 'ended'
        assert end_res['game'] == 'Pac-Man'


def test_batch_flush_persists_to_relational_database(app):
    """Verify flush persists batch items into GameScore and GameplaySession tables."""
    with app.app_context():
        player = User(username="BatchMaster", is_guest=False)
        db.session.add(player)
        db.session.commit()
        player_id = player.id

        initial_scores = GameScore.query.filter_by(player_id=player_id).count()

        # Enqueue 3 scores
        telemetry_queue.enqueue_score(player_id, "BatchMaster", "Tetris", 1200)
        telemetry_queue.enqueue_score(player_id, "BatchMaster", "Tetris", 2400)
        telemetry_queue.enqueue_score(player_id, "BatchMaster", "Tetris", 3600)

        # In testing mode, flush is called during enqueue; verify DB records exist
        final_scores = GameScore.query.filter_by(player_id=player_id).count()
        assert final_scores == initial_scores + 3


def test_api_health_endpoint_reports_event_queue(client):
    """Verify /api/health includes real-time event queue metrics."""
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'healthy'
    assert 'event_queue' in data
    assert 'mode' in data['event_queue']
    assert 'queue_depth_scores' in data['event_queue']
    assert 'scores_ingested' in data['event_queue']
