"""Channel domain models."""

from datetime import datetime

from app.extensions import db


class Channel(db.Model):
    """YouTube channel stored locally for subscriptions and themes."""

    __tablename__ = "channels"

    id = db.Column(db.Integer, primary_key=True)
    youtube_channel_id = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255))
    thumbnail_url = db.Column(db.String(500))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    user_channels = db.relationship("UserChannel", back_populates="channel", cascade="all, delete-orphan")
    videos = db.relationship("Video", back_populates="channel", cascade="all, delete-orphan")
    theme_channels = db.relationship("ThemeChannel", back_populates="channel", cascade="all, delete-orphan")

    def to_dict(self):
        """Serialize the channel for JSON responses."""
        return {
            "id": self.id,
            "youtube_channel_id": self.youtube_channel_id,
            "title": self.title,
            "thumbnail_url": self.thumbnail_url,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserChannel(db.Model):
    """Subscription link between users and channels."""

    __tablename__ = "user_channels"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("channels.id"), nullable=False, index=True)
    subscribed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="user_channels")
    channel = db.relationship("Channel", back_populates="user_channels")

    __table_args__ = (
        db.UniqueConstraint("user_id", "channel_id", name="uq_user_channel"),
    )

    def to_dict(self):
        """Serialize the user-channel link for JSON responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "subscribed_at": self.subscribed_at.isoformat() if self.subscribed_at else None,
        }
