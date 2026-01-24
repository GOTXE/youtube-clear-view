"""Application factory for YouTube Clear View."""

from flask import Flask

from .config import Config
from .extensions import init_extensions


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Flask extensions.
    init_extensions(app)

    return app
