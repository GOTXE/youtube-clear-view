"""Passkey domain model."""

from app.extensions import db
from app.utils.time import utc_now


class UserPasskey(db.Model):
    """A WebAuthn credential registered for a user."""

    __tablename__ = "user_passkeys"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    label = db.Column(db.String(200))
    credential_id = db.Column(db.String(512), nullable=False, unique=True, index=True)
    public_key = db.Column(db.Text, nullable=False)
    sign_count = db.Column(db.Integer, nullable=False, default=0)
    transports = db.Column(db.Text)
    aaguid = db.Column(db.String(64))
    credential_device_type = db.Column(db.String(32))
    credential_backed_up = db.Column(db.Boolean, nullable=False, default=False)
    last_used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    user = db.relationship("User", back_populates="passkeys")

    def to_dict(self):
        """Serialize a passkey for API responses."""
        transports = []
        if self.transports:
            transports = [item for item in self.transports.split(",") if item]

        return {
            "id": self.id,
            "label": self.label,
            "credential_id": self.credential_id,
            "transports": transports,
            "aaguid": self.aaguid,
            "credential_device_type": self.credential_device_type,
            "credential_backed_up": self.credential_backed_up,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
