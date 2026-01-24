"""Video domain models."""

from datetime import datetime

from app.extensions import db


class Video(db.Model):
    """YouTube video metadata stored for playback and filtering."""

    __tablename__ = "videos"

    id = db.Column(db.Integer, primary_key=True)
    youtube_video_id = db.Column(db.String(120), unique=True, index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("channels.id"), nullable=False, index=True)
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    thumbnail_url = db.Column(db.String(500))
    published_at = db.Column(db.DateTime)
    duration = db.Column(db.Integer)
    fetched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    channel = db.relationship("Channel", back_populates="videos")
    watched_entries = db.relationship("WatchedVideo", back_populates="video", cascade="all, delete-orphan")

    def to_dict(self):
        """Serialize the video for JSON responses."""
        return {
            "id": self.id,
            "youtube_video_id": self.youtube_video_id,
            "channel_id": self.channel_id,
            "title": self.title,
            "description": self.description,
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
    watched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
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
