"""Server-side governance for manual refresh execution."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import datetime, timedelta

from app.config import Config
from app.models import UserChannel


_active_refreshes = {}
_active_refreshes_lock = threading.Lock()


def build_scope(channel_id=None):
    """Build a serializable refresh scope descriptor."""
    if channel_id:
        return {"type": "channel", "channel_id": channel_id}
    return {"type": "all_channels", "channel_id": None}


def _subscription_reference_time(subscription):
    """Return the most recent known refresh/check timestamp for a subscription."""
    return subscription.last_checked_at or subscription.last_refreshed_at


def _get_relevant_subscriptions(user_id, channel_id=None):
    """Load the subscriptions that define manual refresh freshness."""
    if channel_id:
        subscriptions = UserChannel.query.filter_by(user_id=user_id, channel_id=channel_id).all()
    else:
        subscriptions = UserChannel.query.filter_by(user_id=user_id).all()
    return subscriptions


def get_manual_refresh_cooldown(channel_id=None):
    """Return the configured cooldown for the given refresh scope."""
    if channel_id:
        return Config.MANUAL_REFRESH_CHANNEL_COOLDOWN_SECONDS
    return Config.MANUAL_REFRESH_FULL_COOLDOWN_SECONDS


def evaluate_manual_refresh(user_id, channel_id=None, now=None):
    """Return whether a manual refresh is allowed for the current freshness window."""
    now = now or datetime.utcnow()
    cooldown_seconds = get_manual_refresh_cooldown(channel_id)
    subscriptions = _get_relevant_subscriptions(user_id, channel_id=channel_id)
    latest_activity = None

    for subscription in subscriptions:
        reference = _subscription_reference_time(subscription)
        if reference and (latest_activity is None or reference > latest_activity):
            latest_activity = reference

    if not latest_activity:
        return {
            "allowed": True,
            "scope": build_scope(channel_id),
            "cooldown_seconds": cooldown_seconds,
            "last_activity_at": None,
            "next_allowed_at": None,
            "retry_after_seconds": 0,
        }

    next_allowed_at = latest_activity + timedelta(seconds=cooldown_seconds)
    retry_after_seconds = int(max((next_allowed_at - now).total_seconds(), 0))
    if retry_after_seconds > 0:
        return {
            "allowed": False,
            "reason": "cooldown_active",
            "status_code": 429,
            "scope": build_scope(channel_id),
            "cooldown_seconds": cooldown_seconds,
            "last_activity_at": latest_activity.isoformat(),
            "next_allowed_at": next_allowed_at.isoformat(),
            "retry_after_seconds": retry_after_seconds,
        }

    return {
        "allowed": True,
        "scope": build_scope(channel_id),
        "cooldown_seconds": cooldown_seconds,
        "last_activity_at": latest_activity.isoformat(),
        "next_allowed_at": next_allowed_at.isoformat(),
        "retry_after_seconds": 0,
    }


def get_active_refresh(user_id):
    """Return in-flight refresh metadata for the user, if any."""
    with _active_refreshes_lock:
        active = _active_refreshes.get(user_id)
        if not active:
            return None
        return {
            "scope": dict(active["scope"]),
            "started_at": active["started_at"],
        }


def list_active_refreshes():
    """Return all in-flight manual refreshes in process-local memory."""
    with _active_refreshes_lock:
        return {
            str(user_id): {
                "scope": dict(active["scope"]),
                "started_at": active["started_at"],
            }
            for user_id, active in _active_refreshes.items()
        }


@contextmanager
def acquire_manual_refresh(user_id, channel_id=None, now=None):
    """Acquire a user-level manual refresh lease, if possible."""
    now = now or datetime.utcnow()
    scope = build_scope(channel_id)

    with _active_refreshes_lock:
        active = _active_refreshes.get(user_id)
        if active:
            yield {
                "acquired": False,
                "reason": "refresh_in_progress",
                "status_code": 409,
                "scope": scope,
                "active_scope": dict(active["scope"]),
                "active_started_at": active["started_at"],
            }
            return

        _active_refreshes[user_id] = {
            "scope": scope,
            "started_at": now.isoformat(),
        }

    try:
        yield {
            "acquired": True,
            "scope": scope,
            "started_at": now.isoformat(),
        }
    finally:
        with _active_refreshes_lock:
            active = _active_refreshes.get(user_id)
            if active and active["scope"] == scope:
                _active_refreshes.pop(user_id, None)
