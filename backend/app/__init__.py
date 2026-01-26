"""Application factory for YT Clear View."""

import os
from flask import Flask

from .config import Config
from .extensions import db, init_extensions
from .logging.logger import configure_logging, get_logger
from .middleware.error_handler import register_error_handlers
from .migrations import (
    ensure_channel_schema,
    ensure_user_channel_schema,
    ensure_user_schema,
    ensure_video_schema,
)
from .routes import register_routes


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Validate configuration early.
    config_class.validate()

    # Configure logging before initializing extensions.
    configure_logging(
        app.config["LOG_LEVEL"],
        app.config["LOG_FILE"],
        app.config["LOG_MAX_SIZE"],
        app.config["LOG_BACKUP_COUNT"],
    )

    # Initialize Flask extensions.
    init_extensions(app)

    # Register routes and error handlers.
    register_routes(app)
    register_error_handlers(app)

    # Create database tables on first run.
    with app.app_context():
        db.create_all()
        ensure_user_schema()
        ensure_user_channel_schema()
        ensure_channel_schema()
        ensure_video_schema()
        os.makedirs(os.path.join(app.instance_path, "channel_thumbnails"), exist_ok=True)

    logger = get_logger(__name__)
    logger.info("Application initialized.", extra={"tracking_id": "SYSTEM"})

    return app
