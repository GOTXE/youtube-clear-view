"""User settings model for presets and scheduling."""

import json
from datetime import datetime

from app.extensions import db

DEFAULT_SCHEDULE_HOURS = [7, 12, 17, 21]
DEFAULT_PRESET = "standard"


class UserSettings(db.Model):
    """Per-user settings for refresh presets and schedules."""

    __tablename__ = "user_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    preset = db.Column(db.String(20), nullable=False, default=DEFAULT_PRESET)
    schedule_hours = db.Column(db.Text, nullable=False, default=json.dumps(DEFAULT_SCHEDULE_HOURS))
    timezone = db.Column(db.String(64), nullable=False, default="UTC")
    backfill_active = db.Column(db.Boolean, default=False)
    backfill_cursor = db.Column(db.Integer)
    backfill_started_at = db.Column(db.DateTime)
    backfill_last_run_at = db.Column(db.DateTime)
    last_schedule_run_at = db.Column(db.DateTime)
    quota_date = db.Column(db.String(10))
    quota_used = db.Column(db.Integer, default=0)
    quota_cap = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", back_populates="settings")

    def get_schedule_hours(self):
        """Return schedule hours as a list of ints or None values."""
        try:
            values = json.loads(self.schedule_hours or "[]")
        except (TypeError, ValueError):
            values = []
        cleaned = []
        for value in values:
            if value is None:
                cleaned.append(None)
                continue
            try:
                hour = int(value)
            except (TypeError, ValueError):
                continue
            if 0 <= hour <= 23:
                cleaned.append(hour)
        return cleaned

    def set_schedule_hours(self, hours):
        """Persist schedule hours list to JSON."""
        safe = []
        for value in hours:
            if value is None:
                safe.append(None)
                continue
            try:
                hour = int(value)
            except (TypeError, ValueError):
                continue
            if 0 <= hour <= 23:
                safe.append(hour)
        self.schedule_hours = json.dumps(safe)

    def to_dict(self):
        """Serialize settings for API responses."""
        return {
            "preset": self.preset,
            "schedule_hours": self.get_schedule_hours(),
            "timezone": self.timezone,
            "backfill_active": self.backfill_active,
            "backfill_cursor": self.backfill_cursor,
            "quota_date": self.quota_date,
            "quota_used": self.quota_used,
            "quota_cap": self.quota_cap,
        }
