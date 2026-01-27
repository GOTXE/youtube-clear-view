"""Category management routes."""

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import require_auth
from app.middleware.error_handler import handle_route_errors
from app.models import Category, Channel, ChannelCategory, UserChannel, Video, WatchedVideo
from app.services import ClassificationService

categories_bp = Blueprint("categories", __name__)
logger = get_logger(__name__)


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


@categories_bp.get("/api/categories")
@handle_route_errors
@require_auth
def list_categories():
    """Return all categories with channel counts for the current user."""
    user = g.current_user

    # Get user's subscribed channel IDs
    user_channel_ids = [
        uc.channel_id for uc in UserChannel.query.filter_by(user_id=user.id).all()
    ]

    categories = Category.query.order_by(Category.name).all()
    results = []

    for category in categories:
        # Count channels in this category that belong to user
        channel_count = 0
        if user_channel_ids:
            channel_count = (
                ChannelCategory.query.filter(
                    ChannelCategory.category_id == category.id,
                    ChannelCategory.channel_id.in_(user_channel_ids),
                ).count()
            )

        data = category.to_dict()
        data["channel_count"] = channel_count
        results.append(data)

    return jsonify(results)


@categories_bp.get("/api/categories/<int:category_id>")
@handle_route_errors
@require_auth
def get_category(category_id):
    """Return details for a specific category."""
    user = g.current_user
    category = Category.query.filter_by(id=category_id).first()
    if not category:
        return _not_found("Category not found.")

    # Get user's subscribed channel IDs
    user_channel_ids = [
        uc.channel_id for uc in UserChannel.query.filter_by(user_id=user.id).all()
    ]

    channel_count = 0
    if user_channel_ids:
        channel_count = (
            ChannelCategory.query.filter(
                ChannelCategory.category_id == category.id,
                ChannelCategory.channel_id.in_(user_channel_ids),
            ).count()
        )

    data = category.to_dict()
    data["channel_count"] = channel_count
    return jsonify(data)


@categories_bp.get("/api/categories/<int:category_id>/channels")
@handle_route_errors
@require_auth
def get_category_channels(category_id):
    """Return channels in a category for the current user."""
    user = g.current_user
    category = Category.query.filter_by(id=category_id).first()
    if not category:
        return _not_found("Category not found.")

    try:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return _bad_request("Invalid pagination values.")

    if limit <= 0 or offset < 0:
        return _bad_request("Invalid pagination values.")

    # Get user's subscribed channel IDs
    user_channel_ids = [
        uc.channel_id for uc in UserChannel.query.filter_by(user_id=user.id).all()
    ]

    if not user_channel_ids:
        return jsonify({"channels": [], "has_more": False, "next_offset": None})

    # Get channels in this category that user is subscribed to
    query = (
        db.session.query(Channel, ChannelCategory)
        .join(ChannelCategory, Channel.id == ChannelCategory.channel_id)
        .filter(
            ChannelCategory.category_id == category_id,
            Channel.id.in_(user_channel_ids),
        )
        .order_by(Channel.title)
    )

    items = query.offset(offset).limit(limit + 1).all()
    has_more = len(items) > limit
    items = items[:limit]

    channels = []
    for channel, channel_cat in items:
        data = channel.to_dict()
        data["category"] = channel_cat.to_dict()
        data["thumbnail_local_url"] = f"/api/channels/{channel.id}/thumbnail"
        channels.append(data)

    next_offset = offset + limit if has_more else None
    return jsonify({"channels": channels, "has_more": has_more, "next_offset": next_offset})


@categories_bp.get("/api/categories/<int:category_id>/videos")
@handle_route_errors
@require_auth
def get_category_videos(category_id):
    """Return recent videos from channels in a category."""
    user = g.current_user
    category = Category.query.filter_by(id=category_id).first()
    if not category:
        return _not_found("Category not found.")

    try:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return _bad_request("Invalid pagination values.")

    if limit <= 0 or offset < 0:
        return _bad_request("Invalid pagination values.")

    # Get user's subscribed channel IDs in this category
    user_subscriptions = UserChannel.query.filter_by(user_id=user.id).all()
    user_channel_ids = [uc.channel_id for uc in user_subscriptions]

    if not user_channel_ids:
        return jsonify({"videos": [], "has_more": False, "next_offset": None})

    # Get channel IDs in this category
    category_channel_ids = [
        cc.channel_id
        for cc in ChannelCategory.query.filter(
            ChannelCategory.category_id == category_id,
            ChannelCategory.channel_id.in_(user_channel_ids),
        ).all()
    ]

    if not category_channel_ids:
        return jsonify({"videos": [], "has_more": False, "next_offset": None})

    # Get videos from those channels
    query = (
        Video.query.filter(Video.channel_id.in_(category_channel_ids))
        .order_by(Video.published_at.desc())
    )

    items = query.offset(offset).limit(limit + 1).all()
    has_more = len(items) > limit
    videos = items[:limit]

    # Get watched video IDs for this user
    video_ids = [video.id for video in videos]
    watched_ids = set()
    if video_ids:
        watched_entries = (
            WatchedVideo.query.filter_by(user_id=user.id)
            .filter(WatchedVideo.video_id.in_(video_ids))
            .all()
        )
        watched_ids = {entry.video_id for entry in watched_entries}

    # Serialize videos in the same format as /api/videos/latest
    results = []
    for video in videos:
        channel = video.channel
        results.append({
            "video": video.to_dict(),
            "channel": channel.to_dict() if channel else None,
            "watched": video.id in watched_ids,
        })

    next_offset = offset + limit if has_more else None
    return jsonify({"videos": results, "has_more": has_more, "next_offset": next_offset})


@categories_bp.post("/api/categories/reclassify-all")
@handle_route_errors
@require_auth
def reclassify_all_channels():
    """Reclassify all channels for the current user."""
    user = g.current_user

    # Get all user's subscribed channels
    subscriptions = UserChannel.query.filter_by(user_id=user.id).all()
    channel_ids = [sub.channel_id for sub in subscriptions]

    if not channel_ids:
        return jsonify({
            "reclassified": 0,
            "total": 0,
            "message": "No channels to reclassify.",
        })

    channels = Channel.query.filter(Channel.id.in_(channel_ids)).all()

    service = ClassificationService()
    reclassified = 0
    errors = []

    for channel in channels:
        try:
            result = service.reclassify_channel(channel)
            if result:
                reclassified += 1
        except Exception as e:
            logger.warning(
                f"Failed to reclassify channel {channel.yt_channel_id}: {e}",
                extra={"tracking_id": generate_tracking_id()},
            )
            errors.append(channel.yt_channel_id)

    return jsonify({
        "reclassified": reclassified,
        "total": len(channels),
        "errors": errors if errors else None,
        "message": f"Reclassified {reclassified} of {len(channels)} channels.",
    })


@categories_bp.get("/api/categories/status")
@handle_route_errors
@require_auth
def get_classifier_status():
    """Return status of all classification methods."""
    service = ClassificationService()
    status = service.get_classifier_status()
    return jsonify(status)
