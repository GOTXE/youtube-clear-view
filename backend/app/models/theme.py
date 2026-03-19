"""Theme domain models."""

from app.extensions import db
from app.utils.time import utc_now


class Theme(db.Model):
    """Custom theme grouping for channels."""

    __tablename__ = "themes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    color = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    user = db.relationship("User", back_populates="themes")
    theme_channels = db.relationship("ThemeChannel", back_populates="theme", cascade="all, delete-orphan")

    def to_dict(self):
        """Serialize the theme for JSON responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "color": self.color,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ThemeChannel(db.Model):
    """Association between themes and channels."""

    __tablename__ = "theme_channels"

    id = db.Column(db.Integer, primary_key=True)
    theme_id = db.Column(db.Integer, db.ForeignKey("themes.id"), nullable=False, index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("channels.id"), nullable=False, index=True)

    theme = db.relationship("Theme", back_populates="theme_channels")
    channel = db.relationship("Channel", back_populates="theme_channels")

    __table_args__ = (
        db.UniqueConstraint("theme_id", "channel_id", name="uq_theme_channel"),
    )

    def to_dict(self):
        """Serialize the theme-channel link for JSON responses."""
        return {
            "id": self.id,
            "theme_id": self.theme_id,
            "channel_id": self.channel_id,
        }
