"""Flask extensions initialization."""

from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

# Shared extension instances.
db = SQLAlchemy()
cors = CORS()


def _parse_origins(origins_value):
    """Parse a comma-separated origins string into a list."""
    return [origin.strip() for origin in origins_value.split(",") if origin.strip()]


def init_extensions(app):
    """Register Flask extensions with the app."""
    db.init_app(app)

    cors.init_app(
        app,
        resources={
            r"/api/*": {
                "origins": _parse_origins(app.config.get("CORS_ORIGINS", "")),
                "supports_credentials": True,
                "allow_headers": ["Content-Type", "X-Requested-With"],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            }
        },
    )
