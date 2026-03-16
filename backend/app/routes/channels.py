"""Channel management routes."""

from datetime import datetime, timedelta
import json
import os
from urllib.parse import urlparse

import requests
from flask import Blueprint, Response, current_app, g, jsonify, redirect, request, send_file, stream_with_context
from sqlalchemy import func

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import require_auth
from app.middleware.error_handler import handle_route_errors
from app.models import Category, Channel, ChannelCategory, UserChannel, Video, WatchedVideo
from app.services import ClassificationService
from app.services.google_oauth import ensure_access_token
from app.models import UserSettings
from app.services.presets import DEFAULT_PRESET
from app.services.refresh_governance import acquire_manual_refresh, evaluate_manual_refresh
from app.services.video_ingest import (
    iter_refresh_user_channels,
    refresh_user_channels,
    upsert_channel_video_evidence,
)
from app.services.yt_api import YTService
from app.services.yt_oauth import fetch_subscriptions_page

channels_bp = Blueprint("channels", __name__)
logger = get_logger(__name__)
THUMBNAIL_TTL_DAYS = 90


def _thumbnail_cache_dir():
    """Return the directory for cached channel thumbnails."""
    cache_dir = os.path.join(current_app.instance_path, "channel_thumbnails")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _resolve_thumbnail_extension(content_type, url):
    """Resolve a thumbnail file extension."""
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    if content_type:
        normalized = content_type.split(";", 1)[0].strip().lower()
        if normalized in mapping:
            return mapping[normalized]

    if url:
        ext = os.path.splitext(urlparse(url).path)[1]
        if ext:
            return ext
    return ".jpg"


def _thumbnail_is_stale(channel):
    """Check if cached thumbnail is stale or missing."""
    if not channel.thumbnail_cache_path or not channel.thumbnail_cached_at:
        return True
    cache_dir = _thumbnail_cache_dir()
    cached_path = os.path.join(cache_dir, channel.thumbnail_cache_path)
    if not os.path.exists(cached_path):
        return True
    cutoff = datetime.utcnow() - timedelta(days=THUMBNAIL_TTL_DAYS)
    return channel.thumbnail_cached_at < cutoff


def _cache_channel_thumbnail(channel):
    """Fetch and cache a channel thumbnail if needed."""
    if not channel.thumbnail_url:
        return None

    cache_dir = _thumbnail_cache_dir()
    if not _thumbnail_is_stale(channel):
        return os.path.join(cache_dir, channel.thumbnail_cache_path)

    try:
        response = requests.get(channel.thumbnail_url, timeout=10)
    except requests.RequestException:
        return None

    if response.status_code != 200 or not response.content:
        return None

    ext = _resolve_thumbnail_extension(response.headers.get("content-type"), channel.thumbnail_url)
    filename = f"channel_{channel.id}{ext}"
    cached_path = os.path.join(cache_dir, filename)

    if channel.thumbnail_cache_path and channel.thumbnail_cache_path != filename:
        old_path = os.path.join(cache_dir, channel.thumbnail_cache_path)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    with open(cached_path, "wb") as file_handle:
        file_handle.write(response.content)

    channel.thumbnail_cache_path = filename
    channel.thumbnail_cached_at = datetime.utcnow()
    db.session.commit()

    return cached_path


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


def _manual_refresh_block_response(decision):
    """Build a structured JSON response for a blocked manual refresh."""
    reason = decision.get("reason")
    if reason == "refresh_in_progress":
        error_message = "Refresh already in progress."
    else:
        error_message = "Refresh cooldown active."

    payload = {
        "error": error_message,
        "status": decision.get("status_code", 409),
        "blocked": True,
        "reason": reason,
        "scope": decision.get("scope"),
        "active_scope": decision.get("active_scope"),
        "active_started_at": decision.get("active_started_at"),
        "cooldown_seconds": decision.get("cooldown_seconds"),
        "last_activity_at": decision.get("last_activity_at"),
        "next_allowed_at": decision.get("next_allowed_at"),
        "retry_after_seconds": decision.get("retry_after_seconds", 0),
    }
    return jsonify(payload), decision.get("status_code", 409)


def _manual_refresh_block_event(decision, refreshed_at):
    """Build an SSE payload for a blocked manual refresh."""
    event = {
        "type": "blocked",
        "blocked": True,
        "reason": decision.get("reason"),
        "scope": decision.get("scope"),
        "active_scope": decision.get("active_scope"),
        "active_started_at": decision.get("active_started_at"),
        "cooldown_seconds": decision.get("cooldown_seconds"),
        "last_activity_at": decision.get("last_activity_at"),
        "next_allowed_at": decision.get("next_allowed_at"),
        "retry_after_seconds": decision.get("retry_after_seconds", 0),
        "refreshed_at": refreshed_at.isoformat(),
    }
    return "event: refresh\ndata: " + json.dumps(event) + "\n\n"


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
        data = channel.to_dict(include_category=True)
        data["thumbnail_local_url"] = f"/api/channels/{channel.id}/thumbnail"
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
        data["last_checked_at"] = (
            subscription.last_checked_at.isoformat()
            if subscription.last_checked_at
            else None
        )
        # Include rating information
        data["rating"] = subscription.rating
        data["rated_at"] = (
            subscription.rated_at.isoformat() if subscription.rated_at else None
        )
        results.append(data)
    return jsonify(results)


@channels_bp.get("/api/channels/<int:channel_id>/thumbnail")
@handle_route_errors
def channel_thumbnail(channel_id):
    """Return a cached channel thumbnail or redirect to the source."""
    channel = Channel.query.filter_by(id=channel_id).first()
    if not channel or not channel.thumbnail_url:
        return "", 404

    cached_path = _cache_channel_thumbnail(channel)
    if cached_path and os.path.exists(cached_path):
        return send_file(cached_path, mimetype="image/*", max_age=60 * 60 * 24)

    return redirect(channel.thumbnail_url)


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

        # Serialize topic_ids to JSON string
        import json
        topic_ids_json = json.dumps(info.get("topic_ids")) if info.get("topic_ids") else None

        channel = Channel(
            yt_channel_id=yt_channel_id,
            title=info.get("title"),
            description=info.get("description"),
            thumbnail_url=info.get("thumbnail"),
            topic_ids=topic_ids_json,
            keywords=info.get("keywords"),
            country=info.get("country"),
        )
        db.session.add(channel)
        db.session.flush()

    subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel.id).first()
    if not subscription:
        subscription = UserChannel(user_id=user.id, channel_id=channel.id)
        db.session.add(subscription)

    db.session.commit()

    # Auto-classify the channel if not already classified
    if not ChannelCategory.query.filter_by(channel_id=channel.id).first():
        try:
            service = ClassificationService()
            service.classify_channel(channel)
        except Exception as e:
            logger.warning(
                f"Failed to auto-classify channel {channel.yt_channel_id}: {e}",
                extra={"tracking_id": generate_tracking_id()},
            )

    data = channel.to_dict(include_category=True)
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
    backfill = bool(payload.get("backfill"))

    if channel_id:
        subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
        if not subscription:
            return _not_found("Subscription not found.")
    else:
        subscription = None

    settings = UserSettings.query.filter_by(user_id=user.id).first()
    if not settings:
        settings = UserSettings(user_id=user.id, preset=DEFAULT_PRESET)
        db.session.add(settings)
        db.session.commit()

    service = _get_service()
    refreshed_at = datetime.utcnow()
    cooldown_decision = evaluate_manual_refresh(user.id, channel_id=channel_id, now=refreshed_at)
    if not cooldown_decision.get("allowed"):
        return _manual_refresh_block_response(cooldown_decision)

    with acquire_manual_refresh(user.id, channel_id=channel_id, now=refreshed_at) as lease:
        if not lease.get("acquired"):
            return _manual_refresh_block_response(lease)

        result = refresh_user_channels(
            user,
            settings,
            service,
            channel_id=channel_id,
            ignore_last_refreshed=backfill,
            now=refreshed_at,
        )

    return jsonify(
        {
            "status": "accepted",
            "scope": cooldown_decision.get("scope"),
            "new_videos": result.get("new_videos", 0),
            "refreshed_at": refreshed_at.isoformat(),
        }
    )


@channels_bp.get("/api/channels/refresh/stream")
@handle_route_errors
@require_auth
def refresh_channels_stream():
    """Stream refresh progress for one or all subscribed channels."""
    user = g.current_user
    user_id = user.id
    channel_id = request.args.get("channel_id", type=int)
    backfill = request.args.get("backfill", "false").lower() == "true"

    if channel_id:
        subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
        if not subscription:
            return _not_found("Subscription not found.")

    settings = UserSettings.query.filter_by(user_id=user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id, preset=DEFAULT_PRESET)
        db.session.add(settings)
        db.session.commit()

    refreshed_at = datetime.utcnow()
    cooldown_decision = evaluate_manual_refresh(user.id, channel_id=channel_id, now=refreshed_at)
    if not cooldown_decision.get("allowed"):
        def blocked_generate():
            yield _manual_refresh_block_event(cooldown_decision, refreshed_at)

        response = Response(stream_with_context(blocked_generate()), mimetype="text/event-stream")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    def generate():
        stream_user = db.session.get(type(user), user_id)
        stream_settings = UserSettings.query.filter_by(user_id=user_id).first()
        if not stream_settings:
            stream_settings = UserSettings(user_id=user_id, preset=DEFAULT_PRESET)
            db.session.add(stream_settings)
            db.session.commit()

        service = _get_service()
        with acquire_manual_refresh(user_id, channel_id=channel_id, now=refreshed_at) as lease:
            if not lease.get("acquired"):
                yield _manual_refresh_block_event(lease, refreshed_at)
                return

            yield "event: refresh\ndata: " + json.dumps(
                {"type": "stream_opened", "refreshed_at": refreshed_at.isoformat()}
            ) + "\n\n"
            for event in iter_refresh_user_channels(
                stream_user,
                stream_settings,
                service,
                channel_id=channel_id,
                ignore_last_refreshed=backfill,
                now=refreshed_at,
            ):
                event.setdefault("refreshed_at", refreshed_at.isoformat())
                yield "event: refresh\ndata: " + json.dumps(event) + "\n\n"

    response = Response(stream_with_context(generate()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


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

    # Classification is deferred until enrichment or enough local video evidence exists.
    classified = 0

    next_token = page_info.get("next_page_token") if page_info else None
    total_results = page_info.get("total_results") if page_info else None
    return jsonify(
        {
            "imported": imported,
            "new_channels": new_channels,
            "new_subscriptions": new_subscriptions,
            "classified": classified,
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


@channels_bp.get("/api/channels/<int:channel_id>/category")
@handle_route_errors
@require_auth
def get_channel_category(channel_id):
    """Return the category for a specific channel."""
    user = g.current_user
    subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
    if not subscription:
        return _not_found("Subscription not found.")

    channel = subscription.channel
    channel_category = ChannelCategory.query.filter_by(channel_id=channel_id).first()

    if not channel_category:
        return jsonify({"category": None, "message": "Channel not classified."})

    category = Category.query.filter_by(id=channel_category.category_id).first()
    return jsonify({
        "category": category.to_dict() if category else None,
        "classification": channel_category.to_dict(),
    })


@channels_bp.put("/api/channels/<int:channel_id>/category")
@handle_route_errors
@require_auth
def update_channel_category(channel_id):
    """Manually assign a category to a channel."""
    user = g.current_user
    subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
    if not subscription:
        return _not_found("Subscription not found.")

    payload = request.get_json(silent=True) or {}
    category_name = payload.get("category_name")
    category_id = payload.get("category_id")

    if not category_name and not category_id:
        return _bad_request("Missing category_name or category_id.")

    if category_id:
        category = Category.query.filter_by(id=category_id).first()
    else:
        category = Category.query.filter_by(name=category_name).first()

    if not category:
        return _not_found("Category not found.")

    service = ClassificationService()
    result = service.manually_classify(subscription.channel, category.name)

    if not result:
        return _bad_request("Failed to classify channel.")

    return jsonify({
        "category": category.to_dict(),
        "classification": result.to_dict(),
        "message": "Category updated successfully.",
    })


@channels_bp.delete("/api/channels/<int:channel_id>/category")
@handle_route_errors
@require_auth
def delete_channel_category(channel_id):
    """Remove manual override and auto-classify channel."""
    user = g.current_user
    subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
    if not subscription:
        return _not_found("Subscription not found.")

    service = ClassificationService()
    result = service.reclassify_channel(subscription.channel)

    if not result:
        return jsonify({
            "category": None,
            "message": "Could not auto-classify channel.",
        })

    category = Category.query.filter_by(id=result.category_id).first()
    return jsonify({
        "category": category.to_dict() if category else None,
        "classification": result.to_dict(),
        "message": "Channel reclassified successfully.",
    })


@channels_bp.put("/api/channels/<int:channel_id>/rating")
@handle_route_errors
@require_auth
def rate_channel(channel_id):
    """Rate a channel (1-5 stars)."""
    user = g.current_user
    subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
    if not subscription:
        return _not_found("Subscription not found.")

    payload = request.get_json(silent=True) or {}
    rating = payload.get("rating")

    if rating is None:
        return _bad_request("Missing rating.")

    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return _bad_request("Invalid rating value.")

    if rating < 1 or rating > 5:
        return _bad_request("Rating must be between 1 and 5.")

    subscription.rating = rating
    subscription.rated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "channel_id": channel_id,
        "rating": rating,
        "rated_at": subscription.rated_at.isoformat(),
        "message": "Rating updated successfully.",
    })


@channels_bp.delete("/api/channels/<int:channel_id>/rating")
@handle_route_errors
@require_auth
def delete_channel_rating(channel_id):
    """Remove rating from a channel."""
    user = g.current_user
    subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
    if not subscription:
        return _not_found("Subscription not found.")

    subscription.rating = None
    subscription.rated_at = None
    db.session.commit()

    return jsonify({
        "channel_id": channel_id,
        "rating": None,
        "message": "Rating removed successfully.",
    })


@channels_bp.post("/api/channels/enrich")
@handle_route_errors
@require_auth
def enrich_channels():
    """
    Enrich channels with topic_ids, keywords, and country from YouTube API.

    This fetches additional metadata for channels that don't have topic_ids,
    which is needed for accurate automatic classification.
    """
    import json

    user = g.current_user
    payload = request.get_json(silent=True) or {}
    channel_id = payload.get("channel_id")
    limit = min(int(payload.get("limit", 50)), 100)

    # Get channels to enrich
    if channel_id:
        # Enrich specific channel
        subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
        if not subscription:
            return _not_found("Subscription not found.")
        channels = [subscription.channel]
    else:
        # Enrich channels without topic_ids
        subscriptions = UserChannel.query.filter_by(user_id=user.id).all()
        channels = [
            sub.channel for sub in subscriptions
            if not sub.channel.topic_ids
        ][:limit]

    if not channels:
        return jsonify({
            "enriched": 0,
            "message": "No channels need enrichment.",
        })

    service = _get_service()
    enriched = 0
    classified = 0
    errors = 0
    enriched_channels = []

    for channel in channels:
        try:
            info = service.get_channel_info(channel.yt_channel_id)
            if info:
                if info.get("topic_ids"):
                    channel.topic_ids = json.dumps(info["topic_ids"])
                if info.get("keywords") and not channel.keywords:
                    channel.keywords = info["keywords"]
                if info.get("country") and not channel.country:
                    channel.country = info["country"]
                enriched += 1
                enriched_channels.append(channel)
        except Exception as e:
            logger.warning(
                f"Failed to enrich channel {channel.yt_channel_id}: {e}",
                extra={"tracking_id": generate_tracking_id()},
            )
            errors += 1

    db.session.commit()

    classifier = ClassificationService()
    for channel in enriched_channels:
        try:
            if classifier.classify_channel(channel):
                classified += 1
        except Exception as e:
            logger.warning(
                f"Failed to classify enriched channel {channel.yt_channel_id}: {e}",
                extra={"tracking_id": generate_tracking_id()},
            )

    # Calculate remaining channels without topic_ids
    remaining = UserChannel.query.filter_by(user_id=user.id).join(Channel).filter(
        (Channel.topic_ids.is_(None)) | (Channel.topic_ids == "")
    ).count()

    return jsonify({
        "enriched": enriched,
        "classified": classified,
        "errors": errors,
        "remaining": remaining,
        "message": f"Enriched {enriched} channels with topic data.",
    })


@channels_bp.post("/api/channels/enrich-video-evidence")
@handle_route_errors
@require_auth
def enrich_channel_video_evidence():
    """Fetch recent video metadata for channels and classify using that evidence."""
    user = g.current_user
    payload = request.get_json(silent=True) or {}
    channel_id = payload.get("channel_id")
    limit = min(int(payload.get("limit", 25)), 100)
    max_results = min(int(payload.get("max_results", 12)), 25)
    only_unclassified = bool(payload.get("only_unclassified", True))

    if channel_id:
        subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
        if not subscription:
            return _not_found("Subscription not found.")
        subscriptions = [subscription]
    else:
        query = UserChannel.query.filter_by(user_id=user.id)
        subscriptions = query.all()
        if only_unclassified:
            subscriptions = [
                subscription
                for subscription in subscriptions
                if not ChannelCategory.query.filter_by(channel_id=subscription.channel_id).first()
            ]
        subscriptions = subscriptions[:limit]

    if not subscriptions:
        remaining = (
            UserChannel.query.filter_by(user_id=user.id)
            .outerjoin(ChannelCategory, ChannelCategory.channel_id == UserChannel.channel_id)
            .filter(ChannelCategory.id.is_(None))
            .count()
        )
        return jsonify({
            "channels_processed": 0,
            "videos_created": 0,
            "videos_updated": 0,
            "classified": 0,
            "remaining_unclassified": remaining,
            "message": "No channels need video evidence enrichment.",
        })

    service = _get_service()
    classifier = ClassificationService()
    channels_processed = 0
    videos_created = 0
    videos_updated = 0
    classified = 0
    errors = 0

    for subscription in subscriptions:
        channel = subscription.channel
        try:
            response = service.get_channel_videos(channel.yt_channel_id, max_results=max_results)
            if not response.get("success", True):
                errors += 1
                continue

            created, updated = upsert_channel_video_evidence(channel, response.get("videos", []))
            videos_created += created
            videos_updated += updated
            channels_processed += 1

            if not ChannelCategory.query.filter_by(channel_id=channel.id).first():
                if classifier.classify_channel(channel):
                    classified += 1
        except Exception as error:
            logger.warning(
                "Failed to enrich video evidence for channel %s: %s",
                channel.yt_channel_id,
                error,
                extra={"tracking_id": generate_tracking_id()},
            )
            db.session.rollback()
            errors += 1

    db.session.commit()

    remaining = (
        UserChannel.query.filter_by(user_id=user.id)
        .outerjoin(ChannelCategory, ChannelCategory.channel_id == UserChannel.channel_id)
        .filter(ChannelCategory.id.is_(None))
        .count()
    )

    return jsonify({
        "channels_processed": channels_processed,
        "videos_created": videos_created,
        "videos_updated": videos_updated,
        "classified": classified,
        "errors": errors,
        "remaining_unclassified": remaining,
        "message": f"Processed {channels_processed} channels with recent video evidence.",
    })
