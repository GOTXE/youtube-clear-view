"""API routes package."""

from flask import Blueprint, jsonify

from app.middleware.error_handler import handle_route_errors
from app.routes.auth import auth_bp

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
