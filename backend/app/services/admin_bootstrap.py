"""Helpers for admin bootstrap, persistence, and recovery."""

from __future__ import annotations

from flask import current_app

from app.extensions import db
from app.logging.logger import get_logger
from app.models import User
from app.services.auth_security import clear_session_token


def has_admin_user() -> bool:
    """Return whether at least one active admin account exists."""
    return db.session.query(User.id).filter(User.is_admin.is_(True)).first() is not None


def is_bootstrap_required() -> bool:
    """Return whether the application still needs its first admin account."""
    return not has_admin_user()


def apply_admin_recovery_if_requested() -> bool:
    """Apply explicit admin recovery mode from environment configuration."""
    if not current_app.config.get("ADMIN_FORCE_RESET", False):
        return False

    logger = get_logger(__name__)
    admins = User.query.filter(User.is_admin.is_(True)).all()
    if not admins:
        logger.warning(
            "Admin recovery requested but no admin users exist.",
            extra={"tracking_id": "SYSTEM"},
        )
        return False

    for user in admins:
        user.is_admin = False
        user.is_active = False
        user.must_change_password = False
        clear_session_token(user)

    db.session.commit()
    logger.warning(
        "Admin recovery mode demoted and disabled %s admin account(s).",
        len(admins),
        extra={"tracking_id": "SYSTEM"},
    )
    return True
