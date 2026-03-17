"""Device domain models."""

from datetime import datetime

from app.extensions import db


class UserDevice(db.Model):
    """Device registered for a user session."""

    __tablename__ = "user_devices"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    device_identifier = db.Column(db.String(255), nullable=False, index=True)
    device_type = db.Column(
        db.Enum("tv", "tablet", "mobile", "desktop", name="device_type"),
        nullable=False,
    )
    device_type_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    frontend_mode = db.Column(
        db.Enum("phone", "desktop_tablet", "tv", name="frontend_mode"),
        nullable=True,
    )
    tv_scale = db.Column(db.String(8))
    tv_scale_confirmed_at = db.Column(db.DateTime)
    screen_size_inches = db.Column(db.Integer)
    viewing_distance_m = db.Column(db.Float)
    user_agent = db.Column(db.String(500))
    last_used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="devices")
    watched_videos = db.relationship("WatchedVideo", back_populates="device")

    __table_args__ = (
        db.UniqueConstraint("user_id", "device_identifier", name="uq_user_device_identifier"),
    )

    def to_dict(self):
        """Serialize the device for JSON responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_identifier": self.device_identifier,
            "device_type": self.device_type,
            "device_type_confirmed": self.device_type_confirmed,
            "frontend_mode": self.frontend_mode,
            "tv_scale": self.tv_scale,
            "tv_scale_confirmed_at": (
                self.tv_scale_confirmed_at.isoformat() if self.tv_scale_confirmed_at else None
            ),
            "screen_size_inches": self.screen_size_inches,
            "viewing_distance_m": self.viewing_distance_m,
            "user_agent": self.user_agent,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
