"""Quota helpers for YT API usage."""

from datetime import datetime

from app.config import Config


def get_daily_cap():
    """Return daily quota cap (80% by default)."""
    cap = int(Config.YT_DAILY_QUOTA * Config.YT_QUOTA_CAP_RATIO)
    return max(cap, 0)


def reset_quota_if_needed(settings):
    """Reset quota counters if day changed."""
    today = datetime.utcnow().date().isoformat()
    if settings.quota_date != today:
        settings.quota_date = today
        settings.quota_used = 0
    settings.quota_cap = get_daily_cap()


def can_consume(settings, units):
    """Check if quota budget allows consuming units."""
    reset_quota_if_needed(settings)
    return settings.quota_used + units <= settings.quota_cap


def consume(settings, units):
    """Consume quota units if possible."""
    reset_quota_if_needed(settings)
    if settings.quota_used + units > settings.quota_cap:
        return False
    settings.quota_used += units
    return True


def mark_quota_exhausted(settings):
    """Mark quota as exhausted for today."""
    reset_quota_if_needed(settings)
    settings.quota_used = settings.quota_cap
