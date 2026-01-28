"""User domain models."""

from datetime import datetime

from app.extensions import db


class User(db.Model):
    """Application user with preferences and session data."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(200))
    email = db.Column(db.String(255), index=True)
    auth_provider = db.Column(db.String(50), nullable=False, default="local")
    google_user_id = db.Column(db.String(255), unique=True, index=True)
    google_avatar_url = db.Column(db.String(500))
    google_access_token = db.Column(db.String(2048))
    google_refresh_token = db.Column(db.String(2048))
    google_token_expires_at = db.Column(db.DateTime)
    google_scopes = db.Column(db.Text)
    theme_preference = db.Column(db.String(20), nullable=False, default="light")
    session_token = db.Column(db.String(255), index=True)
    session_created_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    themes = db.relationship("Theme", back_populates="user", cascade="all, delete-orphan")
    user_channels = db.relationship("UserChannel", back_populates="user", cascade="all, delete-orphan")
    watched_videos = db.relationship("WatchedVideo", back_populates="user", cascade="all, delete-orphan")
    devices = db.relationship("UserDevice", back_populates="user", cascade="all, delete-orphan")
    settings = db.relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        """Serialize the user for JSON responses."""
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "email": self.email,
            "auth_provider": self.auth_provider,
            "google_avatar_url": self.google_avatar_url,
            "theme_preference": self.theme_preference,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
