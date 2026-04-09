"""Site-wide settings persisted in the database."""

from app.extensions import db
from app.utils.time import utc_now


class SiteSetting(db.Model):
    """Key/value store for site-level runtime configuration."""

    __tablename__ = "site_settings"

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    setting_value = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
