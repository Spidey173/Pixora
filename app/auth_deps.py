"""Authentication dependencies & session cookie management for FastAPI.

Replaces Flask-Login and session cookies with standard itsdangerous serialization
compatible with both web browser session cookies and Bearer tokens.
"""
import json
from typing import Optional
from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, status
from itsdangerous import URLSafeTimedSerializer
from markupsafe import Markup

from app.models import AnonymousUser, User
from app.services.anti_cheat import AntiCheatValidator


def get_serializer() -> URLSafeTimedSerializer:
    """Return itsdangerous serializer configured with active SECRET_KEY."""
    secret = AntiCheatValidator._get_secret_key()
    return URLSafeTimedSerializer(secret, salt="cookie-session")


def create_session_cookie(data: dict) -> str:
    """Serialize and sign session dictionary into secure cookie string."""
    s = get_serializer()
    return s.dumps(data)


def decode_session_cookie(cookie_str: str, max_age: int = 86400 * 30) -> Optional[dict]:
    """Verify and decode signed session cookie."""
    if not cookie_str:
        return None
    s = get_serializer()
    try:
        return s.loads(cookie_str, max_age=max_age)
    except Exception:
        return None


def set_flash(response: Response, message: str, category: str = "info"):
    """Set flash message cookie for the next request with lax CSRF protection."""
    flashes = [(category, message)]
    response.set_cookie("_flashes", json.dumps(flashes), max_age=60, path="/", httponly=True, samesite="lax")
    response.set_cookie("pixora_flash", message, max_age=60, path="/", httponly=True, samesite="lax")


def set_session(response: Response, data: dict, max_age: int = 86400 * 30):
    """Set signed session cookie on response."""
    cookie_str = create_session_cookie(data)
    response.set_cookie("session", cookie_str, max_age=max_age, path="/", httponly=True, samesite="lax")


def clear_session(response: Response):
    """Clear session cookie on response."""
    response.delete_cookie("session", path="/")


async def parse_form_or_json(request: Request) -> dict:
    """Parse request body as JSON or urlencoded form using pure Python stdlib."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    import urllib.parse
    body = await request.body()
    if not body:
        return {}

    try:
        decoded = body.decode("utf-8")
        parsed = urllib.parse.parse_qs(decoded, keep_blank_values=True)
        return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
    except Exception:
        return {}


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    session: Optional[str] = Cookie(None)
) -> User | AnonymousUser:
    """Resolve authenticated user from signed session cookie or Bearer token."""
    # 1. Bearer Token check
    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token_data = AntiCheatValidator.verify_player_token(parts[1])
            if token_data and "player_id" in token_data:
                user = User.query.get(int(token_data["player_id"]))
                if user:
                    return user

    # 2. Signed session cookie check
    cookie_val = session or request.cookies.get("session")
    if cookie_val:
        sess_data = decode_session_cookie(cookie_val)
        if sess_data and "_user_id" in sess_data:
            try:
                uid = int(sess_data["_user_id"])
                user = User.query.get(uid)
                if user:
                    return user
            except (ValueError, TypeError):
                pass
        # Fallback to pilot_username
        if sess_data and "pilot_username" in sess_data:
            user = User.query.filter_by(username=sess_data["pilot_username"]).first()
            if user:
                return user

    return AnonymousUser()


async def require_user(
    request: Request,
    user: User | AnonymousUser = Depends(get_current_user)
) -> User:
    """Require authenticated user; redirects browser to /login or returns 401 for API."""
    if not user.is_authenticated:
        # Check if requested content is JSON/API
        accept = request.headers.get("accept", "")
        if "application/json" in accept or request.url.path.startswith("/api/"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "Authentication required", "code": "UNAUTHORIZED"}
            )
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": f"/login?next={request.url.path}"}
        )
    return user


async def require_admin(
    request: Request,
    session: Optional[str] = Cookie(None),
    user: User | AnonymousUser = Depends(get_current_user)
):
    """Require admin authentication; redirects browser to /admin/login."""
    cookie_val = session or request.cookies.get("session")
    sess_data = decode_session_cookie(cookie_val) if cookie_val else {}
    if sess_data and sess_data.get("is_admin_authenticated"):
        return True
    if user.is_authenticated and getattr(user, 'is_admin', False):
        return True

    raise HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        headers={"Location": f"/admin/login?next={request.url.path}"}
    )


class MockField:
    """Form field simulator for Flask-WTF template compatibility."""
    def __init__(self, name, value="", field_type="text"):
        self.name = name
        self.data = value
        self.field_type = field_type
        self.errors = []

    def __call__(self, **kwargs):
        attrs = [f'{k}="{v}"' if not isinstance(v, bool) else (k if v else '') for k, v in kwargs.items()]
        attr_str = ' '.join(filter(None, attrs))
        if self.field_type == "checkbox":
            checked = 'checked' if self.data else ''
            return Markup(f'<input type="checkbox" name="{self.name}" id="{self.name}" {attr_str} {checked}>')
        elif self.field_type == "password":
            return Markup(f'<input type="password" name="{self.name}" value="{self.data or ""}" {attr_str}>')
        return Markup(f'<input type="text" name="{self.name}" value="{self.data or ""}" {attr_str}>')


class MockForm:
    """Form simulator for login & admin templates."""
    def __init__(self, username="", password="", remember_me=False, **kwargs):
        self.username = MockField("username", username, "text")
        self.password = MockField("password", password, "password")
        self.remember_me = MockField("remember_me", remember_me, "checkbox")
        self.errors = {}
        for k, v in kwargs.items():
            setattr(self, k, MockField(k, v))

    def __getattr__(self, name):
        field = MockField(name)
        setattr(self, name, field)
        return field

    def hidden_tag(self):
        return Markup('')

    def validate_on_submit(self):
        return False
