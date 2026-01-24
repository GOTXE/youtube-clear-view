"""Video management routes."""

from flask import Blueprint, g, jsonify, request
from sqlalchemy import or_

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import require_auth
from app.middleware.error_handler import handle_route_errors
from app.models import Theme, ThemeChannel, UserChannel, Video, WatchedVideo

videos_bp = Blueprint("videos", __name__)
logger = get_logger(__name__)


def _bad_request(message):
    """Return a JSON bad request response with tracking ID."""
    tracking_id = generate_tracking_id()
    logger.warning(message, extra={"tracking_id": tracking_id})
    return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400


def _serialize_video(video, channel, watched):
    """Serialize video with channel data and watched flag."""
    return {
        "video": video.to_dict(),
        "channel": channel.to_dict() if channel else None,
        "watched": watched,
    }


def _paginate_videos(query, user_id, limit, offset):
    """Return paginated videos with watched flags."""
    items = query.offset(offset).limit(limit + 1).all()
    has_more = len(items) > limit
    videos = items[:limit]

    video_ids = [video.id for video in videos]
    watched_ids = set()
    if video_ids:
        watched_entries = (
            WatchedVideo.query.filter_by(user_id=user_id)
            .filter(WatchedVideo.video_id.in_(video_ids))
            .all()
        )
        watched_ids = {entry.video_id for entry in watched_entries}

    payload = []
    for video in videos:
        payload.append(_serialize_video(video, video.channel, video.id in watched_ids))

    next_offset = offset + limit if has_more else None
    return payload, has_more, next_offset


@videos_bp.get("/api/videos/latest")
@handle_route_errors
@require_auth
def latest_videos():
    """Return latest videos from all subscribed channels."""
    user = g.current_user
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return _bad_request("Invalid pagination values.")

    if limit <= 0 or offset < 0:
        return _bad_request("Invalid pagination values.")

    channel_ids = [
        sub.channel_id for sub in UserChannel.query.filter_by(user_id=user.id).all()
    ]
    if not channel_ids:
        return jsonify({"videos": [], "has_more": False, "next_offset": None})

    query = Video.query.filter(Video.channel_id.in_(channel_ids)).order_by(
        Video.published_at.desc()
    )
    payload, has_more, next_offset = _paginate_videos(query, user.id, limit, offset)
    return jsonify({"videos": payload, "has_more": has_more, "next_offset": next_offset})


@videos_bp.get("/api/videos/by-theme/<int:theme_id>")
@handle_route_errors
@require_auth
def videos_by_theme(theme_id):
    """Return videos for channels associated with a theme."""
    user = g.current_user
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return _bad_request("Invalid pagination values.")

    if limit <= 0 or offset < 0:
        return _bad_request("Invalid pagination values.")

    theme = Theme.query.filter_by(id=theme_id, user_id=user.id).first()
    if not theme:
        tracking_id = generate_tracking_id()
        logger.warning("Theme not found.", extra={"tracking_id": tracking_id})
        return (
            jsonify({"error": "Not found.", "tracking_id": tracking_id, "status": 404}),
            404,
        )

    channel_ids = [link.channel_id for link in ThemeChannel.query.filter_by(theme_id=theme_id).all()]
    if not channel_ids:
        return jsonify({"videos": [], "has_more": False, "next_offset": None})

    query = Video.query.filter(Video.channel_id.in_(channel_ids)).order_by(
        Video.published_at.desc()
    )
    payload, has_more, next_offset = _paginate_videos(query, user.id, limit, offset)
    return jsonify({"videos": payload, "has_more": has_more, "next_offset": next_offset})


@videos_bp.post("/api/videos/<int:video_id>/watch")
@handle_route_errors
@require_auth
def mark_watched(video_id):
    """Mark a video as watched for the current user."""
    user = g.current_user
    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id")

    video = db.session.get(Video, video_id)
    if not video:
        tracking_id = generate_tracking_id()
        logger.warning("Video not found.", extra={"tracking_id": tracking_id})
        return (
            jsonify({"error": "Not found.", "tracking_id": tracking_id, "status": 404}),
            404,
        )

    watched = WatchedVideo.query.filter_by(user_id=user.id, video_id=video.id).first()
    if not watched:
        watched = WatchedVideo(user_id=user.id, video_id=video.id, device_id=device_id)
        db.session.add(watched)
        db.session.commit()

    return "", 204


@videos_bp.delete("/api/videos/<int:video_id>/unwatch")
@handle_route_errors
@require_auth
def unwatch_video(video_id):
    """Remove watched status for a video and user."""
    user = g.current_user
    watched = WatchedVideo.query.filter_by(user_id=user.id, video_id=video_id).first()
    if watched:
        db.session.delete(watched)
        db.session.commit()
    return "", 204


@videos_bp.get("/api/videos/search")
@handle_route_errors
@require_auth
def search_videos():
    """Search videos in the local database with optional filters."""
    user = g.current_user
    query_text = (request.args.get("q") or "").strip()
    if not query_text:
        return _bad_request("Missing query text.")

    try:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return _bad_request("Invalid pagination values.")

    if limit <= 0 or offset < 0:
        return _bad_request("Invalid pagination values.")

    channel_id = request.args.get("channel_id")
    theme_id = request.args.get("theme_id")

    subscribed_ids = [
        sub.channel_id for sub in UserChannel.query.filter_by(user_id=user.id).all()
    ]
    if not subscribed_ids:
        return jsonify({"videos": [], "has_more": False, "next_offset": None})

    query = Video.query.filter(Video.channel_id.in_(subscribed_ids))

    if channel_id:
        try:
            channel_id = int(channel_id)
        except ValueError:
            return _bad_request("Invalid channel_id.")
        if channel_id not in subscribed_ids:
            return jsonify({"videos": [], "has_more": False, "next_offset": None})
        query = query.filter(Video.channel_id == channel_id)

    if theme_id:
        try:
            theme_id = int(theme_id)
        except ValueError:
            return _bad_request("Invalid theme_id.")
        theme = Theme.query.filter_by(id=theme_id, user_id=user.id).first()
        if not theme:
            tracking_id = generate_tracking_id()
            logger.warning("Theme not found.", extra={"tracking_id": tracking_id})
            return (
                jsonify({"error": "Not found.", "tracking_id": tracking_id, "status": 404}),
                404,
            )
        theme_channel_ids = [
            link.channel_id for link in ThemeChannel.query.filter_by(theme_id=theme_id).all()
        ]
        if theme_channel_ids:
            query = query.filter(Video.channel_id.in_(theme_channel_ids))
        else:
            return jsonify({"videos": [], "has_more": False, "next_offset": None})

    query = query.filter(
        or_(
            Video.title.ilike(f"%{query_text}%"),
            Video.description.ilike(f"%{query_text}%"),
        )
    ).order_by(Video.published_at.desc())

    payload, has_more, next_offset = _paginate_videos(query, user.id, limit, offset)
    return jsonify({"videos": payload, "has_more": has_more, "next_offset": next_offset})
