"""Development-only routes."""

from flask import Blueprint, current_app, g, jsonify

from app.middleware.auth_middleware import require_auth
from app.middleware.error_handler import handle_route_errors
from seed_db import seed_in_app


dev_bp = Blueprint("dev", __name__)


@dev_bp.post("/api/dev/seed")
@handle_route_errors
@require_auth
def seed_database():
    """Seed the database with sample data for local testing."""
    allow_seed = current_app.config.get("ALLOW_DEV_SEED", False)
    if not allow_seed:
        return jsonify({"error": "Forbidden."}), 403

    summary = seed_in_app(g.current_user.id)
    return jsonify(summary)
