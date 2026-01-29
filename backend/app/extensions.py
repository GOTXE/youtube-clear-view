"""Flask extensions initialization."""

import sqlite3

from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

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


@event.listens_for(Engine, "connect")
def set_sqlite_pragmas(dbapi_connection, _connection_record):
    """Configure SQLite connections to reduce lock contention."""
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
