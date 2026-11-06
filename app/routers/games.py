"""Game routing and launcher controllers for FastAPI with legacy URL compatibility and PixoraSDK v2 injection."""
from dataclasses import dataclass
import logging
import os
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from jinja2 import TemplateNotFound

from app.templates import templates

logger = logging.getLogger('pixora.games')

games_router = APIRouter(tags=["games_catalog"])
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


@dataclass(frozen=True)
class GameDefinition:
    """Metadata definition for an arcade game or sub-variant."""
    path: str
    template_path: str
    endpoint: str
    slug: str
    title: str
    category: str
    difficulty: Optional[str] = None
    description: Optional[str] = None
    controls_guide: Optional[str] = None


GAME_DEFINITIONS: List[GameDefinition] = [
    # ── 0. NEON CYBER RACER ─────────────────────────────────
    GameDefinition(
        path='/neon-cyber-racer',
        template_path='Games/neon-cyber-racer/index.html',
        endpoint='neon_cyber_racer_canonical',
        slug='neon-cyber-racer',
        title='Neon Cyber Racer',
        category='Action',
        description='Flagship Phaser 3 arcade racer. Dodge obstacles, drift at relativistic speed.',
        controls_guide='Arrow Keys or A/D to steer, Spacebar to boost.'
    ),
    GameDefinition(
        path='/neon-racer',
        template_path='Games/neon-cyber-racer/index.html',
        endpoint='neon_racer_canonical',
        slug='neon-cyber-racer',
        title='Neon Cyber Racer',
        category='Action',
        controls_guide='Arrow Keys or A/D to steer, Spacebar to boost.'
    ),

    # ── 1. 2048 CYBER GRID ──────────────────────────────────
    GameDefinition(
        path='/2048',
        template_path='Games/2048/2048.html',
        endpoint='updown',
        slug='2048',
        title='2048 Cyber Grid',
        category='Puzzle',
        description='Slide numerical data blocks across the neon matrix to synthesize the 2048 singularity.',
        controls_guide='Arrow Keys or Swipe to slide numbered tiles.'
    ),

    # ── 2. CYBER CRUSH (CANDY CRUSH) ────────────────────────
    GameDefinition(
        path='/Candy_Crush',
        template_path='Games/Candy Crush/Candy_Crush.html',
        endpoint='Candy_Crush',
        slug='candy-crush',
        title='Cyber Crush',
        category='Puzzle',
        description='Match triplets of glowing plasma nodes to initiate chain reactions.',
        controls_guide='Click and drag adjacent tiles to create matches.'
    ),

    # ── 3. FLAPPY BIRD ──────────────────────────────────────
    GameDefinition(
        path='/FlappyBird',
        template_path='Games/Flappy Birds/flappybird.html',
        endpoint='flappybird',
        slug='flappybird',
        title='Flappy Birds',
        category='Arcade',
        description='Pilot an autonomous aerial drone through treacherous conduit pillars.',
        controls_guide='Spacebar, Click, or Tap to flap propulsion thrusters.'
    ),

    # ── 4. SPEEDTYPE PRO ────────────────────────────────────
    GameDefinition(
        path='/speedtype',
        template_path='Games/SpeedType Pro/speedtype.html',
        endpoint='speedtype',
        slug='speedtype',
        title='SpeedType Pro',
        category='Skill',
        description='High-velocity typing simulator for elite hackers. Overclock your keystroke speed.',
        controls_guide='Type highlighted words rapidly into the prompt terminal.'
    ),
    GameDefinition(
        path='/speedtypepro',
        template_path='Games/SpeedType Pro/speedtype.html',
        endpoint='speedtypepro',
        slug='speedtype',
        title='SpeedType Pro (Alias)',
        category='Skill'
    ),

    # ── 5. VECTOR PONG CLASSIC ──────────────────────────────
    GameDefinition(
        path='/pong',
        template_path='Games/pong/pong.html',
        endpoint='pong',
        slug='pong',
        title='Vector Pong Classic',
        category='Retro',
        controls_guide='Up and Down arrow keys to steer your paddle.'
    ),
    GameDefinition(
        path='/pongstart',
        template_path='Games/pong/pongstart.html',
        endpoint='pongstart',
        slug='pong',
        title='Vector Pong Start',
        category='Retro'
    ),
    GameDefinition(
        path='/pongeasy',
        template_path='Games/pong/pongeasy.html',
        endpoint='pongeasy',
        slug='pong',
        title='Pong (Easy)',
        category='Retro',
        difficulty='Easy'
    ),
    GameDefinition(
        path='/pongmedium',
        template_path='Games/pong/pongmedium.html',
        endpoint='pongmedium',
        slug='pong',
        title='Pong (Medium)',
        category='Retro',
        difficulty='Medium'
    ),
    GameDefinition(
        path='/ponghard',
        template_path='Games/pong/ponghard.html',
        endpoint='ponghard',
        slug='pong',
        title='Pong (Hard)',
        category='Retro',
        difficulty='Hard'
    ),
    GameDefinition(
        path='/football',
        template_path='Games/pong/football.html',
        endpoint='football',
        slug='pong',
        title='Pong Football Arena',
        category='Retro'
    ),

    # ── 6. CYBER LABYRINTH (MAZE) ───────────────────────────
    GameDefinition(
        path='/maze',
        template_path='Games/maze/maze.html',
        endpoint='maze_canonical',
        slug='maze',
        title='Cyber Labyrinth',
        category='Puzzle',
        controls_guide='Arrow keys or WASD to navigate corridors.'
    ),
    GameDefinition(
        path='/Maze',
        template_path='Games/maze/maze.html',
        endpoint='maze',
        slug='maze',
        title='Cyber Labyrinth',
        category='Puzzle',
        controls_guide='Arrow keys or WASD to navigate corridors.'
    ),
    GameDefinition(
        path='/maze2ndpage',
        template_path='Games/maze/maze2ndpage.html',
        endpoint='maze2ndpage',
        slug='maze',
        title='Maze Portal',
        category='Puzzle'
    ),
    GameDefinition(
        path='/mazeveasy',
        template_path='Games/maze/mazeveasy.html',
        endpoint='mazeveasy',
        slug='maze',
        title='Maze (Very Easy)',
        category='Puzzle',
        difficulty='Very Easy'
    ),
    GameDefinition(
        path='/mazeeasy',
        template_path='Games/maze/mazeeasy.html',
        endpoint='mazeeasy',
        slug='maze',
        title='Maze (Easy)',
        category='Puzzle',
        difficulty='Easy'
    ),
    GameDefinition(
        path='/mazemedium',
        template_path='Games/maze/mazemedium.html',
        endpoint='mazemedium',
        slug='maze',
        title='Maze (Medium)',
        category='Puzzle',
        difficulty='Medium'
    ),
    GameDefinition(
        path='/mazehard',
        template_path='Games/maze/mazehard.html',
        endpoint='mazehard',
        slug='maze',
        title='Maze (Hard)',
        category='Puzzle',
        difficulty='Hard'
    ),

    # ── 7. MEMORY MATRIX (MEMORY MATCH) ─────────────────────
    GameDefinition(
        path='/memorymatch',
        template_path='Games/MemoryMatch/memorymatch.html',
        endpoint='memorymatch',
        slug='memorymatch',
        title='Memory Matrix',
        category='Brain',
        controls_guide='Click cards to flip and match pairs.'
    ),
    GameDefinition(
        path='/memorymatch2nd',
        template_path='Games/MemoryMatch/memorymatch2nd.html',
        endpoint='memorymatch2nd',
        slug='memorymatch',
        title='Memory Matrix Hub',
        category='Brain'
    ),
    GameDefinition(
        path='/matchingeasy',
        template_path='Games/MemoryMatch/matchingeasy.html',
        endpoint='matchingeasy',
        slug='memorymatch',
        title='Memory Matrix (Easy)',
        category='Brain',
        difficulty='Easy'
    ),
    GameDefinition(
        path='/matchingmedium',
        template_path='Games/MemoryMatch/matchingmedium.html',
        endpoint='matchingmedium',
        slug='memorymatch',
        title='Memory Matrix (Medium)',
        category='Brain',
        difficulty='Medium'
    ),
    GameDefinition(
        path='/matchinghard',
        template_path='Games/MemoryMatch/matchinghard.html',
        endpoint='matchinghard',
        slug='memorymatch',
        title='Memory Matrix (Hard)',
        category='Brain',
        difficulty='Hard'
    ),
    GameDefinition(
        path='/matchinginsane',
        template_path='Games/MemoryMatch/matchinginsane.html',
        endpoint='matchinginsane',
        slug='memorymatch',
        title='Memory Matrix (Insane)',
        category='Brain',
        difficulty='Insane'
    ),

    # ── 8. WHACK A MOLE ─────────────────────────────────────
    GameDefinition(
        path='/mole',
        template_path='Games/wake a mole/mole.html',
        endpoint='mole',
        slug='mole',
        title='Whack a Mole',
        category='Arcade',
        controls_guide='Click bugs rapidly as they appear.'
    ),
    GameDefinition(
        path='/mole2nd',
        template_path='Games/wake a mole/mole2nd.html',
        endpoint='mole2nd',
        slug='mole',
        title='Whack a Mole Hub',
        category='Arcade'
    ),
    GameDefinition(
        path='/moleeasy',
        template_path='Games/wake a mole/moleeasy.html',
        endpoint='moleeasy',
        slug='mole',
        title='Whack a Mole (Easy)',
        category='Arcade',
        difficulty='Easy'
    ),
    GameDefinition(
        path='/molemedium',
        template_path='Games/wake a mole/molemedium.html',
        endpoint='molemedium',
        slug='mole',
        title='Whack a Mole (Medium)',
        category='Arcade',
        difficulty='Medium'
    ),
    GameDefinition(
        path='/molehard',
        template_path='Games/wake a mole/molehard.html',
        endpoint='molehard',
        slug='mole',
        title='Whack a Mole (Hard)',
        category='Arcade',
        difficulty='Hard'
    ),

    # ── 9. QUANTUM TIC-TAC-TOE ──────────────────────────────
    GameDefinition(
        path='/tictactoe',
        template_path='Games/TicTacToe/tictactoe.html',
        endpoint='tictactoe',
        slug='tictactoe',
        title='Quantum Tic-Tac-Toe',
        category='Strategy',
        controls_guide='Click any empty cell to place your token.'
    ),

    # ── 10. SKYLINE TOWER BLOCK ─────────────────────────────
    GameDefinition(
        path='/towerblock',
        template_path='Games/TowerBlock/TowerBlock.html',
        endpoint='towerblock_canonical',
        slug='towerblock',
        title='Skyline Tower Block',
        category='Arcade',
        controls_guide='Click or press Spacebar to drop the swinging block.'
    ),
    GameDefinition(
        path='/TowerBlock',
        template_path='Games/TowerBlock/TowerBlock.html',
        endpoint='towerblock',
        slug='towerblock',
        title='Skyline Tower Block',
        category='Arcade',
        controls_guide='Click or press Spacebar to drop the swinging block.'
    ),

    # ── 11. STONE PAPER SCISSORS ────────────────────────────
    GameDefinition(
        path='/stonepapersissors',
        template_path='Games/Stone Paper Scissors/stonepapersissors.html',
        endpoint='stonepapersissor',
        slug='stonepapersissors',
        title='Stone Paper Scissors',
        category='Arcade',
        controls_guide='Click Rock, Paper, or Scissors to throw your gesture.'
    ),

    # ── 12. TRICKY BRAIN QUEST ──────────────────────────────
    GameDefinition(
        path='/tricky',
        template_path='Games/Tricky/tricky.html',
        endpoint='tricky',
        slug='tricky',
        title='Tricky Brain Quest',
        category='Puzzle',
        controls_guide='Read the clues and select the unexpected solution.'
    ),
    GameDefinition(
        path='/trickygame',
        template_path='Games/Tricky/trickygame.html',
        endpoint='trickygame',
        slug='tricky',
        title='Tricky Brain Quest Game',
        category='Puzzle'
    ),

    # ── 13. BLOOD RELATIONS MYSTERY ─────────────────────────
    GameDefinition(
        path='/relationship',
        template_path='Games/Relationship/relations.html',
        endpoint='relationship_canonical',
        slug='relationship',
        title='Blood Relations Mystery',
        category='Brain',
        controls_guide='Analyze family connections and pick the correct relation.'
    ),
    GameDefinition(
        path='/relations',
        template_path='Games/Relationship/relations.html',
        endpoint='relations',
        slug='relationship',
        title='Blood Relations Mystery',
        category='Brain',
        controls_guide='Analyze family connections and pick the correct relation.'
    ),
    GameDefinition(
        path='/Relationshipeasy',
        template_path='Games/Relationship/Relationshipeasy.html',
        endpoint='relationshipeasy',
        slug='relationship',
        title='Relations (Easy)',
        category='Brain',
        difficulty='Easy'
    ),
    GameDefinition(
        path='/Relationshiphard',
        template_path='Games/Relationship/Relationshiphard.html',
        endpoint='relationshiphard',
        slug='relationship',
        title='Relations (Hard)',
        category='Brain',
        difficulty='Hard'
    ),

    # ── 14. SEQUENCE NUMBER LOGIC ───────────────────────────
    GameDefinition(
        path='/sequence',
        template_path='Games/Sequence/mathsequence.html',
        endpoint='sequence_canonical',
        slug='sequence',
        title='Sequence Number Logic',
        category='Puzzle',
        controls_guide='Identify mathematical progression and enter the next number.'
    ),
    GameDefinition(
        path='/mathsequence',
        template_path='Games/Sequence/mathsequence.html',
        endpoint='mathsequence',
        slug='sequence',
        title='Sequence Number Logic',
        category='Puzzle',
        controls_guide='Identify mathematical progression and enter the next number.'
    ),
    GameDefinition(
        path='/mathsequencegame',
        template_path='Games/Sequence/mathsequencegame.html',
        endpoint='mathsequencegame',
        slug='sequence',
        title='Sequence Game Arena',
        category='Puzzle'
    ),

    # ── 15. NEURAL CROSSWORD MATRIX ─────────────────────────
    GameDefinition(
        path='/crossword',
        template_path='Games/Cross word/Crossword.html',
        endpoint='crossword_canonical',
        slug='crossword',
        title='Neural Crossword',
        category='Brain',
        controls_guide='Click on grid cells and type letters using keyboard.'
    ),
    GameDefinition(
        path='/Crossword',
        template_path='Games/Cross word/Crossword.html',
        endpoint='crossword',
        slug='crossword',
        title='Neural Crossword',
        category='Brain',
        controls_guide='Click on grid cells and type letters using keyboard.'
    ),
    GameDefinition(
        path='/crossword2ndpage',
        template_path='Games/Cross word/crossword2ndpage.html',
        endpoint='crossword2ndpage',
        slug='crossword',
        title='Crossword Topic Select',
        category='Brain'
    ),
    GameDefinition(
        path='/animal',
        template_path='Games/Cross word/crossword animal.html',
        endpoint='animal',
        slug='crossword',
        title='Crossword (Animals)',
        category='Brain'
    ),
    GameDefinition(
        path='/anime',
        template_path='Games/Cross word/crossword anime.html',
        endpoint='anime',
        slug='crossword',
        title='Crossword (Anime)',
        category='Brain'
    ),
    GameDefinition(
        path='/cities',
        template_path='Games/Cross word/crossword cities.html',
        endpoint='cities',
        slug='crossword',
        title='Crossword (Cities)',
        category='Brain'
    ),
    GameDefinition(
        path='/movie',
        template_path='Games/Cross word/crossword movie.html',
        endpoint='movie',
        slug='crossword',
        title='Crossword (Movies)',
        category='Brain'
    ),
    GameDefinition(
        path='/sport',
        template_path='Games/Cross word/crossword sport.html',
        endpoint='sport',
        slug='crossword',
        title='Crossword (Sports)',
        category='Brain'
    ),
    GameDefinition(
        path='/state',
        template_path='Games/Cross word/crossword state.html',
        endpoint='state',
        slug='crossword',
        title='Crossword (States)',
        category='Brain'
    ),

    # ── 16. CYBER QUIZ MATRIX ───────────────────────────────
    GameDefinition(
        path='/quiz',
        template_path='Games/Quiz/quiz.html',
        endpoint='quiz',
        slug='quiz',
        title='Cyber Quiz Matrix',
        category='Trivia',
        controls_guide='Select the correct multiple-choice options.'
    ),
    GameDefinition(
        path='/quiz2ndpage',
        template_path='Games/Quiz/quiz2ndpage.html',
        endpoint='quiz2ndpage',
        slug='quiz',
        title='Quiz Categories',
        category='Trivia'
    ),
    GameDefinition(
        path='/aanimal',
        template_path='Games/Quiz/animal.html',
        endpoint='aanimal',
        slug='quiz',
        title='Quiz (Animal Kingdom)',
        category='Trivia'
    ),
    GameDefinition(
        path='/Cartoon',
        template_path='Games/Quiz/Cartoon.html',
        endpoint='cartoon',
        slug='quiz',
        title='Quiz (Cartoons & Anime)',
        category='Trivia'
    ),
    GameDefinition(
        path='/food',
        template_path='Games/Quiz/food.html',
        endpoint='food',
        slug='quiz',
        title='Quiz (Culinary & Food)',
        category='Trivia'
    ),
    GameDefinition(
        path='/gk',
        template_path='Games/Quiz/gk.html',
        endpoint='gk',
        slug='quiz',
        title='Quiz (General Knowledge)',
        category='Trivia'
    ),
    GameDefinition(
        path='/history',
        template_path='Games/Quiz/history.html',
        endpoint='history',
        slug='quiz',
        title='Quiz (World History)',
        category='Trivia'
    ),
    GameDefinition(
        path='/indiansport',
        template_path='Games/Quiz/indiansport.html',
        endpoint='indiansport',
        slug='quiz',
        title='Quiz (Sports Champions)',
        category='Trivia'
    ),
    GameDefinition(
        path='/movies',
        template_path='Games/Quiz/movies.html',
        endpoint='movies',
        slug='quiz',
        title='Quiz (Cinema & Movies)',
        category='Trivia'
    ),
    GameDefinition(
        path='/place',
        template_path='Games/Quiz/place.html',
        endpoint='place',
        slug='quiz',
        title='Quiz (Geography & Places)',
        category='Trivia'
    ),
    GameDefinition(
        path='/riddle',
        template_path='Games/Quiz/riddle.html',
        endpoint='riddle',
        slug='quiz',
        title='Quiz (Riddles & Logic)',
        category='Trivia'
    ),
]

GAME_REGISTRY: Dict[str, tuple[str, str]] = {
    def_item.path: (def_item.template_path, def_item.endpoint)
    for def_item in GAME_DEFINITIONS
}

_GAMES_BY_PATH: Dict[str, GameDefinition] = {
    def_item.path.lower(): def_item
    for def_item in GAME_DEFINITIONS
}

_GAMES_BY_SLUG: Dict[str, List[GameDefinition]] = {}
for item in GAME_DEFINITIONS:
    _GAMES_BY_SLUG.setdefault(item.slug, []).append(item)


def generate_universal_bridge_script(slug: str, title: str) -> str:
    """Generate universal telemetry and score submission bridge for any game template."""
    return f"""
<!-- Pixora 2.0 Hardened SDK & Universal Score Bridge Auto-Injection -->
<script src="/static/js/pixora-sdk.js"></script>
<script>
(function() {{
    'use strict';
    const GAME_SLUG = "{slug}";
    const GAME_TITLE = "{title}";

    // 1. Initialize Pixora SDK v2
    if (window.Pixora) {{
        window.Pixora.init({{ gameSlug: GAME_SLUG }}).then(() => {{
            if (window.Pixora.gameplayStart) window.Pixora.gameplayStart();
        }}).catch(() => {{}});
    }}

    // 2. Intercept legacy fetch('/api/score...') to route to Pixora SDK v2
    if (window.fetch) {{
        const _origFetch = window.fetch;
        window.fetch = function(...args) {{
            try {{
                const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url ? args[0].url : '');
                if (url.includes('/api/score')) {{
                    const body = args[1] && args[1].body ? JSON.parse(args[1].body) : null;
                    if (body && body.score !== undefined && window.Pixora) {{
                        window.Pixora.submitScore(Number(body.score));
                    }}
                }}
            }} catch(e) {{}}
            return _origFetch.apply(this, args);
        }};
    }}

    // 3. Universal Auto-Detection of Game Over & Scores
    window.addEventListener('load', function() {{
        let _submitted = false;
        function autoSubmit(val) {{
            const s = Math.floor(Number(val));
            if (isNaN(s) || s <= 0 || _submitted) return;
            _submitted = true;
            if (window.Pixora) window.Pixora.submitScore(s);
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


def _resolve_bundle_html(template_path: str, game_def: Optional[GameDefinition] = None) -> Optional[str]:
    """Resolve static web bundle HTML for catalog games loaded from /public/games/."""
    parts = template_path.replace('\\', '/').split('/')
    filename = parts[-1] if parts else ''
    candidates = []

    if game_def:
        candidates.append(os.path.join(basedir, 'public', 'games', game_def.slug, filename))
        candidates.append(os.path.join(basedir, 'public', 'games', game_def.slug, 'index.html'))

    if len(parts) >= 2:
        folder = parts[-2].lower().replace(' ', '').replace('_', '')
        candidates.append(os.path.join(basedir, 'public', 'games', folder, filename))
        candidates.append(os.path.join(basedir, 'public', 'games', folder, 'index.html'))
        folder_map = {
            'candycrush': 'candy-crush',
            'crossword': 'crossword',
            'wakeamole': 'mole',
            'stonepaperscissors': 'stonepapersissors',
            'stonepapersissors': 'stonepapersissors',
            'memorymatch': 'memorymatch',
            'relationship': 'relationship',
            'sequence': 'sequence',
            'tricky': 'tricky',
            'towerblock': 'towerblock',
            'tictactoe': 'tictactoe',
            'pong': 'pong',
            'maze': 'maze',
            'quiz': 'quiz',
        }
        mapped_folder = folder_map.get(folder)
        if mapped_folder:
            candidates.append(os.path.join(basedir, 'public', 'games', mapped_folder, filename))
            candidates.append(os.path.join(basedir, 'public', 'games', mapped_folder, 'index.html'))

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            try:
                with open(candidate, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.warning("Could not read bundle candidate %s: %s", candidate, e)
    return None


def create_game_view(template_path: str, game_def: Optional[GameDefinition] = None):
    """Factory creating FastAPI view function with automatic PixoraSDK injection."""
    async def view(request: Request):
        try:
            jinja_tmpl = templates.get_template(template_path)
            rendered = jinja_tmpl.render({"request": request})
        except (TemplateNotFound, Exception):
            rendered = _resolve_bundle_html(template_path, game_def)
            if rendered is None:
                logger.warning("Game template or bundle '%s' not found.", template_path)
                raise HTTPException(status_code=404, detail="Game template not found")

        if '<script src="/static/js/pixora-sdk.js"></script>' not in rendered and 'PIXORA_GAME_CLIENT' not in rendered:
            game_slug = game_def.slug if game_def else 'arcade-game'
            game_title = game_def.title if game_def else 'Arcade Game'
            sdk_snippet = generate_universal_bridge_script(game_slug, game_title)

            if '</head>' in rendered:
                rendered = rendered.replace('</head>', f'{sdk_snippet}</head>', 1)
            elif '</body>' in rendered:
                rendered = rendered.replace('</body>', f'{sdk_snippet}</body>', 1)
            else:
                rendered = rendered + sdk_snippet

        return HTMLResponse(
            content=rendered,
            headers={
                'X-Frame-Options': 'SAMEORIGIN',
                'X-Content-Type-Options': 'nosniff'
            }
        )

    return view


def register_game_routes(fastapi_app):
    """Register all 17 game routes and their sub-variants directly on FastAPI application."""
    for item in GAME_DEFINITIONS:
        view_func = create_game_view(item.template_path, game_def=item)
        fastapi_app.add_api_route(item.path, view_func, methods=["GET"], name=item.endpoint)


def get_all_game_definitions() -> List[GameDefinition]:
    return list(GAME_DEFINITIONS)


def get_game_definition_by_path(path: str) -> Optional[GameDefinition]:
    return _GAMES_BY_PATH.get(path.strip().lower())


def get_game_definitions_by_slug(slug: str) -> List[GameDefinition]:
    return _GAMES_BY_SLUG.get(slug.strip().lower(), [])


def get_game_categories() -> Dict[str, List[GameDefinition]]:
    grouped: Dict[str, List[GameDefinition]] = {}
    for item in GAME_DEFINITIONS:
        grouped.setdefault(item.category, []).append(item)
    return grouped

