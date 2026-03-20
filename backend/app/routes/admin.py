"""Admin-only operational routes."""

from flask import Blueprint, g, jsonify, request
from sqlalchemy import func

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import require_auth
from app.middleware.error_handler import handle_route_errors
from app.models import Channel, ChannelCategory, User, UserDevice, Video
from app.services.admin_access import is_admin_user
from app.services.auth_policy import validate_password
from app.services.refresh_governance import list_active_refreshes
from app.services.site_settings import get_password_policy, serialize_password_policy, set_password_policy
from app.services.sqlite_metrics import get_sqlite_metrics_snapshot, set_sqlite_metrics_enabled


admin_bp = Blueprint("admin", __name__)
logger = get_logger(__name__)


def _forbidden(message):
    tracking_id = generate_tracking_id()
    logger.warning(message, extra={"tracking_id": tracking_id})
    return jsonify({"error": "Forbidden.", "tracking_id": tracking_id, "status": 403}), 403


def _bad_request(message):
    tracking_id = generate_tracking_id()
    logger.warning(message, extra={"tracking_id": tracking_id})
    return jsonify({"error": "Bad request.", "tracking_id": tracking_id, "status": 400}), 400


def _require_admin():
    user = g.current_user
    if not is_admin_user(user):
        return _forbidden("Admin access required.")
    return None


def _serialize_admin_user(user):
    """Serialize a user summary for admin management."""
    last_device_use = None
    if user.devices:
        timestamps = [device.last_used_at or device.created_at for device in user.devices if (device.last_used_at or device.created_at)]
        if timestamps:
            last_device_use = max(timestamps)
    last_activity_at = max(
        [value for value in (user.session_created_at, last_device_use, user.updated_at) if value is not None],
        default=None,
    )
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "auth_provider": user.auth_provider,
        "google_auth_status": user.google_auth_status,
        "has_password": bool(user.password_hash),
        "totp_enabled": bool(user.totp_enabled),
        "is_admin": bool(user.is_admin),
        "is_active": bool(user.is_active),
        "must_change_password": bool(user.must_change_password),
        "session_created_at": user.session_created_at.isoformat() if user.session_created_at else None,
        "last_activity_at": last_activity_at.isoformat() if last_activity_at else None,
        "device_count": len(user.devices or []),
    }


def _get_other_admin_count(excluded_user_id):
    """Return how many admin users remain besides the given user."""
    return db.session.query(func.count(User.id)).filter(
        User.is_admin.is_(True),
        User.id != excluded_user_id,
    ).scalar() or 0


def _serialize_runtime_user(user):
    devices = sorted(
        user.devices,
        key=lambda device: (
            (device.last_used_at or device.created_at).timestamp()
            if (device.last_used_at or device.created_at)
            else 0
        ),
        reverse=True,
    )
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "auth_provider": user.auth_provider,
        "google_auth_status": user.google_auth_status,
        "totp_enabled": bool(user.totp_enabled),
        "has_active_session": bool(user.session_token_hash),
        "session_created_at": user.session_created_at.isoformat() if user.session_created_at else None,
        "device_count": len(devices),
        "devices": [device.to_dict() for device in devices],
    }


@admin_bp.get("/api/admin/observability/sqlite")
@handle_route_errors
@require_auth
def get_sqlite_observability():
    """Return process-local SQLite observability metrics for admins."""
    denied = _require_admin()
    if denied:
        return denied

    metrics = get_sqlite_metrics_snapshot()
    metrics["active_manual_refreshes"] = list_active_refreshes()
    return jsonify(metrics)


@admin_bp.put("/api/admin/observability/sqlite")
@handle_route_errors
@require_auth
def update_sqlite_observability():
    """Enable or disable detailed SQLite metrics collection for admins."""
    denied = _require_admin()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        return _bad_request("Invalid enabled flag.")

    set_sqlite_metrics_enabled(enabled)
    metrics = get_sqlite_metrics_snapshot()
    metrics["active_manual_refreshes"] = list_active_refreshes()
    return jsonify(metrics)


@admin_bp.get("/api/admin/runtime-state")
@handle_route_errors
@require_auth
def get_runtime_state():
    """Return admin-visible session and device state."""
    denied = _require_admin()
    if denied:
        return denied

    users = User.query.order_by(User.username.asc()).all()
    payload = [
        _serialize_runtime_user(user)
        for user in users
        if user.session_token_hash or user.devices
    ]
    return jsonify({"users": payload})


@admin_bp.get("/api/admin/summary")
@handle_route_errors
@require_auth
def get_admin_summary():
    """Return high-level admin counters for the dedicated admin page."""
    denied = _require_admin()
    if denied:
        return denied

    total_users = db.session.query(func.count(User.id)).scalar() or 0
    active_users = db.session.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
    admin_users = db.session.query(func.count(User.id)).filter(User.is_admin.is_(True)).scalar() or 0
    disabled_users = db.session.query(func.count(User.id)).filter(User.is_active.is_(False)).scalar() or 0
    total_devices = db.session.query(func.count(UserDevice.id)).scalar() or 0
    total_channels = db.session.query(func.count(Channel.id)).scalar() or 0
    total_videos = db.session.query(func.count(Video.id)).scalar() or 0
    unclassified_channels = db.session.query(func.count(Channel.id)).outerjoin(
        ChannelCategory,
        ChannelCategory.channel_id == Channel.id,
    ).filter(ChannelCategory.id.is_(None)).scalar() or 0

    return jsonify({
        "users_total": total_users,
        "users_active": active_users,
        "users_admin": admin_users,
        "users_disabled": disabled_users,
        "devices_total": total_devices,
        "channels_total": total_channels,
        "videos_total": total_videos,
        "channels_unclassified": unclassified_channels,
        "active_refreshes": len(list_active_refreshes()),
    })


@admin_bp.get("/api/admin/users")
@handle_route_errors
@require_auth
def list_admin_users():
    """Return a lightweight list of users for admin management."""
    denied = _require_admin()
    if denied:
        return denied

    query_text = (request.args.get("q") or "").strip().lower()
    users = User.query.order_by(User.username.asc()).all()
    if query_text:
        users = [
            user
            for user in users
            if query_text in (user.username or "").lower()
            or query_text in (user.email or "").lower()
            or query_text in (user.display_name or "").lower()
        ]
    return jsonify({"users": [_serialize_admin_user(user) for user in users]})


@admin_bp.post("/api/admin/users/<int:user_id>/disable")
@handle_route_errors
@require_auth
def disable_admin_user(user_id):
    """Disable a user account."""
    denied = _require_admin()
    if denied:
        return denied

    current_user = g.current_user
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return _bad_request("User not found.")
    if user.id == current_user.id:
        return _bad_request("You cannot disable your own account.")
    if user.is_admin and _get_other_admin_count(user.id) == 0:
        return _bad_request("Cannot disable the last admin.")

    user.is_active = False
    user.session_token_hash = None
    user.session_token = None
    user.session_created_at = None
    db.session.commit()
    return jsonify(_serialize_admin_user(user))


@admin_bp.post("/api/admin/users/<int:user_id>/enable")
@handle_route_errors
@require_auth
def enable_admin_user(user_id):
    """Enable a disabled user account."""
    denied = _require_admin()
    if denied:
        return denied

    user = User.query.filter_by(id=user_id).first()
    if not user:
        return _bad_request("User not found.")

    user.is_active = True
    db.session.commit()
    return jsonify(_serialize_admin_user(user))


@admin_bp.post("/api/admin/users/<int:user_id>/reset-password")
@handle_route_errors
@require_auth
def admin_reset_user_password(user_id):
    """Set a temporary password and force a change on next login."""
    denied = _require_admin()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    temporary_password = payload.get("temporary_password")
    if not isinstance(temporary_password, str) or not temporary_password:
        return _bad_request("Invalid temporary password.")
    password_ok, _ = validate_password(temporary_password, get_password_policy())
    if not password_ok:
        return _bad_request("Invalid temporary password.")

    user = User.query.filter_by(id=user_id).first()
    if not user:
        return _bad_request("User not found.")

    user.set_password(temporary_password)
    user.must_change_password = True
    user.is_active = True
    user.session_token_hash = None
    user.session_token = None
    user.session_created_at = None
    db.session.commit()
    return jsonify(_serialize_admin_user(user))


@admin_bp.get("/api/admin/security/password-policy")
@handle_route_errors
@require_auth
def get_password_policy_settings():
    """Return the active global password policy for admins."""
    denied = _require_admin()
    if denied:
        return denied

    return jsonify(serialize_password_policy())


@admin_bp.put("/api/admin/security/password-policy")
@handle_route_errors
@require_auth
def update_password_policy_settings():
    """Persist a new global password policy for admins."""
    denied = _require_admin()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    policy_name = payload.get("password_policy")
    if not isinstance(policy_name, str):
        return _bad_request("Invalid password policy.")

    try:
        set_password_policy(policy_name)
    except ValueError:
        return _bad_request("Invalid password policy.")

    return jsonify(serialize_password_policy())
