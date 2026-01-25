"""API routes package."""

from flask import Blueprint, jsonify

from app.middleware.error_handler import handle_route_errors
from app.routes.auth import auth_bp
from app.routes.channels import channels_bp
from app.routes.dev import dev_bp
from app.routes.videos import videos_bp
from app.routes.themes import themes_bp
from app.routes.devices import devices_bp

health_bp = Blueprint("health", __name__)


@health_bp.get("/api/health")
@handle_route_errors
def health_check():
    """Return a simple health status for monitoring."""
    return jsonify({"status": "ok"})


def register_routes(app):
    """Register all route blueprints with the app."""
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(channels_bp)
    app.register_blueprint(dev_bp)
    app.register_blueprint(videos_bp)
    app.register_blueprint(themes_bp)
    app.register_blueprint(devices_bp)
