"""Utility to package non-featured games into standalone static web bundles in /public/games/."""
import os
import re
import shutil

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TEMPLATES_GAMES_DIR = os.path.join(BASE_DIR, 'templates', 'Games')
STATIC_GAMES_DIR = os.path.join(BASE_DIR, 'static', 'Games')
PUBLIC_GAMES_DIR = os.path.join(BASE_DIR, 'public', 'games')

# Featured games kept directly in the repository templates:
FEATURED_IN_REPO = {'2048', 'Flappy Birds', 'SpeedType Pro'}

# The 14 games to bundle as static web packages:
BUNDLE_SPECS = [
    {
        'slug': 'neon-racer',
        'aliases': ['neon-cyber-racer'],
        'title': 'Neon Cyber Racer',
        'source_template_dir': None,
        'source_static_bundle': os.path.join(STATIC_GAMES_DIR, 'neon-cyber-racer'),
        'primary_html': 'index.html',
    },
    {
        'slug': 'candy-crush',
        'title': 'Cyber Crush',
        'source_template_dir': os.path.join(TEMPLATES_GAMES_DIR, 'Candy Crush'),
        'source_assets_dir': os.path.join(STATIC_GAMES_DIR, 'Candy Crush'),
        'primary_html': 'Candy_Crush.html',
    },
    {
        'slug': 'mole',
        'title': 'Whack a Mole',
        'source_template_dir': os.path.join(TEMPLATES_GAMES_DIR, 'wake a mole'),
        'source_assets_dir': os.path.join(STATIC_GAMES_DIR, 'wake a mole'),
        'primary_html': 'mole.html',
    },
    {
        'slug': 'maze',
        'title': 'Cyber Labyrinth',
        'source_template_dir': os.path.join(TEMPLATES_GAMES_DIR, 'maze'),
        'source_assets_dir': None,
        'primary_html': 'maze.html',
    },
    {
        'slug': 'pong',
        'title': 'Vector Pong Classic',
        'source_template_dir': os.path.join(TEMPLATES_GAMES_DIR, 'pong'),
        'source_assets_dir': os.path.join(STATIC_GAMES_DIR, 'pong'),
        'primary_html': 'pong.html',
    },
    {
        'slug': 'memorymatch',
        'title': 'Memory Matrix',
        'source_template_dir': os.path.join(TEMPLATES_GAMES_DIR, 'MemoryMatch'),
        'source_assets_dir': None,
        'primary_html': 'memorymatch.html',
    },
    {
        'slug': 'tictactoe',
        'title': 'Quantum Tic-Tac-Toe',
        'source_template_dir': os.path.join(TEMPLATES_GAMES_DIR, 'TicTacToe'),
        'source_assets_dir': None,
        'primary_html': 'tictactoe.html',
    },
    {
        'slug': 'towerblock',
        'title': 'Skyline Tower Block',
        'source_template_dir': os.path.join(TEMPLATES_GAMES_DIR, 'TowerBlock'),
        'source_assets_dir': None,
        'primary_html': 'TowerBlock.html',
    },
    {
        'slug': 'crossword',
        'title': 'Neural Crossword',
        'source_template_dir': os.path.join(TEMPLATES_GAMES_DIR, 'Cross word'),
        'source_assets_dir': os.path.join(STATIC_GAMES_DIR, 'Crossword'),
        'primary_html': 'Crossword.html',
    },
    {
        'slug': 'quiz',
        'title': 'Cyber Quiz Matrix',
        'source_template_dir': os.path.join(TEMPLATES_GAMES_DIR, 'Quiz'),
        'source_assets_dir': os.path.join(STATIC_GAMES_DIR, 'Quiz'),
        'primary_html': 'quiz.html',
    },
    {
        'slug': 'stonepapersissors',
        'title': 'Stone Paper Scissors',
        'source_template_dir': os.path.join(TEMPLATES_GAMES_DIR, 'Stone Paper Scissors'),
        'source_assets_dir': os.path.join(STATIC_GAMES_DIR, 'Stone Paper Scissors'),
        'primary_html': 'stonepapersissors.html',
    },
    {
        'slug': 'tricky',
        'title': 'Tricky Brain Quest',
        'source_template_dir': os.path.join(TEMPLATES_GAMES_DIR, 'Tricky'),
        'source_assets_dir': None,
        'primary_html': 'tricky.html',
    },
    {
        'slug': 'relationship',
        'title': 'Blood Relations Mystery',
        'source_template_dir': os.path.join(TEMPLATES_GAMES_DIR, 'Relationship'),
        'source_assets_dir': None,
        'primary_html': 'relations.html',
    },
    {
        'slug': 'sequence',
        'title': 'Sequence Number Logic',
        'source_template_dir': os.path.join(TEMPLATES_GAMES_DIR, 'Sequence'),
        'source_assets_dir': None,
        'primary_html': 'mathsequence.html',
    },
]

# Mapping endpoint names to relative html files inside static web bundles
URL_FOR_REPLACEMENTS = {
    # Mole
    'mole': 'index.html',
    'mole2nd': 'mole2nd.html',
    'moleeasy': 'moleeasy.html',
    'molemedium': 'molemedium.html',
    'molehard': 'molehard.html',
    # Maze
    'maze': 'index.html',
    'maze2ndpage': 'maze2ndpage.html',
    'mazeveasy': 'mazeveasy.html',
    'mazeeasy': 'mazeeasy.html',
    'mazemedium': 'mazemedium.html',
    'mazehard': 'mazehard.html',
    # Pong
    'pong': 'index.html',
    'pongstart': 'pongstart.html',
    'pongeasy': 'pongeasy.html',
    'pongmedium': 'pongmedium.html',
    'ponghard': 'ponghard.html',
    'football': 'football.html',
    # Memory Match
    'memorymatch': 'index.html',
    'memorymatch2nd': 'memorymatch2nd.html',
    'matchingeasy': 'matchingeasy.html',
    'matchingmedium': 'matchingmedium.html',
    'matchinghard': 'matchinghard.html',
    'matchinginsane': 'matchinginsane.html',
    # Crossword
    'crossword': 'index.html',
    'crossword2ndpage': 'crossword2ndpage.html',
    'movie': 'crossword movie.html',
    'anime': 'crossword anime.html',
    'sport': 'crossword sport.html',
    'state': 'crossword state.html',
    'animal': 'crossword animal.html',
    'cities': 'crossword cities.html',
    # Quiz
    'quiz': 'index.html',
    'quiz2ndpage': 'quiz2ndpage.html',
    'aanimal': 'animal.html',
    'food': 'food.html',
    'gk': 'gk.html',
    'history': 'history.html',
    'indiansport': 'indiansport.html',
    'place': 'place.html',
    'movies': 'movies.html',
    'riddle': 'riddle.html',
    'cartoon': 'Cartoon.html',
    # Relationship
    'relations': 'index.html',
    'relationshipeasy': 'Relationshipeasy.html',
    'relationshiphard': 'Relationshiphard.html',
    # Sequence
    'mathsequence': 'index.html',
    'mathsequencegame': 'mathsequencegame.html',
    # Tricky
    'tricky': 'index.html',
    'trickygame': 'trickygame.html',
}


def _generate_embedded_sdk_script(slug: str, title: str) -> str:
    """Generate embedded PixoraSDK v2 bridge script for the static web bundle."""
    return f"""
<!-- Pixora Platform SDK v2 Bundle Bridge (Poki / Static CDN Architecture) -->
<script>
(function() {{
    'use strict';
    const GAME_SLUG = "{slug}";
    const GAME_TITLE = "{title}";

    // 1. Universal Pixora / Glitch4ce SDK Client
    const PixoraBridge = {{
        init: function() {{
            if (window.parent && window.parent !== window) {{
                window.parent.postMessage({{
                    source: 'PIXORA_GAME_CLIENT',
                    type: 'PIXORA_HANDSHAKE',
                    payload: {{ gameId: GAME_SLUG, version: '2.0.0' }}
                }}, '*');
            }}
        }},
        gameplayStart: function() {{
            if (window.parent && window.parent !== window) {{
                window.parent.postMessage({{
                    source: 'PIXORA_GAME_CLIENT',
                    type: 'PIXORA_GAMEPLAY_START',
                    payload: {{ game: GAME_TITLE, timestamp: Date.now() }}
                }}, '*');
            }}
        }},
        gameplayStop: function() {{
            if (window.parent && window.parent !== window) {{
                window.parent.postMessage({{
                    source: 'PIXORA_GAME_CLIENT',
                    type: 'PIXORA_GAMEPLAY_STOP',
                    payload: {{ game: GAME_TITLE, timestamp: Date.now() }}
                }}, '*');
            }}
        }},
        recordAction: function(action) {{
            // Track physical player interaction for anti-cheat entropy
        }},
        submitScore: function(scoreVal) {{
            const num = Math.floor(Number(scoreVal));
            if (isNaN(num) || num < 0) return;
            if (window.parent && window.parent !== window) {{
                window.parent.postMessage({{
                    source: 'PIXORA_GAME_CLIENT',
                    type: 'PIXORA_SUBMIT_SCORE',
                    payload: {{ game: GAME_TITLE, score: num, timestamp: Date.now() }}
                }}, '*');
            }}
        }}
    }};

    window.Pixora = window.Pixora || PixoraBridge;
    window.Glitch4ce = window.Glitch4ce || PixoraBridge;

    // Auto-initiate handshake with parent theater shell
    PixoraBridge.init();
    PixoraBridge.gameplayStart();

    // Hook common score end functions
    window.addEventListener('load', function() {{
        let _submitted = false;
        function autoSubmit(val) {{
            const s = Math.floor(Number(val));
            if (isNaN(s) || s <= 0 || _submitted) return;
            _submitted = true;
            PixoraBridge.submitScore(s);
            setTimeout(() => {{ _submitted = false; }}, 4000);
        }}

        ['endGame', 'showResult', 'gameOver', 'showFinalScore', 'checkCompletion'].forEach(fn => {{
            if (typeof window[fn] === 'function') {{
                const orig = window[fn];
                window[fn] = function(...args) {{
                    const res = orig.apply(this, args);
                    const score = window.score || 
                                  (window.player1 ? Math.max(window.player1.score, (window.player2 ? window.player2.score : 0)) * 100 : null) || 
                                  (window.correctAnswers ? window.correctAnswers * 100 : null);
                    if (score) autoSubmit(score);
                    return res;
                }};
            }}
        }});
    }});
}})();
</script>
"""


def _clean_and_transform_html(content: str, slug: str, title: str) -> str:
    """Transform server template syntax into self-contained static web bundle HTML."""
    # Replace {{ url_for('endpoint') }} with relative filename
    for ep, rel_file in URL_FOR_REPLACEMENTS.items():
        pattern = rf"""\{{\{{\s*url_for\(\s*['"]{ep}['"]\s*\)\s*\}}\}}"""
        content = re.sub(pattern, rel_file, content)

    # In case there's any remaining static url_for e.g. {{ url_for('static', filename='...') }}
    content = re.sub(r"""\{\{\s*url_for\('static',\s*filename=['"](.*?)['"]\)\s*\}\}""", r"/static/\1", content)

    # Inject embedded SDK script if not already present
    if 'PixoraPlatformSDK' not in content and 'PIXORA_GAME_CLIENT' not in content:
        bridge_script = _generate_embedded_sdk_script(slug, title)
        if '</head>' in content:
            content = content.replace('</head>', f'{bridge_script}</head>', 1)
        elif '</body>' in content:
            content = content.replace('</body>', f'{bridge_script}</body>', 1)
        else:
            content = content + bridge_script

    return content


def build_static_bundles():
    """Package the 14 catalog games into /public/games/."""
    os.makedirs(PUBLIC_GAMES_DIR, exist_ok=True)
    summary = []

    for spec in BUNDLE_SPECS:
        slug = spec['slug']
        title = spec['title']
        dest_dir = os.path.join(PUBLIC_GAMES_DIR, slug)
        os.makedirs(dest_dir, exist_ok=True)

        # 1. Handle pre-existing static bundle (e.g. Neon Cyber Racer)
        if spec.get('source_static_bundle'):
            src = spec['source_static_bundle']
            if os.path.isdir(src):
                for item in os.listdir(src):
                    s = os.path.join(src, item)
                    d = os.path.join(dest_dir, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)

        # 2. Copy and transform HTML files from template directory
        src_tpl = spec.get('source_template_dir')
        if src_tpl and os.path.isdir(src_tpl):
            for filename in os.listdir(src_tpl):
                if filename.endswith('.html'):
                    src_file = os.path.join(src_tpl, filename)
                    with open(src_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    transformed = _clean_and_transform_html(content, slug, title)

                    # Write as specific filename
                    with open(os.path.join(dest_dir, filename), 'w', encoding='utf-8') as f:
                        f.write(transformed)

                    # If this is the primary HTML entrypoint, also write as index.html
                    if filename == spec.get('primary_html'):
                        with open(os.path.join(dest_dir, 'index.html'), 'w', encoding='utf-8') as f:
                            f.write(transformed)

        # 3. Copy any static assets into the bundle directory
        src_assets = spec.get('source_assets_dir')
        if src_assets and os.path.isdir(src_assets):
            for item in os.listdir(src_assets):
                s = os.path.join(src_assets, item)
                d = os.path.join(dest_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

        # 4. Handle aliases (e.g. neon-cyber-racer alias for neon-racer)
        for alias in spec.get('aliases', []):
            alias_dir = os.path.join(PUBLIC_GAMES_DIR, alias)
            os.makedirs(alias_dir, exist_ok=True)
            for item in os.listdir(dest_dir):
                s = os.path.join(dest_dir, item)
                d = os.path.join(alias_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

        bundle_files = os.listdir(dest_dir)
        summary.append(f"✓ {slug}: {len(bundle_files)} files (entry: index.html)")

    print(f"Successfully packaged {len(BUNDLE_SPECS)} static game bundles in {PUBLIC_GAMES_DIR}:")
    for s in summary:
        print(f"  {s}")


if __name__ == '__main__':
    build_static_bundles()

