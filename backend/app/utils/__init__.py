"""Utility helpers package."""

from datetime import UTC, datetime


def utc_now():
    """Return a naive UTC datetime without using deprecated stdlib APIs."""
    return datetime.now(UTC).replace(tzinfo=None)
