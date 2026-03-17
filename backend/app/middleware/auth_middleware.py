"""Authentication middleware for session cookie auth."""

from functools import wraps

from flask import g, jsonify, request

from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.services.auth_security import find_user_by_session_token

COOKIE_NAME = "ytcv_session"


def require_auth(func):
    """Require a valid session token stored in httpOnly cookies."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            tracking_id = generate_tracking_id()
            get_logger(__name__).warning(
                "Missing auth cookie.",
                extra={"tracking_id": tracking_id},
            )
            return (
                jsonify({"error": "Unauthorized.", "tracking_id": tracking_id, "status": 401}),
                401,
            )

        user = find_user_by_session_token(token)
        if not user:
            tracking_id = generate_tracking_id()
            get_logger(__name__).warning(
                "Invalid session token.",
                extra={"tracking_id": tracking_id},
            )
            return (
                jsonify({"error": "Unauthorized.", "tracking_id": tracking_id, "status": 401}),
                401,
            )

        g.current_user = user
        return func(*args, **kwargs)

    return wrapper
