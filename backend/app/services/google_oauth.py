"""Google OAuth helpers for login and token refresh."""

from datetime import timedelta
from urllib.parse import urlencode

import requests
from flask import current_app

from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.utils.time import utc_now

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

logger = get_logger(__name__)


def build_auth_url(state):
    """Build the Google OAuth consent URL."""
    config = current_app.config
    params = {
        "client_id": config.get("GOOGLE_CLIENT_ID"),
        "redirect_uri": config.get("GOOGLE_REDIRECT_URI"),
        "response_type": "code",
        "scope": config.get("GOOGLE_OAUTH_SCOPES"),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code):
    """Exchange an authorization code for tokens."""
    config = current_app.config
    payload = {
        "code": code,
        "client_id": config.get("GOOGLE_CLIENT_ID"),
        "client_secret": config.get("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": config.get("GOOGLE_REDIRECT_URI"),
        "grant_type": "authorization_code",
    }
    return _post_token(payload, "token_exchange")


def refresh_access_token(refresh_token):
    """Refresh an access token using a stored refresh token."""
    if not refresh_token:
        return None

    config = current_app.config
    payload = {
        "client_id": config.get("GOOGLE_CLIENT_ID"),
        "client_secret": config.get("GOOGLE_CLIENT_SECRET"),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    return _post_token(payload, "token_refresh")


def fetch_user_info(access_token):
    """Fetch OpenID user info for the authenticated Google account."""
    if not access_token:
        return None

    try:
        response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
    except requests.RequestException as error:
        logger.warning(
            "Failed to fetch Google user info: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )
        return None

    if not response.ok:
        logger.warning(
            "Google user info returned %s",
            response.status_code,
            extra={"tracking_id": generate_tracking_id()},
        )
        return None

    return response.json()


def apply_token_response(user, token_data):
    """Persist token data onto the user model."""
    if not user or not token_data:
        return None

    access_token = token_data.get("access_token")
    if access_token:
        user.google_access_token = access_token

    refresh_token = token_data.get("refresh_token")
    if refresh_token:
        user.google_refresh_token = refresh_token

    scope = token_data.get("scope") or current_app.config.get("GOOGLE_OAUTH_SCOPES")
    if scope:
        user.google_scopes = scope
    user.google_auth_status = "active"

    expires_in = token_data.get("expires_in")
    if expires_in:
        try:
            user.google_token_expires_at = utc_now() + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            user.google_token_expires_at = None

    return user


def ensure_access_token(user, leeway_seconds=60):
    """Return a valid access token, refreshing if needed."""
    if not user:
        return None

    if user.google_access_token and user.google_token_expires_at:
        refresh_at = user.google_token_expires_at - timedelta(seconds=leeway_seconds)
        if utc_now() < refresh_at:
            return user.google_access_token

    if user.google_access_token and not user.google_token_expires_at:
        return user.google_access_token

    if not user.google_refresh_token:
        return None

    token_data = refresh_access_token(user.google_refresh_token)
    if not token_data:
        return None
    if token_data.get("error") == "invalid_grant":
        user.google_auth_status = "needs_reauth"
        return None
    if not token_data.get("access_token"):
        return None

    apply_token_response(user, token_data)
    return user.google_access_token


def revoke_google_tokens(refresh_token):
    """Revoke a stored Google refresh token."""
    if not refresh_token:
        return False

    try:
        response = requests.post(
            GOOGLE_REVOKE_URL,
            data={"token": refresh_token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
    except requests.RequestException as error:
        logger.warning(
            "Google OAuth revoke request failed: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )
        return False

    return response.ok


def request_device_code():
    """Request a device code from Google for the OAuth device flow.

    Returns a dict with keys: device_code, user_code, verification_url,
    expires_in, interval — or None on failure.
    """
    config = current_app.config
    client_id = config.get("GOOGLE_CLIENT_ID")
    scopes = config.get("GOOGLE_OAUTH_SCOPES")
    if not client_id:
        logger.warning(
            "Cannot request device code: GOOGLE_CLIENT_ID not configured.",
            extra={"tracking_id": generate_tracking_id()},
        )
        return None

    try:
        response = requests.post(
            GOOGLE_DEVICE_CODE_URL,
            data={"client_id": client_id, "scope": scopes},
            timeout=10,
        )
    except requests.RequestException as error:
        logger.warning(
            "Google device code request failed: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )
        return None

    if not response.ok:
        logger.warning(
            "Google device code request returned %s: %s",
            response.status_code,
            response.text[:200],
            extra={"tracking_id": generate_tracking_id()},
        )
        return None

    return response.json()


def poll_device_token(device_code):
    """Poll Google for a token using the device code.

    Returns a dict with one of:
    - Token data (access_token, refresh_token, etc.) on success.
    - {"pending": True} if the user hasn't authorized yet.
    - {"error": "<code>"} on terminal errors (expired, access_denied, etc.).
    - None on network/request failure.
    """
    config = current_app.config
    payload = {
        "client_id": config.get("GOOGLE_CLIENT_ID"),
        "client_secret": config.get("GOOGLE_CLIENT_SECRET"),
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }

    try:
        response = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=10)
    except requests.RequestException as error:
        logger.warning(
            "Google device token poll failed: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )
        return None

    data = {}
    try:
        data = response.json()
    except ValueError:
        return None

    if response.ok:
        return data

    error_code = data.get("error", "")
    if error_code == "authorization_pending":
        return {"pending": True}
    if error_code == "slow_down":
        return {"pending": True, "slow_down": True}

    # Terminal errors: expired_token, access_denied, etc.
    logger.info(
        "Device flow token poll terminal error: %s",
        error_code,
        extra={"tracking_id": generate_tracking_id()},
    )
    return {"error": error_code}


def _post_token(payload, action):
    """Post token requests to Google OAuth endpoints."""
    try:
        response = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=10)
    except requests.RequestException as error:
        logger.warning(
            "Google OAuth %s request failed: %s",
            action,
            error,
            extra={"tracking_id": generate_tracking_id()},
        )
        return None

    if not response.ok:
        logger.warning(
            "Google OAuth %s returned %s",
            action,
            response.status_code,
            extra={"tracking_id": generate_tracking_id()},
        )
        try:
            return response.json()
        except ValueError:
            return None

    return response.json()
