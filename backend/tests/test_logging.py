"""Logging formatter tests."""

import logging
from datetime import UTC, datetime

from app.logging.logger import AppFormatter, set_runtime_log_timezone


def test_app_formatter_uses_configured_timezone():
    formatter = AppFormatter("[%(asctime)s] %(message)s", timezone_name="Europe/Madrid")
    record = logging.makeLogRecord({"msg": "hello"})
    record.created = datetime(2026, 3, 24, 18, 0, 0, tzinfo=UTC).timestamp()

    formatted_time = formatter.formatTime(record)

    assert formatted_time.startswith("2026-03-24 19:00:00,")


def test_set_runtime_log_timezone_updates_existing_handlers(monkeypatch):
    handler = logging.StreamHandler()
    handler.setFormatter(AppFormatter("[%(asctime)s] %(message)s", timezone_name="UTC"))
    root_logger = logging.getLogger()
    previous_handlers = list(root_logger.handlers)
    root_logger.handlers = [handler]
    try:
        normalized = set_runtime_log_timezone("Europe/Madrid")
        assert normalized == "Europe/Madrid"
        assert handler.formatter.timezone_name == "Europe/Madrid"
    finally:
        root_logger.handlers = previous_handlers
