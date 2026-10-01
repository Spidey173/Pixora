"""Seed all 17 arcade games into the Pixora database catalog."""
from app import create_app
from app.extensions import db
from app.models import Game

CATALOG_GAMES = [
    {
        'slug': 'neon-cyber-racer',
        'title': 'Neon Cyber Racer',
        'category': 'Action',
        'description': 'Flagship Phaser 3 arcade racer. Dodge obstacles, drift at relativistic speed, and stream assets at microsecond latency via Cloudflare R2.',
        'thumbnail_url': '/static/Games/Images/neon-cyber-racer.webp',
        'play_url': 'https://pub-bbadfb1090074e17b2f5293b549ce094.r2.dev/games/neon-cyber-racer/index.html',
        'controls_guide': 'Arrow Keys or A/D to steer, Spacebar to boost.',
        'is_featured': True
    },
    {
        'slug': '2048',
        'title': '2048 Cyber Grid',
        'category': 'Puzzle',
        'description': 'Slide numerical data blocks across the neon matrix. Merge matching blocks to synthesize the elusive 2048 singularity.',
        'thumbnail_url': '/static/Games/Images/2048.webp',
        'play_url': '/2048',
        'controls_guide': 'Arrow Keys or Swipe to slide numbered tiles.',
        'is_featured': True
    },
    {
        'slug': 'flappybird',
        'title': 'Flappy Birds',
        'category': 'Arcade',
        'description': 'Pilot an autonomous aerial drone through treacherous data conduit pillars without crashing.',
        'thumbnail_url': '/static/Games/Images/flappybird.webp',
        'play_url': '/FlappyBird',
        'controls_guide': 'Spacebar, Click, or Tap to flap propulsion thrusters.',
        'is_featured': True
    },
    {
        'slug': 'mole',
        'title': 'Whack a Mole',
        'category': 'Arcade',
        'description': 'Eliminate invasive memory bugs popping up through runtime execution registers before they corrupt the heap.',
        'thumbnail_url': '/static/Games/Images/mole.webp',
        'play_url': '/mole',
        'controls_guide': 'Click/Tap on bugs as rapidly as they appear.',
        'is_featured': True
    },
    {
        'slug': 'speedtype',
        'title': 'SpeedType Pro',
        'category': 'Skill',
        'description': 'High-velocity typing simulator for elite hackers. Overclock your keystroke speed and accuracy.',
        'thumbnail_url': '/static/Games/Images/speedtype.webp',
        'play_url': '/speedtype',
        'controls_guide': 'Type highlighted words rapidly into the prompt terminal.',
        'is_featured': False
    },
    {
        'slug': 'maze',
        'title': 'Cyber Labyrinth',
        'category': 'Puzzle',
        'description': 'Navigate complex algorithmic procedurally-generated maze networks to reach the extraction point.',
        'thumbnail_url': '/static/Games/Images/maze.webp',
        'play_url': '/Maze',
        'controls_guide': 'Arrow keys or WASD to navigate through labyrinth corridors.',
        'is_featured': False
    },
    {
        'slug': 'pong',
        'title': 'Vector Pong Classic',
        'category': 'Retro',
        'description': 'The foundational digital duel. Deflect photon energy spheres back and forth against synthetic AI paddle rivals.',
        'thumbnail_url': '/static/Games/Images/pong.webp',
        'play_url': '/pong',
        'controls_guide': 'Up and Down arrow keys to steer your paddle.',
        'is_featured': False
    },
    {
        'slug': 'candy-crush',
        'title': 'Cyber Crush',
        'category': 'Puzzle',
        'description': 'Match triplets of glowing plasma nodes to initiate chain reactions and maximize processing throughput.',
        'thumbnail_url': '/static/Games/Images/candy_crush.webp',
        'play_url': '/Candy_Crush',
        'controls_guide': 'Click and drag adjacent tiles to create matches of 3 or more.',
        'is_featured': False
    },
    {
        'slug': 'memorymatch',
        'title': 'Memory Matrix',
        'category': 'Brain',
        'description': 'Flip holographic cache tiles and identify identical cryptographic symbol pairs before buffer timeout.',
        'thumbnail_url': '/static/Games/Images/MemoryMatch.webp',
        'play_url': '/memorymatch',
        'controls_guide': 'Click cards to flip and match pairs.',
        'is_featured': False
    },
    {
        'slug': 'tictactoe',
        'title': 'Quantum Tic-Tac-Toe',
        'category': 'Strategy',
        'description': 'Engage the local mainframe in an unyielding battle of 3x3 strategic territory acquisition.',
        'thumbnail_url': '/static/Games/Images/TicTacToe.webp',
        'play_url': '/tictactoe',
        'controls_guide': 'Click any empty cell to place your token.',
        'is_featured': False
    },
    {
        'slug': 'towerblock',
        'title': 'Skyline Tower Block',
        'category': 'Arcade',
        'description': 'Stack swinging skyscraper slabs with millisecond precision to construct an infinitely ascending megacity spire.',
        'thumbnail_url': '/static/Games/Images/towerblock.webp',
        'play_url': '/TowerBlock',
        'controls_guide': 'Click or press Spacebar to drop the swinging block.',
        'is_featured': False
    },
    {
        'slug': 'crossword',
        'title': 'Neural Crossword',
        'category': 'Brain',
        'description': 'Decipher encrypted lexical clues to reconstruct neural network language matrices.',
        'thumbnail_url': '/static/Games/Images/crossword.webp',
        'play_url': '/Crossword',
        'controls_guide': 'Click on grid cells and type letters using the keyboard.',
        'is_featured': False
    },
    {
        'slug': 'quiz',
        'title': 'Cyber Quiz Matrix',
        'category': 'Trivia',
        'description': 'Test your intelligence across science, history, geography, and sports in a rapid-fire quiz terminal.',
        'thumbnail_url': '/static/Games/Images/quiz.webp',
        'play_url': '/quiz',
        'controls_guide': 'Select the correct multiple-choice options.',
        'is_featured': False
    },
    {
        'slug': 'stonepapersissors',
        'title': 'Stone Paper Scissors',
        'category': 'Arcade',
        'description': 'Fast-paced rock-paper-scissors challenge against predictive AI simulation models.',
        'thumbnail_url': '/static/Games/Images/stonepapersissors.webp',
        'play_url': '/stonepapersissors',
        'controls_guide': 'Click Rock, Paper, or Scissors to throw your gesture.',
        'is_featured': False
    },
    {
        'slug': 'tricky',
        'title': 'Tricky Brain Quest',
        'category': 'Puzzle',
        'description': 'Mind-bending lateral thinking riddles designed to test cognitive agility and problem solving.',
        'thumbnail_url': '/static/Games/Images/tricky.webp',
        'play_url': '/tricky',
        'controls_guide': 'Read the clues and select the unexpected solution.',
        'is_featured': False
    },
    {
        'slug': 'relationship',
        'title': 'Blood Relations Mystery',
        'category': 'Brain',
        'description': 'Untangle complex genealogical family tree puzzles and test your deductive reasoning.',
        'thumbnail_url': '/static/Games/Images/Relationship.webp',
        'play_url': '/relations',
        'controls_guide': 'Analyze family connections and pick the correct relation.',
        'is_featured': False
    },
    {
        'slug': 'sequence',
        'title': 'Sequence Number Logic',
        'category': 'Puzzle',
        'description': 'Discover algorithmic patterns in numerical sequences and predict the next sequence value.',
        'thumbnail_url': '/static/Games/Images/Sequence.webp',
        'play_url': '/mathsequence',
        'controls_guide': 'Identify mathematical progression and enter the next number.',
        'is_featured': False
    }
]


def seed_catalog():
    """Populate database with default arcade games."""
    app = create_app()
    with app.app_context():
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
                game.controls_guide = item['controls_guide']
                game.is_featured = item.get('is_featured', False)
                updated_count += 1

        db.session.commit()
        print(f"Catalog Seeding Complete: {created_count} created, {updated_count} updated. Total games: {len(CATALOG_GAMES)}")


if __name__ == '__main__':
    seed_catalog()
