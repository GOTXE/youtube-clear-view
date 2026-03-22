"""Helpers for persisted site-wide settings."""

from __future__ import annotations

import json
from datetime import datetime

from flask import current_app

from app.extensions import db
from app.models import SiteSetting
from app.services.auth_policy import PASSWORD_POLICY_RULES, get_password_policy_rules


PASSWORD_POLICY_SETTING_KEY = "password_policy"
REFRESH_SCHEDULE_HOURS_KEY = "refresh_schedule_hours"
REFRESH_SCHEDULE_TIMEZONE_KEY = "refresh_schedule_timezone"
REFRESH_SCHEDULE_LAST_RUN_AT_KEY = "refresh_schedule_last_run_at"
LOG_LEVEL_SETTING_KEY = "log_level"
DEFAULT_REFRESH_SCHEDULE_HOURS = [7, 12, 17, 21]
DEFAULT_REFRESH_SCHEDULE_TIMEZONE = "Europe/Madrid"
DEFAULT_LOG_LEVEL = "INFO"


def _get_setting_record(setting_key: str) -> SiteSetting | None:
    return SiteSetting.query.filter_by(setting_key=setting_key).first()


def _set_setting_value(setting_key: str, value: str) -> str:
    record = _get_setting_record(setting_key)
    if not record:
        record = SiteSetting(setting_key=setting_key, setting_value=value)
        db.session.add(record)
    else:
        record.setting_value = value
    return value


def _sanitize_schedule_hours(hours) -> list[int]:
    safe = []
    for value in hours or []:
        try:
            hour = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= hour <= 23 and hour not in safe:
            safe.append(hour)
    return safe[:4]


def get_refresh_schedule_hours() -> list[int]:
    record = _get_setting_record(REFRESH_SCHEDULE_HOURS_KEY)
    if not record:
        return list(DEFAULT_REFRESH_SCHEDULE_HOURS)
    try:
        values = json.loads(record.setting_value or "[]")
    except (TypeError, ValueError):
        values = []
    hours = _sanitize_schedule_hours(values)
    return hours or list(DEFAULT_REFRESH_SCHEDULE_HOURS)


def set_refresh_schedule_hours(hours) -> list[int]:
    normalized = _sanitize_schedule_hours(hours)
    if not normalized:
        raise ValueError("At least one schedule hour is required.")
    _set_setting_value(REFRESH_SCHEDULE_HOURS_KEY, json.dumps(normalized))
    return normalized


def get_refresh_schedule_timezone() -> str:
    record = _get_setting_record(REFRESH_SCHEDULE_TIMEZONE_KEY)
    if not record or not record.setting_value.strip():
        return DEFAULT_REFRESH_SCHEDULE_TIMEZONE
    return record.setting_value.strip()


def set_refresh_schedule_timezone(timezone_name: str) -> str:
    normalized = (timezone_name or "").strip()
    if not normalized:
        raise ValueError("Invalid schedule timezone.")
    _set_setting_value(REFRESH_SCHEDULE_TIMEZONE_KEY, normalized)
    return normalized


def get_refresh_schedule_last_run_at() -> datetime | None:
    record = _get_setting_record(REFRESH_SCHEDULE_LAST_RUN_AT_KEY)
    if not record or not record.setting_value:
        return None
    try:
        return datetime.fromisoformat(record.setting_value)
    except ValueError:
        return None


def set_refresh_schedule_last_run_at(value: datetime | None) -> str | None:
    if value is None:
        _set_setting_value(REFRESH_SCHEDULE_LAST_RUN_AT_KEY, "")
        return None
    return _set_setting_value(REFRESH_SCHEDULE_LAST_RUN_AT_KEY, value.isoformat())


def serialize_refresh_schedule() -> dict[str, object]:
    return {
        "schedule_hours": get_refresh_schedule_hours(),
        "timezone": get_refresh_schedule_timezone(),
        "last_run_at": (
            get_refresh_schedule_last_run_at().isoformat()
            if get_refresh_schedule_last_run_at()
            else None
        ),
    }


def get_site_log_level(default: str | None = None) -> str:
    record = _get_setting_record(LOG_LEVEL_SETTING_KEY)
    value = record.setting_value.strip().upper() if record and record.setting_value else ""
    if value in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
      return value
    fallback = (default or current_app.config.get("LOG_LEVEL") or DEFAULT_LOG_LEVEL).strip().upper()
    return fallback if fallback in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else DEFAULT_LOG_LEVEL


def set_site_log_level(level_name: str) -> str:
    normalized = (level_name or "").strip().upper()
    if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("Invalid log level.")
    return _set_setting_value(LOG_LEVEL_SETTING_KEY, normalized)


def get_password_policy() -> str:
    """Return the active password policy, using DB override over config default."""
    record = _get_setting_record(PASSWORD_POLICY_SETTING_KEY)
    if record and record.setting_value in PASSWORD_POLICY_RULES:
        return record.setting_value
    return (current_app.config.get("PASSWORD_POLICY") or "strong").strip().lower()


def set_password_policy(policy_name: str) -> str:
    """Persist a new global password policy."""
    normalized = (policy_name or "").strip().lower()
    if normalized not in PASSWORD_POLICY_RULES:
        raise ValueError("Invalid password policy.")

    return _set_setting_value(PASSWORD_POLICY_SETTING_KEY, normalized)


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
