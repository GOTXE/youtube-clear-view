"""Authentication routes using httpOnly cookies."""

import secrets
from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import COOKIE_NAME, require_auth
from app.middleware.error_handler import handle_route_errors
from app.models import User

auth_bp = Blueprint("auth", __name__)

COOKIE_MAX_AGE = 30 * 24 * 60 * 60


def _set_session_cookie(response, token, max_age=COOKIE_MAX_AGE):
    """Attach the session cookie with secure defaults."""
    secure_cookie = current_app.config.get("COOKIE_SECURE", True)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=secure_cookie,
        samesite="Lax",
        max_age=max_age,
        path="/api",
    )


def _clear_session_cookie(response):
    """Expire the session cookie immediately."""
    secure_cookie = current_app.config.get("COOKIE_SECURE", True)
    response.set_cookie(
        COOKIE_NAME,
        "",
        httponly=True,
        secure=secure_cookie,
        samesite="Lax",
        max_age=0,
        expires=0,
        path="/api",
    )


@auth_bp.post("/api/auth/login")
@handle_route_errors
def login():
    """Login or create a user and set a secure session cookie."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    if not username:
        tracking_id = generate_tracking_id()
        get_logger(__name__).warning(
            "Login missing username.",
            extra={"tracking_id": tracking_id},
        )
        return (
            jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}),
            400,
        )

    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(username=username, display_name=username)
        db.session.add(user)

    session_token = secrets.token_urlsafe(32)
    user.session_token = session_token
    user.session_created_at = datetime.utcnow()
    db.session.commit()

    response = jsonify(
        {
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "theme_preference": user.theme_preference,
        }
    )
    _set_session_cookie(response, session_token)
    return response


@auth_bp.post("/api/auth/logout")
@handle_route_errors
def logout():
    """Clear the session cookie and invalidate the server token."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        user = User.query.filter_by(session_token=token).first()
        if user:
            user.session_token = None
            user.session_created_at = None
            db.session.commit()

    response = jsonify({"message": "Logged out"})
    _clear_session_cookie(response)
    return response


@auth_bp.get("/api/auth/users")
@handle_route_errors
def list_users():
    """Return all users for the login selector."""
    users = User.query.order_by(User.username.asc()).all()
    data = [
        {"id": user.id, "username": user.username, "display_name": user.display_name}
        for user in users
    ]
    return jsonify(data)


@auth_bp.get("/api/auth/current")
@handle_route_errors
def current_user():
    """Return the current authenticated user if a valid session exists."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return jsonify({"authenticated": False})

    user = User.query.filter_by(session_token=token).first()
    if not user:
        response = jsonify({"authenticated": False})
        _clear_session_cookie(response)
        return response

    return jsonify(
        {
            "authenticated": True,
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "theme_preference": user.theme_preference,
        }
    )


@auth_bp.put("/api/auth/profile")
@handle_route_errors
@require_auth
def update_profile():
    """Update the user's display name and theme preference."""
    data = request.get_json(silent=True) or {}
    display_name = data.get("display_name")
    theme_preference = data.get("theme_preference")

    if theme_preference and theme_preference not in ("light", "dark"):
        tracking_id = generate_tracking_id()
        return (
            jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}),
            400,
        )

    user = g.current_user
    if display_name is not None:
        cleaned = display_name.strip()
        user.display_name = cleaned if cleaned else None
    if theme_preference:
        user.theme_preference = theme_preference

    db.session.commit()
    return jsonify(
        {
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "theme_preference": user.theme_preference,
        }
    )
