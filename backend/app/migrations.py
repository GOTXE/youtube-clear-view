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
                ("password_hash", "VARCHAR(255)"),
                ("is_admin", "BOOLEAN NOT NULL DEFAULT 0"),
                ("is_active", "BOOLEAN NOT NULL DEFAULT 1"),
                ("must_change_password", "BOOLEAN NOT NULL DEFAULT 0"),
                ("setup_completed", "BOOLEAN NOT NULL DEFAULT 0"),
                ("login_attempts", "INTEGER NOT NULL DEFAULT 0"),
                ("login_locked_until", "DATETIME"),
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
                    "WHEN google_auth_status = 'revoked' THEN 'revoked' "
                    "WHEN auth_provider = 'google' "
                    "AND ((google_refresh_token IS NOT NULL AND google_refresh_token != '') "
                    "OR (google_access_token IS NOT NULL AND google_access_token != '')) "
                    "THEN 'active' "
                    "WHEN auth_provider = 'google' THEN 'needs_reauth' "
                    "ELSE 'not_linked' END "
                    "WHERE google_auth_status IS NULL "
                    "OR google_auth_status = '' "
                    "OR google_auth_status = 'not_linked' "
                    "OR google_auth_status = 'needs_reauth'"
                )
            )
            # 5.1: mark existing established users as setup_completed to avoid
            # forcing the wizard on users who already had working accounts.
            conn.execute(
                text(
                    "UPDATE users SET setup_completed = 1 "
                    "WHERE setup_completed = 0 "
                    "AND (google_user_id IS NOT NULL OR password_hash IS NOT NULL)"
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
            if "last_feed_checked_at" not in columns:
                conn.execute(text("ALTER TABLE user_channels ADD COLUMN last_feed_checked_at DATETIME"))
            if "last_feed_success_at" not in columns:
                conn.execute(text("ALTER TABLE user_channels ADD COLUMN last_feed_success_at DATETIME"))
            if "last_feed_error_at" not in columns:
                conn.execute(text("ALTER TABLE user_channels ADD COLUMN last_feed_error_at DATETIME"))
            if "feed_error_count" not in columns:
                conn.execute(
                    text("ALTER TABLE user_channels ADD COLUMN feed_error_count INTEGER NOT NULL DEFAULT 0")
                )
            if "refresh_mode_override" not in columns:
                conn.execute(text("ALTER TABLE user_channels ADD COLUMN refresh_mode_override VARCHAR(20)"))
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
            if "discovered_via" not in columns:
                conn.execute(
                    text("ALTER TABLE videos ADD COLUMN discovered_via VARCHAR(20) NOT NULL DEFAULT 'api'")
                )
            if "metadata_incomplete" not in columns:
                conn.execute(
                    text("ALTER TABLE videos ADD COLUMN metadata_incomplete BOOLEAN NOT NULL DEFAULT 0")
                )
            if "source_last_seen_at" not in columns:
                conn.execute(text("ALTER TABLE videos ADD COLUMN source_last_seen_at DATETIME"))
            if "feed_published_at" not in columns:
                conn.execute(text("ALTER TABLE videos ADD COLUMN feed_published_at DATETIME"))
            if "feed_updated_at" not in columns:
                conn.execute(text("ALTER TABLE videos ADD COLUMN feed_updated_at DATETIME"))
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_videos_discovered_via ON videos (discovered_via)")
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_videos_metadata_incomplete "
                    "ON videos (metadata_incomplete)"
                )
            )
            conn.execute(
                text(
                    "UPDATE videos "
                    "SET thumbnail_url = 'https://i.ytimg.com/vi/' || yt_video_id || '/hqdefault.jpg' "
                    "WHERE yt_video_id IS NOT NULL "
                    "AND yt_video_id != '' "
                    "AND (thumbnail_url IS NULL OR thumbnail_url = '')"
                )
            )
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


def ensure_refresh_job_schema():
    """Ensure refresh_jobs table exists for backend-owned refresh execution."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS refresh_jobs ("
                    "id INTEGER NOT NULL PRIMARY KEY, "
                    "user_id INTEGER NOT NULL, "
                    "kind VARCHAR(20) NOT NULL DEFAULT 'manual', "
                    "scope_type VARCHAR(20) NOT NULL DEFAULT 'all_channels', "
                    "scope_channel_id INTEGER, "
                    "status VARCHAR(20) NOT NULL DEFAULT 'queued', "
                    "message VARCHAR(255), "
                    "processed_channels INTEGER NOT NULL DEFAULT 0, "
                    "total_channels INTEGER NOT NULL DEFAULT 0, "
                    "new_videos INTEGER NOT NULL DEFAULT 0, "
                    "rate_limited BOOLEAN NOT NULL DEFAULT 0, "
                    "blocked_reason VARCHAR(64), "
                    "created_at DATETIME NOT NULL, "
                    "started_at DATETIME, "
                    "finished_at DATETIME, "
                    "FOREIGN KEY(user_id) REFERENCES users (id), "
                    "FOREIGN KEY(scope_channel_id) REFERENCES channels (id)"
                    ")"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_refresh_jobs_user_id "
                    "ON refresh_jobs (user_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_refresh_jobs_kind "
                    "ON refresh_jobs (kind)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_refresh_jobs_status "
                    "ON refresh_jobs (status)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_refresh_jobs_created_at "
                    "ON refresh_jobs (created_at)"
                )
            )
    except Exception as error:
        logger.warning(
            "Refresh job schema migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def ensure_quota_event_schema():
    """Ensure quota_events table exists for global YouTube quota accounting."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS quota_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        quota_day_pt VARCHAR(10) NOT NULL,
                        api_method VARCHAR(64) NOT NULL,
                        units INTEGER NOT NULL,
                        source VARCHAR(64),
                        success BOOLEAN NOT NULL DEFAULT 1,
                        user_id INTEGER REFERENCES users(id),
                        channel_id INTEGER REFERENCES channels(id),
                        tracking_id VARCHAR(64),
                        notes TEXT
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_quota_events_occurred_at ON quota_events (occurred_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_quota_events_quota_day_pt ON quota_events (quota_day_pt)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_quota_events_api_method ON quota_events (api_method)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_quota_events_source ON quota_events (source)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_quota_events_user_id ON quota_events (user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_quota_events_channel_id ON quota_events (channel_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_quota_events_tracking_id ON quota_events (tracking_id)"))
    except Exception as error:
        logger.warning(
            "Quota event schema migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def ensure_enrich_settings_columns():
    """Ensure user_settings table has enrich task columns."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(user_settings)")).fetchall()
            if not result:
                return

            columns = {row[1] for row in result}
            additions = [
                ("enrich_active", "BOOLEAN DEFAULT 0"),
                ("enrich_phase", "VARCHAR(20)"),
                ("enrich_cursor", "INTEGER DEFAULT 0"),
                ("enrich_total", "INTEGER DEFAULT 0"),
                ("enrich_classified", "INTEGER DEFAULT 0"),
                ("enrich_errors", "INTEGER DEFAULT 0"),
                ("enrich_started_at", "DATETIME"),
                ("auto_classify_date", "VARCHAR(10)"),
                ("auto_classify_attempts", "INTEGER DEFAULT 0"),
                ("auto_classify_last_attempt_at", "DATETIME"),
                ("last_security_reminder_at", "DATETIME"),
            ]

            for name, column_def in additions:
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE user_settings ADD COLUMN {name} {column_def}"))
                    logger.info("Added column %s to user_settings table", name)
    except Exception as error:
        logger.warning(
            "Enrich settings columns migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def ensure_site_settings_schema():
    """Ensure site_settings table exists for admin-managed global settings."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(site_settings)")).fetchall()
            if result:
                return

            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS site_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        setting_key VARCHAR(100) NOT NULL UNIQUE,
                        setting_value TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_site_settings_setting_key "
                    "ON site_settings (setting_key)"
                )
            )
    except Exception as error:
        logger.warning(
            "Site settings schema migration skipped: %s",
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
            if "tv_scale_confirmed_at" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE user_devices "
                        "ADD COLUMN tv_scale_confirmed_at DATETIME"
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
            if "display_name" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE user_devices "
                        "ADD COLUMN display_name VARCHAR(128)"
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


def ensure_login_pairing_schema():
    """Ensure login_pairings table exists for secondary-device pairing."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(login_pairings)")).fetchall()
            if result:
                return

            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS login_pairings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        public_id VARCHAR(64) NOT NULL,
                        pairing_code VARCHAR(16) NOT NULL,
                        device_identifier VARCHAR(128),
                        approved_user_id INTEGER,
                        approved_at DATETIME,
                        expires_at DATETIME NOT NULL,
                        used_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(approved_user_id) REFERENCES users(id)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_login_pairings_public_id "
                    "ON login_pairings (public_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_login_pairings_code "
                    "ON login_pairings (pairing_code)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_login_pairings_approved_user_id "
                    "ON login_pairings (approved_user_id)"
                )
            )
    except Exception as error:
        logger.warning(
            "Login pairing schema migration skipped: %s",
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


def ensure_video_progress_schema():
    """Ensure video_progress table exists for playback resume."""
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    logger = get_logger(__name__)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(video_progress)")).fetchall()
            if result:
                column_names = {row[1] for row in result}
                if "is_continue_watching" not in column_names:
                    conn.execute(text(
                        "ALTER TABLE video_progress "
                        "ADD COLUMN is_continue_watching INTEGER NOT NULL DEFAULT 1"
                    ))
                    logger.info("Added is_continue_watching to video_progress table")
                return

            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS video_progress ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "user_id INTEGER NOT NULL REFERENCES users(id), "
                "video_id INTEGER NOT NULL REFERENCES videos(id), "
                "position_seconds INTEGER NOT NULL, "
                "duration_seconds INTEGER, "
                "is_continue_watching INTEGER NOT NULL DEFAULT 1, "
                "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "UNIQUE(user_id, video_id))"
            ))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_video_progress_user_id ON video_progress (user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_video_progress_video_id ON video_progress (video_id)"))
            logger.info("Created video_progress table")
    except Exception as error:
        logger.warning(
            "Video progress schema migration skipped: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )
