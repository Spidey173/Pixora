"""FastAPI Exception Handlers for Pixora."""
import logging
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.templates import templates

logger = logging.getLogger("pixora.errors")


def is_api_request(request: Request) -> bool:
    """Determine if current request expects a JSON API response."""
    return request.url.path.startswith('/api/') or request.headers.get('accept') == 'application/json'


def register_error_handlers(fastapi_app):
    """Register custom 400, 401, 403, 404, 429, 500 exception handlers on FastAPI."""

    @fastapi_app.exception_handler(StarletteHTTPException)
    async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
        if is_api_request(request):
            if isinstance(exc.detail, dict):
                body = dict(exc.detail)
                body["detail"] = exc.detail
            else:
                body = {"detail": exc.detail, "error": str(exc.detail)}
            return JSONResponse(body, status_code=exc.status_code)

        template_name = f"errors/{exc.status_code}.html"
        try:
            return templates.TemplateResponse(
                template_name,
                {"request": request, "error": exc},
                status_code=exc.status_code
            )
        except Exception:
            return HTMLResponse(
                content=f"<h1>{exc.status_code} - {exc.detail}</h1>",
                status_code=exc.status_code
            )

    @fastapi_app.exception_handler(Exception)
    async def custom_500_handler(request: Request, exc: Exception):
        logger.error("Unhandled internal server error: %s", exc, exc_info=True)
        if is_api_request(request):
            return JSONResponse(
                {"error": "internal_server_error", "message": "A server error occurred."},
                status_code=500
            )

        try:
            return templates.TemplateResponse(
                "errors/500.html",
                {"request": request, "error": exc},
                status_code=500
            )
        except Exception:
            return HTMLResponse(
                content="<h1>500 - Internal Server Error</h1>",
                status_code=500
            )
