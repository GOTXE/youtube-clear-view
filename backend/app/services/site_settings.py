"""Helpers for persisted site-wide settings."""

from __future__ import annotations

from flask import current_app

from app.extensions import db
from app.models import SiteSetting
from app.services.auth_policy import PASSWORD_POLICY_RULES, get_password_policy_rules


PASSWORD_POLICY_SETTING_KEY = "password_policy"


def get_password_policy() -> str:
    """Return the active password policy, using DB override over config default."""
    record = SiteSetting.query.filter_by(setting_key=PASSWORD_POLICY_SETTING_KEY).first()
    if record and record.setting_value in PASSWORD_POLICY_RULES:
        return record.setting_value
    return (current_app.config.get("PASSWORD_POLICY") or "strong").strip().lower()


def set_password_policy(policy_name: str) -> str:
    """Persist a new global password policy."""
    normalized = (policy_name or "").strip().lower()
    if normalized not in PASSWORD_POLICY_RULES:
        raise ValueError("Invalid password policy.")

    record = SiteSetting.query.filter_by(setting_key=PASSWORD_POLICY_SETTING_KEY).first()
    if not record:
        record = SiteSetting(setting_key=PASSWORD_POLICY_SETTING_KEY, setting_value=normalized)
        db.session.add(record)
    else:
        record.setting_value = normalized
    return normalized


def serialize_password_policy() -> dict[str, object]:
    """Build the admin payload for the current password policy."""
    current_policy = get_password_policy()
    options = []
    for policy_name in ("simple", "strong", "unbreakable"):
        rules = get_password_policy_rules(policy_name)
        label = {
            "simple": "Simple",
            "strong": "Strong",
            "unbreakable": "Unbreakable",
        }[policy_name]
        options.append(
            {
                "value": policy_name,
                "label": label,
                "min_length": rules["min_length"],
                "requires_upper": rules["requires_upper"],
                "requires_lower": rules["requires_lower"],
                "requires_digit": rules["requires_digit"],
                "requires_symbol": rules["requires_symbol"],
            }
        )
    return {"password_policy": current_policy, "options": options}
