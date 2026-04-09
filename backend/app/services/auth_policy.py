"""Validation helpers for local account credentials."""

from __future__ import annotations

import re


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,64}$")

PASSWORD_POLICY_RULES = {
    "simple": {
        "min_length": 8,
        "requires_upper": False,
        "requires_lower": False,
        "requires_digit": False,
        "requires_symbol": False,
    },
    "strong": {
        "min_length": 12,
        "requires_upper": True,
        "requires_lower": True,
        "requires_digit": True,
        "requires_symbol": False,
    },
    "unbreakable": {
        "min_length": 16,
        "requires_upper": True,
        "requires_lower": True,
        "requires_digit": True,
        "requires_symbol": True,
    },
}


def sanitize_username_candidate(raw_value: str | None) -> str:
    """Build a safe username candidate from Google profile data."""
    value = (raw_value or "").strip()
    if not value:
        return ""

    normalized = []
    last_was_separator = False
    for char in value:
        if char.isalnum():
            normalized.append(char)
            last_was_separator = False
            continue
        if char in {".", "_", "-"} and not last_was_separator:
            normalized.append(char)
            last_was_separator = True
            continue
        if char.isspace() and not last_was_separator:
            normalized.append("-")
            last_was_separator = True

    candidate = "".join(normalized).strip("._-")
    return candidate[:64]


def validate_username(username: str | None) -> tuple[bool, str | None]:
    """Validate a local username for onboarding and profile updates."""
    normalized = (username or "").strip()
    if not normalized:
        return False, "Username is required."
    if not USERNAME_PATTERN.fullmatch(normalized):
        return (
            False,
            "Username must be 3-64 characters and use only letters, numbers, dot, hyphen, or underscore.",
        )
    return True, None


def get_password_policy_rules(policy_name: str) -> dict[str, bool | int]:
    """Return the normalized rule set for a password policy."""
    return PASSWORD_POLICY_RULES.get(policy_name, PASSWORD_POLICY_RULES["strong"])


def validate_password(password: str | None, policy_name: str) -> tuple[bool, str | None]:
    """Validate a password against the configured global policy."""
    value = password or ""
    rules = get_password_policy_rules(policy_name)
    min_length = int(rules["min_length"])
    if len(value) < min_length:
        return False, f"Password must be at least {min_length} characters."
    if rules["requires_upper"] and not any(char.isupper() for char in value):
        return False, "Password must include at least one uppercase letter."
    if rules["requires_lower"] and not any(char.islower() for char in value):
        return False, "Password must include at least one lowercase letter."
    if rules["requires_digit"] and not any(char.isdigit() for char in value):
        return False, "Password must include at least one number."
    if rules["requires_symbol"] and not any(not char.isalnum() for char in value):
        return False, "Password must include at least one symbol."
    return True, None

