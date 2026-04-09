"""API routes package."""

from flask import Blueprint, current_app, jsonify

from app.middleware.error_handler import handle_route_errors
from app.routes.admin import admin_bp
from app.routes.auth import auth_bp
from app.routes.categories import categories_bp
from app.routes.channels import channels_bp
from app.routes.videos import videos_bp
from app.routes.themes import themes_bp
from app.routes.devices import devices_bp
from app.routes.settings import settings_bp
from app.services.version_check import get_version_status

health_bp = Blueprint("health", __name__)


@health_bp.get("/api/health")
@handle_route_errors
def health_check():
    """Return a simple health status for monitoring."""
    return jsonify({"status": "ok"})


@health_bp.get("/api/version")
@handle_route_errors
def version_check():
    """Return the current backend build identifier."""
    current_version = current_app.config.get("BACKEND_BUILD_ID")
    payload = get_version_status(current_version)
    payload["backend_build_id"] = current_version
    return jsonify(payload)


def register_routes(app):
    """Register all route blueprints with the app."""
    app.register_blueprint(health_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(channels_bp)
    app.register_blueprint(videos_bp)
    app.register_blueprint(themes_bp)
    app.register_blueprint(devices_bp)
    app.register_blueprint(settings_bp)
