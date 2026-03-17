"""TOTP and recovery code helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import quote

from werkzeug.security import check_password_hash, generate_password_hash


def generate_totp_secret() -> str:
    """Generate a base32-encoded TOTP secret."""
    return base64.b32encode(secrets.token_bytes(20)).decode("utf-8").rstrip("=")


def _normalize_secret(secret: str) -> bytes:
    """Normalize a base32 TOTP secret for decoding."""
    normalized = (secret or "").strip().replace(" ", "").upper()
    padding = "=" * (-len(normalized) % 8)
    return base64.b32decode(f"{normalized}{padding}", casefold=True)


def generate_totp_code(secret: str, for_time: float | None = None, step_seconds: int = 30) -> str:
    """Generate a TOTP code for a shared secret."""
    key = _normalize_secret(secret)
    timestamp = int(for_time if for_time is not None else time.time())
    counter = timestamp // step_seconds
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = (
        ((digest[offset] & 0x7F) << 24)
        | ((digest[offset + 1] & 0xFF) << 16)
        | ((digest[offset + 2] & 0xFF) << 8)
        | (digest[offset + 3] & 0xFF)
    )
    return str(binary % 1_000_000).zfill(6)


def verify_totp_code(secret: str, code: str, valid_window: int = 1, for_time: float | None = None) -> bool:
    """Verify a TOTP code within a small allowed time window."""
    normalized_code = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(normalized_code) != 6:
        return False

    base_time = float(for_time if for_time is not None else time.time())
    for offset in range(-valid_window, valid_window + 1):
        candidate_time = base_time + (offset * 30)
        if hmac.compare_digest(generate_totp_code(secret, candidate_time), normalized_code):
            return True
    return False


def build_totp_uri(secret: str, account_name: str, issuer: str = "YT Clear View") -> str:
    """Build an otpauth URI that authenticator apps can import."""
    label = quote(f"{issuer}:{account_name}")
    issuer_param = quote(issuer)
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer_param}&algorithm=SHA1&digits=6&period=30"


def generate_recovery_codes(count: int = 8) -> list[str]:
    """Generate human-readable recovery codes."""
    codes = []
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(count):
        left = "".join(secrets.choice(alphabet) for _ in range(4))
        right = "".join(secrets.choice(alphabet) for _ in range(4))
        codes.append(f"{left}-{right}")
    return codes


def hash_recovery_codes(codes: list[str]) -> list[str]:
    """Hash recovery codes for storage."""
    return [generate_password_hash(code) for code in codes]


def consume_recovery_code(stored_hashes: list[str] | None, candidate: str) -> tuple[bool, list[str]]:
    """Consume a recovery code if it matches one of the stored hashes."""
    normalized = (candidate or "").strip().upper()
    if not normalized or not stored_hashes:
        return False, stored_hashes or []

    remaining = []
    matched = False
    for code_hash in stored_hashes:
        if not matched and check_password_hash(code_hash, normalized):
            matched = True
            continue
        remaining.append(code_hash)
    return matched, remaining
