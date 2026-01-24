"""Flask extensions initialization."""

from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

# Shared extension instances.
db = SQLAlchemy()
cors = CORS()


def init_extensions(app):
    """Register Flask extensions with the app."""
    db.init_app(app)
    cors.init_app(app)
