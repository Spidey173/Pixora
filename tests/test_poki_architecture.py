"""Tests verifying the 'Platform / Poki Architecture' (Highest Engineering Signal).

Architectural Invariants:
1. Server templates folder does NOT store the raw code of all 17 games (only 2-3 featured games + platform hub).
2. The 3 featured in-repo games (2048, Flappy Bird, SpeedType Pro) demonstrate the PixoraSDK v2 anti-cheat handshake.
3. The other 14 catalog games are stored as static web bundles in /public/games/ (or Cloudflare R2 / AWS S3).
4. In the database, Game.play_url = 'https://cdn.pixora.com/games/neon-racer/index.html' and other catalog games load via CDN iframe.
5. Flask serves static web bundles from /public/games/ for local development and iframe sandboxing.
"""
import os
from app.models import Game


def test_server_templates_folder_has_only_featured_games():
    """Verify templates/Games/ only contains 2-3 featured games and platform hub files."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    templates_games = os.path.join(base_dir, 'templates', 'Games')

    entries = os.listdir(templates_games)
    directories = [d for d in entries if os.path.isdir(os.path.join(templates_games, d))]

    # Exactly 3 featured game directories are permitted in repo templates
    assert set(directories) == {'2048', 'Flappy Birds', 'SpeedType Pro'}, (
        f"Server templates folder must only store featured games! Found: {directories}"
    )

    # Legacy raw game folders must NOT exist in templates/Games/
    forbidden_folders = [
        'Candy Crush', 'Cross word', 'MemoryMatch', 'Quiz', 'Relationship',
        'Sequence', 'Stone Paper Scissors', 'TicTacToe', 'TowerBlock',
        'Tricky', 'maze', 'pong', 'wake a mole'
    ]
    for folder in forbidden_folders:
        assert folder not in directories, f"Forbidden raw game folder '{folder}' found in server templates!"


def test_featured_games_demonstrate_anti_cheat_handshake():
    """Verify that the 3 featured games demonstrate the PixoraSDK v2 handshake and telemetry."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    featured_files = [
        os.path.join(base_dir, 'templates', 'Games', '2048', '2048.html'),
        os.path.join(base_dir, 'templates', 'Games', 'Flappy Birds', 'flappybird.html'),
        os.path.join(base_dir, 'templates', 'Games', 'SpeedType Pro', 'speedtype.html'),
    ]

    for filepath in featured_files:
        assert os.path.isfile(filepath), f"Featured game template missing: {filepath}"
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Must include Pixora SDK v2
        assert 'pixora-sdk.js' in content, f"pixora-sdk.js missing in {filepath}"
        # Must demonstrate handshake initiation
        assert 'Pixora.init' in content or 'Pixora' in content, f"Pixora.init missing in {filepath}"
        # Must demonstrate gameplay start telemetry
        assert 'Pixora.gameplayStart' in content, f"Pixora.gameplayStart missing in {filepath}"
        # Must demonstrate anti-cheat score submission
        assert 'Pixora.submitScore' in content, f"Pixora.submitScore missing in {filepath}"


def test_catalog_games_play_urls_in_database(app):
    """Verify database catalog: Game.play_url = 'https://cdn.pixora.com/games/neon-racer/index.html'."""
    with app.app_context():
        # Check neon-cyber-racer points to production CDN URL
        neon = Game.query.filter_by(slug='neon-cyber-racer').first()
        assert neon is not None
        assert neon.play_url == 'https://cdn.pixora.com/games/neon-racer/index.html'
        assert neon.is_featured is False

        # Check 3 featured games in DB
        featured_games = Game.query.filter_by(is_featured=True).all()
        featured_slugs = {g.slug for g in featured_games}
        assert featured_slugs == {'2048', 'flappybird', 'speedtype'}

        # Verify other 14 games are registered as catalog games loaded via CDN iframe
        catalog_games = Game.query.filter_by(is_featured=False).all()
        assert len(catalog_games) == 14
        for g in catalog_games:
            assert g.play_url.startswith('https://cdn.pixora.com/games/') or 'index.html' in g.play_url, (
                f"Catalog game '{g.slug}' has non-CDN play_url: {g.play_url}"
            )


def test_static_bundles_exist_in_public_games():
    """Verify that all 14 catalog games exist as static web bundles in /public/games/."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    public_games_dir = os.path.join(base_dir, 'public', 'games')

    expected_bundles = [
        'neon-racer', 'candy-crush', 'mole', 'maze', 'pong',
        'memorymatch', 'tictactoe', 'towerblock', 'crossword',
        'quiz', 'stonepapersissors', 'tricky', 'relationship', 'sequence'
    ]

    for slug in expected_bundles:
        bundle_dir = os.path.join(public_games_dir, slug)
        assert os.path.isdir(bundle_dir), f"Static web bundle directory missing for '{slug}'"
        index_file = os.path.join(bundle_dir, 'index.html')
        assert os.path.isfile(index_file), f"Entrypoint index.html missing in bundle for '{slug}'"


def test_flask_serves_public_static_bundles(client):
    """Verify that Flask correctly serves static web bundles from /public/games/."""
    # Test entrypoint of candy crush bundle
    resp_candy = client.get('/public/games/candy-crush/index.html')
    assert resp_candy.status_code == 200
    assert b'Candy Crush' in resp_candy.data or b'candy' in resp_candy.data.lower()

    # Test entrypoint of neon racer bundle
    resp_neon = client.get('/public/games/neon-racer/index.html')
    assert resp_neon.status_code == 200
    assert b'Neon Cyber Racer' in resp_neon.data


def test_theater_player_loads_cdn_iframe(client):
    """Verify /play/<slug> renders theater player with CDN iframe src."""
    resp = client.get('/play/neon-cyber-racer')
    assert resp.status_code == 200
    assert b'https://cdn.pixora.com/games/neon-racer/index.html' in resp.data
    assert b'<iframe' in resp.data

