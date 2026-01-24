"""Channel management routes."""

from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import require_auth
from app.middleware.error_handler import handle_route_errors
from app.models import Channel, UserChannel, Video, WatchedVideo
from app.services.youtube_api import YouTubeService

channels_bp = Blueprint("channels", __name__)
logger = get_logger(__name__)


def _parse_datetime(value):
    """Parse ISO timestamps into datetime objects."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _get_service():
    """Create a YouTube service instance using app config."""
    return YouTubeService(current_app.config.get("YOUTUBE_API_KEY"))


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


@channels_bp.get("/api/channels")
@handle_route_errors
@require_auth
def list_channels():
    """Return the authenticated user's subscribed channels."""
    user = g.current_user
    subscriptions = UserChannel.query.filter_by(user_id=user.id).all()
    results = []
    for subscription in subscriptions:
        channel = subscription.channel
        data = channel.to_dict()
        data["subscribed_at"] = (
            subscription.subscribed_at.isoformat() if subscription.subscribed_at else None
        )
        results.append(data)
    return jsonify(results)


@channels_bp.post("/api/channels/subscribe")
@handle_route_errors
@require_auth
def subscribe_channel():
    """Subscribe the current user to a YouTube channel."""
    user = g.current_user
    payload = request.get_json(silent=True) or {}
    youtube_channel_id = (payload.get("youtube_channel_id") or "").strip()
    if not youtube_channel_id:
        return _bad_request("Missing youtube_channel_id.")

    channel = Channel.query.filter_by(youtube_channel_id=youtube_channel_id).first()
    if not channel:
        service = _get_service()
        info = service.get_channel_info(youtube_channel_id)
        if not info:
            return _not_found("Channel info not found.")
        channel = Channel(
            youtube_channel_id=youtube_channel_id,
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
        channels = [subscription.channel]
    else:
        channels = [sub.channel for sub in UserChannel.query.filter_by(user_id=user.id).all()]

    service = _get_service()
    new_videos = 0
    for channel in channels:
        response = service.get_channel_videos(channel.youtube_channel_id)
        for item in response.get("videos", []):
            video_id = item.get("video_id")
            if not video_id:
                continue
            exists = Video.query.filter_by(youtube_video_id=video_id).first()
            if exists:
                continue
            video = Video(
                youtube_video_id=video_id,
                channel_id=channel.id,
                title=item.get("title"),
                description=item.get("description"),
                thumbnail_url=item.get("thumbnail"),
                published_at=_parse_datetime(item.get("published_at")),
                duration=item.get("duration"),
            )
            db.session.add(video)
            new_videos += 1

    db.session.commit()
    return jsonify({"new_videos": new_videos})


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
