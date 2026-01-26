"""Global error handling utilities."""

import logging
from functools import wraps

from flask import jsonify, request

from app.logging.tracking import generate_tracking_id


def _log_exception(logger, error, tracking_id):
    """Log detailed error information for internal diagnostics."""
    logger.exception(
        "Unhandled error: %s | method=%s path=%s ip=%s",
        error,
        request.method,
        request.path,
        request.remote_addr,
        extra={"tracking_id": tracking_id},
    )


def register_error_handlers(app):
    """Register JSON error handlers with tracking IDs."""

    logger = logging.getLogger("app.errors")

    def _json_error(error, message, status_code):
        tracking_id = generate_tracking_id()
        _log_exception(logger, error, tracking_id)
        return (
            jsonify({"error": message, "tracking_id": tracking_id, "status": status_code}),
            status_code,
        )

    @app.errorhandler(400)
    def bad_request(error):
        return _json_error(error, "Bad request.", 400)

    @app.errorhandler(401)
    def unauthorized(error):
        return _json_error(error, "Unauthorized.", 401)

    @app.errorhandler(403)
    def forbidden(error):
        return _json_error(error, "Forbidden.", 403)

    @app.errorhandler(404)
    def not_found(error):
        return _json_error(error, "Not found.", 404)

    @app.errorhandler(500)
    def server_error(error):
        return _json_error(error, "Internal server error.", 500)


def handle_route_errors(func):
    """Decorator to catch unhandled exceptions in routes."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as error:
            logger = logging.getLogger("app.errors")
            tracking_id = generate_tracking_id()
            _log_exception(logger, error, tracking_id)
            return (
                jsonify(
                    {
                        "error": "Internal server error.",
                        "tracking_id": tracking_id,
                        "status": 500,
                    }
                ),
                500,
            )

    return wrapper
