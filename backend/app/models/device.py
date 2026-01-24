"""Device domain models."""

from datetime import datetime

from app.extensions import db


class UserDevice(db.Model):
    """Device registered for a user session."""

    __tablename__ = "user_devices"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    device_identifier = db.Column(db.String(255), unique=True, nullable=False, index=True)
    device_type = db.Column(
        db.Enum("tv", "tablet", "mobile", "desktop", name="device_type"),
        nullable=False,
    )
    user_agent = db.Column(db.String(500))
    last_used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="devices")
    watched_videos = db.relationship("WatchedVideo", back_populates="device")

    def to_dict(self):
        """Serialize the device for JSON responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_identifier": self.device_identifier,
            "device_type": self.device_type,
            "user_agent": self.user_agent,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
