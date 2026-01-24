"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

# Load environment variables from .env if present.
load_dotenv()


class Config:
    """Base configuration class for Flask."""

    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///youtube_clear_view.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
