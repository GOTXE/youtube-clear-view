"""User domain models."""

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.services.auth_security import decrypt_secret, encrypt_secret
from app.utils.time import utc_now


class User(db.Model):
    """Application user with preferences and session data."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(200))
    email = db.Column(db.String(255), index=True)
    auth_provider = db.Column(db.String(50), nullable=False, default="local")
    google_user_id = db.Column(db.String(255), unique=True, index=True)
    google_avatar_url = db.Column(db.String(500))
    _google_access_token = db.Column("google_access_token", db.String(4096))
    _google_refresh_token = db.Column("google_refresh_token", db.String(4096))
    google_token_expires_at = db.Column(db.DateTime)
    _google_scopes = db.Column("google_scopes", db.Text)
    google_auth_status = db.Column(db.String(32), nullable=False, default="not_linked")
    password_hash = db.Column(db.String(255))
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    setup_completed = db.Column(db.Boolean, nullable=False, default=False)
    login_attempts = db.Column(db.Integer, nullable=False, default=0)
    login_locked_until = db.Column(db.DateTime)
    _totp_secret = db.Column("totp_secret", db.String(4096))
    _totp_pending_secret = db.Column("totp_pending_secret", db.String(4096))
    totp_enabled = db.Column(db.Boolean, nullable=False, default=False)
    recovery_codes_hashes = db.Column(db.Text)
    theme_preference = db.Column(db.String(20), nullable=False, default="light")
    _legacy_session_token = db.Column("session_token", db.String(255), index=True)
    session_token_hash = db.Column(db.String(64), index=True)
    session_created_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    themes = db.relationship("Theme", back_populates="user", cascade="all, delete-orphan")
    user_channels = db.relationship("UserChannel", back_populates="user", cascade="all, delete-orphan")
    watched_videos = db.relationship("WatchedVideo", back_populates="user", cascade="all, delete-orphan")
    devices = db.relationship("UserDevice", back_populates="user", cascade="all, delete-orphan")
    passkeys = db.relationship("UserPasskey", back_populates="user", cascade="all, delete-orphan")
    sessions = db.relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    approved_pairings = db.relationship("LoginPairing", back_populates="approved_user")
    settings = db.relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def google_access_token(self):
        """Return the decrypted Google access token."""
        return decrypt_secret(self._google_access_token)

    @google_access_token.setter
    def google_access_token(self, value):
        """Persist the Google access token encrypted at rest."""
        self._google_access_token = encrypt_secret(value)

    @property
    def google_refresh_token(self):
        """Return the decrypted Google refresh token."""
        return decrypt_secret(self._google_refresh_token)

    @google_refresh_token.setter
    def google_refresh_token(self, value):
        """Persist the Google refresh token encrypted at rest."""
        self._google_refresh_token = encrypt_secret(value)

    @property
    def google_scopes(self):
        """Return the decrypted Google scopes payload."""
        return decrypt_secret(self._google_scopes)

    @google_scopes.setter
    def google_scopes(self, value):
        """Persist OAuth scopes encrypted at rest."""
        self._google_scopes = encrypt_secret(value)

    @property
    def session_token(self):
        """Expose the legacy raw session token column for compatibility only."""
        return self._legacy_session_token

    @session_token.setter
    def session_token(self, value):
        """Allow clearing or reading the legacy raw session token field."""
        self._legacy_session_token = value

    @property
    def totp_secret(self):
        """Return the decrypted active TOTP secret."""
        return decrypt_secret(self._totp_secret)

    @totp_secret.setter
    def totp_secret(self, value):
        """Persist the active TOTP secret encrypted at rest."""
        self._totp_secret = encrypt_secret(value)

    @property
    def totp_pending_secret(self):
        """Return the decrypted pending TOTP secret."""
        return decrypt_secret(self._totp_pending_secret)

    @totp_pending_secret.setter
    def totp_pending_secret(self, value):
        """Persist a pending TOTP secret encrypted at rest."""
        self._totp_pending_secret = encrypt_secret(value)

    def set_password(self, password):
        """Hash and store a new password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Return True if password matches stored hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def is_locked(self):
        """Return True if account is temporarily locked due to failed attempts."""
        if self.login_locked_until is None:
            return False
        return utc_now() < self.login_locked_until

    @property
    def has_any_credential(self):
        """Return True if the user has at least one auth credential set up."""
        return bool(self.password_hash) or bool(self.passkeys)

    def to_dict(self):
        """Serialize the user for JSON responses."""
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "email": self.email,
            "auth_provider": self.auth_provider,
            "google_avatar_url": self.google_avatar_url,
            "google_auth_status": self.google_auth_status,
            "is_admin": bool(self.is_admin),
            "is_active": bool(self.is_active),
            "must_change_password": bool(self.must_change_password),
            "totp_enabled": self.totp_enabled,
            "setup_completed": self.setup_completed,
            "has_password": bool(self.password_hash),
            "theme_preference": self.theme_preference,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
