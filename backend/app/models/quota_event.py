"""Quota ledger model for YouTube API usage."""

from app.extensions import db
from app.utils.time import utc_now


class QuotaEvent(db.Model):
    """Persist one logical quota consumption event for the project."""

    __tablename__ = "quota_events"

    id = db.Column(db.Integer, primary_key=True)
    occurred_at = db.Column(db.DateTime, nullable=False, default=utc_now, index=True)
    quota_day_pt = db.Column(db.String(10), nullable=False, index=True)
    api_method = db.Column(db.String(64), nullable=False, index=True)
    units = db.Column(db.Integer, nullable=False)
    source = db.Column(db.String(64), index=True)
    success = db.Column(db.Boolean, nullable=False, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("channels.id"), index=True)
    tracking_id = db.Column(db.String(64), index=True)
    notes = db.Column(db.Text)

    user = db.relationship("User")
    channel = db.relationship("Channel")

    def to_dict(self):
        """Serialize the quota ledger row."""
        return {
            "id": self.id,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "quota_day_pt": self.quota_day_pt,
            "api_method": self.api_method,
            "units": self.units,
            "source": self.source,
            "success": self.success,
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "tracking_id": self.tracking_id,
            "notes": self.notes,
        }
