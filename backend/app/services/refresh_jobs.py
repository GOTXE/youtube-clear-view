"""Backend-owned refresh job helpers."""

import threading

from flask import current_app

from app.config import Config
from app.extensions import db
from app.logging.logger import get_logger
from app.models import RefreshJob, User, UserSettings
from app.services.presets import DEFAULT_PRESET
from app.services.refresh_governance import acquire_manual_refresh
from app.services.video_ingest import iter_refresh_user_channels
from app.services.yt_api import YTService
from app.utils.time import utc_now


KIND_MANUAL = "manual"
KIND_SCHEDULED = "scheduled"

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_BLOCKED = "blocked"

logger = get_logger(__name__)


def create_refresh_job(user_id, kind=KIND_MANUAL, channel_id=None, message=None):
    """Create and persist a refresh job record."""
    job = RefreshJob(
        user_id=user_id,
        kind=kind,
        scope_type="channel" if channel_id else "all_channels",
        scope_channel_id=channel_id,
        status=STATUS_QUEUED,
        message=message,
    )
    db.session.add(job)
    db.session.commit()
    return job


def mark_job_running(job, total_channels=0, message=None):
    """Mark a queued job as running."""
    job.status = STATUS_RUNNING
    job.total_channels = int(total_channels or 0)
    job.started_at = utc_now()
    if message is not None:
        job.message = message
    db.session.commit()
    return job


def update_job_progress(job, processed_channels=None, new_videos=None, message=None):
    """Update incremental job progress."""
    if processed_channels is not None:
        job.processed_channels = int(processed_channels)
    if new_videos is not None:
        job.new_videos = int(new_videos)
    if message is not None:
        job.message = message
    db.session.commit()
    return job


def mark_job_completed(job, new_videos=0, processed_channels=None, rate_limited=False, message=None):
    """Mark a refresh job as completed."""
    job.status = STATUS_COMPLETED
    job.new_videos = int(new_videos or 0)
    if processed_channels is not None:
        job.processed_channels = int(processed_channels)
    job.rate_limited = bool(rate_limited)
    job.message = message
    job.finished_at = utc_now()
    db.session.commit()
    return job


def mark_job_blocked(job, reason, message=None, processed_channels=None):
    """Mark a refresh job as blocked."""
    job.status = STATUS_BLOCKED
    job.blocked_reason = reason
    if processed_channels is not None:
        job.processed_channels = int(processed_channels)
    job.message = message
    job.finished_at = utc_now()
    db.session.commit()
    return job


def mark_job_failed(job, message=None):
    """Mark a refresh job as failed."""
    job.status = STATUS_FAILED
    job.message = message
    job.finished_at = utc_now()
    db.session.commit()
    return job


def get_latest_refresh_job(user_id, kind=None):
    """Return the latest refresh job for a user."""
    query = RefreshJob.query.filter_by(user_id=user_id)
    if kind:
        query = query.filter_by(kind=kind)
    return query.order_by(RefreshJob.created_at.desc(), RefreshJob.id.desc()).first()


def get_active_refresh_job(user_id, kind=None):
    """Return the latest queued/running refresh job for a user."""
    query = RefreshJob.query.filter(
        RefreshJob.user_id == user_id,
        RefreshJob.status.in_((STATUS_QUEUED, STATUS_RUNNING)),
    )
    if kind:
        query = query.filter(RefreshJob.kind == kind)
    return query.order_by(RefreshJob.created_at.desc(), RefreshJob.id.desc()).first()


def get_active_global_refresh_job():
    """Return the latest queued/running scheduled refresh job across all users."""
    return (
        RefreshJob.query.filter(
            RefreshJob.kind == KIND_SCHEDULED,
            RefreshJob.status.in_((STATUS_QUEUED, STATUS_RUNNING)),
        )
        .order_by(RefreshJob.created_at.desc(), RefreshJob.id.desc())
        .first()
    )


def is_global_refresh_running():
    """Return whether a scheduled refresh job is currently active."""
    return get_active_global_refresh_job() is not None


def _get_or_create_settings_for_user(user_id):
    settings = UserSettings.query.filter_by(user_id=user_id).first()
    if settings:
        return settings
    settings = UserSettings(user_id=user_id, preset=DEFAULT_PRESET)
    db.session.add(settings)
    db.session.commit()
    return settings


def _execute_job(app, job_id, user_id, kind, channel_id=None, ignore_last_refreshed=False):
    with app.app_context():
        job = db.session.get(RefreshJob, job_id)
        user = db.session.get(User, user_id)
        if not job or not user:
            logger.warning(
                "Refresh job bootstrap aborted: job or user missing (job_id=%s, user_id=%s, kind=%s)",
                job_id,
                user_id,
                kind,
            )
            return

        settings = _get_or_create_settings_for_user(user_id)
        service = YTService(Config.YT_API_KEY)

        from app.models import UserChannel  # local import to avoid circulars
        if channel_id:
            total_channels = UserChannel.query.filter_by(user_id=user_id, channel_id=channel_id).count()
        else:
            total_channels = UserChannel.query.filter_by(user_id=user_id).count()

        mark_job_running(job, total_channels=total_channels, message="running")
        logger.info(
            "Refresh job accepted (job_id=%s, user_id=%s, kind=%s, channel_id=%s, total_channels=%s)",
            job.id,
            user_id,
            kind,
            channel_id,
            total_channels,
        )
        try:
            if kind == KIND_MANUAL:
                with acquire_manual_refresh(user_id, channel_id=channel_id, now=utc_now()) as lease:
                    if not lease.get("acquired"):
                        logger.info(
                            "Refresh job blocked by governance (job_id=%s, user_id=%s, reason=%s)",
                            job.id,
                            user_id,
                            lease.get("reason") or "refresh_in_progress",
                        )
                        mark_job_blocked(job, lease.get("reason") or "refresh_in_progress", message="blocked")
                        return
                    _consume_events(job, user, settings, service, channel_id, ignore_last_refreshed)
                return

            _consume_events(job, user, settings, service, channel_id, ignore_last_refreshed)
        except Exception:
            db.session.rollback()
            logger.exception(
                "Refresh job crashed unexpectedly (job_id=%s, user_id=%s, kind=%s, channel_id=%s)",
                job_id,
                user_id,
                kind,
                channel_id,
            )
            failed_job = db.session.get(RefreshJob, job_id)
            if failed_job is not None and failed_job.status not in (STATUS_COMPLETED, STATUS_BLOCKED, STATUS_FAILED):
                mark_job_failed(failed_job, message="Refresh failed due to an internal error")


def _consume_events(job, user, settings, service, channel_id, ignore_last_refreshed):
    for event in iter_refresh_user_channels(
        user,
        settings,
        service,
        channel_id=channel_id,
        ignore_last_refreshed=ignore_last_refreshed,
        now=utc_now(),
    ):
        event_type = event.get("type")
        if event_type == "start":
            mark_job_running(
                job,
                total_channels=event.get("total_channels", 0),
                message="Actualizando canales y videos desde YouTube",
            )
        elif event_type == "channel_complete":
            update_job_progress(
                job,
                processed_channels=event.get("processed_channels", 0),
                new_videos=event.get("new_videos", 0),
                message="Actualizando canales y videos desde YouTube",
            )
        elif event_type == "complete":
            if event.get("blocked"):
                logger.info(
                    "Refresh job blocked during execution (job_id=%s, user_id=%s, reason=%s)",
                    job.id,
                    user.id,
                    event.get("reason") or "blocked",
                )
                mark_job_blocked(
                    job,
                    event.get("reason") or "blocked",
                    message="Imposible ejecutar, prioridad update programado"
                    if event.get("reason") == "scheduled_priority"
                    else "La cuota de YouTube esta agotada. Los updates quedan en pausa hasta el siguiente reinicio oficial."
                    if event.get("reason") == "quota_exhausted"
                    else "blocked",
                    processed_channels=event.get("processed_channels", 0),
                )
            else:
                logger.info(
                    "Refresh job completed (job_id=%s, user_id=%s, processed=%s/%s, new_videos=%s, rate_limited=%s)",
                    job.id,
                    user.id,
                    event.get("processed_channels", 0),
                    job.total_channels,
                    event.get("new_videos", 0),
                    event.get("rate_limited", False),
                )
                mark_job_completed(
                    job,
                    new_videos=event.get("new_videos", 0),
                    processed_channels=event.get("processed_channels", 0),
                    rate_limited=event.get("rate_limited", False),
                    message=f"Actualizacion completada: {event.get('new_videos', 0)} videos nuevos",
                )


def start_refresh_job(user_id, kind=KIND_MANUAL, channel_id=None, ignore_last_refreshed=False):
    """Create and launch a refresh job in a background thread."""
    app = current_app._get_current_object()
    job = create_refresh_job(user_id, kind=kind, channel_id=channel_id, message="queued")
    logger.info(
        "Refresh job queued (job_id=%s, user_id=%s, kind=%s, channel_id=%s, backfill=%s)",
        job.id,
        user_id,
        kind,
        channel_id,
        ignore_last_refreshed,
    )
    thread = threading.Thread(
        target=_execute_job,
        args=(app, job.id, user_id, kind, channel_id, ignore_last_refreshed),
        daemon=True,
    )
    thread.start()
    return job


def recover_interrupted_refresh_jobs():
    """Mark queued/running jobs as failed after an application restart."""
    stale_jobs = (
        RefreshJob.query.filter(RefreshJob.status.in_((STATUS_QUEUED, STATUS_RUNNING)))
        .order_by(RefreshJob.created_at.asc(), RefreshJob.id.asc())
        .all()
    )
    recovered = 0
    for job in stale_jobs:
        job.status = STATUS_FAILED
        job.message = "Refresh interrumpido por reinicio del backend"
        job.finished_at = utc_now()
        recovered += 1
    if recovered:
        db.session.commit()
        logger.warning(
            "Recovered interrupted refresh jobs after startup (count=%s)",
            recovered,
            extra={"tracking_id": "SYSTEM"},
        )
    return recovered
