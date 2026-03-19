"""Pairing code domain model for secondary-device sign-in."""

from app.extensions import db
from app.utils.time import utc_now


class LoginPairing(db.Model):
    """A short-lived pairing request approved from another authenticated device."""

    __tablename__ = "login_pairings"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    pairing_code = db.Column(db.String(16), nullable=False, unique=True, index=True)
    device_identifier = db.Column(db.String(128))
    approved_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    approved_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    approved_user = db.relationship("User", back_populates="approved_pairings")

    def is_expired(self, now=None):
        """Return whether the pairing request is expired."""
        now = now or utc_now()
        return bool(self.expires_at and self.expires_at <= now)

    def to_dict(self):
        """Serialize the pairing request for API responses."""
        return {
            "public_id": self.public_id,
            "pairing_code": self.pairing_code,
            "device_identifier": self.device_identifier,
            "approved_user_id": self.approved_user_id,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
