"""Admin-only operational routes."""

from flask import Blueprint, g, jsonify, request

from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.middleware.auth_middleware import require_auth
from app.middleware.error_handler import handle_route_errors
from app.services.admin_access import is_admin_user
from app.services.refresh_governance import list_active_refreshes
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
