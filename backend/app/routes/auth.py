"""Authentication routes using httpOnly cookies."""

import json
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, redirect, request, session

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import COOKIE_NAME, require_auth
from app.middleware.error_handler import handle_route_errors
from app.models import LoginPairing, User, UserPasskey
from app.services.auth_security import bind_session_token, clear_session_token, find_user_by_session_token
from app.services.google_oauth import (
    apply_token_response,
    build_auth_url,
    exchange_code_for_tokens,
    fetch_user_info,
    revoke_google_tokens,
)
from app.services.admin_access import is_admin_user
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
PASSKEY_REGISTRATION_KEY = "passkey_registration"
PASSKEY_AUTHENTICATION_KEY = "passkey_authentication"
MFA_CHALLENGE_KEY = "mfa_challenge"
MFA_CHALLENGE_MAX_AGE_SECONDS = 10 * 60
PAIRING_CODE_TTL_MINUTES = 10


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


def _serialize_authenticated_user(user):
    """Serialize the authenticated user payload consistently."""
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
        "is_admin": is_admin_user(user),
        "theme_preference": user.theme_preference,
    }


def _user_requires_mfa(user):
    """Return whether the user must complete a TOTP challenge after primary auth."""
    return bool(user and user.totp_enabled and user.totp_secret)


def _store_mfa_challenge(user):
    """Persist a short-lived MFA challenge in the signed browser session."""
    session[MFA_CHALLENGE_KEY] = {
        "user_id": user.id,
        "created_at": datetime.utcnow().timestamp(),
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

    if datetime.utcnow().timestamp() - created_at > MFA_CHALLENGE_MAX_AGE_SECONDS:
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


def _clear_existing_session_from_cookie():
    """Invalidate the currently active persisted session, if any."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return

    current_user = find_user_by_session_token(token)
    if current_user:
        clear_session_token(current_user)


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
            expires_at=datetime.utcnow() + timedelta(minutes=PAIRING_CODE_TTL_MINUTES),
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
        "expires_at": pairing.expires_at.isoformat() if pairing.expires_at else None,
        "approved_at": pairing.approved_at.isoformat() if pairing.approved_at else None,
        "used_at": pairing.used_at.isoformat() if pairing.used_at else None,
    }


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

    if _user_requires_mfa(user):
        _clear_existing_session_from_cookie()
        _store_mfa_challenge(user)
        db.session.commit()

        response = jsonify(_serialize_mfa_required(user))
        _clear_session_cookie(response)
        return response

    session_token = _issue_session_for_user(user)
    db.session.commit()

    response = jsonify(
        _serialize_authenticated_user(user) | {"authenticated": True}
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
    _clear_mfa_challenge()

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

    if _user_requires_mfa(user):
        _clear_existing_session_from_cookie()
        _store_mfa_challenge(user)
        _remember_google_user(user.id)
        db.session.commit()

        response = jsonify(_serialize_mfa_required(user))
        _clear_session_cookie(response)
        return response

    session_token = _issue_session_for_user(user)
    _remember_google_user(user.id)
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
        pending_user = _get_pending_mfa_user()
        if pending_user:
            return jsonify(_serialize_mfa_required(pending_user))
        return jsonify({"authenticated": False})

    user = find_user_by_session_token(token)
    if not user:
        pending_user = _get_pending_mfa_user()
        if pending_user:
            response = jsonify(_serialize_mfa_required(pending_user))
            _clear_session_cookie(response)
            return response
        response = jsonify({"authenticated": False})
        _clear_session_cookie(response)
        return response

    return jsonify(
        _serialize_authenticated_user(user)
    )


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
    code = ((request.get_json(silent=True) or {}).get("code") or "").strip().upper()
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
    pairing.approved_at = datetime.utcnow()
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

    pairing.used_at = datetime.utcnow()
    session_token = _issue_session_for_user(user)
    db.session.commit()

    response = jsonify(_serialize_authenticated_user(user) | {"pairing_claimed": True})
    _set_session_cookie(response, session_token)
    return response


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
    passkey.last_used_at = datetime.utcnow()
    passkey.credential_device_type = str(verified.credential_device_type.value)
    passkey.credential_backed_up = verified.credential_backed_up

    user = passkey.user
    session_token = _issue_session_for_user(user)
    db.session.commit()

    session.pop(PASSKEY_AUTHENTICATION_KEY, None)
    session.modified = True
    response = jsonify(_serialize_authenticated_user(user))
    _set_session_cookie(response, session_token)
    return response


@auth_bp.post("/api/auth/mfa/verify")
@handle_route_errors
def verify_mfa_challenge():
    """Complete a pending MFA challenge and issue the authenticated session."""
    user = _get_pending_mfa_user()
    if not user:
        return _forbidden("No MFA challenge is pending.")

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

    session_token = _issue_session_for_user(user)
    _clear_mfa_challenge()
    db.session.commit()

    response = jsonify(_serialize_authenticated_user(user))
    _set_session_cookie(response, session_token)
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
