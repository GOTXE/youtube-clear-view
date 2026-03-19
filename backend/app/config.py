"""Application configuration loaded from environment variables."""

import os
import secrets

from dotenv import load_dotenv

# Load environment variables from .env if present.
load_dotenv()


def _resolve_secret_key():
    """Return FLASK_SECRET_KEY from env, or auto-generate and persist one.

    The key is stored in a file next to the database so it survives
    container rebuilds as long as the data volume is preserved.
    """
    env_key = os.getenv("FLASK_SECRET_KEY")
    if env_key:
        return env_key

    db_uri = os.getenv("DATABASE_URI", "sqlite:///yt_clear_view.db")
    if db_uri.startswith("sqlite:///"):
        db_path = db_uri.replace("sqlite:///", "", 1)
        key_dir = os.path.dirname(os.path.abspath(db_path)) if os.path.dirname(db_path) else "."
    else:
        key_dir = os.path.join(os.path.dirname(__file__), "..")

    key_file = os.path.join(key_dir, ".flask_secret_key")

    if os.path.isfile(key_file):
        with open(key_file, "r") as fh:
            stored = fh.read().strip()
            if stored:
                return stored

    new_key = secrets.token_hex(32)
    os.makedirs(key_dir, exist_ok=True)
    with open(key_file, "w") as fh:
        fh.write(new_key)
    return new_key


class Config:
    """Base configuration class for Flask."""

    FLASK_SECRET_KEY = _resolve_secret_key()
    YT_API_KEY = os.getenv("YT_API_KEY")
    DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///yt_clear_view.db")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5550"))
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")
    COOKIE_SECURE = os.getenv("COOKIE_SECURE")
    if COOKIE_SECURE is None:
        COOKIE_SECURE = not FLASK_DEBUG
    else:
        COOKIE_SECURE = COOKIE_SECURE.lower() == "true"

    _env_log_level = os.getenv("LOG_LEVEL")
    if _env_log_level:
        LOG_LEVEL = _env_log_level
    else:
        LOG_LEVEL = "DEBUG" if FLASK_DEBUG else "INFO"
    LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")
    LOG_MAX_SIZE = int(os.getenv("LOG_MAX_SIZE", str(10 * 1024 * 1024)))
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    LOG_VIEWER_USER = os.getenv("LOG_VIEWER_USER")
    LOG_VIEWER_PASSWORD = os.getenv("LOG_VIEWER_PASSWORD")
    LOG_VIEWER_PORT = int(os.getenv("LOG_VIEWER_PORT", "5551"))

    GUNICORN_WORKERS = int(os.getenv("GUNICORN_WORKERS", "2"))

    YT_DAILY_QUOTA = int(os.getenv("YT_DAILY_QUOTA", "10000"))
    YT_QUOTA_CAP_RATIO = float(os.getenv("YT_QUOTA_CAP_RATIO", "0.8"))
    YT_REFRESH_COST = int(os.getenv("YT_REFRESH_COST", "2"))
    SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "false").lower() == "true"
    SCHEDULER_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "60"))
    BACKFILL_INTERVAL_MINUTES = int(os.getenv("BACKFILL_INTERVAL_MINUTES", "15"))
    BACKFILL_MAX_CHANNELS = int(os.getenv("BACKFILL_MAX_CHANNELS", "50"))

    AUTH_MODE = os.getenv("AUTH_MODE", "local")
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
    GOOGLE_OAUTH_SCOPES = os.getenv(
        "GOOGLE_OAUTH_SCOPES",
        "openid email profile https://www.googleapis.com/auth/youtube.readonly",
    )
    FRONTEND_URL = os.getenv("FRONTEND_URL", "")

    SQLALCHEMY_DATABASE_URI = DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    if DATABASE_URI.startswith("sqlite"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "connect_args": {
                "check_same_thread": False,
                "timeout": 30,
            }
        }

    @staticmethod
    def validate():
        """Validate critical configuration values."""
        if not Config.FLASK_DEBUG and not Config.YT_API_KEY:
            raise ValueError("YT_API_KEY is required in production.")

        origins = [origin.strip() for origin in Config.CORS_ORIGINS.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS is required.")
        if "*" in origins:
            raise ValueError("CORS_ORIGINS must be explicit (no wildcard '*').")

        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if Config.LOG_LEVEL.upper() not in valid_levels:
            raise ValueError("LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL.")

        auth_mode = (Config.AUTH_MODE or "local").lower()
        if auth_mode not in ("local", "google"):
            raise ValueError("AUTH_MODE must be 'local' or 'google'.")

        if auth_mode == "google":
            missing = []
            if not Config.GOOGLE_CLIENT_ID:
                missing.append("GOOGLE_CLIENT_ID")
            if not Config.GOOGLE_CLIENT_SECRET:
                missing.append("GOOGLE_CLIENT_SECRET")
            if not Config.GOOGLE_REDIRECT_URI:
                missing.append("GOOGLE_REDIRECT_URI")
            if not Config.FRONTEND_URL:
                missing.append("FRONTEND_URL")
            if missing:
                raise ValueError(f"Missing Google OAuth config: {', '.join(missing)}")

        if Config.YT_DAILY_QUOTA <= 0:
            raise ValueError("YT_DAILY_QUOTA must be positive.")
        if not 0 < Config.YT_QUOTA_CAP_RATIO <= 1:
            raise ValueError("YT_QUOTA_CAP_RATIO must be between 0 and 1.")
