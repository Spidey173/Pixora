"""Unit tests for SQLAlchemy models."""
from app.extensions import db
from app.models import GameplaySession, GameScore, User


def test_user_creation_and_password_hashing(app):
    """Test user creation, password hashing, and verification."""
    with app.app_context():
        user = User(username='NeoPlayer', is_guest=False)
        user.set_password('Synthwave2026!')
        db.session.add(user)
        db.session.commit()

        queried = User.query.filter_by(username='NeoPlayer').first()
        assert queried is not None
        assert queried.username == 'NeoPlayer'
        assert queried.password_hash is not None
        assert queried.password_hash != 'Synthwave2026!'
        assert queried.check_password('Synthwave2026!') is True
        assert queried.check_password('WrongPass!') is False
        assert queried.is_authenticated is True


def test_gameplay_session_relationship(app, test_user):
    """Test relationship between User and GameplaySession."""
    with app.app_context():
        user = db.session.get(User, test_user.id)
        session1 = GameplaySession(player_id=user.id, game_name='2048')
        session2 = GameplaySession(player_id=user.id, game_name='Flappy Bird')
        db.session.add_all([session1, session2])
        db.session.commit()

        assert user.total_plays == 2
        sessions = user.sessions.all()
        assert len(sessions) == 2
        game_names = [s.game_name for s in sessions]
        assert '2048' in game_names
        assert 'Flappy Bird' in game_names


def test_game_score_model_and_highest_score(app, test_user):
    """Test GameScore model, user highest_score property, and dictionary serialization."""
    with app.app_context():
        user = db.session.get(User, test_user.id)
        assert user.highest_score == 0

        score1 = GameScore(player_id=user.id, game_name='2048', score=1200)
        score2 = GameScore(player_id=user.id, game_name='Flappy Bird', score=4500)
        db.session.add_all([score1, score2])
        db.session.commit()

        assert user.highest_score == 4500
        score_dict = score2.to_dict()
        assert score_dict['score'] == 4500
        assert score_dict['game_name'] == 'Flappy Bird'
        assert score_dict['username'] == user.username


def test_cascade_delete(app, test_user):
    """Test that deleting a user cascades to their gameplay sessions and scores."""
    with app.app_context():
        user = db.session.get(User, test_user.id)
        session1 = GameplaySession(player_id=user.id, game_name='Maze')
        score1 = GameScore(player_id=user.id, game_name='Maze', score=900)
        db.session.add_all([session1, score1])
        db.session.commit()

        assert GameplaySession.query.filter_by(player_id=user.id).count() == 1
        assert GameScore.query.filter_by(player_id=user.id).count() == 1

        db.session.delete(user)
        db.session.commit()

        assert GameplaySession.query.filter_by(player_id=test_user.id).count() == 0
        assert GameScore.query.filter_by(player_id=test_user.id).count() == 0

