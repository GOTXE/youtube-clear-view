"""Video ingestion and refresh logic with caps."""

from datetime import datetime, timedelta

from sqlalchemy import or_

from app.config import Config
from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.models import ChannelCategory, UserChannel, Video
from app.services.classification_service import ClassificationService
from app.services.presets import get_preset
from app.services.quota import consume, mark_quota_exhausted, reset_quota_if_needed

logger = get_logger(__name__)


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _is_short(duration):
    if duration is None:
        return False
    try:
        return int(duration) <= 60
    except (TypeError, ValueError):
        return False


def _serialize_tags(value):
    if not value:
        return None
    if isinstance(value, list):
        cleaned = [str(tag).strip() for tag in value if str(tag).strip()]
        return " ".join(cleaned) if cleaned else None
    text = str(value).strip()
    return text or None


def _update_video_from_item(video, item, published_at):
    updated = False
    serialized_tags = _serialize_tags(item.get("tags"))

    if item.get("title") and item.get("title") != video.title:
        video.title = item.get("title")
        updated = True
    if item.get("description") and item.get("description") != video.description:
        video.description = item.get("description")
        updated = True
    if item.get("thumbnail") and item.get("thumbnail") != video.thumbnail_url:
        video.thumbnail_url = item.get("thumbnail")
        updated = True
    if published_at and published_at != video.published_at:
        video.published_at = published_at
        updated = True
    if item.get("duration") is not None and item.get("duration") != video.duration:
        video.duration = item.get("duration")
        updated = True
    if item.get("video_category_id") and item.get("video_category_id") != video.video_category_id:
        video.video_category_id = item.get("video_category_id")
        updated = True
    if serialized_tags and serialized_tags != video.tags:
        video.tags = serialized_tags
        updated = True

    return updated


def upsert_channel_video_evidence(channel, items):
    """Upsert local video evidence for a channel from YT API items."""
    created = 0
    updated = 0

    for item in items:
        video_id = item.get("video_id")
        if not video_id:
            continue

        published_at = _parse_datetime(item.get("published_at"))
        exists = Video.query.filter_by(yt_video_id=video_id).first()
        if exists:
            if _update_video_from_item(exists, item, published_at):
                updated += 1
            continue

        video = Video(
            yt_video_id=video_id,
            channel_id=channel.id,
            title=item.get("title"),
            description=item.get("description"),
            video_category_id=item.get("video_category_id"),
            tags=_serialize_tags(item.get("tags")),
            thumbnail_url=item.get("thumbnail"),
            published_at=published_at,
            duration=item.get("duration"),
        )
        db.session.add(video)
        created += 1

    return created, updated


def _range_counts(channel_id, start, end, is_short):
    query = Video.query.filter(Video.channel_id == channel_id)
    if start:
        query = query.filter(Video.published_at.isnot(None), Video.published_at >= start)
    if end:
        query = query.filter(Video.published_at.isnot(None), Video.published_at < end)
    if is_short:
        query = query.filter(Video.duration <= 60)
    else:
        query = query.filter(or_(Video.duration.is_(None), Video.duration > 60))
    return query.count()


def _prune_range(channel_id, start, end, is_short, cap):
    if cap <= 0:
        return
    query = Video.query.filter(Video.channel_id == channel_id)
    if start:
        query = query.filter(Video.published_at.isnot(None), Video.published_at >= start)
    if end:
        query = query.filter(Video.published_at.isnot(None), Video.published_at < end)
    if is_short:
        query = query.filter(Video.duration <= 60)
    else:
        query = query.filter(or_(Video.duration.is_(None), Video.duration > 60))

    items = query.order_by(Video.published_at.desc()).all()
    for video in items[cap:]:
        db.session.delete(video)


def _delete_older_than(channel_id, cutoff):
    if not cutoff:
        return
    old_items = (
        Video.query.filter(Video.channel_id == channel_id, Video.published_at.isnot(None))
        .filter(Video.published_at < cutoff)
        .all()
    )
    for video in old_items:
        db.session.delete(video)


def iter_refresh_user_channels(
    user,
    settings,
    service,
    channel_id=None,
    ignore_last_refreshed=False,
    now=None,
):
    """Yield incremental refresh progress for a user with per-channel caps."""
    now = now or datetime.utcnow()
    preset = get_preset(settings.preset)
    recent_days = preset["recent_days"]
    older_min_days = preset["older_min_days"]
    older_max_days = preset["older_max_days"]

    recent_cutoff = now - timedelta(days=recent_days)
    older_min_cutoff = now - timedelta(days=older_min_days)
    older_max_cutoff = now - timedelta(days=older_max_days)

    if channel_id:
        subscriptions = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).all()
    else:
        subscriptions = UserChannel.query.filter_by(user_id=user.id).all()

    total_channels = len(subscriptions)
    if not subscriptions:
        yield {
            "type": "complete",
            "new_videos": 0,
            "rate_limited": False,
            "processed_channels": 0,
            "total_channels": 0,
        }
        return

    new_videos = 0
    rate_limited = False
    processed_channels = 0
    classifier = None

    reset_quota_if_needed(settings)

    yield {
        "type": "start",
        "new_videos": 0,
        "rate_limited": False,
        "processed_channels": 0,
        "total_channels": total_channels,
    }

    for index, subscription in enumerate(subscriptions, start=1):
        channel = subscription.channel
        channel_new_videos = 0
        channel_metadata_updates = 0

        yield {
            "type": "channel_started",
            "channel_id": channel.id,
            "yt_channel_id": channel.yt_channel_id,
            "channel_title": channel.title,
            "processed_channels": processed_channels,
            "current_channel": index,
            "total_channels": total_channels,
            "new_videos": new_videos,
        }

        if not consume(settings, Config.YT_REFRESH_COST):
            db.session.commit()
            yield {
                "type": "complete",
                "new_videos": new_videos,
                "rate_limited": False,
                "processed_channels": processed_channels,
                "total_channels": total_channels,
                "blocked": True,
                "reason": "quota_cap_reached",
            }
            break

        response = service.get_channel_videos(channel.yt_channel_id)
        if response.get("rate_limited"):
            mark_quota_exhausted(settings)
            rate_limited = True
            db.session.commit()
            yield {
                "type": "complete",
                "new_videos": new_videos,
                "rate_limited": True,
                "processed_channels": processed_channels,
                "total_channels": total_channels,
                "blocked": True,
                "reason": "upstream_rate_limited",
            }
            break
        if not response.get("success", True):
            logger.warning(
                "Channel refresh failed.",
                extra={"tracking_id": generate_tracking_id(), "channel_id": channel.id},
            )
            subscription.last_checked_at = now
            db.session.commit()
            processed_channels += 1
            yield {
                "type": "channel_complete",
                "channel_id": channel.id,
                "yt_channel_id": channel.yt_channel_id,
                "channel_title": channel.title,
                "channel_new_videos": 0,
                "new_videos": new_videos,
                "processed_channels": processed_channels,
                "current_channel": index,
                "total_channels": total_channels,
                "success": False,
            }
            continue

        latest_seen = subscription.last_refreshed_at

        recent_video_count = _range_counts(channel.id, recent_cutoff, None, False)
        recent_short_count = _range_counts(channel.id, recent_cutoff, None, True)
        older_video_count = _range_counts(channel.id, older_max_cutoff, older_min_cutoff, False)
        older_short_count = _range_counts(channel.id, older_max_cutoff, older_min_cutoff, True)

        for item in response.get("videos", []):
            video_id = item.get("video_id")
            if not video_id:
                continue

            published_at = _parse_datetime(item.get("published_at"))
            if not published_at:
                continue

            if published_at < older_max_cutoff:
                continue

            exists = Video.query.filter_by(yt_video_id=video_id).first()
            if exists:
                if _update_video_from_item(exists, item, published_at):
                    channel_metadata_updates += 1
                continue

            if not ignore_last_refreshed and subscription.last_refreshed_at:
                if published_at <= subscription.last_refreshed_at:
                    continue

            is_short = _is_short(item.get("duration"))

            if published_at >= recent_cutoff:
                if is_short:
                    if recent_short_count >= preset["recent_short_cap"]:
                        continue
                    recent_short_count += 1
                else:
                    if recent_video_count >= preset["recent_video_cap"]:
                        continue
                    recent_video_count += 1
            elif published_at < older_min_cutoff and published_at >= older_max_cutoff:
                if is_short:
                    if older_short_count >= preset["older_short_cap"]:
                        continue
                    older_short_count += 1
                else:
                    if older_video_count >= preset["older_video_cap"]:
                        continue
                    older_video_count += 1
            else:
                continue

            video = Video(
                yt_video_id=video_id,
                channel_id=channel.id,
                title=item.get("title"),
                description=item.get("description"),
                video_category_id=item.get("video_category_id"),
                tags=_serialize_tags(item.get("tags")),
                thumbnail_url=item.get("thumbnail"),
                published_at=published_at,
                duration=item.get("duration"),
            )
            db.session.add(video)
            new_videos += 1
            channel_new_videos += 1

            if latest_seen is None or published_at > latest_seen:
                latest_seen = published_at

        if latest_seen:
            subscription.last_refreshed_at = latest_seen
        subscription.last_checked_at = now

        _delete_older_than(channel.id, older_max_cutoff)
        _prune_range(channel.id, recent_cutoff, None, False, preset["recent_video_cap"])
        _prune_range(channel.id, recent_cutoff, None, True, preset["recent_short_cap"])
        _prune_range(channel.id, older_max_cutoff, older_min_cutoff, False, preset["older_video_cap"])
        _prune_range(channel.id, older_max_cutoff, older_min_cutoff, True, preset["older_short_cap"])

        db.session.commit()

        if not ChannelCategory.query.filter_by(channel_id=channel.id).first():
            try:
                if classifier is None:
                    classifier = ClassificationService()
                classifier.classify_channel(channel)
            except Exception as error:
                logger.warning(
                    "Automatic channel classification after refresh failed: %s",
                    error,
                    extra={"tracking_id": generate_tracking_id(), "channel_id": channel.id},
                )

        processed_channels += 1
        yield {
            "type": "channel_complete",
            "channel_id": channel.id,
            "yt_channel_id": channel.yt_channel_id,
            "channel_title": channel.title,
            "channel_new_videos": channel_new_videos,
            "channel_metadata_updates": channel_metadata_updates,
            "new_videos": new_videos,
            "processed_channels": processed_channels,
            "current_channel": index,
            "total_channels": total_channels,
            "success": True,
        }
    else:
        yield {
            "type": "complete",
            "new_videos": new_videos,
            "rate_limited": rate_limited,
            "processed_channels": processed_channels,
            "total_channels": total_channels,
        }


def refresh_user_channels(user, settings, service, channel_id=None, ignore_last_refreshed=False, now=None):
    """Refresh videos for a user with per-channel caps."""
    summary = {
        "new_videos": 0,
        "rate_limited": False,
        "processed_channels": 0,
        "total_channels": 0,
    }
    for event in iter_refresh_user_channels(
        user,
        settings,
        service,
        channel_id=channel_id,
        ignore_last_refreshed=ignore_last_refreshed,
        now=now,
    ):
        if event.get("type") == "complete":
            summary.update(
                {
                    "new_videos": event.get("new_videos", 0),
                    "rate_limited": event.get("rate_limited", False),
                    "processed_channels": event.get("processed_channels", 0),
                    "total_channels": event.get("total_channels", 0),
                }
            )
    return summary
