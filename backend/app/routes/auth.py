"""Authentication routes using httpOnly cookies."""

import json
import secrets
from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, redirect, request, session

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import COOKIE_NAME, require_auth
from app.middleware.error_handler import handle_route_errors
from app.models import User
from app.services.auth_security import bind_session_token, clear_session_token, find_user_by_session_token
from app.services.google_oauth import (
    apply_token_response,
    build_auth_url,
    exchange_code_for_tokens,
    fetch_user_info,
    revoke_google_tokens,
)
from app.services.totp_auth import (
    build_totp_uri,
    consume_recovery_code,
    generate_recovery_codes,
    generate_totp_secret,
    hash_recovery_codes,
    verify_totp_code,
)

auth_bp = Blueprint("auth", __name__)

COOKIE_MAX_AGE = 30 * 24 * 60 * 60
STATE_COOKIE_NAME = "ytcv_oauth_state"
STATE_COOKIE_MAX_AGE = 10 * 60
KNOWN_GOOGLE_USERS_KEY = "known_google_user_ids"


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


def _set_state_cookie(response, state):
    """Set a short-lived OAuth state cookie."""
    secure_cookie = current_app.config.get("COOKIE_SECURE", True)
    response.set_cookie(
        STATE_COOKIE_NAME,
        state,
        httponly=True,
        secure=secure_cookie,
        samesite="Lax",
        max_age=STATE_COOKIE_MAX_AGE,
        path="/api/auth/google",
    )


def _clear_state_cookie(response):
    """Clear the OAuth state cookie."""
    secure_cookie = current_app.config.get("COOKIE_SECURE", True)
    response.set_cookie(
        STATE_COOKIE_NAME,
        "",
        httponly=True,
        secure=secure_cookie,
        samesite="Lax",
        max_age=0,
        expires=0,
        path="/api/auth/google",
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


def _auth_mode():
    """Return the configured authentication mode."""
    return (current_app.config.get("AUTH_MODE") or "local").lower()


def _forbidden(message):
    """Return a forbidden response with a tracking ID."""
    tracking_id = generate_tracking_id()
    get_logger(__name__).warning(message, extra={"tracking_id": tracking_id})
    return jsonify({"error": "Forbidden.", "tracking_id": tracking_id, "status": 403}), 403


def _server_error(message):
    """Return a generic server error response with a tracking ID."""
    tracking_id = generate_tracking_id()
    get_logger(__name__).error(message, extra={"tracking_id": tracking_id})
    return (
        jsonify({"error": "Internal server error.", "tracking_id": tracking_id, "status": 500}),
        500,
    )


def _redirect_to_frontend(error_code=None):
    """Redirect back to the configured frontend URL."""
    base_url = current_app.config.get("FRONTEND_URL") or "/"
    if not error_code:
        return redirect(base_url)

    separator = "&" if "?" in base_url else "?"
    return redirect(f"{base_url}{separator}auth_error={error_code}")


def _get_known_google_user_ids():
    """Return the browser-known Google user ids stored in the signed session."""
    raw_ids = session.get(KNOWN_GOOGLE_USERS_KEY, [])
    if not isinstance(raw_ids, list):
        return []

    user_ids = []
    for value in raw_ids:
        try:
            user_ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return user_ids


def _remember_google_user(user_id):
    """Remember a Google account in the browser session for fast switching."""
    user_ids = [known_id for known_id in _get_known_google_user_ids() if known_id != user_id]
    user_ids.insert(0, int(user_id))
    session[KNOWN_GOOGLE_USERS_KEY] = user_ids[:10]
    session.modified = True


def _serialize_switchable_user(user, current_user_id=None):
    """Serialize a switchable Google account for the frontend."""
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "auth_provider": user.auth_provider,
        "google_avatar_url": user.google_avatar_url,
        "google_auth_status": user.google_auth_status,
        "is_current": bool(current_user_id and user.id == current_user_id),
    }


def _issue_session_for_user(user):
    """Create and persist a fresh server-side session token for a user."""
    session_token = secrets.token_urlsafe(32)
    bind_session_token(user, session_token)
    user.session_created_at = datetime.utcnow()
    return session_token


@auth_bp.post("/api/auth/login")
@handle_route_errors
def login():
    """Login or create a user and set a secure session cookie."""
    if _auth_mode() != "local":
        return _forbidden("Local login disabled in Google OAuth mode.")

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

    session_token = _issue_session_for_user(user)
    db.session.commit()

    response = jsonify(
        {
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "auth_provider": user.auth_provider,
            "email": user.email,
            "google_avatar_url": user.google_avatar_url,
            "google_auth_status": user.google_auth_status,
            "totp_enabled": user.totp_enabled,
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
        user = find_user_by_session_token(token)
        if user:
            clear_session_token(user)
            db.session.commit()

    response = jsonify({"message": "Logged out"})
    _clear_session_cookie(response)
    return response


@auth_bp.get("/api/auth/accounts")
@handle_route_errors
def list_switchable_accounts():
    """Return Google accounts already known in this browser session."""
    if _auth_mode() != "google":
        return _forbidden("Google account switching not enabled.")

    known_ids = _get_known_google_user_ids()
    if not known_ids:
        return jsonify({"accounts": [], "current_user_id": None})

    token = request.cookies.get(COOKIE_NAME)
    current_user = find_user_by_session_token(token) if token else None
    users = (
        User.query.filter(User.id.in_(known_ids), User.auth_provider == "google")
        .order_by(User.display_name.asc(), User.username.asc())
        .all()
    )

    order = {user_id: index for index, user_id in enumerate(known_ids)}
    users.sort(key=lambda user: order.get(user.id, len(order)))
    current_user_id = current_user.id if current_user else None

    return jsonify(
        {
            "accounts": [
                _serialize_switchable_user(user, current_user_id=current_user_id) for user in users
            ],
            "current_user_id": current_user_id,
        }
    )


@auth_bp.post("/api/auth/switch")
@handle_route_errors
def switch_account():
    """Switch the active session to another known Google account."""
    if _auth_mode() != "google":
        return _forbidden("Google account switching not enabled.")

    data = request.get_json(silent=True) or {}
    target_user_id = data.get("user_id")
    try:
        target_user_id = int(target_user_id)
    except (TypeError, ValueError):
        tracking_id = generate_tracking_id()
        return (
            jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}),
            400,
        )

    known_ids = _get_known_google_user_ids()
    if target_user_id not in known_ids:
        return _forbidden("Account not available for switching in this browser.")

    user = User.query.filter_by(id=target_user_id, auth_provider="google").first()
    if not user:
        tracking_id = generate_tracking_id()
        return (
            jsonify({"error": "Not found.", "tracking_id": tracking_id, "status": 404}),
            404,
        )

    session_token = _issue_session_for_user(user)
    _remember_google_user(user.id)
    db.session.commit()

    response = jsonify(
        {
            "authenticated": True,
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "auth_provider": user.auth_provider,
            "google_avatar_url": user.google_avatar_url,
            "google_auth_status": user.google_auth_status,
            "totp_enabled": user.totp_enabled,
            "theme_preference": user.theme_preference,
        }
    )
    _set_session_cookie(response, session_token)
    return response


@auth_bp.get("/api/auth/users")
@handle_route_errors
def list_users():
    """Return all users for the login selector."""
    if _auth_mode() != "local":
        return _forbidden("User list disabled in Google OAuth mode.")

    users = User.query.order_by(User.username.asc()).all()
    data = [
        {"id": user.id, "username": user.username, "display_name": user.display_name}
        for user in users
    ]
    return jsonify(data)


@auth_bp.get("/api/auth/provider")
@handle_route_errors
def auth_provider():
    """Return the configured authentication mode."""
    mode = _auth_mode()
    login_url = "/api/auth/google" if mode == "google" else None
    return jsonify({"auth_mode": mode, "google_login_url": login_url})


@auth_bp.get("/api/auth/google")
@handle_route_errors
def google_login():
    """Start the Google OAuth flow."""
    if _auth_mode() != "google":
        return _forbidden("Google OAuth not enabled.")

    if (
        not current_app.config.get("GOOGLE_CLIENT_ID")
        or not current_app.config.get("GOOGLE_CLIENT_SECRET")
        or not current_app.config.get("GOOGLE_REDIRECT_URI")
    ):
        return _server_error("Missing Google OAuth configuration.")

    state = secrets.token_urlsafe(24)
    auth_url = build_auth_url(state)
    response = redirect(auth_url)
    _set_state_cookie(response, state)
    return response


@auth_bp.get("/api/auth/google/callback")
@handle_route_errors
def google_callback():
    """Handle the Google OAuth callback and create a session."""
    if _auth_mode() != "google":
        return _forbidden("Google OAuth not enabled.")

    error = request.args.get("error")
    if error:
        response = _redirect_to_frontend("oauth_denied")
        _clear_state_cookie(response)
        return response

    state = request.args.get("state")
    code = request.args.get("code")
    cookie_state = request.cookies.get(STATE_COOKIE_NAME)
    if not state or not code or state != cookie_state:
        response = _redirect_to_frontend("state_mismatch")
        _clear_state_cookie(response)
        return response

    token_data = exchange_code_for_tokens(code)
    if not token_data or not token_data.get("access_token"):
        response = _redirect_to_frontend("token_error")
        _clear_state_cookie(response)
        return response

    user_info = fetch_user_info(token_data.get("access_token"))
    if not user_info or not user_info.get("sub"):
        response = _redirect_to_frontend("profile_error")
        _clear_state_cookie(response)
        return response

    google_user_id = user_info.get("sub")
    email = user_info.get("email")
    display_name = user_info.get("name") or email or "Google user"
    avatar_url = user_info.get("picture")

    user = User.query.filter_by(google_user_id=google_user_id).first()
    if not user and email:
        user = User.query.filter_by(email=email).first()

    if not user:
        username = email or f"google_{google_user_id}"
        if User.query.filter_by(username=username).first():
            username = f"google_{google_user_id}"
        user = User(username=username, display_name=display_name)
        db.session.add(user)
        db.session.flush()

    user.auth_provider = "google"
    user.google_user_id = google_user_id
    user.google_avatar_url = avatar_url
    user.google_auth_status = "active"
    if email:
        user.email = email
    if display_name and not user.display_name:
        user.display_name = display_name

    apply_token_response(user, token_data)

    session_token = _issue_session_for_user(user)
    _remember_google_user(user.id)
    db.session.commit()

    response = _redirect_to_frontend()
    _set_session_cookie(response, session_token)
    _clear_state_cookie(response)
    return response


@auth_bp.get("/api/auth/current")
@handle_route_errors
def current_user():
    """Return the current authenticated user if a valid session exists."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return jsonify({"authenticated": False})

    user = find_user_by_session_token(token)
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
            "email": user.email,
            "auth_provider": user.auth_provider,
            "google_avatar_url": user.google_avatar_url,
            "google_auth_status": user.google_auth_status,
            "totp_enabled": user.totp_enabled,
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


@auth_bp.post("/api/auth/google/unlink")
@handle_route_errors
@require_auth
def unlink_google_account():
    """Unlink Google OAuth tokens from the current user."""
    user = g.current_user
    if user.auth_provider != "google":
        return _forbidden("Google account not linked.")

    refresh_token = user.google_refresh_token
    if refresh_token:
        revoke_google_tokens(refresh_token)

    user.google_access_token = None
    user.google_refresh_token = None
    user.google_scopes = None
    user.google_token_expires_at = None
    user.google_auth_status = "revoked"
    db.session.commit()

    return jsonify(
        {
            "user_id": user.id,
            "auth_provider": user.auth_provider,
            "google_auth_status": user.google_auth_status,
        }
    )


def _load_recovery_hashes(user):
    """Load persisted recovery code hashes for a user."""
    if not user.recovery_codes_hashes:
        return []
    try:
        data = json.loads(user.recovery_codes_hashes)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


@auth_bp.get("/api/auth/mfa/status")
@handle_route_errors
@require_auth
def mfa_status():
    """Return current MFA enrollment state for the authenticated user."""
    user = g.current_user
    return jsonify(
        {
            "totp_enabled": user.totp_enabled,
            "totp_pending": bool(user.totp_pending_secret),
            "recovery_codes_remaining": len(_load_recovery_hashes(user)),
        }
    )


@auth_bp.post("/api/auth/totp/setup")
@handle_route_errors
@require_auth
def setup_totp():
    """Create a pending TOTP secret for the current user."""
    user = g.current_user
    secret = generate_totp_secret()
    account_name = user.email or user.username or f"user-{user.id}"
    user.totp_pending_secret = secret
    db.session.commit()

    return jsonify({"secret": secret, "otpauth_url": build_totp_uri(secret, account_name)})


@auth_bp.post("/api/auth/totp/confirm")
@handle_route_errors
@require_auth
def confirm_totp():
    """Confirm TOTP setup and issue new recovery codes."""
    user = g.current_user
    if not user.totp_pending_secret:
        tracking_id = generate_tracking_id()
        return (
            jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}),
            400,
        )

    data = request.get_json(silent=True) or {}
    if not verify_totp_code(user.totp_pending_secret, data.get("code")):
        tracking_id = generate_tracking_id()
        return (
            jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}),
            400,
        )

    recovery_codes = generate_recovery_codes()
    user.totp_secret = user.totp_pending_secret
    user.totp_pending_secret = None
    user.totp_enabled = True
    user.recovery_codes_hashes = json.dumps(hash_recovery_codes(recovery_codes))
    db.session.commit()

    return jsonify({"totp_enabled": True, "recovery_codes": recovery_codes})


@auth_bp.post("/api/auth/recovery-codes/regenerate")
@handle_route_errors
@require_auth
def regenerate_recovery_codes():
    """Regenerate recovery codes after confirming the current TOTP code."""
    user = g.current_user
    if not user.totp_enabled or not user.totp_secret:
        return _forbidden("TOTP is not enabled.")

    data = request.get_json(silent=True) or {}
    if not verify_totp_code(user.totp_secret, data.get("code")):
        tracking_id = generate_tracking_id()
        return (
            jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}),
            400,
        )

    recovery_codes = generate_recovery_codes()
    user.recovery_codes_hashes = json.dumps(hash_recovery_codes(recovery_codes))
    db.session.commit()
    return jsonify({"recovery_codes": recovery_codes})


@auth_bp.post("/api/auth/recovery-codes/consume")
@handle_route_errors
@require_auth
def consume_recovery_code_route():
    """Consume one recovery code for the authenticated user."""
    user = g.current_user
    matched, remaining = consume_recovery_code(_load_recovery_hashes(user), (request.get_json(silent=True) or {}).get("code"))
    if not matched:
        tracking_id = generate_tracking_id()
        return (
            jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}),
            400,
        )

    user.recovery_codes_hashes = json.dumps(remaining)
    db.session.commit()
    return jsonify({"accepted": True, "recovery_codes_remaining": len(remaining)})
