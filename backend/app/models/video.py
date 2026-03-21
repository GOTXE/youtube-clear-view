"""Video domain models."""

from app.extensions import db
from app.utils.time import utc_now


class Video(db.Model):
    """YT video metadata stored for playback and filtering."""

    __tablename__ = "videos"

    id = db.Column(db.Integer, primary_key=True)
    yt_video_id = db.Column(db.String(120), unique=True, index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("channels.id"), nullable=False, index=True)
    title = db.Column(db.String(255), index=True)
    description = db.Column(db.Text, index=True)
    video_category_id = db.Column(db.String(20), index=True)
    tags = db.Column(db.Text)
    thumbnail_url = db.Column(db.String(500))
    published_at = db.Column(db.DateTime)
    duration = db.Column(db.Integer)
    fetched_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    channel = db.relationship("Channel", back_populates="videos")
    watched_entries = db.relationship("WatchedVideo", back_populates="video", cascade="all, delete-orphan")

    def to_dict(self):
        """Serialize the video for JSON responses."""
        return {
            "id": self.id,
            "yt_video_id": self.yt_video_id,
            "channel_id": self.channel_id,
            "title": self.title,
            "description": self.description,
            "video_category_id": self.video_category_id,
            "tags": self.tags,
            "thumbnail_url": self.thumbnail_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "duration": self.duration,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
        }


class WatchedVideo(db.Model):
    """Tracks watched videos per user and device."""

    __tablename__ = "watched_videos"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=False, index=True)
    watched_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    device_id = db.Column(db.Integer, db.ForeignKey("user_devices.id"), index=True)

    user = db.relationship("User", back_populates="watched_videos")
    video = db.relationship("Video", back_populates="watched_entries")
    device = db.relationship("UserDevice", back_populates="watched_videos")

    __table_args__ = (
        db.UniqueConstraint("user_id", "video_id", name="uq_user_video"),
    )

    def to_dict(self):
        """Serialize the watched video record for JSON responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "video_id": self.video_id,
            "device_id": self.device_id,
            "watched_at": self.watched_at.isoformat() if self.watched_at else None,
        }


class VideoProgress(db.Model):
    """Tracks playback position for resume functionality."""

    __tablename__ = "video_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=False, index=True)
    position_seconds = db.Column(db.Integer, nullable=False)
    duration_seconds = db.Column(db.Integer)
    is_continue_watching = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", backref="video_progress_entries")
    video = db.relationship("Video", backref="progress_entries")

    __table_args__ = (
        db.UniqueConstraint("user_id", "video_id", name="uq_user_video_progress"),
    )
