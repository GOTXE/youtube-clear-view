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
                ("google_auth_status", "VARCHAR(32) NOT NULL DEFAULT 'not_linked'"),
                ("totp_secret", "VARCHAR(4096)"),
                ("totp_pending_secret", "VARCHAR(4096)"),
                ("totp_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
                ("recovery_codes_hashes", "TEXT"),
                ("session_token_hash", "VARCHAR(64)"),
            ]

            for name, column_def in additions:
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {column_def}"))

            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_users_session_token_hash ON users (session_token_hash)")
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_google_user_id "
                    "ON users (google_user_id)"
                )
            )
            conn.execute(
                text(
                    "UPDATE users SET google_auth_status = CASE "
                    "WHEN auth_provider = 'google' AND google_refresh_token IS NOT NULL THEN 'active' "
                    "WHEN auth_provider = 'google' THEN 'needs_reauth' "
                    "ELSE 'not_linked' END "
                    "WHERE google_auth_status IS NULL OR google_auth_status = ''"
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
            if "last_checked_at" not in columns:
                conn.execute(text("ALTER TABLE user_channels ADD COLUMN last_checked_at DATETIME"))
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
            if "thumbnail_cache_path" not in columns:
                conn.execute(text("ALTER TABLE channels ADD COLUMN thumbnail_cache_path VARCHAR(500)"))
            if "thumbnail_cached_at" not in columns:
                conn.execute(text("ALTER TABLE channels ADD COLUMN thumbnail_cached_at DATETIME"))
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
            if "video_category_id" not in columns:
                conn.execute(text("ALTER TABLE videos ADD COLUMN video_category_id VARCHAR(20)"))
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_videos_video_category_id ON videos (video_category_id)")
                )
            if "tags" not in columns:
                conn.execute(text("ALTER TABLE videos ADD COLUMN tags TEXT"))
    except Exception as error:
        logger.warning(
            "Video schema migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def ensure_user_settings_schema():
    """Ensure user_settings table exists for presets/scheduling."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(user_settings)")).fetchall()
            if result:
                return

            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL UNIQUE,
                        preset VARCHAR(20) NOT NULL DEFAULT 'standard',
                        schedule_hours TEXT NOT NULL DEFAULT '[7, 12, 17, 21]',
                        timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
                        backfill_active BOOLEAN DEFAULT 0,
                        backfill_cursor INTEGER,
                        backfill_started_at DATETIME,
                        backfill_last_run_at DATETIME,
                        last_schedule_run_at DATETIME,
                        quota_date VARCHAR(10),
                        quota_used INTEGER DEFAULT 0,
                        quota_cap INTEGER DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    )
                    """
                )
            )
    except Exception as error:
        logger.warning(
            "User settings schema migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def ensure_user_device_schema():
    """Ensure newer user device columns exist in SQLite dev databases."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(user_devices)")).fetchall()
            if not result:
                return

            columns = {row[1] for row in result}
            if "device_type_confirmed" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE user_devices "
                        "ADD COLUMN device_type_confirmed BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            if "frontend_mode" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE user_devices "
                        "ADD COLUMN frontend_mode VARCHAR(32)"
                    )
                )
            if "tv_scale" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE user_devices "
                        "ADD COLUMN tv_scale VARCHAR(8)"
                    )
                )
            if "screen_size_inches" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE user_devices "
                        "ADD COLUMN screen_size_inches INTEGER"
                    )
                )
            if "viewing_distance_m" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE user_devices "
                        "ADD COLUMN viewing_distance_m FLOAT"
                    )
                )
    except Exception as error:
        logger.warning(
            "User device schema migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def ensure_user_passkey_schema():
    """Ensure user_passkeys table exists for WebAuthn credentials."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(user_passkeys)")).fetchall()
            if result:
                return

            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_passkeys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        label VARCHAR(200),
                        credential_id VARCHAR(512) NOT NULL,
                        public_key TEXT NOT NULL,
                        sign_count INTEGER NOT NULL DEFAULT 0,
                        transports TEXT,
                        aaguid VARCHAR(64),
                        credential_device_type VARCHAR(32),
                        credential_backed_up BOOLEAN NOT NULL DEFAULT 0,
                        last_used_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_passkeys_credential_id "
                    "ON user_passkeys (credential_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_user_passkeys_user_id "
                    "ON user_passkeys (user_id)"
                )
            )
    except Exception as error:
        logger.warning(
            "User passkey schema migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def ensure_category_schema():
    """Ensure categories table exists and is seeded with predefined categories."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        from app.models import PREDEFINED_CATEGORIES

        with engine.begin() as conn:
            # Check if categories table exists
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='categories'")
            ).fetchone()

            if not result:
                # Create categories table
                conn.execute(text("""
                    CREATE TABLE categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(50) UNIQUE NOT NULL,
                        display_name_es VARCHAR(50) NOT NULL,
                        color VARCHAR(7) NOT NULL,
                        icon VARCHAR(10),
                        description TEXT,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX ix_categories_name ON categories (name)"))
                logger.info("Categories table created")

            existing_names = {
                row[0]
                for row in conn.execute(text("SELECT name FROM categories")).fetchall()
            }
            inserted = 0
            for category in PREDEFINED_CATEGORIES:
                if category["name"] in existing_names:
                    continue
                conn.execute(
                    text(
                        "INSERT INTO categories (name, display_name_es, color, icon, created_at) "
                        "VALUES (:name, :display_es, :color, :icon, CURRENT_TIMESTAMP)"
                    ),
                    {
                        "name": category["name"],
                        "display_es": category["display_name_es"],
                        "color": category["color"],
                        "icon": category["icon"],
                    },
                )
                inserted += 1

            if inserted:
                logger.info("Seeded %s missing predefined categories", inserted)
    except Exception as error:
        logger.warning(
            "Category schema migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def ensure_channel_category_schema():
    """Ensure channel_categories table exists for classification."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='channel_categories'")
            ).fetchone()

            if not result:
                conn.execute(text("""
                    CREATE TABLE channel_categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        channel_id INTEGER UNIQUE NOT NULL,
                        category_id INTEGER NOT NULL,
                        is_auto_classified BOOLEAN NOT NULL DEFAULT 1,
                        classification_method VARCHAR(20),
                        confidence_score FLOAT,
                        classified_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (channel_id) REFERENCES channels (id),
                        FOREIGN KEY (category_id) REFERENCES categories (id),
                        CHECK (classification_method IN ('youtube_topics', 'tfidf', 'manual')),
                        CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0)
                    )
                """))
                conn.execute(text("CREATE UNIQUE INDEX ix_channel_categories_channel_id ON channel_categories (channel_id)"))
                conn.execute(text("CREATE INDEX ix_channel_categories_category_id ON channel_categories (category_id)"))
                logger.info("Channel categories table created")
    except Exception as error:
        logger.warning(
            "Channel category schema migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def ensure_channel_classification_columns():
    """Ensure channels table has classification columns (topic_ids, keywords, country)."""
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
            additions = [
                ("topic_ids", "TEXT"),
                ("keywords", "TEXT"),
                ("country", "VARCHAR(2)"),
            ]

            for name, column_def in additions:
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE channels ADD COLUMN {name} {column_def}"))
                    logger.info(f"Added column {name} to channels table")
    except Exception as error:
        logger.warning(
            "Channel classification columns migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def ensure_user_channel_rating_columns():
    """Ensure user_channels table has rating columns."""
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
            if "rating" not in columns:
                conn.execute(text("ALTER TABLE user_channels ADD COLUMN rating INTEGER"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_channels_rating ON user_channels (rating)"))
                logger.info("Added rating column to user_channels table")
            if "rated_at" not in columns:
                conn.execute(text("ALTER TABLE user_channels ADD COLUMN rated_at DATETIME"))
                logger.info("Added rated_at column to user_channels table")
    except Exception as error:
        logger.warning(
            "User channel rating columns migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )
