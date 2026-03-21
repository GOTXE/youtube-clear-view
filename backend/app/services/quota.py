"""Quota helpers for YT API usage."""

from app.config import Config
from app.models import UserSettings
from app.utils.time import utc_now


def get_daily_cap():
    """Return daily quota cap (80% by default)."""
    cap = int(Config.YT_DAILY_QUOTA * Config.YT_QUOTA_CAP_RATIO)
    return max(cap, 0)


def reset_quota_if_needed(settings):
    """Reset quota counters if day changed."""
    today = utc_now().date().isoformat()
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


def get_reserved_quota_units():
    """Return quota units reserved for scheduled refresh preference."""
    reserved = int(Config.YT_DAILY_QUOTA * Config.MANUAL_REFRESH_RESERVED_QUOTA_RATIO)
    return max(reserved, Config.YT_REFRESH_COST)


def get_global_quota_snapshot():
    """Return an estimated global quota snapshot aggregated from app state."""
    today = utc_now().date().isoformat()
    settings_list = UserSettings.query.all()
    used = 0
    for settings in settings_list:
        reset_quota_if_needed(settings)
        if settings.quota_date == today:
            used += int(settings.quota_used or 0)

    daily_limit = int(Config.YT_DAILY_QUOTA)
    app_cap = get_daily_cap()
    reserved = get_reserved_quota_units()
    remaining_daily = max(daily_limit - used, 0)
    remaining_app_cap = max(app_cap - used, 0)
    return {
        "date": today,
        "used": used,
        "daily_limit": daily_limit,
        "app_cap": app_cap,
        "remaining_daily": remaining_daily,
        "remaining_app_cap": remaining_app_cap,
        "reserved_for_scheduled": reserved,
    }


def should_block_manual_refresh_for_scheduled_priority():
    """Return whether manual refresh should be blocked to preserve scheduled quota."""
    snapshot = get_global_quota_snapshot()
    return snapshot["remaining_app_cap"] <= snapshot["reserved_for_scheduled"]
