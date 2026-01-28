"""Background scheduler for auto refresh and backfill."""

import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import Config
from app.extensions import db
from app.logging.logger import get_logger
from app.models import User, UserSettings, UserChannel
from app.services.presets import DEFAULT_PRESET
from app.services.quota import can_consume, consume, mark_quota_exhausted, reset_quota_if_needed
from app.services.yt_api import YTService
from app.services.video_ingest import refresh_user_channels

logger = get_logger(__name__)


def _get_or_create_settings(user):
    settings = UserSettings.query.filter_by(user_id=user.id).first()
    if settings:
        return settings
    settings = UserSettings(user_id=user.id, preset=DEFAULT_PRESET)
    db.session.add(settings)
    db.session.commit()
    return settings


def _hours_due(settings, now_utc):
    try:
        tz = ZoneInfo(settings.timezone or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")
    local_now = now_utc.astimezone(tz)
    hours = [hour for hour in settings.get_schedule_hours() if hour is not None]
    if not hours:
        return False
    if local_now.hour not in hours:
        return False
    if settings.last_schedule_run_at:
        last_local = settings.last_schedule_run_at.astimezone(tz)
        if last_local.date() == local_now.date() and last_local.hour == local_now.hour:
            return False
    return True


def _backfill_due(settings, now_utc):
    if not settings.backfill_active:
        return False
    if not settings.backfill_last_run_at:
        return True
    return now_utc - settings.backfill_last_run_at >= timedelta(
        minutes=Config.BACKFILL_INTERVAL_MINUTES
    )


def run_backfill_step(user, settings, service):
    subscriptions = UserChannel.query.filter_by(user_id=user.id).all()
    if not subscriptions:
        settings.backfill_active = False
        settings.backfill_cursor = None
        return

    subscriptions.sort(key=lambda sub: sub.channel_id)
    start_idx = settings.backfill_cursor or 0
    max_channels = Config.BACKFILL_MAX_CHANNELS
    now = datetime.utcnow()

    processed = 0
    idx = start_idx
    while idx < len(subscriptions) and processed < max_channels:
        if not can_consume(settings, Config.YT_REFRESH_COST):
            break
        subscription = subscriptions[idx]
        result = refresh_user_channels(
            user,
            settings,
            service,
            channel_id=subscription.channel_id,
            ignore_last_refreshed=True,
            now=now,
        )
        if result.get("rate_limited"):
            mark_quota_exhausted(settings)
            break
        idx += 1
        processed += 1

    settings.backfill_last_run_at = now

    if idx >= len(subscriptions):
        settings.backfill_active = False
        settings.backfill_cursor = None
    else:
        settings.backfill_cursor = idx


def _run_scheduled_refresh(user, settings, service):
    reset_quota_if_needed(settings)
    if not can_consume(settings, Config.YT_REFRESH_COST):
        return
    result = refresh_user_channels(user, settings, service, now=datetime.utcnow())
    if result.get("rate_limited"):
        mark_quota_exhausted(settings)
    settings.last_schedule_run_at = datetime.utcnow()


def scheduler_tick():
    """Run one scheduler tick for all users."""
    if not Config.SCHEDULER_ENABLED:
        return

    api_key = Config.YT_API_KEY
    service = YTService(api_key)
    now = datetime.utcnow()

    for user in User.query.all():
        settings = _get_or_create_settings(user)

        if settings.backfill_active:
            if _backfill_due(settings, now):
                run_backfill_step(user, settings, service)
            continue

        if _hours_due(settings, now):
            _run_scheduled_refresh(user, settings, service)

    db.session.commit()


def start_scheduler(app):
    """Start background scheduler thread."""
    if not Config.SCHEDULER_ENABLED:
        logger.info("Scheduler disabled.", extra={"tracking_id": "SYSTEM"})
        return

    def _loop():
        with app.app_context():
            while True:
                try:
                    scheduler_tick()
                except Exception as error:
                    logger.exception("Scheduler tick failed: %s", error)
                time.sleep(Config.SCHEDULER_INTERVAL_SECONDS)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    logger.info("Scheduler started.", extra={"tracking_id": "SYSTEM"})
