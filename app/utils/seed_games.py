"""Seed all 17 arcade games into the Pixora database catalog following the Platform / Poki Architecture.

Architectural Model:
- The platform repository is the infrastructure engine (Auth, Anti-Cheat, High Scores, Real-Time Streams).
- 3 Featured games remain directly inside repository templates to demonstrate the PixoraSDK v2
  authoritative anti-cheat handshake (2048, Flappy Bird, SpeedType Pro).
- The remaining 14 catalog games are stored as static web bundles in /public/games/ (or Cloudflare R2 / AWS S3)
  and loaded via fast, same-origin/CDN iframes.
"""
import os
import random
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Game

CDN_BASE_URL = os.environ.get('CDN_BASE_URL', '').rstrip('/')


def _bundle_url(subpath: str) -> str:
    """Resolve game bundle playable URL according to Poki architecture."""
    if CDN_BASE_URL and 'cdn.pixora.com' not in CDN_BASE_URL:
        return f"{CDN_BASE_URL}/games/{subpath}/index.html"
    return f"https://cdn.pixora.com/games/{subpath}/index.html"


CATALOG_GAMES = [
    # ── 1. NEON CYBER RACER (CATALOG GAME VIA POKI BUNDLE) ────
    {
        'slug': 'neon-cyber-racer',
        'title': 'Neon Cyber Racer',
        'category': 'Action',
        'description': 'Flagship Phaser 3 arcade racer. Dodge obstacles, drift at relativistic speed, and stream assets at microsecond latency via Cloudflare R2.',
        'thumbnail_url': '/static/Games/Images/neon-cyber-racer.webp',
        'play_url': _bundle_url('neon-racer'),
        'r2_asset_key': 'games/neon-racer/index.html',
        'controls_guide': 'Arrow Keys or A/D to steer, Spacebar to boost.',
        'is_featured': False
    },

    # ── 2. 2048 CYBER GRID (FEATURED IN-REPO DEMO #1) ──────────
    {
        'slug': '2048',
        'title': '2048 Cyber Grid',
        'category': 'Puzzle',
        'description': 'Slide numerical data blocks across the neon matrix. Demonstrates the PixoraSDK v2 authoritative anti-cheat handshake and action entropy.',
        'thumbnail_url': '/static/Games/Images/2048.webp',
        'play_url': '/2048',
        'r2_asset_key': None,
        'controls_guide': 'Arrow Keys or Swipe to slide numbered tiles.',
        'is_featured': True
    },

    # ── 3. FLAPPY BIRD (FEATURED IN-REPO DEMO #2) ──────────────
    {
        'slug': 'flappybird',
        'title': 'Flappy Birds',
        'category': 'Arcade',
        'description': 'Pilot an autonomous aerial drone through treacherous conduit pillars. Demonstrates sub-second action telemetry and score verification.',
        'thumbnail_url': '/static/Games/Images/flappybird.webp',
        'play_url': '/FlappyBird',
        'r2_asset_key': None,
        'controls_guide': 'Spacebar, Click, or Tap to flap propulsion thrusters.',
        'is_featured': True
    },

    # ── 4. SPEEDTYPE PRO (FEATURED IN-REPO DEMO #3) ────────────
    {
        'slug': 'speedtype',
        'title': 'SpeedType Pro',
        'category': 'Skill',
        'description': 'High-velocity typing simulator for elite hackers. Demonstrates keystroke entropy logging and cryptographic session lifecycle.',
        'thumbnail_url': '/static/Games/Images/speedtype.webp',
        'play_url': '/speedtype',
        'r2_asset_key': None,
        'controls_guide': 'Type highlighted words rapidly into the prompt terminal.',
        'is_featured': True
    },

    # ── 5. WHACK A MOLE (CATALOG GAME VIA POKI BUNDLE) ────────
    {
        'slug': 'mole',
        'title': 'Whack a Mole',
        'category': 'Arcade',
        'description': 'Eliminate invasive memory bugs popping up through runtime execution registers before they corrupt the heap.',
        'thumbnail_url': '/static/Games/Images/mole.webp',
        'play_url': _bundle_url('mole'),
        'r2_asset_key': 'games/mole/index.html',
        'controls_guide': 'Click/Tap on bugs as rapidly as they appear.',
        'is_featured': False
    },

    # ── 6. CYBER LABYRINTH (CATALOG GAME VIA POKI BUNDLE) ─────
    {
        'slug': 'maze',
        'title': 'Cyber Labyrinth',
        'category': 'Puzzle',
        'description': 'Navigate complex algorithmic procedurally-generated maze networks to reach the extraction point.',
        'thumbnail_url': '/static/Games/Images/maze.webp',
        'play_url': _bundle_url('maze'),
        'r2_asset_key': 'games/maze/index.html',
        'controls_guide': 'Arrow keys or WASD to navigate through labyrinth corridors.',
        'is_featured': False
    },

    # ── 7. VECTOR PONG CLASSIC (CATALOG GAME VIA POKI BUNDLE) ─
    {
        'slug': 'pong',
        'title': 'Vector Pong Classic',
        'category': 'Retro',
        'description': 'The foundational digital duel. Deflect photon energy spheres back and forth against synthetic AI paddle rivals.',
        'thumbnail_url': '/static/Games/Images/pong.webp',
        'play_url': _bundle_url('pong'),
        'r2_asset_key': 'games/pong/index.html',
        'controls_guide': 'Up and Down arrow keys to steer your paddle.',
        'is_featured': False
    },

    # ── 8. CYBER CRUSH (CATALOG GAME VIA POKI BUNDLE) ─────────
    {
        'slug': 'candy-crush',
        'title': 'Cyber Crush',
        'category': 'Puzzle',
        'description': 'Match triplets of glowing plasma nodes to initiate chain reactions and maximize processing throughput.',
        'thumbnail_url': '/static/Games/Images/candy_crush.webp',
        'play_url': _bundle_url('candy-crush'),
        'r2_asset_key': 'games/candy-crush/index.html',
        'controls_guide': 'Click and drag adjacent tiles to create matches of 3 or more.',
        'is_featured': False
    },

    # ── 9. MEMORY MATRIX (CATALOG GAME VIA POKI BUNDLE) ───────
    {
        'slug': 'memorymatch',
        'title': 'Memory Matrix',
        'category': 'Brain',
        'description': 'Flip holographic cache tiles and identify identical cryptographic symbol pairs before buffer timeout.',
        'thumbnail_url': '/static/Games/Images/MemoryMatch.webp',
        'play_url': _bundle_url('memorymatch'),
        'r2_asset_key': 'games/memorymatch/index.html',
        'controls_guide': 'Click cards to flip and match pairs.',
        'is_featured': False
    },

    # ── 10. QUANTUM TIC-TAC-TOE (CATALOG GAME VIA POKI BUNDLE) 
    {
        'slug': 'tictactoe',
        'title': 'Quantum Tic-Tac-Toe',
        'category': 'Strategy',
        'description': 'Engage the local mainframe in an unyielding battle of 3x3 strategic territory acquisition.',
        'thumbnail_url': '/static/Games/Images/TicTacToe.webp',
        'play_url': _bundle_url('tictactoe'),
        'r2_asset_key': 'games/tictactoe/index.html',
        'controls_guide': 'Click any empty cell to place your token.',
        'is_featured': False
    },

    # ── 11. SKYLINE TOWER BLOCK (CATALOG GAME VIA POKI BUNDLE) 
    {
        'slug': 'towerblock',
        'title': 'Skyline Tower Block',
        'category': 'Arcade',
        'description': 'Stack swinging skyscraper slabs with millisecond precision to construct an infinitely ascending megacity spire.',
        'thumbnail_url': '/static/Games/Images/towerblock.webp',
        'play_url': _bundle_url('towerblock'),
        'r2_asset_key': 'games/towerblock/index.html',
        'controls_guide': 'Click or press Spacebar to drop the swinging block.',
        'is_featured': False
    },

    # ── 12. NEURAL CROSSWORD (CATALOG GAME VIA POKI BUNDLE) ───
    {
        'slug': 'crossword',
        'title': 'Neural Crossword',
        'category': 'Brain',
        'description': 'Decipher encrypted lexical clues to reconstruct neural network language matrices.',
        'thumbnail_url': '/static/Games/Images/crossword.webp',
        'play_url': _bundle_url('crossword'),
        'r2_asset_key': 'games/crossword/index.html',
        'controls_guide': 'Click on grid cells and type letters using the keyboard.',
        'is_featured': False
    },

    # ── 13. CYBER QUIZ MATRIX (CATALOG GAME VIA POKI BUNDLE) ──
    {
        'slug': 'quiz',
        'title': 'Cyber Quiz Matrix',
        'category': 'Trivia',
        'description': 'Test your intelligence across science, history, geography, and sports in a rapid-fire quiz terminal.',
        'thumbnail_url': '/static/Games/Images/quiz.webp',
        'play_url': _bundle_url('quiz'),
        'r2_asset_key': 'games/quiz/index.html',
        'controls_guide': 'Select the correct multiple-choice options.',
        'is_featured': False
    },

    # ── 14. STONE PAPER SCISSORS (CATALOG GAME VIA POKI BUNDLE) 
    {
        'slug': 'stonepapersissors',
        'title': 'Stone Paper Scissors',
        'category': 'Arcade',
        'description': 'Fast-paced rock-paper-scissors challenge against predictive AI simulation models.',
        'thumbnail_url': '/static/Games/Images/stonepapersissors.webp',
        'play_url': _bundle_url('stonepapersissors'),
        'r2_asset_key': 'games/stonepapersissors/index.html',
        'controls_guide': 'Click Rock, Paper, or Scissors to throw your gesture.',
        'is_featured': False
    },

    # ── 15. TRICKY BRAIN QUEST (CATALOG GAME VIA POKI BUNDLE) ─
    {
        'slug': 'tricky',
        'title': 'Tricky Brain Quest',
        'category': 'Puzzle',
        'description': 'Mind-bending lateral thinking riddles designed to test cognitive agility and problem solving.',
        'thumbnail_url': '/static/Games/Images/tricky.webp',
        'play_url': _bundle_url('tricky'),
        'r2_asset_key': 'games/tricky/index.html',
        'controls_guide': 'Read the clues and select the unexpected solution.',
        'is_featured': False
    },

    # ── 16. BLOOD RELATIONS (CATALOG GAME VIA POKI BUNDLE) ────
    {
        'slug': 'relationship',
        'title': 'Blood Relations Mystery',
        'category': 'Brain',
        'description': 'Untangle complex genealogical family tree puzzles and test your deductive reasoning.',
        'thumbnail_url': '/static/Games/Images/Relationship.webp',
        'play_url': _bundle_url('relationship'),
        'r2_asset_key': 'games/relationship/index.html',
        'controls_guide': 'Analyze family connections and pick the correct relation.',
        'is_featured': False
    },

    # ── 17. SEQUENCE NUMBER LOGIC (CATALOG GAME VIA POKI BUNDLE) 
    {
        'slug': 'sequence',
        'title': 'Sequence Number Logic',
        'category': 'Puzzle',
        'description': 'Discover algorithmic patterns in numerical sequences and predict the next sequence value.',
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
