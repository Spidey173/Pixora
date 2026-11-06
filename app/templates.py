"""FastAPI Jinja2 Templates Configuration & Flask-Compatible Template Helpers.

Provides seamless Jinja2 template rendering with automatic resolution of:
- url_for('static', filename=...) -> /static/...
- url_for('main.games') -> /games
- get_flashed_messages(with_categories=False)
- current_user object context
"""
import os
from jinja2 import pass_context
from starlette.templating import Jinja2Templates

from app.models import AnonymousUser

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
template_dir = os.path.join(basedir, 'templates')


class PixoraTemplates(Jinja2Templates):
    """Jinja2Templates supporting both (name, context) and (request, name, context) signatures with auto-flash cleanup."""
    def TemplateResponse(self, *args, **kwargs):
        req = None
        if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], dict):
            name = args[0]
            context = args[1]
            req = context.get('request') or kwargs.pop('request', None)
            status_code = kwargs.pop('status_code', 200)
            if len(args) > 2 and isinstance(args[2], int):
                status_code = args[2]
            resp = super().TemplateResponse(request=req, name=name, context=context, status_code=status_code, **kwargs)
        else:
            resp = super().TemplateResponse(*args, **kwargs)
            req = kwargs.get('request')
            if not req and len(args) > 0 and hasattr(args[0], 'cookies'):
                req = args[0]

        # Lifecycle cleanup: delete flash cookies so alerts display only once and do not persist across reloads
        if req and hasattr(req, 'cookies'):
            if '_flashes' in req.cookies:
                resp.delete_cookie('_flashes', path='/')
            if 'pixora_flash' in req.cookies:
                resp.delete_cookie('pixora_flash', path='/')

        return resp


templates = PixoraTemplates(directory=template_dir)

# Route resolution table for template compatibility (Flask Blueprint dot-notation to FastAPI paths)
ROUTE_MAP = {
    'main.games': '/games',
    'games': '/games',
    'main.index': '/',
    'index': '/',
    'auth.login': '/login',
    'login': '/login',
    'auth.logout': '/logout',
    'logout': '/logout',
    'auth.register': '/register',
    'register': '/register',
    'main.profile': '/profile',
    'profile': '/profile',
    'main.leaderboard_page': '/leaderboard',
    'leaderboard_page': '/leaderboard',
    'main.infrastructure_page': '/infrastructure',
    'infrastructure_page': '/infrastructure',
    'admin.dashboard': '/admin',
    'admin.index': '/admin',
    'admin': '/admin',
    'admin.login': '/admin/login',
    'admin.logout': '/admin/logout',
    'admin.upload_game': '/admin/games/upload',
    'admin.upload': '/admin/games/upload',
}


def template_url_for(endpoint: str, **kwargs) -> str:
    """Resolve legacy Flask blueprint dot-notation and static asset paths for Jinja2 templates."""
    if endpoint == 'static':
        filename = kwargs.get('filename') or kwargs.get('path', '')
        # Direct public CDN mapping for offloaded media assets
        cdn_url = f"/static/{filename.lstrip('/')}"
        return cdn_url

    if endpoint in ('games_catalog', 'public'):
        filename = kwargs.get('filename', '')
        return f"/public/games/{filename.lstrip('/')}"

    if endpoint in ('main.play_game', 'play_game'):
        slug = kwargs.get('slug', '')
        return f"/play/{slug}"

    if endpoint in ('admin.player_detail', 'player_detail'):
        pid = kwargs.get('player_id', '') or kwargs.get('username', '')
        return f"/admin/player/{pid}"

    if endpoint in ('admin.delete_game', 'delete_game'):
        gid = kwargs.get('game_id', '') or kwargs.get('slug', '')
        return f"/admin/games/{gid}/delete"

    if endpoint in ('admin.delete_score', 'delete_score'):
        sid = kwargs.get('score_id', '')
        return f"/admin/scores/{sid}/delete"

    if endpoint in ROUTE_MAP:
        target = ROUTE_MAP[endpoint]
    else:
        target = f"/{endpoint.replace('.', '/')}"

    if kwargs:
        query_str = '&'.join(f"{k}={v}" for k, v in kwargs.items())
        return f"{target}?{query_str}"
    return target


@pass_context
def template_get_flashed_messages(context, with_categories: bool = False):
    """Template helper returning session flashed messages with single-use lifecycle support."""
    flashes = context.get('flashes')
    if flashes is None:
        request = context.get('request')
        if request and hasattr(request, 'cookies'):
            raw_flashes = request.cookies.get('_flashes') or request.cookies.get('pixora_flash')
            if raw_flashes:
                import json
                try:
                    parsed = json.loads(raw_flashes)
                    if isinstance(parsed, list):
                        flashes = parsed
                    elif isinstance(parsed, str):
                        flashes = [('message', parsed)]
                    else:
                        flashes = []
                except Exception:
                    flashes = [('message', str(raw_flashes))]
            else:
                flashes = []
        else:
            flashes = []

    if not with_categories:
        return [f[1] if isinstance(f, (list, tuple)) and len(f) == 2 else f for f in flashes]
    
    formatted = []
    for f in flashes:
        if isinstance(f, (list, tuple)) and len(f) == 2:
            formatted.append(f)
        else:
            formatted.append(('message', str(f)))
    return formatted


class TemplateConfig:
    """Hashable config container for Jinja2 environment globals."""
    def __init__(self, data=None):
        self._data = data or {}

    def __getitem__(self, item):
        return self._data.get(item, '')

    def get(self, item, default=''):
        return self._data.get(item, default)

    def __hash__(self):
        return 0

    def __eq__(self, other):
        return isinstance(other, TemplateConfig)


# Register globals into Jinja2 environment
templates.env.globals['url_for'] = template_url_for
templates.env.globals['get_flashed_messages'] = template_get_flashed_messages
templates.env.globals['csrf_token'] = lambda: "pixora-csrf-token"
templates.env.globals['config'] = TemplateConfig()
templates.env.globals['current_user'] = AnonymousUser()
