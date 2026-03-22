"""Quota helpers for YouTube API usage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, insert, select, update

from app.config import Config
from app.extensions import db
from app.models import QuotaEvent, SiteSetting, UserSettings
from app.services.site_settings import (
    QUOTA_EXHAUSTED_UNTIL_KEY,
    get_quota_exhausted_until,
    get_refresh_schedule_timezone,
)
from app.utils.time import utc_now

PACIFIC_TZ = ZoneInfo("America/Los_Angeles")


def _utc_to_pacific(value: datetime | None = None) -> datetime:
    current = value or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(PACIFIC_TZ)


def get_current_quota_day_pt(value: datetime | None = None) -> str:
    """Return the official YouTube quota day key in Pacific Time."""
    return _utc_to_pacific(value).date().isoformat()


def get_next_quota_reset_pt(value: datetime | None = None) -> datetime:
    """Return the next quota reset timestamp in Pacific Time."""
    current_pt = _utc_to_pacific(value)
    tomorrow = current_pt.date() + timedelta(days=1)
    return datetime.combine(tomorrow, datetime.min.time(), tzinfo=PACIFIC_TZ)


def get_next_quota_reset_app_timezone(app_timezone: str | None = None, value: datetime | None = None) -> datetime:
    """Return the next quota reset translated to the configured app timezone."""
    target_tz = ZoneInfo(app_timezone or get_refresh_schedule_timezone() or "UTC")
    return get_next_quota_reset_pt(value).astimezone(target_tz)


def get_daily_cap():
    """Return the visible daily quota ceiling used for estimation."""
    cap = int(Config.YT_DAILY_QUOTA)
    return max(cap, 0)


def clear_quota_exhausted():
    """Clear any persisted upstream quota exhaustion state."""
    with db.engine.begin() as connection:
        connection.execute(
            update(SiteSetting.__table__)
            .where(SiteSetting.setting_key == QUOTA_EXHAUSTED_UNTIL_KEY)
            .values(setting_value="")
        )
    db.session.expire_all()


def get_quota_exhausted_snapshot(app_timezone: str | None = None):
    """Return whether upstream quota exhaustion is currently active."""
    exhausted_until = get_quota_exhausted_until()
    if not exhausted_until:
        return {
            "quota_exhausted": False,
            "quota_exhausted_until_pt": None,
            "quota_exhausted_until_app_timezone": None,
        }

    if exhausted_until.tzinfo is None:
        exhausted_until = exhausted_until.replace(tzinfo=PACIFIC_TZ)
    else:
        exhausted_until = exhausted_until.astimezone(PACIFIC_TZ)

    now_pt = _utc_to_pacific()
    if now_pt >= exhausted_until:
        return {
            "quota_exhausted": False,
            "quota_exhausted_until_pt": None,
            "quota_exhausted_until_app_timezone": None,
        }

    app_tz = ZoneInfo(app_timezone or get_refresh_schedule_timezone() or "UTC")
    return {
        "quota_exhausted": True,
        "quota_exhausted_until_pt": exhausted_until.isoformat(),
        "quota_exhausted_until_app_timezone": exhausted_until.astimezone(app_tz).isoformat(),
    }


def record_quota_event(
    api_method: str,
    units: int,
    *,
    source: str | None = None,
    success: bool = True,
    user_id: int | None = None,
    channel_id: int | None = None,
    tracking_id: str | None = None,
    notes: str | None = None,
    occurred_at: datetime | None = None,
):
    """Persist a single real YouTube quota consumption event."""
    event_time = occurred_at or utc_now()
    payload = {
        "occurred_at": event_time,
        "quota_day_pt": get_current_quota_day_pt(event_time),
        "api_method": (api_method or "unknown").strip(),
        "units": max(int(units or 0), 0),
        "source": (source or "").strip() or None,
        "success": bool(success),
        "user_id": user_id,
        "channel_id": channel_id,
        "tracking_id": tracking_id,
        "notes": notes,
    }
    # Persist quota usage outside the request transaction so an upstream
    # rollback does not erase real API consumption.
    with db.engine.begin() as connection:
        connection.execute(insert(QuotaEvent.__table__).values(**payload))
    return payload


def reset_quota_if_needed(settings):
    """Maintain legacy per-user quota fields using the official PT day."""
    if not settings:
        return
    today_pt = get_current_quota_day_pt()
    if settings.quota_date != today_pt:
        settings.quota_date = today_pt
        settings.quota_used = 0
    settings.quota_cap = get_daily_cap()


def can_consume(settings, units):
    """Check whether upstream quota exhaustion is currently active."""
    if settings:
        reset_quota_if_needed(settings)
    return not get_quota_exhausted_snapshot().get("quota_exhausted", False)


def consume(settings, units, **kwargs):
    """Gate work only when YouTube has already reported quota exhaustion."""
    if not can_consume(settings, units):
        return False
    if settings:
        reset_quota_if_needed(settings)
        settings.quota_used = get_global_quota_snapshot()["used"]
        settings.quota_cap = get_daily_cap()
    return True


def mark_quota_exhausted(settings):
    """Pause YouTube-consuming work until the next official Pacific reset."""
    next_reset_pt = get_next_quota_reset_pt()
    with db.engine.begin() as connection:
        existing = connection.execute(
            select(SiteSetting.id).where(SiteSetting.setting_key == QUOTA_EXHAUSTED_UNTIL_KEY)
        ).scalar_one_or_none()
        if existing is None:
            connection.execute(
                insert(SiteSetting.__table__).values(
                    setting_key=QUOTA_EXHAUSTED_UNTIL_KEY,
                    setting_value=next_reset_pt.isoformat(),
                )
            )
        else:
            connection.execute(
                update(SiteSetting.__table__)
                .where(SiteSetting.setting_key == QUOTA_EXHAUSTED_UNTIL_KEY)
                .values(setting_value=next_reset_pt.isoformat())
            )
    db.session.expire_all()
    if settings:
        reset_quota_if_needed(settings)
        settings.quota_used = get_global_quota_snapshot()["used"]
        settings.quota_cap = get_daily_cap()


def get_reserved_quota_units():
    """Return quota units reserved for scheduled refresh preference."""
    reserved = int(Config.YT_DAILY_QUOTA * Config.MANUAL_REFRESH_RESERVED_QUOTA_RATIO)
    return max(reserved, Config.YT_REFRESH_COST)


def _sum_quota_for_day(quota_day_pt: str) -> int:
    total = db.session.query(func.coalesce(func.sum(QuotaEvent.units), 0)).filter(
        QuotaEvent.quota_day_pt == quota_day_pt
    ).scalar()
    return int(total or 0)


def get_global_quota_snapshot(app_timezone: str | None = None):
    """Return a project-wide quota snapshot using the official PT quota day."""
    quota_day_pt = get_current_quota_day_pt()
    used = _sum_quota_for_day(quota_day_pt)

    daily_limit = int(Config.YT_DAILY_QUOTA)
    app_cap = get_daily_cap()
    reserved = get_reserved_quota_units()
    remaining_daily = max(daily_limit - used, 0)
    remaining_app_cap = max(app_cap - used, 0)
    reset_at_pt = get_next_quota_reset_pt()
    reset_at_app_tz = get_next_quota_reset_app_timezone(app_timezone)
    exhausted = get_quota_exhausted_snapshot(app_timezone)

    return {
        "quota_day_pt": quota_day_pt,
        "used": used,
        "daily_limit": daily_limit,
        "app_cap": app_cap,
        "remaining_daily": remaining_daily,
        "remaining_app_cap": remaining_app_cap,
        "reserved_for_scheduled": reserved,
        "reset_at_pt": reset_at_pt.isoformat(),
        "reset_at_app_timezone": reset_at_app_tz.isoformat(),
        "app_timezone": str(reset_at_app_tz.tzinfo or app_timezone or "UTC"),
        "official_timezone": "America/Los_Angeles",
        **exhausted,
    }


def should_block_manual_refresh_for_scheduled_priority():
    """Local quota estimation no longer hard-blocks manual refreshes."""
    return False
