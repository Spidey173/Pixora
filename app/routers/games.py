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


# Import GAME_DEFINITIONS from app.routes.games if available, or redefine
try:
    from app.routes.games import GAME_DEFINITIONS as _EXISTING_DEFS
    GAME_DEFINITIONS = _EXISTING_DEFS
except ImportError:
    GAME_DEFINITIONS = []

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

