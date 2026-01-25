"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

# Load environment variables from .env if present.
load_dotenv()


class Config:
    """Base configuration class for Flask."""

    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
    DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///youtube_clear_view.db")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5550"))
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")
    COOKIE_SECURE = os.getenv("COOKIE_SECURE")
    if COOKIE_SECURE is None:
        COOKIE_SECURE = not FLASK_DEBUG
    else:
        COOKIE_SECURE = COOKIE_SECURE.lower() == "true"

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")
    LOG_MAX_SIZE = int(os.getenv("LOG_MAX_SIZE", str(10 * 1024 * 1024)))
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    LOG_VIEWER_USER = os.getenv("LOG_VIEWER_USER")
    LOG_VIEWER_PASSWORD = os.getenv("LOG_VIEWER_PASSWORD")
    LOG_VIEWER_PORT = int(os.getenv("LOG_VIEWER_PORT", "5551"))

    GUNICORN_WORKERS = int(os.getenv("GUNICORN_WORKERS", "2"))
    ALLOW_DEV_SEED = os.getenv("ALLOW_DEV_SEED", "False").lower() == "true"

    SQLALCHEMY_DATABASE_URI = DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    @staticmethod
    def validate():
        """Validate critical configuration values."""
        if not Config.FLASK_SECRET_KEY:
            raise ValueError("FLASK_SECRET_KEY is required.")
        if not Config.FLASK_DEBUG and not Config.YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY is required in production.")

        origins = [origin.strip() for origin in Config.CORS_ORIGINS.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS is required.")
        if "*" in origins:
            raise ValueError("CORS_ORIGINS must be explicit (no wildcard '*').")

        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if Config.LOG_LEVEL.upper() not in valid_levels:
            raise ValueError("LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL.")
