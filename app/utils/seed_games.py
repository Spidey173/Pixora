"""Seed the 17 arcade games into the Pixora database catalog."""
import os
import random
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Game

CDN_BASE_URL = os.environ.get('CDN_BASE_URL', '').rstrip('/')


def _bundle_url(subpath: str) -> str:
    """Return the playable URL for a game bundle."""
    if CDN_BASE_URL and 'cdn.pixora.com' not in CDN_BASE_URL:
        return f"{CDN_BASE_URL}/games/{subpath}/index.html"
    return f"https://cdn.pixora.com/games/{subpath}/index.html"


CATALOG_GAMES = [
    {
        'slug': 'neon-cyber-racer',
        'title': 'Neon Cyber Racer',
        'category': 'Action',
        'description': 'Fast-paced arcade racer. Dodge obstacles, steer, and boost to high speed.',
        'thumbnail_url': '/static/Games/Images/neon-cyber-racer.webp',
        'play_url': _bundle_url('neon-racer'),
        'r2_asset_key': 'games/neon-racer/index.html',
        'controls_guide': 'Arrow Keys or A/D to steer, Spacebar to boost.',
        'is_featured': False
    },
    {
        'slug': '2048',
        'title': '2048 Cyber Grid',
        'category': 'Puzzle',
        'description': 'Slide numbered tiles across the grid and combine them to reach 2048.',
        'thumbnail_url': '/static/Games/Images/2048.webp',
        'play_url': '/2048',
        'r2_asset_key': None,
        'controls_guide': 'Arrow Keys or Swipe to slide numbered tiles.',
        'is_featured': True
    },
    {
        'slug': 'flappybird',
        'title': 'Flappy Birds',
        'category': 'Arcade',
        'description': 'Guide your bird through obstacles by tapping or pressing the spacebar.',
        'thumbnail_url': '/static/Games/Images/flappybird.webp',
        'play_url': '/FlappyBird',
        'r2_asset_key': None,
        'controls_guide': 'Spacebar, Click, or Tap to flap propulsion thrusters.',
        'is_featured': True
    },
    {
        'slug': 'speedtype',
        'title': 'SpeedType Pro',
        'category': 'Skill',
        'description': 'Test and improve your typing speed and accuracy by typing displayed words.',
        'thumbnail_url': '/static/Games/Images/speedtype.webp',
        'play_url': '/speedtype',
        'r2_asset_key': None,
        'controls_guide': 'Type highlighted words rapidly into the prompt terminal.',
        'is_featured': True
    },
    {
        'slug': 'mole',
        'title': 'Whack a Mole',
        'category': 'Arcade',
        'description': 'Click or tap on moles as quickly as they appear before they hide.',
        'thumbnail_url': '/static/Games/Images/mole.webp',
        'play_url': _bundle_url('mole'),
        'r2_asset_key': 'games/mole/index.html',
        'controls_guide': 'Click/Tap on bugs as rapidly as they appear.',
        'is_featured': False
    },
    {
        'slug': 'maze',
        'title': 'Cyber Labyrinth',
        'category': 'Puzzle',
        'description': 'Find your way through labyrinth corridors to reach the exit.',
        'thumbnail_url': '/static/Games/Images/maze.webp',
        'play_url': _bundle_url('maze'),
        'r2_asset_key': 'games/maze/index.html',
        'controls_guide': 'Arrow keys or WASD to navigate through labyrinth corridors.',
        'is_featured': False
    },
    {
        'slug': 'pong',
        'title': 'Vector Pong Classic',
        'category': 'Retro',
        'description': 'Classic paddle game. Move your paddle up and down to deflect the ball.',
        'thumbnail_url': '/static/Games/Images/pong.webp',
        'play_url': _bundle_url('pong'),
        'r2_asset_key': 'games/pong/index.html',
        'controls_guide': 'Up and Down arrow keys to steer your paddle.',
        'is_featured': False
    },
    {
        'slug': 'candy-crush',
        'title': 'Cyber Crush',
        'category': 'Puzzle',
        'description': 'Match 3 or more adjacent tiles of the same color to clear them.',
        'thumbnail_url': '/static/Games/Images/candy_crush.webp',
        'play_url': _bundle_url('candy-crush'),
        'r2_asset_key': 'games/candy-crush/index.html',
        'controls_guide': 'Click and drag adjacent tiles to create matches of 3 or more.',
        'is_featured': False
    },
    {
        'slug': 'memorymatch',
        'title': 'Memory Matrix',
        'category': 'Brain',
        'description': 'Flip cards to find and match pairs before time runs out.',
        'thumbnail_url': '/static/Games/Images/MemoryMatch.webp',
        'play_url': _bundle_url('memorymatch'),
        'r2_asset_key': 'games/memorymatch/index.html',
        'controls_guide': 'Click cards to flip and match pairs.',
        'is_featured': False
    },
    {
        'slug': 'tictactoe',
        'title': 'Quantum Tic-Tac-Toe',
        'category': 'Strategy',
        'description': 'Classic 3x3 Tic-Tac-Toe game against the computer.',
        'thumbnail_url': '/static/Games/Images/TicTacToe.webp',
        'play_url': _bundle_url('tictactoe'),
        'r2_asset_key': 'games/tictactoe/index.html',
        'controls_guide': 'Click any empty cell to place your token.',
        'is_featured': False
    },
    {
        'slug': 'towerblock',
        'title': 'Skyline Tower Block',
        'category': 'Arcade',
        'description': 'Stack swinging skyscraper blocks to build the tallest tower possible.',
        'thumbnail_url': '/static/Games/Images/towerblock.webp',
        'play_url': _bundle_url('towerblock'),
        'r2_asset_key': 'games/towerblock/index.html',
        'controls_guide': 'Click or press Spacebar to drop the swinging block.',
        'is_featured': False
    },
    {
        'slug': 'crossword',
        'title': 'Neural Crossword',
        'category': 'Brain',
        'description': 'Solve crossword clues to fill the grid with the correct words.',
        'thumbnail_url': '/static/Games/Images/crossword.webp',
        'play_url': _bundle_url('crossword'),
        'r2_asset_key': 'games/crossword/index.html',
        'controls_guide': 'Click on grid cells and type letters using the keyboard.',
        'is_featured': False
    },
    {
        'slug': 'quiz',
        'title': 'Cyber Quiz Matrix',
        'category': 'Trivia',
        'description': 'Answer trivia questions across science, history, geography, and sports.',
        'thumbnail_url': '/static/Games/Images/quiz.webp',
        'play_url': _bundle_url('quiz'),
        'r2_asset_key': 'games/quiz/index.html',
        'controls_guide': 'Select the correct multiple-choice options.',
        'is_featured': False
    },
    {
        'slug': 'stonepapersissors',
        'title': 'Stone Paper Scissors',
        'category': 'Arcade',
        'description': 'Classic rock, paper, scissors game against the computer.',
        'thumbnail_url': '/static/Games/Images/stonepapersissors.webp',
        'play_url': _bundle_url('stonepapersissors'),
        'r2_asset_key': 'games/stonepapersissors/index.html',
        'controls_guide': 'Click Rock, Paper, or Scissors to throw your gesture.',
        'is_featured': False
    },
    {
        'slug': 'tricky',
        'title': 'Tricky Brain Quest',
        'category': 'Puzzle',
        'description': 'Fun riddles and brain teasers that test problem-solving skills.',
        'thumbnail_url': '/static/Games/Images/tricky.webp',
        'play_url': _bundle_url('tricky'),
        'r2_asset_key': 'games/tricky/index.html',
        'controls_guide': 'Read the clues and select the unexpected solution.',
        'is_featured': False
    },
    {
        'slug': 'relationship',
        'title': 'Blood Relations Mystery',
        'category': 'Brain',
        'description': 'Solve family tree puzzles to determine who is related to whom.',
        'thumbnail_url': '/static/Games/Images/Relationship.webp',
        'play_url': _bundle_url('relationship'),
        'r2_asset_key': 'games/relationship/index.html',
        'controls_guide': 'Analyze family connections and pick the correct relation.',
        'is_featured': False
    },
    {
        'slug': 'sequence',
        'title': 'Sequence Number Logic',
        'category': 'Puzzle',
        'description': 'Find the pattern in number sequences and guess the next number.',
        'thumbnail_url': '/static/Games/Images/Sequence.webp',
        'play_url': _bundle_url('sequence'),
        'r2_asset_key': 'games/sequence/index.html',
        'controls_guide': 'Identify mathematical progression and enter the next number.',
        'is_featured': False
    }
]


def _populate_catalog_entries():
    """Execute insertion of catalog games and baseline leaderboard scores into active session."""
    created_count = 0
    updated_count = 0

    for item in CATALOG_GAMES:
        game = Game.query.filter_by(slug=item['slug']).first()
        if not game:
            game = Game(
                slug=item['slug'],
                title=item['title'],
                category=item['category'],
                description=item['description'],
                thumbnail_url=item['thumbnail_url'],
                play_url=item['play_url'],
                r2_asset_key=item.get('r2_asset_key'),
                controls_guide=item['controls_guide'],
                is_featured=item.get('is_featured', False),
                is_published=True
            )
            db.session.add(game)
            created_count += 1
        else:
            game.title = item['title']
            game.category = item['category']
            game.description = item['description']
            game.thumbnail_url = item['thumbnail_url']
            game.play_url = item['play_url']
            game.r2_asset_key = item.get('r2_asset_key')
            game.controls_guide = item['controls_guide']
            game.is_featured = item.get('is_featured', False)
            updated_count += 1

    db.session.commit()
    print(f"🎮 Catalog Seeding Complete: {created_count} created, {updated_count} updated. Total games: {len(CATALOG_GAMES)}")

    # Seed baseline pilots and leaderboard scores if table is empty
    from app.models import User, GameScore, GameplaySession
    if GameScore.query.count() == 0:
        try:
            from app.utils.reset_and_seed import PILOTS, CURATED_SCORES
            user_map = {}
            for p_info in PILOTS:
                u = User.query.filter_by(username=p_info['username']).first()
                if not u:
                    u = User(
                        username=p_info['username'],
                        is_guest=p_info.get('is_guest', False),
                        is_admin=p_info.get('is_admin', False)
                    )
                    if p_info.get('password'):
                        u.set_password(p_info['password'])
                    db.session.add(u)
                    db.session.flush()
                user_map[p_info['username']] = u

            now = datetime.now(timezone.utc)
            score_count = 0
            for game_title, scores_dict in CURATED_SCORES.items():
                for username, score_val in scores_dict.items():
                    pilot = user_map.get(username)
                    if pilot:
                        score = GameScore(
                            player_id=pilot.id,
                            game_name=game_title,
                            score=score_val,
                            achieved_at=now - timedelta(hours=random.randint(1, 24))
                        )
                        db.session.add(score)
                        score_count += 1

                        # Also add a matching GameplaySession
                        dur = random.randint(45, 300)
                        session = GameplaySession(
                            player_id=pilot.id,
                            game_name=game_title,
                            started_at=now - timedelta(hours=random.randint(1, 24), seconds=dur),
                            ended_at=now - timedelta(hours=random.randint(1, 24)),
                            duration_seconds=dur
                        )
                        db.session.add(session)

            db.session.commit()
            print(f"🏆 Championship Leaderboards seeded with {score_count} authentic scores across top pilots.")
        except Exception as seed_err:
            db.session.rollback()
            print("Leaderboard baseline seed skipped:", seed_err)


def seed_catalog(app=None):
    """Populate database with default arcade games using pure SQLAlchemy."""
    db.create_all()
    _populate_catalog_entries()


if __name__ == '__main__':
    seed_catalog()
