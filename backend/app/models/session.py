"""User session domain model."""

from app.extensions import db
from app.utils.time import utc_now


class UserSession(db.Model):
    """Server-side persisted session token hash."""

    __tablename__ = "user_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    last_used_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="sessions")
