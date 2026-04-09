"""WebAuthn/passkey helpers for auth v2."""

import base64
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from flask import current_app
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import options_to_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)


PASSKEY_CHALLENGE_TTL_SECONDS = 600


def encode_b64url(value: bytes) -> str:
    """Encode bytes using unpadded base64url."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def decode_b64url(value: str) -> bytes:
    """Decode an unpadded base64url string to bytes."""
    if not value:
        raise ValueError("Missing base64url value.")
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def get_passkey_rp_name() -> str:
    """Return the relying-party display name."""
    return current_app.config.get("PASSKEY_RP_NAME") or "YT Clear View"


def get_passkey_origin() -> str:
    """Return the primary allowed WebAuthn origin."""
    configured = (current_app.config.get("PASSKEY_ORIGIN") or current_app.config.get("FRONTEND_URL") or "").strip()
    if configured:
        return configured.rstrip("/")
    return "http://localhost:8080"


def get_passkey_allowed_origins() -> list[str]:
    """Return all allowed origins for passkey verification."""
    configured = current_app.config.get("PASSKEY_ALLOWED_ORIGINS", "") or ""
    origins = [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    primary = get_passkey_origin()
    if primary not in origins:
        origins.insert(0, primary)
    return origins


def get_passkey_rp_id() -> str:
    """Return the relying-party ID derived from config."""
    configured = (current_app.config.get("PASSKEY_RP_ID") or "").strip()
    if configured:
        return configured

    parsed = urlparse(get_passkey_origin())
    return parsed.hostname or "localhost"


def build_registration_options(user, existing_passkeys):
    """Build registration options for the current user."""
    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=decode_b64url(passkey.credential_id))
        for passkey in existing_passkeys
    ]
    options = generate_registration_options(
        rp_id=get_passkey_rp_id(),
        rp_name=get_passkey_rp_name(),
        user_name=user.email or user.username,
        user_id=str(user.id).encode("utf-8"),
        user_display_name=user.display_name or user.username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=exclude_credentials,
    )
    return json.loads(options_to_json(options)), encode_b64url(options.challenge)


def build_authentication_options():
    """Build usernameless authentication options for discoverable passkeys."""
    options = generate_authentication_options(
        rp_id=get_passkey_rp_id(),
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    return json.loads(options_to_json(options)), encode_b64url(options.challenge)


def verify_registration_credential(credential, expected_challenge: str):
    """Verify a registration credential and return the verified result."""
    return verify_registration_response(
        credential=credential,
        expected_challenge=decode_b64url(expected_challenge),
        expected_rp_id=get_passkey_rp_id(),
        expected_origin=get_passkey_allowed_origins(),
        require_user_verification=False,
    )


def verify_authentication_credential(credential, passkey, expected_challenge: str):
    """Verify an authentication assertion for a known passkey."""
    return verify_authentication_response(
        credential=credential,
        expected_challenge=decode_b64url(expected_challenge),
        expected_rp_id=get_passkey_rp_id(),
        expected_origin=get_passkey_allowed_origins(),
        credential_public_key=decode_b64url(passkey.public_key),
        credential_current_sign_count=passkey.sign_count,
        require_user_verification=False,
    )


def build_challenge_payload(challenge: str, user_id: int | None = None, label: str | None = None) -> dict:
    """Build a signed-session payload for a WebAuthn challenge."""
    payload = {
        "challenge": challenge,
        "issued_at": datetime.now(UTC).isoformat(),
    }
    if user_id is not None:
        payload["user_id"] = user_id
    if label:
        payload["label"] = label
    return payload


def challenge_is_valid(payload: dict | None, expected_user_id: int | None = None) -> bool:
    """Check whether a stored challenge payload is still valid."""
    if not payload or not payload.get("challenge") or not payload.get("issued_at"):
        return False

    if expected_user_id is not None and payload.get("user_id") != expected_user_id:
        return False

    try:
        issued_at = datetime.fromisoformat(payload["issued_at"])
    except ValueError:
        return False

    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=UTC)

    return datetime.now(UTC) - issued_at <= timedelta(seconds=PASSKEY_CHALLENGE_TTL_SECONDS)
