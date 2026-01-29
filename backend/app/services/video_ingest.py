"""Video ingestion and refresh logic with caps."""

from datetime import datetime, timedelta

from sqlalchemy import or_

from app.config import Config
from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.models import UserChannel, Video
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


def refresh_user_channels(user, settings, service, channel_id=None, ignore_last_refreshed=False, now=None):
    """Refresh videos for a user with per-channel caps."""
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

    if not subscriptions:
        return {"new_videos": 0, "rate_limited": False}

    new_videos = 0
    rate_limited = False

    reset_quota_if_needed(settings)

    for subscription in subscriptions:
        channel = subscription.channel

        if not consume(settings, Config.YT_REFRESH_COST):
            break

        response = service.get_channel_videos(channel.yt_channel_id)
        if response.get("rate_limited"):
            mark_quota_exhausted(settings)
            rate_limited = True
            break
        if not response.get("success", True):
            logger.warning(
                "Channel refresh failed.",
                extra={"tracking_id": generate_tracking_id(), "channel_id": channel.id},
            )
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

            if not ignore_last_refreshed and subscription.last_refreshed_at:
                if published_at <= subscription.last_refreshed_at:
                    continue

            exists = Video.query.filter_by(yt_video_id=video_id).first()
            if exists:
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
                thumbnail_url=item.get("thumbnail"),
                published_at=published_at,
                duration=item.get("duration"),
            )
            db.session.add(video)
            new_videos += 1

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
    return {"new_videos": new_videos, "rate_limited": rate_limited}
