"""Comprehensive database reset, catalog population, and authentic arcade telemetry seeding."""
import random
from datetime import datetime, timedelta, timezone

from app import create_app
from app.extensions import db
from app.models import Game, GameScore, GameplaySession, User
from app.utils.seed_games import CATALOG_GAMES

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False


# Legendary Arcade Pilots
PILOTS = [
    {
        'username': 'Pru',
        'is_guest': False,
        'password': 'pru',
        'is_admin': False,
        'bio': 'Pixora Core Pilot'
    },
    {
        'username': 'VortexAce',
        'is_guest': False,
        'password': 'Password123!',
        'is_admin': False,
        'bio': 'Apex racer & speedrun champion'
    },
    {
        'username': 'CyberNinja',
        'is_guest': False,
        'password': 'Password123!',
        'is_admin': False,
        'bio': 'Algorithmic matrix & 2048 grandmaster'
    },
    {
        'username': 'NeonGhost',
        'is_guest': False,
        'password': 'Password123!',
        'is_admin': False,
        'bio': 'Sub-second reaction reflex specialist'
    },
    {
        'username': 'PixelKnight',
        'is_guest': False,
        'password': 'Password123!',
        'is_admin': False,
        'bio': 'Retro arcade tactician & labyrinth navigator'
    },
    {
        'username': 'QuantumPilot',
        'is_guest': False,
        'password': 'Password123!',
        'is_admin': False,
        'bio': 'Precision aeronaut & aerial drone ace'
    },
    {
        'username': 'SynthWave99',
        'is_guest': False,
        'password': 'Password123!',
        'is_admin': False,
        'bio': 'High-velocity typing overclock specialist'
    },
    {
        'username': 'GlitchQueen',
        'is_guest': False,
        'password': 'Password123!',
        'is_admin': False,
        'bio': 'Memory cache and neural crossword solver'
    }
]

# Curated scores per game per pilot (realistic authentic ranges)
CURATED_SCORES = {
    'Neon Cyber Racer': {
        'VortexAce': 9450,
        'Pru': 6420,
        'NeonGhost': 5200,
        'QuantumPilot': 4100,
        'CyberNinja': 3050,
        'SynthWave99': 2400
    },
    '2048 Cyber Grid': {
        'CyberNinja': 4096,
        'Pru': 2048,
        'PixelKnight': 1024,
        'GlitchQueen': 768,
        'VortexAce': 512
    },
    'Whack a Mole': {
        'NeonGhost': 420,
        'GlitchQueen': 340,
        'Pru': 260,
        'SynthWave99': 190,
        'QuantumPilot': 150
    },
    'Flappy Birds': {
        'QuantumPilot': 98,
        'Pru': 68,
        'VortexAce': 52,
        'NeonGhost': 38,
        'PixelKnight': 24
    },
    'SpeedType Pro': {
        'SynthWave99': 132,
        'Pru': 98,
        'CyberNinja': 89,
        'GlitchQueen': 82,
        'PixelKnight': 71
    },
    'Cyber Labyrinth': {
        'PixelKnight': 1840,
        'Pru': 1420,
        'VortexAce': 1150,
        'CyberNinja': 980
    },
    'Vector Pong Classic': {
        'NeonGhost': 21,
        'Pru': 18,
        'QuantumPilot': 15,
        'SynthWave99': 11
    },
    'Cyber Crush': {
        'GlitchQueen': 8450,
        'Pru': 6120,
        'PixelKnight': 4900,
        'SynthWave99': 3800
    },
    'Memory Matrix': {
        'GlitchQueen': 3200,
        'Pru': 2450,
        'CyberNinja': 2100,
        'NeonGhost': 1800
    },
    'Skyline Tower Block': {
        'PixelKnight': 68,
        'Pru': 54,
        'VortexAce': 44,
        'SynthWave99': 36
    },
    'Quantum Tic-Tac-Toe': {
        'CyberNinja': 15,
        'Pru': 12,
        'PixelKnight': 9,
        'VortexAce': 7
    },
    'Neural Crossword': {
        'GlitchQueen': 1200,
        'Pru': 950,
        'CyberNinja': 820,
        'SynthWave99': 640
    },
    'Cyber Quiz Matrix': {
        'CyberNinja': 100,
        'Pru': 90,
        'GlitchQueen': 80,
        'PixelKnight': 70
    },
    'Stone Paper Scissors': {
        'NeonGhost': 18,
        'Pru': 14,
        'QuantumPilot': 11,
        'VortexAce': 8
    },
    'Hex Glitch Match': {
        'GlitchQueen': 4800,
        'Pru': 3900,
        'PixelKnight': 2950
    },
    'Orbital Gravity Runner': {
        'VortexAce': 7200,
        'Pru': 5600,
        'QuantumPilot': 4300
    },
    'Synthwave Pinball': {
        'VortexAce': 18400,
        'Pru': 14200,
        'NeonGhost': 11900
    }
}


def reset_and_seed_everything():
    """Drop, recreate, seed all 17 games, users, gameplay sessions, and curated scores."""
    app = create_app('development')
    with app.app_context():
        print("💥 Resetting database tables...")
        db.drop_all()
        db.create_all()

        # 1. Seed All 17 Games
        print("🎮 Seeding catalog with all 17 titles...")
        game_map = {}
        for item in CATALOG_GAMES:
            game = Game(
                slug=item['slug'],
                title=item['title'],
                category=item['category'],
                description=item['description'],
                thumbnail_url=item['thumbnail_url'],
                play_url=item['play_url'],
                controls_guide=item['controls_guide'],
                is_featured=item.get('is_featured', False),
                is_published=True,
                play_count=0
            )
            db.session.add(game)
            game_map[item['title']] = game
            game_map[item['slug']] = game
        db.session.commit()

        # 2. Seed Admin and Pilots
        print("👥 Seeding administrator and authentic arcade pilots...")
        # Admin account
        admin = User(username='admin', is_admin=True, is_guest=False)
        admin.set_password('admin123')
        db.session.add(admin)

        user_map = {}
        now = datetime.now(timezone.utc)

        for p_info in PILOTS:
            created_days = random.randint(10, 45)
            user = User(
                username=p_info['username'],
                is_guest=p_info['is_guest'],
                is_admin=p_info['is_admin'],
                created_at=now - timedelta(days=created_days),
                last_seen=now - timedelta(minutes=random.randint(2, 120))
            )
            if p_info['password']:
                user.set_password(p_info['password'])
            db.session.add(user)
            user_map[p_info['username']] = user

        db.session.commit()

        # 3. Seed Gameplay Sessions & Authentic Play Counts
        print("⏱️ Seeding gameplay sessions and synchronizing play counts...")
        for game_title, scores_dict in CURATED_SCORES.items():
            g_obj = game_map.get(game_title)
            if not g_obj:
                continue

            session_count = 0
            for username, score_val in scores_dict.items():
                pilot = user_map.get(username)
                if not pilot:
                    continue

                # Pru played Neon Cyber Racer 7 times (matching the user's observed telemetry)
                if username == 'Pru' and game_title == 'Neon Cyber Racer':
                    num_plays = 7
                elif username == 'Pru':
                    num_plays = random.randint(3, 5)
                else:
                    num_plays = random.randint(2, 4)

                for play_idx in range(num_plays):
                    session_count += 1
                    hrs_ago = random.randint(1, 48)
                    started = now - timedelta(hours=hrs_ago, minutes=random.randint(0, 50))
                    duration = random.randint(45, 420)
                    ended = started + timedelta(seconds=duration)

                    session = GameplaySession(
                        player_id=pilot.id,
                        game_name=game_title,
                        started_at=started,
                        ended_at=ended,
                        duration_seconds=duration
                    )
                    db.session.add(session)

                # Record curated high score for this pilot
                achieved = now - timedelta(hours=random.randint(1, 24))
                score = GameScore(
                    player_id=pilot.id,
                    game_name=game_title,
                    score=score_val,
                    achieved_at=achieved
                )
                db.session.add(score)

            # Synchronize Game.play_count with total sessions
            g_obj.play_count = session_count

        db.session.commit()
        print("💾 Database seeding complete! Total users:", User.query.count(),
              "Scores:", GameScore.query.count(),
              "Sessions:", GameplaySession.query.count())

        # 4. Flush and Hydrate Redis
        redis_url = app.config.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
        if REDIS_AVAILABLE:
            try:
                import json
                r = redis.Redis.from_url(redis_url, decode_responses=True)
                if r.ping():
                    print("⚡ Redis connected. Flushing old cache keys...")
                    # Delete any glitch4ce:* keys
                    for k in r.scan_iter("glitch4ce:*"):
                        r.delete(k)

                    print("🚀 Warming Redis Sorted Sets with fresh seed scores...")
                    all_scores = GameScore.query.order_by(GameScore.score.desc()).all()
                    pipe = r.pipeline()
                    for s in all_scores:
                        entry = {
                            'id': s.id,
                            'player_id': s.player_id,
                            'username': s.player.username,
                            'game_name': s.game_name,
                            'score': s.score,
                            'achieved_at': s.achieved_at.isoformat() if s.achieved_at else None
                        }
                        pipe.zadd(f'glitch4ce:lb:entries:{s.game_name}', {json.dumps(entry): s.score})
                        pipe.zadd(f'glitch4ce:lb:bests:{s.game_name}', {f'{s.player_id}:{s.player.username}': s.score}, gt=True)
                    pipe.execute()
                    print("✅ Redis live leaderboards warmed successfully!")
            except Exception as e:
                print("⚠️ Redis warming notice:", e)


if __name__ == '__main__':
    reset_and_seed_everything()
