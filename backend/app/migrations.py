"""Lightweight SQLite schema updates for development."""

from sqlalchemy import text

from app.extensions import db
from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id


def ensure_user_schema():
    """Ensure newer user columns exist in SQLite dev databases."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(users)")).fetchall()
            if not result:
                return

            columns = {row[1] for row in result}
            additions = [
                ("email", "VARCHAR(255)"),
                ("auth_provider", "VARCHAR(50) NOT NULL DEFAULT 'local'"),
                ("google_user_id", "VARCHAR(255)"),
                ("google_avatar_url", "VARCHAR(500)"),
                ("google_access_token", "VARCHAR(2048)"),
                ("google_refresh_token", "VARCHAR(2048)"),
                ("google_token_expires_at", "DATETIME"),
                ("google_scopes", "TEXT"),
            ]

            for name, column_def in additions:
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {column_def}"))

            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_google_user_id "
                    "ON users (google_user_id)"
                )
            )
    except Exception as error:
        logger.warning(
            "User schema migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def ensure_user_channel_schema():
    """Ensure newer user channel columns exist in SQLite dev databases."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(user_channels)")).fetchall()
            if not result:
                return

            columns = {row[1] for row in result}
            if "last_refreshed_at" not in columns:
                conn.execute(text("ALTER TABLE user_channels ADD COLUMN last_refreshed_at DATETIME"))
    except Exception as error:
        logger.warning(
            "User channel schema migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def ensure_channel_schema():
    """Ensure channel identifier columns exist for YT naming."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(channels)")).fetchall()
            if not result:
                return

            columns = {row[1] for row in result}
            if "yt_channel_id" not in columns:
                conn.execute(text("ALTER TABLE channels ADD COLUMN yt_channel_id VARCHAR(120)"))
                if "youtube_channel_id" in columns:
                    conn.execute(
                        text(
                            "UPDATE channels SET yt_channel_id = youtube_channel_id "
                            "WHERE yt_channel_id IS NULL"
                        )
                    )
                conn.execute(
                    text("CREATE UNIQUE INDEX IF NOT EXISTS uq_channels_yt_channel_id ON channels (yt_channel_id)")
                )
            if "youtube_channel_id" in columns:
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_channels_youtube_channel_id ON channels (youtube_channel_id)")
                )
    except Exception as error:
        logger.warning(
            "Channel schema migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def ensure_video_schema():
    """Ensure video identifier columns exist for YT naming."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(videos)")).fetchall()
            if not result:
                return

            columns = {row[1] for row in result}
            if "yt_video_id" not in columns:
                conn.execute(text("ALTER TABLE videos ADD COLUMN yt_video_id VARCHAR(120)"))
                if "youtube_video_id" in columns:
                    conn.execute(
                        text(
                            "UPDATE videos SET yt_video_id = youtube_video_id "
                            "WHERE yt_video_id IS NULL"
                        )
                    )
                conn.execute(
                    text("CREATE UNIQUE INDEX IF NOT EXISTS uq_videos_yt_video_id ON videos (yt_video_id)")
                )
            if "youtube_video_id" in columns:
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_videos_youtube_video_id ON videos (youtube_video_id)")
                )
    except Exception as error:
        logger.warning(
            "Video schema migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )
