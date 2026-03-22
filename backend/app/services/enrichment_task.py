"""Background enrichment task for channel classification."""

import json
import threading
import time

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.models import Channel, ChannelCategory, UserChannel, UserSettings
from app.services import ClassificationService
from app.services.video_ingest import upsert_channel_video_evidence
from app.services.yt_api import YTService
from app.utils.time import utc_now

logger = get_logger(__name__)

ENRICH_TOPIC_BATCH_SIZE = 50
ENRICH_VIDEO_BATCH_SIZE = 25
ENRICH_VIDEO_MAX_RESULTS = 12
ENRICH_STEP_DELAY_SECONDS = 5

_active_enrichments = {}
_enrichment_lock = threading.Lock()


def enrich_status_dict(settings):
    """Build a status dict from settings enrich fields."""
    phase = settings.enrich_phase
    mode = "full" if phase and phase.startswith("full_") else "basic"
    return {
        "active": settings.enrich_active or False,
        "phase": phase,
        "mode": mode,
        "cursor": settings.enrich_cursor or 0,
        "total": settings.enrich_total or 0,
        "classified": settings.enrich_classified or 0,
        "errors": settings.enrich_errors or 0,
        "started_at": (
            settings.enrich_started_at.isoformat() if settings.enrich_started_at else None
        ),
    }


def start_enrich_task(app, user, settings, mode="basic"):
    """Initialize enrich fields and launch a daemon thread.

    Returns a status dict on success.  Raises ValueError if already running.
    """
    with _enrichment_lock:
        existing = _active_enrichments.get(user.id)
        if existing and existing.is_alive():
            raise ValueError("already_running")

    # Count channels needing work
    if mode == "full":
        evidence_count = _count_channels_needing_classification(user.id)
        reclassify_count = _count_all_user_channels(user.id)
        total = evidence_count + reclassify_count
        initial_phase = "full_video_evidence"
    else:
        topic_count = _count_channels_needing_topics(user.id)
        unclassified_count = _count_channels_needing_classification(user.id)
        total = max(topic_count, unclassified_count)
        initial_phase = "topic_ids"

    if total == 0:
        return None

    now = utc_now()
    settings.enrich_active = True
    settings.enrich_phase = initial_phase
    settings.enrich_cursor = 0
    settings.enrich_total = total
    settings.enrich_classified = 0
    settings.enrich_errors = 0
    settings.enrich_started_at = now
    db.session.commit()

    thread = threading.Thread(
        target=_enrich_loop,
        args=(app, user.id, settings.id),
        daemon=True,
        name=f"enrich-user-{user.id}",
    )

    with _enrichment_lock:
        _active_enrichments[user.id] = thread

    thread.start()
    logger.info(
        "Enrich task started for user %s (%s channels)",
        user.id,
        total,
        extra={"tracking_id": generate_tracking_id()},
    )

    return enrich_status_dict(settings)


def _finish_task(settings):
    """Mark the enrichment task as finished."""
    settings.enrich_active = False
    settings.enrich_phase = None
    db.session.commit()


def _enrich_loop(app, user_id, settings_id):
    """Main loop executed inside the daemon thread."""
    with app.app_context():
        try:
            api_key = app.config.get("YT_API_KEY")
            service = YTService(api_key)
            classifier = ClassificationService()
            # Track channel IDs already attempted to avoid re-processing
            # channels that the classifier cannot classify.
            attempted_ids = set()

            while True:
                settings = db.session.get(UserSettings, settings_id)
                if not settings or not settings.enrich_active:
                    break

                # Hard stop: cursor reached total — all channels processed
                if (settings.enrich_cursor or 0) >= (settings.enrich_total or 0):
                    _finish_task(settings)
                    break

                phase = settings.enrich_phase

                if phase == "topic_ids":
                    has_more = _run_topic_ids_step(
                        user_id, settings, service, classifier, attempted_ids
                    )
                    if not has_more:
                        # Transition to video_evidence phase
                        remaining = _count_channels_needing_classification(
                            user_id, exclude_ids=attempted_ids
                        )
                        if remaining > 0:
                            settings.enrich_phase = "video_evidence"
                            db.session.commit()
                        else:
                            _finish_task(settings)
                            break
                elif phase == "video_evidence":
                    has_more = _run_video_evidence_step(
                        user_id, settings, service, classifier, attempted_ids
                    )
                    if not has_more:
                        _finish_task(settings)
                        break
                elif phase == "full_video_evidence":
                    has_more = _run_full_video_evidence_step(
                        user_id, settings, service, attempted_ids
                    )
                    if not has_more:
                        settings.enrich_phase = "full_reclassify"
                        db.session.commit()
                elif phase == "full_reclassify":
                    has_more = _run_full_reclassify_step(
                        user_id, settings, classifier, attempted_ids
                    )
                    if not has_more:
                        _finish_task(settings)
                        break
                else:
                    _finish_task(settings)
                    break

                time.sleep(ENRICH_STEP_DELAY_SECONDS)

        except Exception as exc:
            logger.error(
                "Enrich loop crashed for user %s: %s",
                user_id,
                exc,
                extra={"tracking_id": generate_tracking_id()},
            )
            try:
                settings = db.session.get(UserSettings, settings_id)
                if settings:
                    _finish_task(settings)
            except Exception:
                pass
        finally:
            with _enrichment_lock:
                _active_enrichments.pop(user_id, None)
            logger.info(
                "Enrich task finished for user %s",
                user_id,
                extra={"tracking_id": generate_tracking_id()},
            )


def _run_topic_ids_step(user_id, settings, service, classifier, attempted_ids):
    """Enrich a batch of channels with topic_ids. Returns True if more work remains."""
    channels = _channels_needing_topics(
        user_id, limit=ENRICH_TOPIC_BATCH_SIZE, exclude_ids=attempted_ids
    )
    if not channels:
        return False

    for channel in channels:
        attempted_ids.add(channel.id)
        try:
            info = service.get_channel_info(channel.yt_channel_id)
            if info:
                if info.get("topic_ids"):
                    channel.topic_ids = json.dumps(info["topic_ids"])
                if info.get("keywords") and not channel.keywords:
                    channel.keywords = info["keywords"]
                if info.get("country") and not channel.country:
                    channel.country = info["country"]

                # Try to classify immediately after enrichment
                if not ChannelCategory.query.filter_by(channel_id=channel.id).first():
                    if classifier.classify_channel(channel):
                        settings.enrich_classified = (settings.enrich_classified or 0) + 1
        except Exception as exc:
            logger.warning(
                "Failed to enrich channel %s: %s",
                channel.yt_channel_id,
                exc,
                extra={"tracking_id": generate_tracking_id()},
            )
            settings.enrich_errors = (settings.enrich_errors or 0) + 1

    settings.enrich_cursor = min(
        (settings.enrich_cursor or 0) + len(channels),
        settings.enrich_total or 0,
    )
    db.session.commit()

    remaining = _count_channels_needing_topics(user_id, exclude_ids=attempted_ids)
    return remaining > 0


def _run_video_evidence_step(user_id, settings, service, classifier, attempted_ids):
    """Enrich a batch with video evidence. Returns True if more work remains."""
    channels = _channels_needing_classification(
        user_id, limit=ENRICH_VIDEO_BATCH_SIZE, exclude_ids=attempted_ids
    )
    if not channels:
        return False

    for channel in channels:
        attempted_ids.add(channel.id)
        try:
            response = service.get_channel_videos(
                channel.yt_channel_id, max_results=ENRICH_VIDEO_MAX_RESULTS
            )
            if response.get("success", True):
                upsert_channel_video_evidence(channel, response.get("videos", []))

                if not ChannelCategory.query.filter_by(channel_id=channel.id).first():
                    if classifier.classify_channel(channel):
                        settings.enrich_classified = (settings.enrich_classified or 0) + 1
        except Exception as exc:
            logger.warning(
                "Failed video evidence for channel %s: %s",
                channel.yt_channel_id,
                exc,
                extra={"tracking_id": generate_tracking_id()},
            )
            db.session.rollback()
            settings.enrich_errors = (settings.enrich_errors or 0) + 1

    settings.enrich_cursor = min(
        (settings.enrich_cursor or 0) + len(channels),
        settings.enrich_total or 0,
    )
    db.session.commit()

    remaining = _count_channels_needing_classification(
        user_id, exclude_ids=attempted_ids
    )
    return remaining > 0


def _run_full_video_evidence_step(user_id, settings, service, attempted_ids):
    """Enrich unclassified channels with recent video evidence before a full reclassification."""
    channels = _channels_needing_classification(
        user_id, limit=ENRICH_VIDEO_BATCH_SIZE, exclude_ids=attempted_ids
    )
    if not channels:
        return False

    for channel in channels:
        attempted_ids.add(channel.id)
        try:
            response = service.get_channel_videos(
                channel.yt_channel_id, max_results=ENRICH_VIDEO_MAX_RESULTS
            )
            if response.get("success", True):
                upsert_channel_video_evidence(channel, response.get("videos", []))
        except Exception as exc:
            logger.warning(
                "Failed full video evidence for channel %s: %s",
                channel.yt_channel_id,
                exc,
                extra={"tracking_id": generate_tracking_id()},
            )
            db.session.rollback()
            settings.enrich_errors = (settings.enrich_errors or 0) + 1

    settings.enrich_cursor = min(
        (settings.enrich_cursor or 0) + len(channels),
        settings.enrich_total or 0,
    )
    db.session.commit()

    remaining = _count_channels_needing_classification(
        user_id, exclude_ids=attempted_ids
    )
    return remaining > 0


def _run_full_reclassify_step(user_id, settings, classifier, attempted_ids):
    """Reclassify all subscribed channels in batches."""
    channels = _all_user_channels(user_id, limit=ENRICH_VIDEO_BATCH_SIZE, exclude_ids=attempted_ids)
    if not channels:
        return False

    for channel in channels:
        attempted_ids.add(channel.id)
        try:
            result = classifier.reclassify_channel(channel)
            if result:
                settings.enrich_classified = (settings.enrich_classified or 0) + 1
        except Exception as exc:
            logger.warning(
                "Failed full reclassification for channel %s: %s",
                channel.yt_channel_id,
                exc,
                extra={"tracking_id": generate_tracking_id()},
            )
            db.session.rollback()
            settings.enrich_errors = (settings.enrich_errors or 0) + 1

    settings.enrich_cursor = min(
        (settings.enrich_cursor or 0) + len(channels),
        settings.enrich_total or 0,
    )
    db.session.commit()

    remaining = _count_all_user_channels(user_id, exclude_ids=attempted_ids)
    return remaining > 0


def _count_channels_needing_topics(user_id, exclude_ids=None):
    """Count subscribed channels without topic_ids."""
    query = (
        UserChannel.query.filter_by(user_id=user_id)
        .join(Channel)
        .filter((Channel.topic_ids.is_(None)) | (Channel.topic_ids == ""))
    )
    if exclude_ids:
        query = query.filter(Channel.id.notin_(exclude_ids))
    return query.count()


def _count_channels_needing_classification(user_id, exclude_ids=None):
    """Count subscribed channels without a category assignment."""
    query = (
        UserChannel.query.filter_by(user_id=user_id)
        .outerjoin(ChannelCategory, ChannelCategory.channel_id == UserChannel.channel_id)
        .filter(ChannelCategory.id.is_(None))
    )
    if exclude_ids:
        query = query.filter(UserChannel.channel_id.notin_(exclude_ids))
    return query.count()


def _count_all_user_channels(user_id, exclude_ids=None):
    """Count all subscribed channels for a user."""
    query = UserChannel.query.filter_by(user_id=user_id)
    if exclude_ids:
        query = query.filter(UserChannel.channel_id.notin_(exclude_ids))
    return query.count()


def _channels_needing_topics(user_id, limit=50, exclude_ids=None):
    """Return subscribed channels without topic_ids."""
    query = (
        UserChannel.query.filter_by(user_id=user_id)
        .join(Channel)
        .filter((Channel.topic_ids.is_(None)) | (Channel.topic_ids == ""))
    )
    if exclude_ids:
        query = query.filter(Channel.id.notin_(exclude_ids))
    subs = query.limit(limit).all()
    return [sub.channel for sub in subs]


def _channels_needing_classification(user_id, limit=25, exclude_ids=None):
    """Return subscribed channels without a category."""
    query = (
        UserChannel.query.filter_by(user_id=user_id)
        .outerjoin(ChannelCategory, ChannelCategory.channel_id == UserChannel.channel_id)
        .filter(ChannelCategory.id.is_(None))
    )
    if exclude_ids:
        query = query.filter(UserChannel.channel_id.notin_(exclude_ids))
    subs = query.limit(limit).all()
    return [sub.channel for sub in subs]


def _all_user_channels(user_id, limit=25, exclude_ids=None):
    """Return subscribed channels for a user."""
    query = UserChannel.query.filter_by(user_id=user_id)
    if exclude_ids:
        query = query.filter(UserChannel.channel_id.notin_(exclude_ids))
    subs = query.limit(limit).all()
    return [sub.channel for sub in subs]
