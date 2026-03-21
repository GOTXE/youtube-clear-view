"""User settings routes."""

from flask import Blueprint, g, jsonify, request

from app.config import Config
from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import require_auth
from app.middleware.error_handler import handle_route_errors
from app.models import UserSettings
from app.services.presets import DEFAULT_PRESET, PRESETS
from app.services.quota import reset_quota_if_needed
from app.services.scheduler import run_backfill_step
from app.services.video_ingest import refresh_user_channels
from app.services.yt_api import YTService
from app.utils.time import utc_now

settings_bp = Blueprint("settings", __name__)
logger = get_logger(__name__)


def _bad_request(message):
    tracking_id = generate_tracking_id()
    logger.warning(message, extra={"tracking_id": tracking_id})
    return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400


def _get_or_create_settings(user):
    settings = UserSettings.query.filter_by(user_id=user.id).first()
    if settings:
        return settings
    settings = UserSettings(user_id=user.id, preset=DEFAULT_PRESET)
    db.session.add(settings)
    db.session.commit()
    return settings


@settings_bp.get("/api/settings")
@handle_route_errors
@require_auth
def get_settings():
    """Return user-visible refresh settings, preset definitions, and quota status."""
    user = g.current_user
    settings = _get_or_create_settings(user)
    reset_quota_if_needed(settings)
    db.session.commit()

    payload = settings.to_dict()
    payload.pop("schedule_hours", None)
    payload["presets"] = PRESETS
    payload["quota"] = {
        "daily_limit": Config.YT_DAILY_QUOTA,
        "cap_ratio": Config.YT_QUOTA_CAP_RATIO,
        "cap": settings.quota_cap,
        "used": settings.quota_used,
        "remaining": max(settings.quota_cap - settings.quota_used, 0),
    }
    return jsonify(payload)


@settings_bp.put("/api/settings")
@handle_route_errors
@require_auth
def update_settings():
    """Update user-visible preset settings for the current user."""
    user = g.current_user
    settings = _get_or_create_settings(user)
    payload = request.get_json(silent=True) or {}

    preset = payload.get("preset")
    if preset and preset not in PRESETS:
        return _bad_request("Invalid preset.")

    timezone = payload.get("timezone")
    if timezone:
        settings.timezone = timezone

    start_backfill = bool(payload.get("start_backfill"))
    preset_changed = bool(preset and preset != settings.preset)
    if preset_changed:
        settings.preset = preset
        if start_backfill:
            settings.backfill_active = True
            settings.backfill_cursor = 0
            settings.backfill_started_at = utc_now()
            settings.backfill_last_run_at = None

            service = YTService(Config.YT_API_KEY)
            run_backfill_step(user, settings, service)

    run_now = bool(payload.get("run_now"))
    if run_now and preset_changed:
        service = YTService(Config.YT_API_KEY)
        refresh_user_channels(user, settings, service, now=utc_now())
        settings.last_schedule_run_at = utc_now()

    reset_quota_if_needed(settings)
    db.session.commit()
    payload = settings.to_dict()
    payload.pop("schedule_hours", None)
    return jsonify(payload)
