"""Authentication security helpers for sessions and token storage."""

from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

from app.extensions import db

if TYPE_CHECKING:
    from app.models import User


def _build_fernet_key(secret: str) -> bytes:
    """Derive a stable Fernet key from an application secret."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    """Return the configured token cipher."""
    configured_key = current_app.config.get("AUTH_TOKEN_ENCRYPTION_KEY")
    if configured_key:
        return Fernet(configured_key.encode("utf-8"))

    fallback_secret = current_app.config.get("FLASK_SECRET_KEY") or current_app.config.get("SECRET_KEY")
    if not fallback_secret:
        raise ValueError("AUTH_TOKEN_ENCRYPTION_KEY or FLASK_SECRET_KEY is required.")

    return Fernet(_build_fernet_key(fallback_secret))


def encrypt_secret(value: str | None) -> str | None:
    """Encrypt a secret for storage."""
    if not value:
        return None
    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str | None:
    """Decrypt a stored secret, falling back to plaintext for legacy rows."""
    if not value:
        return None

    try:
        return _get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return value


def hash_session_token(token: str | None) -> str | None:
    """Hash a raw session token for database lookup."""
    if not token:
        return None
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def bind_session_token(user: User, token: str) -> str:
    """Persist a new hashed session token for the user."""
    user.session_token_hash = hash_session_token(token)
    user.session_token = None
    return token


def clear_session_token(user: User) -> None:
    """Clear all persisted session token state."""
    user.session_token_hash = None
    user.session_token = None
    user.session_created_at = None


def find_user_by_session_token(token: str | None, migrate_legacy: bool = True) -> User | None:
    """Find the authenticated user for a raw session token."""
    if not token:
        return None

    from app.models import User

    hashed = hash_session_token(token)
    user = User.query.filter_by(session_token_hash=hashed).first()
    if user:
        return user

    user = User.query.filter_by(_legacy_session_token=token).first()
    if user and migrate_legacy:
        user.session_token_hash = hashed
        user.session_token = None
        db.session.commit()
    return user
