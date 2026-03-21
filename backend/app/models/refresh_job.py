"""Refresh job persistence model."""

from app.extensions import db
from app.utils.time import utc_now


class RefreshJob(db.Model):
    """Persist scheduled and manual refresh execution state."""

    __tablename__ = "refresh_jobs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False, default="manual", index=True)
    scope_type = db.Column(db.String(20), nullable=False, default="all_channels")
    scope_channel_id = db.Column(db.Integer, db.ForeignKey("channels.id"))
    status = db.Column(db.String(20), nullable=False, default="queued", index=True)
    message = db.Column(db.String(255))
    processed_channels = db.Column(db.Integer, nullable=False, default=0)
    total_channels = db.Column(db.Integer, nullable=False, default=0)
    new_videos = db.Column(db.Integer, nullable=False, default=0)
    rate_limited = db.Column(db.Boolean, nullable=False, default=False)
    blocked_reason = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)

    user = db.relationship("User", backref="refresh_jobs")
    scope_channel = db.relationship("Channel")

    def to_dict(self):
        """Serialize a refresh job for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "kind": self.kind,
            "scope_type": self.scope_type,
            "scope_channel_id": self.scope_channel_id,
            "status": self.status,
            "message": self.message,
            "processed_channels": self.processed_channels,
            "total_channels": self.total_channels,
            "new_videos": self.new_videos,
            "rate_limited": bool(self.rate_limited),
            "blocked_reason": self.blocked_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
