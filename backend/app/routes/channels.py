"""Channel management routes."""

from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import func

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import require_auth
from app.middleware.error_handler import handle_route_errors
from app.models import Channel, UserChannel, Video, WatchedVideo
from app.services.google_oauth import ensure_access_token
from app.services.yt_api import YTService
from app.services.yt_oauth import fetch_subscriptions_page

channels_bp = Blueprint("channels", __name__)
logger = get_logger(__name__)


def _parse_datetime(value):
    """Parse ISO timestamps into datetime objects."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None)
    except ValueError:
        return None


def _get_service():
    """Create a YT service instance using app config."""
    return YTService(current_app.config.get("YT_API_KEY"))


def _bad_request(message):
    """Return a JSON bad request response with tracking ID."""
    tracking_id = generate_tracking_id()
    logger.warning(message, extra={"tracking_id": tracking_id})
    return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400


def _not_found(message):
    """Return a JSON not found response with tracking ID."""
    tracking_id = generate_tracking_id()
    logger.warning(message, extra={"tracking_id": tracking_id})
    return jsonify({"error": "Not found.", "tracking_id": tracking_id, "status": 404}), 404


def _unauthorized(message):
    """Return a JSON unauthorized response with tracking ID."""
    tracking_id = generate_tracking_id()
    logger.warning(message, extra={"tracking_id": tracking_id})
    return jsonify({"error": "Unauthorized.", "tracking_id": tracking_id, "status": 401}), 401


def _forbidden(message):
    """Return a JSON forbidden response with tracking ID."""
    tracking_id = generate_tracking_id()
    logger.warning(message, extra={"tracking_id": tracking_id})
    return jsonify({"error": "Forbidden.", "tracking_id": tracking_id, "status": 403}), 403


def _extract_thumbnail(thumbnails):
    """Pick the best thumbnail URL from YT thumbnail data."""
    if not thumbnails:
        return None
    for key in ("high", "medium", "default"):
        url = thumbnails.get(key, {}).get("url")
        if url:
            return url
    return None


@channels_bp.get("/api/channels")
@handle_route_errors
@require_auth
def list_channels():
    """Return the authenticated user's subscribed channels."""
    user = g.current_user
    subscriptions = UserChannel.query.filter_by(user_id=user.id).all()
    channel_ids = [subscription.channel_id for subscription in subscriptions]
    recent_total_7 = {}
    recent_total_30 = {}
    recent_unwatched_7 = {}
    recent_unwatched_30 = {}
    unwatched_total = {}
    latest_video_map = {}

    if channel_ids:
        cutoff_7 = datetime.utcnow() - timedelta(days=7)
        cutoff_30 = datetime.utcnow() - timedelta(days=30)

        latest_rows = (
            db.session.query(Video.channel_id, func.max(Video.published_at))
            .filter(Video.channel_id.in_(channel_ids), Video.published_at.isnot(None))
            .group_by(Video.channel_id)
            .all()
        )
        latest_video_map = {row[0]: row[1] for row in latest_rows}

        recent_total_7 = {
            row[0]: row[1]
            for row in (
                db.session.query(Video.channel_id, func.count(Video.id))
                .filter(
                    Video.channel_id.in_(channel_ids),
                    Video.published_at.isnot(None),
                    Video.published_at >= cutoff_7,
                )
                .group_by(Video.channel_id)
                .all()
            )
        }

        recent_total_30 = {
            row[0]: row[1]
            for row in (
                db.session.query(Video.channel_id, func.count(Video.id))
                .filter(
                    Video.channel_id.in_(channel_ids),
                    Video.published_at.isnot(None),
                    Video.published_at >= cutoff_30,
                )
                .group_by(Video.channel_id)
                .all()
            )
        }

        watched_subquery = (
            db.session.query(WatchedVideo.video_id)
            .filter_by(user_id=user.id)
            .subquery()
        )

        recent_unwatched_7 = {
            row[0]: row[1]
            for row in (
                db.session.query(Video.channel_id, func.count(Video.id))
                .filter(
                    Video.channel_id.in_(channel_ids),
                    Video.published_at.isnot(None),
                    Video.published_at >= cutoff_7,
                    ~Video.id.in_(watched_subquery),
                )
                .group_by(Video.channel_id)
                .all()
            )
        }

        recent_unwatched_30 = {
            row[0]: row[1]
            for row in (
                db.session.query(Video.channel_id, func.count(Video.id))
                .filter(
                    Video.channel_id.in_(channel_ids),
                    Video.published_at.isnot(None),
                    Video.published_at >= cutoff_30,
                    ~Video.id.in_(watched_subquery),
                )
                .group_by(Video.channel_id)
                .all()
            )
        }

        unwatched_total = {
            row[0]: row[1]
            for row in (
                db.session.query(Video.channel_id, func.count(Video.id))
                .filter(Video.channel_id.in_(channel_ids), ~Video.id.in_(watched_subquery))
                .group_by(Video.channel_id)
                .all()
            )
        }

    results = []
    for subscription in subscriptions:
        channel = subscription.channel
        data = channel.to_dict()
        data["latest_video_at"] = (
            latest_video_map.get(channel.id).isoformat()
            if latest_video_map.get(channel.id)
            else None
        )
        data["recent_total_7"] = int(recent_total_7.get(channel.id, 0))
        data["recent_total_30"] = int(recent_total_30.get(channel.id, 0))
        data["recent_unwatched_7"] = int(recent_unwatched_7.get(channel.id, 0))
        data["recent_unwatched_30"] = int(recent_unwatched_30.get(channel.id, 0))
        data["unwatched_total"] = int(unwatched_total.get(channel.id, 0))
        data["subscribed_at"] = (
            subscription.subscribed_at.isoformat() if subscription.subscribed_at else None
        )
        data["last_refreshed_at"] = (
            subscription.last_refreshed_at.isoformat()
            if subscription.last_refreshed_at
            else None
        )
        results.append(data)
    return jsonify(results)


@channels_bp.post("/api/channels/subscribe")
@handle_route_errors
@require_auth
def subscribe_channel():
    """Subscribe the current user to a YT channel."""
    user = g.current_user
    payload = request.get_json(silent=True) or {}
    yt_channel_id = (payload.get("yt_channel_id") or "").strip()
    if not yt_channel_id:
        return _bad_request("Missing yt_channel_id.")

    channel = Channel.query.filter_by(yt_channel_id=yt_channel_id).first()
    if not channel:
        service = _get_service()
        info = service.get_channel_info(yt_channel_id)
        if not info:
            return _not_found("Channel info not found.")
        channel = Channel(
            yt_channel_id=yt_channel_id,
            title=info.get("title"),
            description=info.get("description"),
            thumbnail_url=info.get("thumbnail"),
        )
        db.session.add(channel)
        db.session.flush()

    subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel.id).first()
    if not subscription:
        subscription = UserChannel(user_id=user.id, channel_id=channel.id)
        db.session.add(subscription)

    db.session.commit()

    data = channel.to_dict()
    data["subscribed_at"] = subscription.subscribed_at.isoformat() if subscription.subscribed_at else None
    return jsonify(data), 201


@channels_bp.delete("/api/channels/<int:channel_id>/unsubscribe")
@handle_route_errors
@require_auth
def unsubscribe_channel(channel_id):
    """Unsubscribe the current user from a channel."""
    user = g.current_user
    subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
    if not subscription:
        return _not_found("Subscription not found.")
    db.session.delete(subscription)
    db.session.commit()
    return "", 204


@channels_bp.post("/api/channels/refresh")
@handle_route_errors
@require_auth
def refresh_channels():
    """Refresh videos for one or all subscribed channels."""
    user = g.current_user
    payload = request.get_json(silent=True) or {}
    channel_id = payload.get("channel_id")

    if channel_id:
        subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
        if not subscription:
            return _not_found("Subscription not found.")
        subscriptions = [subscription]
    else:
        subscriptions = UserChannel.query.filter_by(user_id=user.id).all()

    service = _get_service()
    new_videos = 0
    refreshed_at = datetime.utcnow()
    for subscription in subscriptions:
        channel = subscription.channel
        response = service.get_channel_videos(channel.yt_channel_id)
        if not response.get("success", True):
            logger.warning(
                "Channel refresh failed.",
                extra={"tracking_id": generate_tracking_id(), "channel_id": channel.id},
            )
            continue

        latest_seen = subscription.last_refreshed_at
        for item in response.get("videos", []):
            video_id = item.get("video_id")
            if not video_id:
                continue
            published_at = _parse_datetime(item.get("published_at"))
            if subscription.last_refreshed_at and published_at:
                if published_at <= subscription.last_refreshed_at:
                    continue
            exists = Video.query.filter_by(yt_video_id=video_id).first()
            if exists:
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
            if published_at and (latest_seen is None or published_at > latest_seen):
                latest_seen = published_at

        if latest_seen:
            subscription.last_refreshed_at = latest_seen

    db.session.commit()
    return jsonify({"new_videos": new_videos, "refreshed_at": refreshed_at.isoformat()})


@channels_bp.post("/api/channels/import")
@handle_route_errors
@require_auth
def import_subscriptions():
    """Import YT subscriptions for the authenticated user."""
    user = g.current_user
    if user.auth_provider != "google":
        return _forbidden("Subscription import requires Google OAuth.")

    payload = request.get_json(silent=True) or {}
    page_token = payload.get("page_token")
    try:
        max_results = int(payload.get("max_results", 50))
    except (TypeError, ValueError):
        return _bad_request("Invalid max_results.")

    if max_results <= 0 or max_results > 50:
        return _bad_request("Invalid max_results.")

    access_token = ensure_access_token(user)
    if not access_token:
        return _unauthorized("Missing or expired Google OAuth credentials.")

    if db.session.is_modified(user):
        db.session.commit()

    items, error_status, page_info = fetch_subscriptions_page(
        access_token,
        page_token=page_token,
        max_results=max_results,
    )
    if items is None:
        if error_status in (401, 403):
            return _unauthorized("Google OAuth credentials rejected.")
        tracking_id = generate_tracking_id()
        logger.warning(
            "YT subscription import failed with status %s.",
            error_status,
            extra={"tracking_id": tracking_id},
        )
        return (
            jsonify({"error": "Upstream error.", "tracking_id": tracking_id, "status": 502}),
            502,
        )

    imported = 0
    new_channels = 0
    new_subscriptions = 0

    for item in items:
        snippet = item.get("snippet", {})
        resource = snippet.get("resourceId", {})
        yt_channel_id = resource.get("channelId")
        if not yt_channel_id:
            continue

        imported += 1
        channel = Channel.query.filter_by(yt_channel_id=yt_channel_id).first()
        if not channel:
            channel = Channel(
                yt_channel_id=yt_channel_id,
                title=snippet.get("title"),
                description=snippet.get("description"),
                thumbnail_url=_extract_thumbnail(snippet.get("thumbnails", {})),
            )
            db.session.add(channel)
            db.session.flush()
            new_channels += 1
        else:
            if not channel.title and snippet.get("title"):
                channel.title = snippet.get("title")
            if not channel.description and snippet.get("description"):
                channel.description = snippet.get("description")
            if not channel.thumbnail_url:
                channel.thumbnail_url = _extract_thumbnail(snippet.get("thumbnails", {}))

        subscription = UserChannel.query.filter_by(
            user_id=user.id,
            channel_id=channel.id,
        ).first()
        if not subscription:
            subscribed_at = _parse_datetime(snippet.get("publishedAt"))
            subscription = UserChannel(
                user_id=user.id,
                channel_id=channel.id,
                subscribed_at=subscribed_at or datetime.utcnow(),
            )
            db.session.add(subscription)
            new_subscriptions += 1

    db.session.commit()

    next_token = page_info.get("next_page_token") if page_info else None
    total_results = page_info.get("total_results") if page_info else None
    return jsonify(
        {
            "imported": imported,
            "new_channels": new_channels,
            "new_subscriptions": new_subscriptions,
            "next_page_token": next_token,
            "total_results": total_results,
            "finished": next_token is None,
        }
    )


@channels_bp.get("/api/channels/<int:channel_id>/videos")
@handle_route_errors
@require_auth
def get_channel_videos(channel_id):
    """Return videos for a specific channel with pagination."""
    user = g.current_user
    subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
    if not subscription:
        return _not_found("Subscription not found.")

    try:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return _bad_request("Invalid pagination values.")

    if limit <= 0 or offset < 0:
        return _bad_request("Invalid pagination values.")

    query = Video.query.filter_by(channel_id=channel_id).order_by(Video.published_at.desc())
    items = query.offset(offset).limit(limit + 1).all()
    has_more = len(items) > limit
    videos = items[:limit]

    video_ids = [video.id for video in videos]
    watched_ids = set()
    if video_ids:
        watched_entries = (
            WatchedVideo.query.filter_by(user_id=user.id)
            .filter(WatchedVideo.video_id.in_(video_ids))
            .all()
        )
        watched_ids = {entry.video_id for entry in watched_entries}

    payload = [
        {"video": video.to_dict(), "watched": video.id in watched_ids} for video in videos
    ]
    next_offset = offset + limit if has_more else None
    return jsonify({"videos": payload, "has_more": has_more, "next_offset": next_offset})
