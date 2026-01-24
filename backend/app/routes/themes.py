"""Theme management routes."""

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import require_auth
from app.middleware.error_handler import handle_route_errors
from app.models import Channel, Theme, ThemeChannel, UserChannel


themes_bp = Blueprint("themes", __name__)
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


def _serialize_theme(theme):
    """Serialize a theme with its channel list."""
    links = ThemeChannel.query.filter_by(theme_id=theme.id).all()
    channel_ids = [link.channel_id for link in links]
    channels = []
    if channel_ids:
        channels = (
            Channel.query.filter(Channel.id.in_(channel_ids))
            .order_by(Channel.title.asc())
            .all()
        )
    return {
        "id": theme.id,
        "name": theme.name,
        "color": theme.color,
        "channels": [
            {"id": channel.id, "title": channel.title, "thumbnail_url": channel.thumbnail_url}
            for channel in channels
        ],
    }


@themes_bp.get("/api/themes")
@handle_route_errors
@require_auth
def list_themes():
    """Return all themes for the current user."""
    user = g.current_user
    themes = Theme.query.filter_by(user_id=user.id).order_by(Theme.created_at.desc()).all()
    return jsonify([_serialize_theme(theme) for theme in themes])


@themes_bp.post("/api/themes")
@handle_route_errors
@require_auth
def create_theme():
    """Create a new theme for the current user."""
    user = g.current_user
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    color = (payload.get("color") or "").strip()
    if not name:
        return _bad_request("Missing theme name.")

    theme = Theme(user_id=user.id, name=name, color=color or None)
    db.session.add(theme)
    db.session.commit()

    return jsonify(_serialize_theme(theme)), 201


@themes_bp.put("/api/themes/<int:theme_id>")
@handle_route_errors
@require_auth
def update_theme(theme_id):
    """Update an existing theme."""
    user = g.current_user
    theme = Theme.query.filter_by(id=theme_id, user_id=user.id).first()
    if not theme:
        return _not_found("Theme not found.")

    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    color = payload.get("color")

    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            return _bad_request("Theme name cannot be empty.")
        theme.name = cleaned

    if color is not None:
        theme.color = color.strip() if color.strip() else None

    db.session.commit()
    return jsonify(_serialize_theme(theme))


@themes_bp.delete("/api/themes/<int:theme_id>")
@handle_route_errors
@require_auth
def delete_theme(theme_id):
    """Delete a theme and its channel links."""
    user = g.current_user
    theme = Theme.query.filter_by(id=theme_id, user_id=user.id).first()
    if not theme:
        return _not_found("Theme not found.")

    ThemeChannel.query.filter_by(theme_id=theme.id).delete()
    db.session.delete(theme)
    db.session.commit()
    return "", 204


@themes_bp.post("/api/themes/<int:theme_id>/channels")
@handle_route_errors
@require_auth
def add_channel_to_theme(theme_id):
    """Add a channel to a theme."""
    user = g.current_user
    theme = Theme.query.filter_by(id=theme_id, user_id=user.id).first()
    if not theme:
        return _not_found("Theme not found.")

    payload = request.get_json(silent=True) or {}
    channel_id = payload.get("channel_id")
    if not channel_id:
        return _bad_request("Missing channel_id.")

    try:
        channel_id = int(channel_id)
    except ValueError:
        return _bad_request("Invalid channel_id.")

    subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
    if not subscription:
        return _not_found("Channel not subscribed.")

    existing = ThemeChannel.query.filter_by(theme_id=theme.id, channel_id=channel_id).first()
    if not existing:
        db.session.add(ThemeChannel(theme_id=theme.id, channel_id=channel_id))
        db.session.commit()

    return jsonify(_serialize_theme(theme))


@themes_bp.delete("/api/themes/<int:theme_id>/channels/<int:channel_id>")
@handle_route_errors
@require_auth
def remove_channel_from_theme(theme_id, channel_id):
    """Remove a channel from a theme."""
    user = g.current_user
    theme = Theme.query.filter_by(id=theme_id, user_id=user.id).first()
    if not theme:
        return _not_found("Theme not found.")

    link = ThemeChannel.query.filter_by(theme_id=theme.id, channel_id=channel_id).first()
    if not link:
        return _not_found("Channel not in theme.")

    db.session.delete(link)
    db.session.commit()
    return jsonify(_serialize_theme(theme))
