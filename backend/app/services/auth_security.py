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
    from app.models import UserSession

    token_hash = hash_session_token(token)
    user.session_token_hash = token_hash
    user.session_token = None
    if token_hash:
        db.session.add(UserSession(user=user, token_hash=token_hash))
    return token


def clear_session_token(user: User) -> None:
    """Clear all persisted session token state."""
    from app.models import UserSession

    UserSession.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    user.session_token_hash = None
    user.session_token = None
    user.session_created_at = None


def clear_session_by_raw_token(token: str | None) -> None:
    """Clear a single persisted session by its raw token."""
    if not token:
        return

    from app.models import UserSession

    token_hash = hash_session_token(token)
    if not token_hash:
        return
    persisted_session = UserSession.query.filter_by(token_hash=token_hash).first()
    if not persisted_session:
        return

    user = persisted_session.user
    db.session.delete(persisted_session)

    if user and user.session_token_hash == token_hash:
        replacement = (
            UserSession.query.filter_by(user_id=user.id)
            .order_by(UserSession.created_at.desc())
            .first()
        )
        user.session_token_hash = replacement.token_hash if replacement else None
        user.session_created_at = replacement.created_at if replacement else None
        user.session_token = None


def find_user_by_session_token(token: str | None, migrate_legacy: bool = True) -> User | None:
    """Find the authenticated user for a raw session token."""
    if not token:
        return None

    from app.models import User, UserSession

    hashed = hash_session_token(token)
    persisted_session = UserSession.query.filter_by(token_hash=hashed).first()
    if persisted_session:
        return User.query.filter_by(id=persisted_session.user_id).first()

    user = User.query.filter_by(session_token_hash=hashed).first()
    if user:
        has_persisted_sessions = UserSession.query.filter_by(user_id=user.id).first() is not None
        if not has_persisted_sessions:
            # Backfill legacy single-session records into user_sessions.
            db.session.add(UserSession(user_id=user.id, token_hash=hashed))
            db.session.commit()
            return user
        return None

    user = User.query.filter_by(_legacy_session_token=token).first()
    if user and migrate_legacy:
        user.session_token_hash = hashed
        user.session_token = None
        db.session.add(UserSession(user_id=user.id, token_hash=hashed))
        db.session.commit()
    return user
