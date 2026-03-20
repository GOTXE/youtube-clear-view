"""Helpers for minimal admin-only access control."""


def is_admin_user(user):
    """Return whether the given user has admin access."""
    return bool(user and getattr(user, "is_admin", False))
