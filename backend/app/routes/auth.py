"""Authentication routes using httpOnly cookies."""

import json
import secrets
from datetime import timedelta

from flask import Blueprint, current_app, g, jsonify, redirect, request, session
from sqlalchemy import or_

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import ADMIN_COOKIE_NAME, COOKIE_NAME, require_auth
from app.middleware.error_handler import handle_route_errors
from app.middleware.rate_limiter import check_rate_limit, reset_rate_limit
from app.models import LoginPairing, User, UserPasskey, UserSettings
from app.services.auth_security import bind_session_token, clear_session_token, find_user_by_session_token
from app.services.google_oauth import (
    apply_token_response,
    build_auth_url,
    exchange_code_for_tokens,
    fetch_user_info,
    poll_device_token,
    request_device_code,
    revoke_google_tokens,
)
from app.services.admin_access import is_admin_user
from app.services.admin_bootstrap import (
    clear_bootstrap_window,
    get_bootstrap_window_info,
    is_bootstrap_locked,
    is_bootstrap_required,
)
from app.services.auth_policy import (
    sanitize_username_candidate,
    validate_password,
    validate_username,
)
from app.services.passkey_auth import (
    build_authentication_options,
    build_challenge_payload,
    build_registration_options,
    challenge_is_valid,
    decode_b64url,
    encode_b64url,
    verify_authentication_credential,
    verify_registration_credential,
)
from app.services.site_settings import get_password_policy
from app.services.totp_auth import (
    build_totp_uri,
    consume_recovery_code,
    generate_recovery_codes,
    generate_totp_secret,
    hash_recovery_codes,
    verify_totp_code,
)
from app.utils.time import utc_now

auth_bp = Blueprint("auth", __name__)

COOKIE_MAX_AGE = 30 * 24 * 60 * 60
STATE_COOKIE_NAME = "ytcv_oauth_state"
STATE_COOKIE_MAX_AGE = 10 * 60
KNOWN_GOOGLE_USERS_KEY = "known_google_user_ids"
PASSKEY_REGISTRATION_KEY = "passkey_registration"
PASSKEY_AUTHENTICATION_KEY = "passkey_authentication"
MFA_CHALLENGE_KEY = "mfa_challenge"
MFA_CHALLENGE_MAX_AGE_SECONDS = 10 * 60
PASSWORD_CHANGE_CHALLENGE_KEY = "password_change_challenge"
PASSWORD_CHANGE_CHALLENGE_MAX_AGE_SECONDS = 15 * 60
PAIRING_CODE_TTL_MINUTES = 10

# Rate limiting: register / passkey-verify
_REGISTER_RATE_MAX = 10       # max 10 register attempts
_REGISTER_RATE_WINDOW = 3600  # per hour per IP
_PASSKEY_RATE_MAX = 20        # max 20 passkey verifications
_PASSKEY_RATE_WINDOW = 3600   # per hour per IP

# CSRF
CSRF_SESSION_KEY = "ytcv_csrf_token"
CSRF_HEADER = "X-CSRF-Token"


def _get_or_create_csrf_token() -> str:
    """Return the current session CSRF token, creating one if absent."""
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_hex(32)
        session[CSRF_SESSION_KEY] = token
        session.modified = True
    return token


def _validate_csrf() -> bool:
    """Return True if CSRF validation is disabled or token matches."""
    if not current_app.config.get("CSRF_ENABLED", True):
        return True
    expected = session.get(CSRF_SESSION_KEY)
    if not expected:
        return False
    received = request.headers.get(CSRF_HEADER, "")
    return secrets.compare_digest(expected, received)


def _set_cookie(response, cookie_name, token, path, max_age):
    """Attach an auth cookie with secure defaults."""
    secure_cookie = current_app.config.get("COOKIE_SECURE", True)
    response.set_cookie(
        cookie_name,
        token,
        httponly=True,
        secure=secure_cookie,
        samesite="Lax",
        max_age=max_age,
        path=path,
    )


def _set_session_cookie(response, token, max_age=COOKIE_MAX_AGE):
    """Attach the main user session cookie."""
    _set_cookie(response, COOKIE_NAME, token, "/api", max_age)


def _set_admin_session_cookie(response, token, max_age=COOKIE_MAX_AGE):
    """Attach the dedicated admin session cookie."""
    _set_cookie(response, ADMIN_COOKIE_NAME, token, "/api/admin", max_age)


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


def _clear_cookie(response, cookie_name, path):
    """Expire an auth cookie immediately."""
    secure_cookie = current_app.config.get("COOKIE_SECURE", True)
    response.set_cookie(
        cookie_name,
        "",
        httponly=True,
        secure=secure_cookie,
        samesite="Lax",
        max_age=0,
        expires=0,
        path=path,
    )


def _clear_session_cookie(response):
    """Expire the main user session cookie immediately."""
    _clear_cookie(response, COOKIE_NAME, "/api")


def _clear_admin_session_cookie(response):
    """Expire the dedicated admin session cookie immediately."""
    _clear_cookie(response, ADMIN_COOKIE_NAME, "/api/admin")


def _auth_mode():
    """Return the configured authentication mode."""
    return (current_app.config.get("AUTH_MODE") or "local").lower()


def _is_admin_surface_request():
    """Return whether the request is targeting the dedicated gestor auth flow."""
    return (request.headers.get("X-YTCV-Surface") or "").strip().lower() == "gestor"


def _set_scoped_session_cookie(response, token, user, max_age=COOKIE_MAX_AGE):
    """Attach the proper auth cookie for the current request surface."""
    if _is_admin_surface_request():
        if not is_admin_user(user):
            return _forbidden("Admin access required.")
        _set_admin_session_cookie(response, token, max_age=max_age)
        return None
    _set_session_cookie(response, token, max_age=max_age)
    return None


def _clear_scoped_session_cookie(response):
    """Clear the auth cookie for the current request surface."""
    if _is_admin_surface_request():
        _clear_admin_session_cookie(response)
        return
    _clear_session_cookie(response)


def _get_scoped_session_token():
    """Return the auth token for the current request surface."""
    if _is_admin_surface_request():
        return request.cookies.get(ADMIN_COOKIE_NAME)
    return request.cookies.get(COOKIE_NAME)


def _forbidden(message):
    """Return a forbidden response with a tracking ID."""
    tracking_id = generate_tracking_id()
    get_logger(__name__).warning(message, extra={"tracking_id": tracking_id})
    return jsonify({"error": "Forbidden.", "tracking_id": tracking_id, "status": 403}), 403


def _unauthorized(message):
    """Return a generic unauthorized response with a tracking ID."""
    tracking_id = generate_tracking_id()
    get_logger(__name__).warning(message, extra={"tracking_id": tracking_id})
    return (
        jsonify({"error": "Unauthorized.", "tracking_id": tracking_id, "status": 401}),
        401,
    )


def _server_error(message):
    """Return a generic server error response with a tracking ID."""
    tracking_id = generate_tracking_id()
    get_logger(__name__).error(message, extra={"tracking_id": tracking_id})
    return (
        jsonify({"error": "Internal server error.", "tracking_id": tracking_id, "status": 500}),
        500,
    )


def _save_oauth_origin():
    """Remember the caller's origin so the post-OAuth redirect lands on the
    same host the user started from (important for LAN access via IP)."""
    origin = request.headers.get("Origin") or request.referrer
    if origin:
        # Strip path — keep only scheme + host + port
        from urllib.parse import urlparse

        parsed = urlparse(origin)
        session["_oauth_origin"] = f"{parsed.scheme}://{parsed.netloc}"


def _redirect_to_frontend(code=None):
    """Redirect back to the frontend URL.

    Uses the origin saved at the start of the OAuth flow so that LAN clients
    (e.g. ``http://192.168.1.50:8080``) are redirected back to the same host
    instead of always landing on the configured ``FRONTEND_URL``.

    Pass ``code='needs_setup'`` to signal the wizard, or an error code string
    (any other value) which will be surfaced as ``auth_error=<code>``.
    """
    base_url = session.pop("_oauth_origin", None) or current_app.config.get("FRONTEND_URL") or "/"
    if not code:
        return redirect(base_url)

    separator = "&" if "?" in base_url else "?"
    if code == "needs_setup":
        return redirect(f"{base_url}{separator}auth_status=needs_setup")
    return redirect(f"{base_url}{separator}auth_error={code}")


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
    user.session_created_at = utc_now()
    return session_token


def _get_or_create_user_settings(user):
    """Return per-user settings, creating them if missing."""
    settings = UserSettings.query.filter_by(user_id=user.id).first()
    if settings:
        return settings
    settings = UserSettings(user_id=user.id)
    db.session.add(settings)
    db.session.flush()
    return settings


def _has_passkey(user):
    """Return True when the user has at least one registered passkey."""
    if not user or not user.id:
        return False
    return UserPasskey.query.filter_by(user_id=user.id).first() is not None


def _security_reminder_due(user):
    """Return True when the user should be reminded about TOTP/passkey."""
    if not user:
        return False
    if user.totp_enabled or _has_passkey(user):
        return False

    settings = UserSettings.query.filter_by(user_id=user.id).first()
    if not settings:
        return True
    if not settings.last_security_reminder_at:
        return True

    return (utc_now() - settings.last_security_reminder_at) >= timedelta(days=30)


def _serialize_authenticated_user(user):
    """Serialize the authenticated user payload consistently."""
    has_passkey = _has_passkey(user)
    return {
        "authenticated": True,
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "auth_provider": user.auth_provider,
        "google_avatar_url": user.google_avatar_url,
        "google_auth_status": user.google_auth_status,
        "totp_enabled": user.totp_enabled,
        "has_passkey": has_passkey,
        "security_reminder_due": bool((not user.totp_enabled and not has_passkey) and _security_reminder_due(user)),
        "is_admin": is_admin_user(user),
        "theme_preference": user.theme_preference,
        "has_password": bool(user.password_hash),
        "username_suggestion": _build_google_username_suggestion(
            email=user.email,
            display_name=user.display_name,
            fallback_username=user.username,
        ),
    }


def _build_google_username_suggestion(email=None, display_name=None, fallback_username=None):
    """Derive a safe editable username suggestion from Google profile data."""
    candidates = []
    if email and "@" in email:
        candidates.append(email.split("@", 1)[0])
    if display_name:
        candidates.append(display_name)
    if fallback_username:
        candidates.append(fallback_username)

    for candidate in candidates:
        sanitized = sanitize_username_candidate(candidate)
        if sanitized:
            return sanitized
    return ""


def _find_user_for_identifier(identifier):
    """Resolve a user by username or email without exposing which field matched."""
    normalized = (identifier or "").strip().lower()
    if not normalized:
        return None

    return User.query.filter(
        or_(
            db.func.lower(User.username) == normalized,
            db.func.lower(User.email) == normalized,
        )
    ).first()


def _user_requires_mfa(user):
    """Return whether the user must complete a TOTP challenge after primary auth."""
    return bool(user and user.totp_enabled and user.totp_secret)


def _store_mfa_challenge(user):
    """Persist a short-lived MFA challenge in the signed browser session."""
    session[MFA_CHALLENGE_KEY] = {
        "user_id": user.id,
        "created_at": utc_now().timestamp(),
    }
    session.modified = True


def _clear_mfa_challenge():
    """Clear any pending MFA challenge."""
    if MFA_CHALLENGE_KEY in session:
        session.pop(MFA_CHALLENGE_KEY, None)
        session.modified = True


def _load_mfa_challenge():
    """Load and validate the pending MFA challenge payload."""
    raw = session.get(MFA_CHALLENGE_KEY)
    if not isinstance(raw, dict):
        return None

    user_id = raw.get("user_id")
    created_at = raw.get("created_at")
    try:
        user_id = int(user_id)
        created_at = float(created_at)
    except (TypeError, ValueError):
        _clear_mfa_challenge()
        return None

    if utc_now().timestamp() - created_at > MFA_CHALLENGE_MAX_AGE_SECONDS:
        _clear_mfa_challenge()
        return None

    return {"user_id": user_id, "created_at": created_at}


def _get_pending_mfa_user():
    """Resolve the user behind a pending MFA challenge if one exists."""
    challenge = _load_mfa_challenge()
    if not challenge:
        return None

    user = User.query.filter_by(id=challenge["user_id"]).first()
    if not _user_requires_mfa(user):
        _clear_mfa_challenge()
        return None
    return user


def _serialize_mfa_required(user):
    """Serialize the pending MFA challenge payload for the frontend."""
    return {
        "authenticated": False,
        "mfa_required": True,
        "user_id": user.id,
        "display_name": user.display_name,
        "email": user.email,
        "auth_provider": user.auth_provider,
        "available_methods": ["totp", "recovery_code"],
    }


def _store_password_change_challenge(user):
    """Persist a short-lived password-change challenge in the signed browser session."""
    session[PASSWORD_CHANGE_CHALLENGE_KEY] = {
        "user_id": user.id,
        "created_at": utc_now().timestamp(),
    }
    session.modified = True


def _clear_password_change_challenge():
    """Clear any pending password-change challenge."""
    if PASSWORD_CHANGE_CHALLENGE_KEY in session:
        session.pop(PASSWORD_CHANGE_CHALLENGE_KEY, None)
        session.modified = True


def _load_password_change_challenge():
    """Load and validate the pending password-change challenge payload."""
    raw = session.get(PASSWORD_CHANGE_CHALLENGE_KEY)
    if not isinstance(raw, dict):
        return None

    user_id = raw.get("user_id")
    created_at = raw.get("created_at")
    try:
        user_id = int(user_id)
        created_at = float(created_at)
    except (TypeError, ValueError):
        _clear_password_change_challenge()
        return None

    if utc_now().timestamp() - created_at > PASSWORD_CHANGE_CHALLENGE_MAX_AGE_SECONDS:
        _clear_password_change_challenge()
        return None

    return {"user_id": user_id, "created_at": created_at}


def _get_pending_password_change_user():
    """Resolve the user behind a pending password-change challenge if one exists."""
    challenge = _load_password_change_challenge()
    if not challenge:
        return None

    user = User.query.filter_by(id=challenge["user_id"]).first()
    if not user or not user.must_change_password:
        _clear_password_change_challenge()
        return None
    return user


def _serialize_password_change_required(user):
    """Serialize the pending password-change challenge payload."""
    return {
        "authenticated": False,
        "password_change_required": True,
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
    }


def _clear_existing_session_from_cookie():
    """Invalidate the currently active persisted session, if any."""
    token = _get_scoped_session_token()
    if not token:
        return

    current_user = find_user_by_session_token(token)
    if current_user:
        clear_session_token(current_user)


def _handle_password_change_required(user):
    """Return a limited challenge response forcing a password change."""
    _clear_existing_session_from_cookie()
    _clear_mfa_challenge()
    _store_password_change_challenge(user)
    db.session.commit()

    response = jsonify(_serialize_password_change_required(user))
    _clear_scoped_session_cookie(response)
    return response


def _generate_pairing_code():
    """Generate a human-readable pairing code."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    first = "".join(secrets.choice(alphabet) for _ in range(4))
    second = "".join(secrets.choice(alphabet) for _ in range(4))
    return f"{first}-{second}"


def _create_login_pairing(device_identifier=None):
    """Create a unique login pairing request."""
    for _ in range(10):
        pairing = LoginPairing(
            public_id=secrets.token_urlsafe(16),
            pairing_code=_generate_pairing_code(),
            device_identifier=(device_identifier or "").strip()[:128] or None,
            expires_at=utc_now() + timedelta(minutes=PAIRING_CODE_TTL_MINUTES),
        )
        db.session.add(pairing)
        try:
            db.session.flush()
            return pairing
        except Exception:
            db.session.rollback()
    raise RuntimeError("Unable to create unique pairing code.")


def _serialize_pairing_status(pairing, status):
    """Serialize a pairing request status for API responses."""
    return {
        "status": status,
        "public_id": pairing.public_id,
        "pairing_code": pairing.pairing_code,
        "expires_at": (pairing.expires_at.isoformat() + "Z") if pairing.expires_at else None,
        "approved_at": (pairing.approved_at.isoformat() + "Z") if pairing.approved_at else None,
        "used_at": (pairing.used_at.isoformat() + "Z") if pairing.used_at else None,
    }


_MAX_LOGIN_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


def _record_failed_login(user):
    """Increment failed login counter and lock account if threshold reached."""
    user.login_attempts = (user.login_attempts or 0) + 1
    if user.login_attempts >= _MAX_LOGIN_ATTEMPTS:
        user.login_locked_until = utc_now() + timedelta(minutes=_LOCKOUT_MINUTES)
        get_logger(__name__).warning(
            "Account locked after %s failed attempts: user_id=%s",
            _MAX_LOGIN_ATTEMPTS,
            user.id,
        )


def _reset_login_attempts(user):
    """Clear failed login state on successful authentication."""
    user.login_attempts = 0
    user.login_locked_until = None


@auth_bp.post("/api/auth/login")
@handle_route_errors
def login():
    """Authenticate a local user with username and password."""
    if not _validate_csrf():
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username:
        tracking_id = generate_tracking_id()
        return (
            jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}),
            400,
        )

    user = User.query.filter_by(username=username).first()
    if not user:
        return _unauthorized("Invalid credentials.")
    if _is_admin_surface_request() and not is_admin_user(user):
        return _forbidden("Admin access required.")
    if not user.is_active:
        return jsonify({"error": "Account is disabled.", "status": 403}), 403

    if user.is_locked:
        return (
            jsonify({"error": "Account temporarily locked. Try again later.", "status": 423}),
            423,
        )

    if not user.password_hash:
        return _unauthorized("Local password is not configured for this user.")

    if not user.check_password(password):
        _record_failed_login(user)
        db.session.commit()
        return _unauthorized("Invalid credentials.")
    _reset_login_attempts(user)

    if _user_requires_mfa(user):
        _clear_existing_session_from_cookie()
        _store_mfa_challenge(user)
        db.session.commit()

        response = jsonify(_serialize_mfa_required(user))
        _clear_scoped_session_cookie(response)
        return response

    if user.must_change_password:
        return _handle_password_change_required(user)

    session_token = _issue_session_for_user(user)
    db.session.commit()

    payload = _serialize_authenticated_user(user) | {"authenticated": True}
    if not user.setup_completed:
        payload["needs_setup"] = True

    response = jsonify(payload)
    denied = _set_scoped_session_cookie(response, session_token, user)
    if denied:
        return denied
    return response


@auth_bp.post("/api/auth/register")
@handle_route_errors
def register():
    """Create a new local user account with username and password."""
    if not current_app.config.get("LOCAL_SIGNUP_ENABLED", False):
        return _forbidden("Local sign-up is disabled.")

    if not _validate_csrf():
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400

    ip = request.remote_addr or "unknown"
    if not check_rate_limit(f"register:{ip}", _REGISTER_RATE_MAX, _REGISTER_RATE_WINDOW):
        return (
            jsonify({"error": "Too many requests. Try again later.", "status": 429}),
            429,
        )

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip() or None

    username_ok, username_error = validate_username(username)
    if not username_ok:
        return jsonify({"error": username_error, "status": 400}), 400
    password_ok, password_error = validate_password(password, get_password_policy())
    if not password_ok:
        return jsonify({"error": password_error, "status": 400}), 400
    if User.query.filter_by(username=username).first():
        return (
            jsonify({"error": "Username already taken.", "status": 409}),
            409,
        )

    user = User(
        username=username,
        display_name=display_name or username,
        auth_provider="local",
        setup_completed=True,
    )
    user.set_password(password)
    db.session.add(user)
    session_token = _issue_session_for_user(user)
    db.session.commit()

    response = jsonify(_serialize_authenticated_user(user) | {"authenticated": True})
    _set_session_cookie(response, session_token)
    return response, 201


@auth_bp.post("/api/auth/fallback-login")
@handle_route_errors
def fallback_login():
    """Sign in a returning user with identifier plus TOTP or recovery code."""
    data = request.get_json(silent=True) or {}
    identifier = (data.get("identifier") or "").strip()
    method = (data.get("method") or "").strip()
    code = (data.get("code") or "").strip()
    if not identifier or method not in {"totp", "recovery_code"} or not code:
        tracking_id = generate_tracking_id()
        get_logger(__name__).warning(
            "Fallback login missing identifier or code.",
            extra={"tracking_id": tracking_id},
        )
        return (
            jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}),
            400,
        )

    user = _find_user_for_identifier(identifier)
    if not user or not user.totp_enabled:
        return _unauthorized("Fallback login failed.")
    if _is_admin_surface_request() and not is_admin_user(user):
        return _forbidden("Admin access required.")

    if method == "totp":
        if not user.totp_secret or not verify_totp_code(user.totp_secret, code):
            return _unauthorized("Fallback login failed.")
    else:
        matched, remaining = consume_recovery_code(_load_recovery_hashes(user), code)
        if not matched:
            return _unauthorized("Fallback login failed.")
        user.recovery_codes_hashes = json.dumps(remaining)

    _clear_existing_session_from_cookie()
    _clear_mfa_challenge()
    session_token = _issue_session_for_user(user)
    db.session.commit()

    response = jsonify(_serialize_authenticated_user(user) | {"authenticated": True})
    denied = _set_scoped_session_cookie(response, session_token, user)
    if denied:
        return denied
    return response


@auth_bp.post("/api/auth/logout")
@handle_route_errors
def logout():
    """Clear the session cookie and invalidate the server token."""
    token = _get_scoped_session_token()
    if token:
        user = find_user_by_session_token(token)
        if user:
            clear_session_token(user)
            db.session.commit()
    _clear_mfa_challenge()

    response = jsonify({"message": "Logged out"})
    _clear_scoped_session_cookie(response)
    return response


@auth_bp.get("/api/auth/accounts")
@handle_route_errors
@require_auth
def list_switchable_accounts():
    """Return active users available for account switching on this device."""
    current_user = g.current_user
    users = (
        User.query.filter_by(is_active=True, is_admin=False)
        .order_by(User.display_name.asc(), User.username.asc())
        .all()
    )

    return jsonify(
        {
            "accounts": [
                _serialize_switchable_user(user, current_user_id=current_user.id) for user in users
            ],
            "current_user_id": current_user.id,
        }
    )


@auth_bp.post("/api/auth/switch")
@handle_route_errors
@require_auth
def switch_account():
    """Switch the active session to another active user."""
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

    user = User.query.filter_by(id=target_user_id, is_active=True, is_admin=False).first()
    if not user:
        tracking_id = generate_tracking_id()
        return (
            jsonify({"error": "Not found.", "tracking_id": tracking_id, "status": 404}),
            404,
        )

    if _user_requires_mfa(user):
        _clear_existing_session_from_cookie()
        _store_mfa_challenge(user)
        db.session.commit()

        response = jsonify(_serialize_mfa_required(user))
        _clear_session_cookie(response)
        return response

    if user.must_change_password:
        return _handle_password_change_required(user)

    session_token = _issue_session_for_user(user)
    db.session.commit()

    response = jsonify(
        _serialize_authenticated_user(user)
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
    """Return the configured authentication mode and available login options."""
    mode = _auth_mode()
    google_configured = bool(
        current_app.config.get("GOOGLE_CLIENT_ID")
        and current_app.config.get("GOOGLE_CLIENT_SECRET")
        and current_app.config.get("GOOGLE_REDIRECT_URI")
    )
    bootstrap_required = is_bootstrap_required()
    payload = {
        "auth_mode": mode,
        "google_login_url": "/api/auth/google" if google_configured else None,
        "google_link_url": "/api/auth/google/link" if google_configured else None,
        "local_signup_enabled": bool(current_app.config.get("LOCAL_SIGNUP_ENABLED", False)),
        "registration_mode": "google_first",
        "password_policy": get_password_policy(),
        "csrf_token": _get_or_create_csrf_token(),
        "bootstrap_required": bootstrap_required,
    }
    if bootstrap_required:
        payload["bootstrap_window"] = get_bootstrap_window_info()
    return jsonify(payload)


@auth_bp.get("/api/bootstrap/status")
@handle_route_errors
def bootstrap_status():
    """Return whether the application still requires an admin bootstrap."""
    bootstrap_required = is_bootstrap_required()
    payload = {"bootstrap_required": bootstrap_required}
    if bootstrap_required:
        payload["bootstrap_window"] = get_bootstrap_window_info()
    return jsonify(payload)


@auth_bp.post("/api/bootstrap/admin")
@handle_route_errors
def bootstrap_admin():
    """Create the first administrator account when none exists yet."""
    if not is_bootstrap_required():
        return jsonify({"error": "Bootstrap already completed.", "status": 409}), 409

    if is_bootstrap_locked():
        return jsonify({
            "error": "Bootstrap window expired. Restart the application to try again.",
            "status": 423,
            "locked": True,
        }), 423

    if not _validate_csrf():
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    display_name = (data.get("display_name") or "").strip() or None
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or ""

    username_ok, username_error = validate_username(username)
    if not username_ok:
        return jsonify({"error": username_error, "status": 400}), 400
    if password != confirm_password:
        return jsonify({"error": "Passwords do not match.", "status": 400}), 400
    password_ok, password_error = validate_password(password, get_password_policy())
    if not password_ok:
        return jsonify({"error": password_error, "status": 400}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken.", "status": 409}), 409

    user = User(
        username=username,
        display_name=display_name or username,
        auth_provider="local",
        is_admin=True,
        is_active=True,
        must_change_password=False,
        setup_completed=True,
    )
    user.set_password(password)
    db.session.add(user)
    session_token = _issue_session_for_user(user)
    db.session.commit()
    clear_bootstrap_window()

    response = jsonify(_serialize_authenticated_user(user) | {"authenticated": True})
    _set_admin_session_cookie(response, session_token)
    return response, 201


_GOOGLE_OAUTH_INTENT_KEY = "google_oauth_intent"
_GOOGLE_OAUTH_INTENT_LOGIN = "login"
_GOOGLE_OAUTH_INTENT_LINK = "link"


def _google_oauth_configured():
    return bool(
        current_app.config.get("GOOGLE_CLIENT_ID")
        and current_app.config.get("GOOGLE_CLIENT_SECRET")
        and current_app.config.get("GOOGLE_REDIRECT_URI")
    )


@auth_bp.get("/api/auth/google")
@handle_route_errors
def google_login():
    """Start the Google OAuth login flow (no existing session required)."""
    if not _google_oauth_configured():
        return _server_error("Missing Google OAuth configuration.")

    state = secrets.token_urlsafe(24)
    session[_GOOGLE_OAUTH_INTENT_KEY] = _GOOGLE_OAUTH_INTENT_LOGIN
    _save_oauth_origin()
    auth_url = build_auth_url(state)
    response = redirect(auth_url)
    _set_state_cookie(response, state)
    return response


@auth_bp.get("/api/auth/google/link")
@handle_route_errors
@require_auth
def google_link():
    """Start the Google OAuth flow to link a YouTube account to the current user."""
    if not _google_oauth_configured():
        return _server_error("Missing Google OAuth configuration.")

    state = secrets.token_urlsafe(24)
    session[_GOOGLE_OAUTH_INTENT_KEY] = _GOOGLE_OAUTH_INTENT_LINK
    _save_oauth_origin()
    auth_url = build_auth_url(state)
    response = redirect(auth_url)
    _set_state_cookie(response, state)
    return response


@auth_bp.get("/api/auth/google/callback")
@handle_route_errors
def google_callback():
    """Handle the Google OAuth callback for both login and YouTube-link flows."""
    oauth_intent = session.pop(_GOOGLE_OAUTH_INTENT_KEY, _GOOGLE_OAUTH_INTENT_LOGIN)

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

    # --- Link intent: attach YouTube tokens to the already-authenticated user ---
    if oauth_intent == _GOOGLE_OAUTH_INTENT_LINK:
        token = request.cookies.get(COOKIE_NAME)
        linked_user = find_user_by_session_token(token) if token else None
        if not linked_user:
            response = _redirect_to_frontend("link_requires_auth")
            _clear_state_cookie(response)
            return response

        linked_user.google_user_id = google_user_id
        linked_user.google_avatar_url = avatar_url
        linked_user.google_auth_status = "active"
        if email:
            linked_user.email = linked_user.email or email
        apply_token_response(linked_user, token_data)
        db.session.commit()

        response = _redirect_to_frontend()
        _clear_state_cookie(response)
        return response

    # --- Login intent: find or create a user account ---
    user = User.query.filter_by(google_user_id=google_user_id).first()
    if not user and email:
        user = User.query.filter_by(email=email).first()

    is_new_user = user is None
    if is_new_user:
        username = email or f"google_{google_user_id}"
        if User.query.filter_by(username=username).first():
            username = f"google_{google_user_id}"
        user = User(
            username=username,
            display_name=display_name,
            auth_provider="google",
            setup_completed=False,
        )
        db.session.add(user)
        db.session.flush()

    user.google_user_id = google_user_id
    user.google_avatar_url = avatar_url
    user.google_auth_status = "active"
    if email:
        user.email = email
    if display_name and not user.display_name:
        user.display_name = display_name

    apply_token_response(user, token_data)

    if _user_requires_mfa(user):
        _clear_existing_session_from_cookie()
        _remember_google_user(user.id)
        _store_mfa_challenge(user)
        db.session.commit()

        response = _redirect_to_frontend()
        _clear_session_cookie(response)
        _clear_state_cookie(response)
        return response

    session_token = _issue_session_for_user(user)
    _remember_google_user(user.id)
    db.session.commit()

    # Redirect with needs_setup flag so the frontend shows the setup wizard.
    redirect_url = "needs_setup" if (not user.setup_completed or not user.password_hash) else None
    response = _redirect_to_frontend(redirect_url)
    _set_session_cookie(response, session_token)
    _clear_state_cookie(response)
    return response


_DEVICE_FLOW_DEVICE_CODE_KEY = "device_flow_device_code"
_DEVICE_FLOW_INTENT_KEY = "device_flow_intent"


def _google_device_flow_configured():
    """Device flow only needs client_id + client_secret (no redirect URI)."""
    return bool(
        current_app.config.get("GOOGLE_CLIENT_ID")
        and current_app.config.get("GOOGLE_CLIENT_SECRET")
    )


@auth_bp.post("/api/auth/google/device/start")
@handle_route_errors
def google_device_start():
    """Start the Google OAuth device flow and return user_code + verification_url."""
    if not _validate_csrf():
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400

    if not _google_device_flow_configured():
        return _server_error("Missing Google OAuth configuration.")

    intent = (request.get_json(silent=True) or {}).get("intent", "login")
    if intent not in ("login", "link"):
        intent = "login"

    result = request_device_code()
    if not result or "device_code" not in result:
        return _server_error("Could not start device flow.")

    session[_DEVICE_FLOW_DEVICE_CODE_KEY] = result["device_code"]
    session[_DEVICE_FLOW_INTENT_KEY] = intent

    verification_url = result.get("verification_url", "")
    qr_code = _build_qr_data_url(verification_url) if verification_url else None

    return jsonify({
        "user_code": result.get("user_code"),
        "verification_url": verification_url,
        "qr_code": qr_code,
        "expires_in": result.get("expires_in"),
        "interval": result.get("interval", 5),
    })


@auth_bp.get("/api/auth/google/device/status")
@handle_route_errors
def google_device_status():
    """Poll the device flow status. Returns pending, success, or error."""
    device_code = session.get(_DEVICE_FLOW_DEVICE_CODE_KEY)
    if not device_code:
        return jsonify({"error": "no_device_flow", "status": 400}), 400

    result = poll_device_token(device_code)
    if result is None:
        return _server_error("Failed to poll device status.")

    if result.get("pending"):
        payload = {"status": "pending"}
        if result.get("slow_down"):
            payload["slow_down"] = True
        return jsonify(payload)

    if result.get("error"):
        session.pop(_DEVICE_FLOW_DEVICE_CODE_KEY, None)
        session.pop(_DEVICE_FLOW_INTENT_KEY, None)
        session.pop("_device_flow_tokens", None)
        session.pop("_device_flow_identity", None)
        return jsonify({"status": "error", "error": result["error"]})

    # Success: we have tokens.  Fetch Google identity.
    access_token = result.get("access_token")
    if not access_token:
        return _server_error("Device flow returned no access token.")

    user_info = fetch_user_info(access_token)
    if not user_info or not user_info.get("sub"):
        return _server_error("Could not retrieve Google identity.")

    google_user_id = user_info["sub"]
    email = user_info.get("email")
    name = user_info.get("name", "")
    picture = user_info.get("picture", "")
    intent = session.pop(_DEVICE_FLOW_INTENT_KEY, "login")
    session.pop(_DEVICE_FLOW_DEVICE_CODE_KEY, None)

    # Store token data temporarily in session for the linking/creation step.
    session["_device_flow_tokens"] = {
        "access_token": access_token,
        "refresh_token": result.get("refresh_token"),
        "expires_in": result.get("expires_in"),
        "scope": result.get("scope"),
    }
    session["_device_flow_identity"] = {
        "google_user_id": google_user_id,
        "email": email,
        "name": name,
        "picture": picture,
    }

    # Check if an existing user matches.
    user = User.query.filter_by(google_user_id=google_user_id).first()
    email_match_user = None
    if not user and email:
        email_match_user = User.query.filter_by(email=email).first()

    if user:
        # Known Google user — update tokens and log in.
        apply_token_response(user, result)
        session_token = _issue_session_for_user(user)
        db.session.commit()
        session.pop("_device_flow_tokens", None)
        session.pop("_device_flow_identity", None)
        response = jsonify({
            "status": "authenticated",
            "user": _serialize_authenticated_user(user),
            "setup_completed": user.setup_completed,
        })
        _set_admin_session_cookie(response, session_token)
        return response

    if email_match_user:
        # Email match — needs user confirmation before linking.
        return jsonify({
            "status": "confirm_link",
            "google_identity": {
                "google_user_id": google_user_id,
                "email": email,
                "name": name,
                "picture": picture,
            },
            "existing_username": email_match_user.username,
        })

    # No match — new user, needs setup wizard.
    return jsonify({
        "status": "new_user",
        "google_identity": {
            "google_user_id": google_user_id,
            "email": email,
            "name": name,
            "picture": picture,
        },
    })


@auth_bp.post("/api/auth/google/device/confirm-link")
@handle_route_errors
def google_device_confirm_link():
    """Confirm linking a Google account to an existing local user (email match)."""
    if not _validate_csrf():
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400

    tokens = session.get("_device_flow_tokens")
    identity = session.get("_device_flow_identity")
    if not tokens or not identity:
        return jsonify({"error": "No pending device flow.", "status": 400}), 400

    google_user_id = identity.get("google_user_id")
    email = identity.get("email")
    if not google_user_id or not email:
        return jsonify({"error": "Incomplete Google identity.", "status": 400}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "No matching user found.", "status": 404}), 404

    # Link Google identity to existing user.
    user.google_user_id = google_user_id
    user.email = email
    user.google_avatar_url = identity.get("picture", "")
    apply_token_response(user, tokens)
    session_token = _issue_session_for_user(user)
    db.session.commit()

    session.pop("_device_flow_tokens", None)
    session.pop("_device_flow_identity", None)

    response = jsonify({
        "status": "authenticated",
        "user": _serialize_authenticated_user(user),
        "setup_completed": user.setup_completed,
    })
    _set_admin_session_cookie(response, session_token)
    return response


@auth_bp.post("/api/auth/google/device/create-account")
@handle_route_errors
def google_device_create_account():
    """Create a new local account from a device flow Google identity."""
    if not _validate_csrf():
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400

    tokens = session.get("_device_flow_tokens")
    identity = session.get("_device_flow_identity")
    if not tokens or not identity:
        return jsonify({"error": "No pending device flow.", "status": 400}), 400

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or ""

    username_ok, username_error = validate_username(username)
    if not username_ok:
        return jsonify({"error": username_error, "status": 400}), 400
    if password != confirm_password:
        return jsonify({"error": "Passwords do not match.", "status": 400}), 400
    password_ok, password_error = validate_password(password, get_password_policy())
    if not password_ok:
        return jsonify({"error": password_error, "status": 400}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken.", "status": 409}), 409

    google_user_id = identity.get("google_user_id")
    email = identity.get("email")
    name = identity.get("name", "")
    picture = identity.get("picture", "")

    user = User(
        username=username,
        display_name=name or username,
        email=email,
        google_user_id=google_user_id,
        google_avatar_url=picture,
        auth_provider="google",
        is_active=True,
        setup_completed=True,
    )
    user.set_password(password)
    apply_token_response(user, tokens)
    db.session.add(user)
    session_token = _issue_session_for_user(user)
    db.session.commit()

    session.pop("_device_flow_tokens", None)
    session.pop("_device_flow_identity", None)

    response = jsonify({
        "status": "authenticated",
        "user": _serialize_authenticated_user(user),
        "setup_completed": True,
    })
    _set_admin_session_cookie(response, session_token)
    return response, 201


@auth_bp.post("/api/auth/google/device/relink")
@handle_route_errors
@require_auth
def google_device_relink():
    """Relink Google tokens for an authenticated user via device flow."""
    tokens = session.get("_device_flow_tokens")
    identity = session.get("_device_flow_identity")
    if not tokens or not identity:
        return jsonify({"error": "No pending device flow.", "status": 400}), 400

    user = g.current_user
    google_user_id = identity.get("google_user_id")

    # Safety: ensure the Google identity matches the current user or is new.
    if user.google_user_id and user.google_user_id != google_user_id:
        existing = User.query.filter_by(google_user_id=google_user_id).first()
        if existing and existing.id != user.id:
            session.pop("_device_flow_tokens", None)
            session.pop("_device_flow_identity", None)
            return jsonify({
                "error": "This Google account is already linked to another user.",
                "status": 409,
            }), 409

    user.google_user_id = google_user_id
    user.email = identity.get("email") or user.email
    user.google_avatar_url = identity.get("picture", "")
    apply_token_response(user, tokens)
    db.session.commit()

    session.pop("_device_flow_tokens", None)
    session.pop("_device_flow_identity", None)

    return jsonify({
        "user_id": user.id,
        "google_user_id": user.google_user_id,
        "google_auth_status": user.google_auth_status,
    })


@auth_bp.post("/api/auth/google/complete-setup")
@handle_route_errors
@require_auth
def google_complete_setup():
    """Complete first-time setup for a user who registered via Google OAuth."""
    user = g.current_user
    data = request.get_json(silent=True) or {}
    password_policy = get_password_policy()

    new_username = (data.get("username") or "").strip()
    new_password = data.get("password") or ""

    username_ok, username_error = validate_username(new_username)
    if not username_ok:
        return jsonify({"error": username_error, "status": 400}), 400
    password_ok, password_error = validate_password(new_password, password_policy)
    if not password_ok:
        return jsonify({"error": password_error, "status": 400}), 400
    if User.query.filter(User.username == new_username, User.id != user.id).first():
        return jsonify({"error": "Username already taken.", "status": 409}), 409

    user.username = new_username
    user.set_password(new_password)

    user.setup_completed = True
    db.session.commit()

    return jsonify(
        _serialize_authenticated_user(user)
        | {
            "authenticated": True,
            "setup_completed": True,
            "username_suggestion": _build_google_username_suggestion(
                email=user.email,
                display_name=user.display_name,
                fallback_username=user.username,
            ),
        }
    )


@auth_bp.get("/api/auth/current")
@handle_route_errors
def current_user():
    """Return the current authenticated user if a valid session exists."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        pending_password_user = _get_pending_password_change_user()
        if pending_password_user:
            return jsonify(_serialize_password_change_required(pending_password_user))
        pending_user = _get_pending_mfa_user()
        if pending_user:
            return jsonify(_serialize_mfa_required(pending_user))
        return jsonify({"authenticated": False})

    user = find_user_by_session_token(token)
    if not user:
        pending_password_user = _get_pending_password_change_user()
        if pending_password_user:
            response = jsonify(_serialize_password_change_required(pending_password_user))
            _clear_session_cookie(response)
            return response
        pending_user = _get_pending_mfa_user()
        if pending_user:
            response = jsonify(_serialize_mfa_required(pending_user))
            _clear_session_cookie(response)
            return response
        response = jsonify({"authenticated": False})
        _clear_session_cookie(response)
        return response

    if not user.is_active:
        clear_session_token(user)
        db.session.commit()
        response = jsonify({"authenticated": False})
        _clear_session_cookie(response)
        return response

    return jsonify(
        _serialize_authenticated_user(user)
    )


@auth_bp.get("/api/admin/auth/current")
@handle_route_errors
def current_admin_user():
    """Return the current authenticated admin for the gestor surface."""
    token = request.cookies.get(ADMIN_COOKIE_NAME)
    if not token:
        pending_password_user = _get_pending_password_change_user()
        if pending_password_user and is_admin_user(pending_password_user):
            return jsonify(_serialize_password_change_required(pending_password_user))
        pending_user = _get_pending_mfa_user()
        if pending_user and is_admin_user(pending_user):
            return jsonify(_serialize_mfa_required(pending_user))
        return jsonify({"authenticated": False})

    user = find_user_by_session_token(token)
    if not user or not is_admin_user(user):
        pending_password_user = _get_pending_password_change_user()
        if pending_password_user and is_admin_user(pending_password_user):
            response = jsonify(_serialize_password_change_required(pending_password_user))
            _clear_admin_session_cookie(response)
            return response
        pending_user = _get_pending_mfa_user()
        if pending_user and is_admin_user(pending_user):
            response = jsonify(_serialize_mfa_required(pending_user))
            _clear_admin_session_cookie(response)
            return response
        response = jsonify({"authenticated": False})
        _clear_admin_session_cookie(response)
        return response

    if not user.is_active:
        clear_session_token(user)
        db.session.commit()
        response = jsonify({"authenticated": False})
        _clear_admin_session_cookie(response)
        return response

    return jsonify(_serialize_authenticated_user(user))


@auth_bp.post("/api/admin/auth/logout")
@handle_route_errors
def logout_admin():
    """Clear the dedicated admin session cookie and invalidate the server token."""
    token = request.cookies.get(ADMIN_COOKIE_NAME)
    if token:
        user = find_user_by_session_token(token)
        if user:
            clear_session_token(user)
            db.session.commit()
    _clear_mfa_challenge()

    response = jsonify({"message": "Logged out"})
    _clear_admin_session_cookie(response)
    return response


@auth_bp.post("/api/auth/security-reminder/ack")
@handle_route_errors
@require_auth
def acknowledge_security_reminder():
    """Record that the user has seen the TOTP/passkey reminder."""
    user = g.current_user
    settings = _get_or_create_user_settings(user)
    settings.last_security_reminder_at = utc_now()
    db.session.commit()
    return jsonify({"acknowledged": True, "last_security_reminder_at": settings.last_security_reminder_at.isoformat()})


@auth_bp.post("/api/auth/pairing/start")
@handle_route_errors
def start_pairing():
    """Start a short-lived pairing flow for a secondary device."""
    data = request.get_json(silent=True) or {}
    pairing = _create_login_pairing(device_identifier=data.get("device_identifier"))
    db.session.commit()
    return jsonify(_serialize_pairing_status(pairing, "pending"))


@auth_bp.post("/api/auth/pairing/approve")
@handle_route_errors
@require_auth
def approve_pairing():
    """Approve a pairing request from an already authenticated session."""
    raw = ((request.get_json(silent=True) or {}).get("code") or "").strip().upper()
    # Normalize: strip non-alphanumeric, then re-insert hyphen (XXXX-XXXX)
    digits = "".join(c for c in raw if c.isalnum())
    if len(digits) == 8:
        code = f"{digits[:4]}-{digits[4:]}"
    else:
        code = raw
    if not code:
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400

    pairing = LoginPairing.query.filter_by(pairing_code=code).first()
    if not pairing:
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Not found.", "tracking_id": tracking_id, "status": 404}), 404
    if pairing.is_expired():
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Gone.", "tracking_id": tracking_id, "status": 410}), 410
    if pairing.used_at:
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Conflict.", "tracking_id": tracking_id, "status": 409}), 409

    pairing.approved_user_id = g.current_user.id
    pairing.approved_at = utc_now()
    db.session.commit()
    return jsonify(_serialize_pairing_status(pairing, "approved"))


@auth_bp.post("/api/auth/pairing/claim")
@handle_route_errors
def claim_pairing():
    """Claim a pairing request from the original device and receive a session if approved."""
    public_id = ((request.get_json(silent=True) or {}).get("public_id") or "").strip()
    if not public_id:
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400

    pairing = LoginPairing.query.filter_by(public_id=public_id).first()
    if not pairing:
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Not found.", "tracking_id": tracking_id, "status": 404}), 404
    if pairing.is_expired():
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Gone.", "tracking_id": tracking_id, "status": 410}), 410
    if pairing.used_at:
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Conflict.", "tracking_id": tracking_id, "status": 409}), 409
    if not pairing.approved_user_id:
        return jsonify(_serialize_pairing_status(pairing, "pending"))

    user = User.query.filter_by(id=pairing.approved_user_id).first()
    if not user:
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Not found.", "tracking_id": tracking_id, "status": 404}), 404

    pairing.used_at = utc_now()
    session_token = _issue_session_for_user(user)
    db.session.commit()

    response = jsonify(_serialize_authenticated_user(user) | {"authenticated": True, "pairing_claimed": True})
    _set_session_cookie(response, session_token)
    return response


@auth_bp.put("/api/auth/profile")
@handle_route_errors
@require_auth
def update_profile():
    """Update the user's display name, theme preference, and username (local only)."""
    data = request.get_json(silent=True) or {}
    display_name = data.get("display_name")
    theme_preference = data.get("theme_preference")
    new_username = data.get("username")

    if theme_preference and theme_preference not in ("light", "dark"):
        tracking_id = generate_tracking_id()
        return (
            jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}),
            400,
        )

    user = g.current_user

    # Username change
    if new_username is not None:
        cleaned_username = new_username.strip()
        username_ok, username_error = validate_username(cleaned_username)
        if not username_ok:
            tracking_id = generate_tracking_id()
            return (
                jsonify({"error": username_error, "tracking_id": tracking_id, "status": 400}),
                400,
            )
        existing = User.query.filter(
            User.username == cleaned_username, User.id != user.id
        ).first()
        if existing:
            tracking_id = generate_tracking_id()
            return (
                jsonify({"error": "Username already taken.", "tracking_id": tracking_id, "status": 409}),
                409,
            )
        user.username = cleaned_username

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
            "auth_provider": user.auth_provider,
            "is_admin": is_admin_user(user),
        }
    )


@auth_bp.post("/api/auth/profile/password")
@handle_route_errors
def change_password():
    """Change the authenticated user's password."""
    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""
    password_ok, password_error = validate_password(new_password, get_password_policy())
    if not password_ok:
        return jsonify({"error": password_error, "status": 400}), 400

    token = _get_scoped_session_token()
    user = find_user_by_session_token(token) if token else None
    if user and not user.is_active:
        clear_session_token(user)
        db.session.commit()
        user = None
    user = user or _get_pending_password_change_user()
    if not user:
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Unauthorized.", "tracking_id": tracking_id, "status": 401}), 401
    if user.password_hash and not user.check_password(current_password):
        return _unauthorized("Current password is incorrect.")

    user.set_password(new_password)
    user.must_change_password = False
    if not user.setup_completed:
        user.setup_completed = True
    session_token = _issue_session_for_user(user)
    _clear_password_change_challenge()
    db.session.commit()

    response = jsonify({"message": "Password updated.", "authenticated": True} | _serialize_authenticated_user(user))
    denied = _set_scoped_session_cookie(response, session_token, user)
    if denied:
        return denied
    return response


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


def _normalize_passkey_label(label):
    """Normalize an optional passkey label."""
    cleaned = (label or "").strip()
    return cleaned[:200] if cleaned else None


def _extract_credential_id(credential):
    """Extract a credential ID from a WebAuthn payload."""
    if not isinstance(credential, dict):
        return None

    for key in ("id", "rawId"):
        value = credential.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


@auth_bp.get("/api/auth/passkeys")
@handle_route_errors
@require_auth
def list_passkeys():
    """Return registered passkeys for the current user."""
    user = g.current_user
    passkeys = (
        UserPasskey.query.filter_by(user_id=user.id)
        .order_by(UserPasskey.created_at.asc(), UserPasskey.id.asc())
        .all()
    )
    return jsonify({"passkeys": [passkey.to_dict() for passkey in passkeys]})


@auth_bp.post("/api/auth/passkeys/register/options")
@handle_route_errors
@require_auth
def passkey_registration_options():
    """Generate passkey registration options for the current user."""
    user = g.current_user
    label = _normalize_passkey_label((request.get_json(silent=True) or {}).get("label"))
    options, challenge = build_registration_options(user, user.passkeys or [])
    session[PASSKEY_REGISTRATION_KEY] = build_challenge_payload(challenge, user_id=user.id, label=label)
    session.modified = True
    return jsonify({"publicKey": options})


@auth_bp.post("/api/auth/passkeys/register/verify")
@handle_route_errors
@require_auth
def passkey_registration_verify():
    """Verify a passkey registration response and persist it."""
    user = g.current_user
    pending = session.get(PASSKEY_REGISTRATION_KEY)
    if not challenge_is_valid(pending, expected_user_id=user.id):
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400

    data = request.get_json(silent=True) or {}
    credential = data.get("credential")
    verified = verify_registration_credential(credential, pending["challenge"])

    credential_id = encode_b64url(verified.credential_id)
    existing = UserPasskey.query.filter_by(credential_id=credential_id).first()
    if existing:
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Conflict.", "tracking_id": tracking_id, "status": 409}), 409

    transports = []
    if isinstance(data.get("transports"), list):
        transports = [str(item) for item in data["transports"] if item]

    passkey = UserPasskey(
        user_id=user.id,
        label=_normalize_passkey_label(data.get("label")) or pending.get("label"),
        credential_id=credential_id,
        public_key=encode_b64url(verified.credential_public_key),
        sign_count=verified.sign_count,
        transports=",".join(transports) if transports else None,
        aaguid=verified.aaguid,
        credential_device_type=str(verified.credential_device_type.value),
        credential_backed_up=verified.credential_backed_up,
    )
    db.session.add(passkey)
    db.session.commit()

    session.pop(PASSKEY_REGISTRATION_KEY, None)
    session.modified = True
    return jsonify({"passkey": passkey.to_dict()})


@auth_bp.delete("/api/auth/passkeys/<int:passkey_id>")
@handle_route_errors
@require_auth
def delete_passkey(passkey_id):
    """Delete a passkey owned by the current user."""
    user = g.current_user
    passkey = UserPasskey.query.filter_by(id=passkey_id, user_id=user.id).first()
    if not passkey:
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Not found.", "tracking_id": tracking_id, "status": 404}), 404

    db.session.delete(passkey)
    db.session.commit()
    return jsonify({"deleted": True, "passkey_id": passkey_id})


@auth_bp.post("/api/auth/passkeys/authenticate/options")
@handle_route_errors
def passkey_authentication_options():
    """Generate authentication options for discoverable passkeys."""
    options, challenge = build_authentication_options()
    session[PASSKEY_AUTHENTICATION_KEY] = build_challenge_payload(challenge)
    session.modified = True
    return jsonify({"publicKey": options})


@auth_bp.post("/api/auth/passkeys/authenticate/verify")
@handle_route_errors
def passkey_authentication_verify():
    """Verify a passkey assertion and issue a session."""
    ip = request.remote_addr or "unknown"
    if not check_rate_limit(f"passkey_verify:{ip}", _PASSKEY_RATE_MAX, _PASSKEY_RATE_WINDOW):
        return (
            jsonify({"error": "Too many requests. Try again later.", "status": 429}),
            429,
        )

    pending = session.get(PASSKEY_AUTHENTICATION_KEY)
    if not challenge_is_valid(pending):
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400

    data = request.get_json(silent=True) or {}
    credential = data.get("credential")
    credential_id = _extract_credential_id(credential)
    if not credential_id:
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400

    passkey = UserPasskey.query.filter_by(credential_id=credential_id).first()
    if not passkey:
        return _forbidden("Passkey not available.")

    verified = verify_authentication_credential(credential, passkey, pending["challenge"])
    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = utc_now()
    passkey.credential_device_type = str(verified.credential_device_type.value)
    passkey.credential_backed_up = verified.credential_backed_up

    user = passkey.user
    if _is_admin_surface_request() and not is_admin_user(user):
        return _forbidden("Admin access required.")
    session_token = _issue_session_for_user(user)
    db.session.commit()

    session.pop(PASSKEY_AUTHENTICATION_KEY, None)
    session.modified = True
    response = jsonify(_serialize_authenticated_user(user))
    denied = _set_scoped_session_cookie(response, session_token, user)
    if denied:
        return denied
    return response


@auth_bp.post("/api/auth/mfa/verify")
@handle_route_errors
def verify_mfa_challenge():
    """Complete a pending MFA challenge and issue the authenticated session."""
    user = _get_pending_mfa_user()
    if not user:
        return _forbidden("No MFA challenge is pending.")
    if _is_admin_surface_request() and not is_admin_user(user):
        return _forbidden("Admin access required.")

    data = request.get_json(silent=True) or {}
    method = (data.get("method") or "").strip()
    code = (data.get("code") or "").strip()
    if method not in {"totp", "recovery_code"} or not code:
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400

    if method == "totp":
        if not verify_totp_code(user.totp_secret, code):
            tracking_id = generate_tracking_id()
            return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400
    else:
        matched, remaining = consume_recovery_code(_load_recovery_hashes(user), code)
        if not matched:
            tracking_id = generate_tracking_id()
            return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400
        user.recovery_codes_hashes = json.dumps(remaining)

    _clear_mfa_challenge()
    if user.must_change_password:
        return _handle_password_change_required(user)
    session_token = _issue_session_for_user(user)
    db.session.commit()

    response = jsonify(_serialize_authenticated_user(user))
    denied = _set_scoped_session_cookie(response, session_token, user)
    if denied:
        return denied
    return response


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


def _build_qr_data_url(content: str) -> str | None:
    """Generate a QR code SVG with white background for the given content.

    Returns a data URL (base64-encoded SVG) that renders well on any
    background colour, including dark themes.
    """
    try:
        import base64
        import io

        import qrcode
        import qrcode.image.svg

        img = qrcode.make(content, image_factory=qrcode.image.svg.SvgPathImage)
        raw = io.BytesIO()
        img.save(raw)
        svg_str = raw.getvalue().decode("utf-8")

        # Inject a white rounded-rect background right after the opening <svg ...> tag
        # so the QR is readable on any dark surface.
        import re

        svg_str = re.sub(
            r"(<svg[^>]*>)",
            r'\1<rect width="100%" height="100%" rx="8" ry="8" fill="white"/>',
            svg_str,
            count=1,
        )

        encoded = base64.b64encode(svg_str.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Failed to generate QR code")
        return None


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

    otpauth_url = build_totp_uri(secret, account_name)
    return jsonify({
        "secret": secret,
        "otpauth_url": otpauth_url,
        "qr_code": _build_qr_data_url(otpauth_url),
    })


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


@auth_bp.delete("/api/auth/totp")
@handle_route_errors
@require_auth
def disable_totp():
    """Disable TOTP for the current user (requires current TOTP code or password)."""
    user = g.current_user
    if not user.totp_enabled:
        return _forbidden("TOTP is not enabled.")

    data = request.get_json(silent=True) or {}
    totp_code = data.get("code")
    password = data.get("password")

    if totp_code:
        if not verify_totp_code(user.totp_secret, totp_code):
            tracking_id = generate_tracking_id()
            return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400
    elif password:
        if not user.check_password(password):
            tracking_id = generate_tracking_id()
            return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400
    else:
        tracking_id = generate_tracking_id()
        return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400

    user.totp_secret = None
    user.totp_pending_secret = None
    user.totp_enabled = False
    user.recovery_codes_hashes = None
    db.session.commit()
    return jsonify({"totp_enabled": False})


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
