"""Channel domain models."""

from app.extensions import db
from app.utils.time import utc_now


class Channel(db.Model):
    """YT channel stored locally for subscriptions and themes."""

    __tablename__ = "channels"

    id = db.Column(db.Integer, primary_key=True)
    yt_channel_id = db.Column(db.String(120), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255))
    thumbnail_url = db.Column(db.String(500))
    thumbnail_cache_path = db.Column(db.String(500))
    thumbnail_cached_at = db.Column(db.DateTime)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    # Classification metadata
    topic_ids = db.Column(db.Text)
    keywords = db.Column(db.Text)
    country = db.Column(db.String(2))

    # Relationships
    user_channels = db.relationship("UserChannel", back_populates="channel", cascade="all, delete-orphan")
    videos = db.relationship("Video", back_populates="channel", cascade="all, delete-orphan")
    theme_channels = db.relationship("ThemeChannel", back_populates="channel", cascade="all, delete-orphan")
    channel_category = db.relationship("ChannelCategory", back_populates="channel", uselist=False, cascade="all, delete-orphan")

    def to_dict(self, include_category=False):
        """Serialize the channel for JSON responses."""
        import json
        data = {
            "id": self.id,
            "yt_channel_id": self.yt_channel_id,
            "title": self.title,
            "thumbnail_url": self.thumbnail_url,
            "description": self.description,
            "topic_ids": json.loads(self.topic_ids) if self.topic_ids else None,
            "keywords": self.keywords,
            "country": self.country,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_category and self.channel_category:
            data["category"] = self.channel_category.to_dict()
        return data


class UserChannel(db.Model):
    """Subscription link between users and channels."""

    __tablename__ = "user_channels"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("channels.id"), nullable=False, index=True)
    subscribed_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    last_refreshed_at = db.Column(db.DateTime)
    last_checked_at = db.Column(db.DateTime)

    # Rating system (1-5 stars)
    rating = db.Column(db.Integer, index=True)
    rated_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="user_channels")
    channel = db.relationship("Channel", back_populates="user_channels")

    __table_args__ = (
        db.UniqueConstraint("user_id", "channel_id", name="uq_user_channel"),
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_rating_range"),
    )

    def to_dict(self):
        """Serialize the user-channel link for JSON responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "subscribed_at": self.subscribed_at.isoformat() if self.subscribed_at else None,
            "last_refreshed_at": self.last_refreshed_at.isoformat() if self.last_refreshed_at else None,
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "rating": self.rating,
            "rated_at": self.rated_at.isoformat() if self.rated_at else None,
        }
