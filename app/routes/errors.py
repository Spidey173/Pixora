"""Cyberpunk styled custom error handlers."""
from flask import Blueprint, jsonify, render_template, request

errors_bp = Blueprint('errors', __name__)


def is_api_request():
    """Determine if current request expects a JSON API response."""
    return request.path.startswith('/api/') or request.headers.get('Accept') == 'application/json'


@errors_bp.app_errorhandler(400)
def bad_request_error(error):
    if is_api_request():
        return jsonify({'error': 'bad_request', 'message': str(error)}), 400
    return render_template('errors/400.html', error=error), 400


@errors_bp.app_errorhandler(401)
def unauthorized_error(error):
    if is_api_request():
        return jsonify({'error': 'unauthorized', 'message': 'Authentication required.'}), 401
    return render_template('errors/401.html', error=error), 401


@errors_bp.app_errorhandler(403)
def forbidden_error(error):
    if is_api_request():
        return jsonify({'error': 'forbidden', 'message': 'Access denied.'}), 403
    return render_template('errors/403.html', error=error), 403


@errors_bp.app_errorhandler(404)
def not_found_error(error):
    if is_api_request():
        return jsonify({'error': 'not_found', 'message': 'Resource not found.'}), 404
    return render_template('errors/404.html', error=error), 404


@errors_bp.app_errorhandler(429)
def ratelimit_handler(error):
    if is_api_request():
        return jsonify({'error': 'rate_limit_exceeded', 'message': 'Too many requests. Please slow down.'}), 429
    return render_template('errors/429.html', error=error), 429


@errors_bp.app_errorhandler(500)
def internal_server_error(error):
    if is_api_request():
        return jsonify({'error': 'internal_server_error', 'message': 'A server error occurred.'}), 500
    return render_template('errors/500.html', error=error), 500
