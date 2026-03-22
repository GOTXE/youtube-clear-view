"""Admin-only operational routes."""

import logging
from datetime import UTC, datetime, timedelta
import os
import time
from zoneinfo import ZoneInfo
from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import func

from app.extensions import db
from app.logging.logger import get_logger, set_runtime_log_level
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import require_auth
from app.middleware.error_handler import handle_route_errors
from app.models import Channel, ChannelCategory, User, UserDevice, Video
from app.services.admin_access import is_admin_user
from app.services.auth_policy import validate_password
from app.services.refresh_governance import list_active_refreshes
from app.services.quota import get_global_quota_snapshot
from app.services.site_settings import (
    get_password_policy,
    get_refresh_schedule_timezone,
    get_site_log_level,
    serialize_password_policy,
    serialize_refresh_schedule,
    set_password_policy,
    set_refresh_schedule_hours,
    set_refresh_schedule_timezone,
    set_site_log_level,
)
from app.services.sqlite_metrics import get_sqlite_metrics_snapshot, set_sqlite_metrics_enabled


admin_bp = Blueprint("admin", __name__)
logger = get_logger(__name__)
LOG_RECORD_START_PREFIX = "[20"
TRACKING_CONTEXT_RECORDS = 20


def _read_admin_log_entries(limit=5000):
    """Read the latest log file entries, including rotated files."""
    log_file = current_app.config.get("LOG_FILE")
    if not log_file or not os.path.exists(log_file):
        return [], False
    log_dir = os.path.dirname(log_file) or "."
    base_name = os.path.basename(log_file)
    candidates = []
    for entry in os.listdir(log_dir):
        if entry == base_name or entry.startswith(f"{base_name}."):
            candidates.append(os.path.join(log_dir, entry))
    ordered = sorted(
        candidates,
        key=lambda path: (0 if os.path.basename(path) == base_name else int(os.path.basename(path).split(".")[-1] or 0)),
    )
    return _tail_lines_from_files(ordered, limit)


def _get_admin_log_files():
    """Return ordered current and rotated log files."""
    log_file = current_app.config.get("LOG_FILE")
    if not log_file or not os.path.exists(log_file):
        return []
    log_dir = os.path.dirname(log_file) or "."
    base_name = os.path.basename(log_file)
    candidates = []
    for entry in os.listdir(log_dir):
        if entry == base_name or entry.startswith(f"{base_name}."):
            candidates.append(os.path.join(log_dir, entry))
    return sorted(
        candidates,
        key=lambda path: (0 if os.path.basename(path) == base_name else int(os.path.basename(path).split(".")[-1] or 0)),
    )


def _tail_log_lines(log_file, count):
    """Read the last N log lines efficiently."""
    count = max(int(count or 1), 1)
    buffer = b""
    line_count = 0
    more_available = False

    with open(log_file, "rb") as file_handle:
        file_handle.seek(0, os.SEEK_END)
        position = file_handle.tell()

        while position > 0 and line_count <= count:
            read_size = min(4096, position)
            position -= read_size
            file_handle.seek(position)
            buffer = file_handle.read(read_size) + buffer
            line_count = buffer.count(b"\n")

        more_available = position > 0

    lines = buffer.splitlines()
    if len(lines) > count:
        lines = lines[-count:]

    decoded = [line.decode("utf-8", errors="ignore") for line in lines]
    return decoded, more_available


def _tail_lines_from_files(log_files, count):
    """Read the last N lines across current and rotated log files."""
    count = max(int(count or 1), 1)
    collected = []
    more_available = False

    for log_file in reversed(log_files):
        if not os.path.exists(log_file):
            continue
        lines, file_has_more = _tail_log_lines(log_file, count)
        if lines:
            collected = lines + collected
            if len(collected) > count:
                collected = collected[-count:]
                more_available = True
                break
        if file_has_more:
            more_available = True

    return collected, more_available


def _filter_log_entries(entries, levels=None, search=None, tracking_id=None):
    """Filter log entries by level, free text, and tracking id."""
    filtered = []
    search_lower = (search or "").lower().strip()
    tracking = (tracking_id or "").strip().upper()
    for entry in entries:
        if levels and not any(f"[{level}]" in entry for level in levels):
            continue
        if tracking and tracking not in entry.upper():
            continue
        if search_lower and search_lower not in entry.lower():
            continue
        filtered.append(entry)
    return filtered


def _group_log_records(entries):
    """Group raw log lines into logical log records with multiline context."""
    records = []
    current = []

    for entry in entries:
        if entry.startswith(LOG_RECORD_START_PREFIX) and current:
            records.append("\n".join(current))
            current = [entry]
            continue
        current.append(entry)

    if current:
        records.append("\n".join(current))

    return records


def _search_records_by_tracking_id(tracking_id):
    """Search full log history and return surrounding context for a tracking id."""
    tracking = (tracking_id or "").strip().upper()
    if not tracking:
        return []

    matches = []
    for log_file in reversed(_get_admin_log_files()):
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as file_handle:
                lines = file_handle.read().splitlines()
        except OSError:
            continue
        records = _group_log_records(lines)
        hit_indexes = [index for index, record in enumerate(records) if tracking in record.upper()]
        if not hit_indexes:
            continue

        context_ranges = []
        for index in hit_indexes:
            start = max(index - TRACKING_CONTEXT_RECORDS, 0)
            end = min(index + TRACKING_CONTEXT_RECORDS + 1, len(records))
            if context_ranges and start <= context_ranges[-1][1]:
                context_ranges[-1] = (context_ranges[-1][0], max(context_ranges[-1][1], end))
            else:
                context_ranges.append((start, end))

        file_header = f"===== {os.path.basename(log_file)} ====="
        for start, end in context_ranges:
            block = [file_header, *records[start:end]]
            matches.append("\n\n".join(block))
    return matches


def _next_quota_reset_utc():
    """Return next daily quota reset timestamp."""
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).date()
    return datetime.combine(tomorrow, datetime.min.time(), tzinfo=UTC)


def _server_timezone_label():
    """Return a readable configured timezone label for gestor/log display."""
    try:
      local_now = datetime.now(ZoneInfo(get_refresh_schedule_timezone() or "UTC"))
    except Exception:
      local_now = datetime.now().astimezone()
    offset = local_now.utcoffset() or timedelta(0)
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    tz_name = local_now.tzname() or "Local"
    return f"{tz_name} (UTC{sign}{hours:02d}:{minutes:02d})"


def _current_logs_day_prefix():
    """Return current local day prefix for log stats."""
    try:
        current_day = datetime.now(ZoneInfo(get_refresh_schedule_timezone() or "UTC"))
    except Exception:
        current_day = datetime.now().astimezone()
    return current_day.strftime("%Y-%m-%d")


def _set_runtime_log_level(level_name: str):
    """Update root logger and handlers for the current worker process."""
    normalized = set_runtime_log_level(level_name)
    current_app.config["LOG_LEVEL"] = normalized
    return normalized


def _serialize_logs_meta():
    """Return runtime metadata useful in the logs view."""
    quota = get_global_quota_snapshot()
    return {
        "log_runtime": {
            "level": str(current_app.config.get("LOG_LEVEL", "INFO")).upper(),
            "configured_level": get_site_log_level(current_app.config.get("LOG_LEVEL", "INFO")),
            "rotate_enabled": int(current_app.config.get("LOG_BACKUP_COUNT", 0) or 0) > 0,
            "max_size_bytes": int(current_app.config.get("LOG_MAX_SIZE", 0) or 0),
            "backup_count": int(current_app.config.get("LOG_BACKUP_COUNT", 0) or 0),
            "timestamps_timezone": _server_timezone_label(),
            "timestamps_are_utc": time.tzname[0] == "UTC" and time.localtime().tm_isdst == 0,
        },
        "quota": {
            **quota,
            "reset_at_utc": _next_quota_reset_utc().isoformat(),
        },
    }


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
    quota = get_global_quota_snapshot()

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
        "quota_used": quota["used"],
        "quota_daily_limit": quota["daily_limit"],
        "quota_app_cap": quota["app_cap"],
        "quota_remaining": quota["remaining_app_cap"],
        "quota_reserved_for_scheduled": quota["reserved_for_scheduled"],
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


@admin_bp.get("/api/admin/refresh-schedule")
@handle_route_errors
@require_auth
def get_refresh_schedule_settings():
    """Return the active global refresh schedule for admins."""
    denied = _require_admin()
    if denied:
        return denied

    return jsonify(serialize_refresh_schedule())


@admin_bp.put("/api/admin/refresh-schedule")
@handle_route_errors
@require_auth
def update_refresh_schedule_settings():
    """Persist the global refresh schedule for admins."""
    denied = _require_admin()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    schedule_hours = payload.get("schedule_hours")
    timezone_name = payload.get("timezone")

    try:
        if schedule_hours is not None:
            set_refresh_schedule_hours(schedule_hours)
        if timezone_name is not None:
            set_refresh_schedule_timezone(timezone_name)
    except ValueError as error:
        return _bad_request(str(error))

    db.session.commit()
    return jsonify(serialize_refresh_schedule())


@admin_bp.get("/api/admin/timezone")
@handle_route_errors
@require_auth
def get_admin_timezone():
    """Return the current global timezone setting."""
    denied = _require_admin()
    if denied:
        return denied
    timezone_name = get_refresh_schedule_timezone()
    return jsonify({"timezone": timezone_name})


@admin_bp.put("/api/admin/timezone")
@handle_route_errors
@require_auth
def update_admin_timezone():
    """Persist the global timezone used by scheduler and log display."""
    denied = _require_admin()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    timezone_name = payload.get("timezone")
    try:
        set_refresh_schedule_timezone(timezone_name)
    except ValueError as error:
        return _bad_request(str(error))
    db.session.commit()
    return jsonify({"timezone": get_refresh_schedule_timezone(), "restart_required": False})


@admin_bp.put("/api/admin/logs/level")
@handle_route_errors
@require_auth
def update_admin_log_level():
    """Update the runtime log level for the current backend worker."""
    denied = _require_admin()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        level = _set_runtime_log_level(payload.get("level"))
        set_site_log_level(level)
    except ValueError as error:
        return _bad_request(str(error))
    db.session.commit()
    restart_required = int(current_app.config.get("GUNICORN_WORKERS", 1) or 1) > 1
    return jsonify({"level": level, "configured_level": level, "restart_required": restart_required})


@admin_bp.get("/api/admin/logs/entries")
@handle_route_errors
@require_auth
def get_admin_log_entries():
    """Return filtered log entries for gestor."""
    denied = _require_admin()
    if denied:
        return denied

    levels_param = request.args.get("level", "")
    search = request.args.get("search")
    tracking_id = request.args.get("tracking_id")

    try:
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return _bad_request("Invalid pagination values.")

    if limit <= 0 or offset < 0:
        return _bad_request("Invalid pagination values.")

    levels = [level.strip().upper() for level in levels_param.split(",") if level.strip()]
    if tracking_id:
        records = _search_records_by_tracking_id(tracking_id)
        more_available = False
    else:
        entries, more_available = _read_admin_log_entries(5000)
        records = _group_log_records(entries)
    filtered = _filter_log_entries(records, levels=levels, search=search, tracking_id=tracking_id)

    total = len(filtered)
    end = max(total - offset, 0)
    start = max(end - limit, 0)
    sliced = list(reversed(filtered[start:end]))
    has_more = total - offset > limit or more_available
    next_offset = offset + limit if has_more else None

    return jsonify({"entries": sliced, "has_more": has_more, "next_offset": next_offset})


@admin_bp.get("/api/admin/logs/stats")
@handle_route_errors
@require_auth
def get_admin_log_stats():
    """Return log stats and recent errors for gestor."""
    denied = _require_admin()
    if denied:
        return denied

    entries, _ = _read_admin_log_entries(5000)
    records = _group_log_records(entries)
    levels = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
    recent_errors = []
    current_day_prefix = _current_logs_day_prefix()

    for entry in records:
        if not entry.startswith(f"[{current_day_prefix}"):
            continue
        for level in levels:
            if f"[{level}]" in entry:
                levels[level] += 1
                if level in ("ERROR", "CRITICAL"):
                    recent_errors.append(entry)
                break

    return jsonify({"levels": levels, "recent_errors": list(reversed(recent_errors[-20:])), "scope": "daily"})


@admin_bp.get("/api/admin/logs/meta")
@handle_route_errors
@require_auth
def get_admin_logs_meta():
    """Return runtime metadata for the gestor logs view."""
    denied = _require_admin()
    if denied:
        return denied

    return jsonify(_serialize_logs_meta())
