"""Database Seed and Mock Telemetry Generator Utility."""
import random
from datetime import datetime, timedelta, timezone

from app import create_app
from app.extensions import db
from app.models import GameplaySession, GameScore, User

MOCK_GAMES = [
    '2048', 'Flappy Bird', 'Crossword', 'Candy Crush', 'Pong',
    'Whack-a-Mole', 'Tower Block', 'Memory Match', 'Tic-Tac-Toe', 'Quiz'
]

MOCK_USERNAMES = [
    'CyberNinja', 'NeonRider', 'SynthWave99', 'PixelMaster',
    'RetroGamer', 'GlitchQueen', 'ArcadeHero', 'VaporBoy'
]


def seed_database(count=5):
    """Seed database with mock users, telemetry, and high scores."""
    app = create_app('development')
    with app.app_context():
        print("🌱 Seeding database with mock telemetry...")
        created_users = []

        for username in MOCK_USERNAMES[:count]:
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(
                    username=username,
                    is_guest=(random.random() > 0.5),
                    created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))
                )
                if not user.is_guest:
                    user.set_password('Pass1234!')
                db.session.add(user)
                db.session.commit()
            created_users.append(user)

        for user in created_users:
            # Create 3-7 gameplay sessions
            for _ in range(random.randint(3, 7)):
                game = random.choice(MOCK_GAMES)
                started = datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 100))
                ended = started + timedelta(seconds=random.randint(30, 600))
                session = GameplaySession(
                    player_id=user.id,
                    game_name=game,
                    started_at=started,
                    ended_at=ended,
                    duration_seconds=int((ended - started).total_seconds())
                )
                db.session.add(session)

                # Add high score entry
                score_val = random.randint(100, 9500)
                score = GameScore(
                    player_id=user.id,
                    game_name=game,
                    score=score_val,
                    achieved_at=ended
                )
                db.session.add(score)

        db.session.commit()
        print("✅ Database successfully seeded!")


if __name__ == '__main__':
    seed_database()
