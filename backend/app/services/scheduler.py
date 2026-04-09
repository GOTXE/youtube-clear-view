"""Background scheduler for auto refresh and backfill."""

import threading
import time
from datetime import timedelta
from zoneinfo import ZoneInfo

from flask import current_app
from sqlalchemy import func

from app.config import Config
from app.extensions import db
from app.logging.logger import get_logger
from app.models import ChannelCategory, User, UserSettings, UserChannel
from app.services.enrichment_task import start_enrich_task
from app.services.refresh_jobs import get_active_global_refresh_job, get_active_refresh_job, start_refresh_job
from app.services.presets import DEFAULT_PRESET
from app.services.quota import can_consume, consume, mark_quota_exhausted, reset_quota_if_needed
from app.services.site_settings import (
    get_refresh_schedule_hours,
    get_refresh_schedule_last_run_at,
    get_refresh_schedule_timezone,
    set_refresh_schedule_last_run_at,
)
from app.services.yt_api import YTService
from app.utils.time import utc_now

logger = get_logger(__name__)


def _get_or_create_settings(user):
    settings = UserSettings.query.filter_by(user_id=user.id).first()
    if settings:
        return settings
    settings = UserSettings(user_id=user.id, preset=DEFAULT_PRESET)
    db.session.add(settings)
    db.session.commit()
    return settings


def _hours_due(now_utc):
    tz = _scheduler_timezone()
    local_now = now_utc.astimezone(tz)
    hours = [hour for hour in get_refresh_schedule_hours() if hour is not None]
    if not hours:
        return False
    if local_now.hour not in hours:
        return False
    last_run_at = get_refresh_schedule_last_run_at()
    if last_run_at:
        last_local = last_run_at.astimezone(tz)
        if last_local.date() == local_now.date() and last_local.hour == local_now.hour:
            return False
    return True


def _scheduler_timezone():
    """Return the configured scheduler timezone."""
    try:
        return ZoneInfo(get_refresh_schedule_timezone() or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _auto_classify_day_key(now_utc):
    """Return the current local scheduler day key."""
    return now_utc.astimezone(_scheduler_timezone()).date().isoformat()


def _count_unclassified_channels(user_id):
    """Count subscribed channels without an assigned category."""
    return (
        UserChannel.query.filter_by(user_id=user_id)
        .outerjoin(ChannelCategory, ChannelCategory.channel_id == UserChannel.channel_id)
        .filter(ChannelCategory.id.is_(None))
        .with_entities(func.count(UserChannel.channel_id))
        .scalar()
        or 0
    )


def _auto_basic_classification_due(settings, now_utc):
    """Return whether an automatic basic classification attempt is due."""
    if not Config.AUTO_BASIC_CLASSIFICATION_ENABLED:
        return False
    if settings.enrich_active:
        return False

    day_key = _auto_classify_day_key(now_utc)
    attempts = settings.auto_classify_attempts or 0
    if settings.auto_classify_date != day_key:
        attempts = 0

    if attempts >= Config.AUTO_BASIC_CLASSIFICATION_MAX_RUNS_PER_DAY:
        return False

    last_attempt = settings.auto_classify_last_attempt_at
    if last_attempt:
        min_interval = timedelta(hours=Config.AUTO_BASIC_CLASSIFICATION_MIN_INTERVAL_HOURS)
        if now_utc - last_attempt < min_interval:
            return False

    return True


def _mark_auto_classification_attempt(settings, now_utc):
    """Persist a new automatic classification attempt for the current day."""
    day_key = _auto_classify_day_key(now_utc)
    if settings.auto_classify_date != day_key:
        settings.auto_classify_date = day_key
        settings.auto_classify_attempts = 0
    settings.auto_classify_attempts = (settings.auto_classify_attempts or 0) + 1
    settings.auto_classify_last_attempt_at = now_utc


def _maybe_run_auto_basic_classification(user, settings, now_utc):
    """Run automatic basic classification when the user still has unclassified channels."""
    if not _auto_basic_classification_due(settings, now_utc):
        return False
    if _count_unclassified_channels(user.id) <= 0:
        return False
    if get_active_global_refresh_job() or get_active_refresh_job(user.id):
        return False

    try:
        _mark_auto_classification_attempt(settings, now_utc)
        db.session.commit()
        status = start_enrich_task(current_app._get_current_object(), user, settings, mode="basic")
    except ValueError:
        return False

    if status is None:
        return False

    logger.info(
        "Automatic basic classification started for user %s",
        user.id,
        extra={"tracking_id": "SYSTEM"},
    )
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
    now = utc_now()

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
    start_refresh_job(user.id, kind="scheduled")
    settings.last_schedule_run_at = utc_now()


def scheduler_tick():
    """Run one scheduler tick for all users."""
    if not Config.SCHEDULER_ENABLED:
        return

    api_key = Config.YT_API_KEY
    now = utc_now()
    refresh_due = _hours_due(now)

    service = YTService(api_key)
    ran_any = False

    for user in User.query.filter(User.is_active.is_(True)).all():
        settings = _get_or_create_settings(user)

        if settings.backfill_active:
            if _backfill_due(settings, now):
                run_backfill_step(user, settings, service)
            continue

        if refresh_due:
            _run_scheduled_refresh(user, settings, service)
            ran_any = True

        _maybe_run_auto_basic_classification(user, settings, now)

    if refresh_due and ran_any:
        set_refresh_schedule_last_run_at(now)

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
