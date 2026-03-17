"""Device management routes."""

import math
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import require_auth
from app.middleware.error_handler import handle_route_errors
from app.models import UserDevice


devices_bp = Blueprint("devices", __name__)
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


def _serialize_device(device):
    """Serialize a device for JSON responses."""
    return {
        "id": device.id,
        "device_identifier": device.device_identifier,
        "device_type": device.device_type,
        "device_type_confirmed": bool(device.device_type_confirmed),
        "frontend_mode": device.frontend_mode,
        "tv_scale": device.tv_scale,
        "tv_scale_confirmed_at": (
            device.tv_scale_confirmed_at.isoformat() if device.tv_scale_confirmed_at else None
        ),
        "screen_size_inches": device.screen_size_inches,
        "viewing_distance_m": device.viewing_distance_m,
        "user_agent": device.user_agent,
        "last_used_at": device.last_used_at.isoformat() if device.last_used_at else None,
        "created_at": device.created_at.isoformat() if device.created_at else None,
    }


def _suggest_device_type(screen_width, screen_height):
    """Suggest a device type based on screen size."""
    diagonal = math.sqrt(screen_width ** 2 + screen_height ** 2)
    if screen_width >= 1920 and diagonal >= 40:
        return "tv", 0.9
    if screen_width >= 768 and screen_width < 1920:
        return "tablet", 0.7
    if screen_width < 768:
        return "mobile", 0.7
    return "desktop", 0.6


@devices_bp.post("/api/devices/register")
@handle_route_errors
@require_auth
def register_device():
    """Register a device for the current user."""
    user = g.current_user
    payload = request.get_json(silent=True) or {}
    device_identifier = (payload.get("device_identifier") or "").strip()
    user_agent = (payload.get("user_agent") or "").strip()

    if not device_identifier:
        return _bad_request("Missing device_identifier.")

    device = UserDevice.query.filter_by(user_id=user.id, device_identifier=device_identifier).first()
    if device:
        device.last_used_at = datetime.utcnow()
        if user_agent:
            device.user_agent = user_agent
        db.session.commit()
        return jsonify(_serialize_device(device))

    device = UserDevice(
        user_id=user.id,
        device_identifier=device_identifier,
        user_agent=user_agent or None,
        last_used_at=datetime.utcnow(),
        device_type="desktop",
        device_type_confirmed=False,
    )
    db.session.add(device)
    db.session.commit()
    return jsonify(_serialize_device(device))


@devices_bp.get("/api/devices")
@handle_route_errors
@require_auth
def list_devices():
    """Return devices registered for the current user."""
    user = g.current_user
    devices = UserDevice.query.filter_by(user_id=user.id).order_by(UserDevice.created_at.asc()).all()
    return jsonify([_serialize_device(device) for device in devices])


@devices_bp.put("/api/devices/<int:device_id>/type")
@handle_route_errors
@require_auth
def update_device_type(device_id):
    """Update the device type for a user's device."""
    user = g.current_user
    payload = request.get_json(silent=True) or {}
    device_type = payload.get("device_type")

    if device_type not in ("tv", "tablet", "mobile", "desktop"):
        return _bad_request("Invalid device_type.")

    device = UserDevice.query.filter_by(id=device_id, user_id=user.id).first()
    if not device:
        return _not_found("Device not found.")

    device.device_type = device_type
    device.device_type_confirmed = True
    db.session.commit()
    return jsonify(_serialize_device(device))


@devices_bp.put("/api/devices/<int:device_id>/preferences")
@handle_route_errors
@require_auth
def update_device_preferences(device_id):
    """Update frontend mode and TV setup preferences for a user's device."""
    user = g.current_user
    payload = request.get_json(silent=True) or {}

    device = UserDevice.query.filter_by(id=device_id, user_id=user.id).first()
    if not device:
        return _not_found("Device not found.")

    frontend_mode = payload.get("frontend_mode")
    tv_scale = payload.get("tv_scale")
    screen_size_inches = payload.get("screen_size_inches")
    viewing_distance_m = payload.get("viewing_distance_m")

    if frontend_mode is not None and frontend_mode not in ("phone", "desktop_tablet", "tv"):
        return _bad_request("Invalid frontend_mode.")

    if tv_scale is not None and tv_scale not in ("M", "L", "XL", "XXL"):
        return _bad_request("Invalid tv_scale.")

    if screen_size_inches in ("", None):
        screen_size_inches = None
    else:
        try:
            screen_size_inches = int(screen_size_inches)
        except (TypeError, ValueError):
            return _bad_request("Invalid screen_size_inches.")
        if screen_size_inches < 20 or screen_size_inches > 150:
            return _bad_request("Invalid screen_size_inches.")

    if viewing_distance_m in ("", None):
        viewing_distance_m = None
    else:
        try:
            viewing_distance_m = float(viewing_distance_m)
        except (TypeError, ValueError):
            return _bad_request("Invalid viewing_distance_m.")
        if viewing_distance_m <= 0 or viewing_distance_m > 20:
            return _bad_request("Invalid viewing_distance_m.")

    device.frontend_mode = frontend_mode
    device.tv_scale = tv_scale
    device.screen_size_inches = screen_size_inches
    device.viewing_distance_m = viewing_distance_m
    if frontend_mode == "tv" and tv_scale:
        device.tv_scale_confirmed_at = datetime.utcnow()
    else:
        device.tv_scale_confirmed_at = None
    db.session.commit()
    return jsonify(_serialize_device(device))


@devices_bp.delete("/api/devices/<int:device_id>")
@handle_route_errors
@require_auth
def delete_device(device_id):
    """Delete a device registered to the current user."""
    user = g.current_user
    device = UserDevice.query.filter_by(id=device_id, user_id=user.id).first()
    if not device:
        return _not_found("Device not found.")

    db.session.delete(device)
    db.session.commit()
    return "", 204


@devices_bp.post("/api/devices/detect")
@handle_route_errors
@require_auth
def detect_device():
    """Suggest a device type based on basic characteristics."""
    payload = request.get_json(silent=True) or {}
    screen_width = payload.get("screen_width")
    screen_height = payload.get("screen_height")

    try:
        screen_width = int(screen_width)
        screen_height = int(screen_height)
    except (TypeError, ValueError):
        return _bad_request("Invalid screen dimensions.")

    if screen_width <= 0 or screen_height <= 0:
        return _bad_request("Invalid screen dimensions.")

    suggested_type, confidence = _suggest_device_type(screen_width, screen_height)
    return jsonify({"suggested_type": suggested_type, "confidence": confidence})
