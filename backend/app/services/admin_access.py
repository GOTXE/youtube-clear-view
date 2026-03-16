"""Helpers for minimal admin-only access control."""

from flask import current_app


def get_admin_usernames():
    """Return normalized admin usernames from configuration."""
    raw = current_app.config.get("ADMIN_USERNAMES", "")
    return {value.strip().lower() for value in raw.split(",") if value.strip()}


def is_admin_user(user):
    """Return whether the given user has admin access."""
    if not user:
        return False
    username = (getattr(user, "username", None) or "").strip().lower()
    email = (getattr(user, "email", None) or "").strip().lower()
    allowed = get_admin_usernames()
    return bool(username and username in allowed) or bool(email and email in allowed)
