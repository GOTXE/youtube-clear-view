"""Logging configuration helpers."""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

from colorlog import ColoredFormatter

_configured = False
DEFAULT_LOG_TIMEZONE = "Europe/Madrid"


def _resolve_timezone(timezone_name):
    normalized = str(timezone_name or "").strip() or DEFAULT_LOG_TIMEZONE
    try:
        return normalized, ZoneInfo(normalized)
    except Exception:
        return "UTC", ZoneInfo("UTC")


class _TimezoneFormatterMixin:
    """Format timestamps using the configured application timezone."""

    def __init__(self, *args, timezone_name=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_timezone(timezone_name or DEFAULT_LOG_TIMEZONE)

    def set_timezone(self, timezone_name):
        self.timezone_name, self._timezone = _resolve_timezone(timezone_name)

    def formatTime(self, record, datefmt=None):
        current_time = datetime.fromtimestamp(record.created, self._timezone)
        if datefmt:
            return current_time.strftime(datefmt)
        return current_time.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]


class AppFormatter(_TimezoneFormatterMixin, logging.Formatter):
    """Standard formatter that renders timestamps in the app timezone."""


class AppColoredFormatter(_TimezoneFormatterMixin, ColoredFormatter):
    """Colored formatter that renders timestamps in the app timezone."""


class TrackingIdFilter(logging.Filter):
    """Ensure a tracking_id attribute exists on all log records."""

    def filter(self, record):
        if not hasattr(record, "tracking_id"):
            record.tracking_id = "-"
        return True


def configure_logging(level, log_file, max_bytes, backup_count, timezone_name=DEFAULT_LOG_TIMEZONE):
    """Configure console and file logging once per process."""
    global _configured
    if _configured:
        return

    level_name = str(level).upper()
    level_value = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level_value)

    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level_value)
    console_handler.addFilter(TrackingIdFilter())
    console_handler.setFormatter(
        AppColoredFormatter(
            "[%(asctime)s] [%(log_color)s%(levelname)s%(reset)s] "
            "[%(tracking_id)s] [%(name)s] %(message)s",
            timezone_name=timezone_name,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )
    )

    file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    file_handler.setLevel(level_value)
    file_handler.addFilter(TrackingIdFilter())
    file_handler.setFormatter(
        AppFormatter(
            "[%(asctime)s] [%(levelname)s] [%(tracking_id)s] [%(name)s] %(message)s",
            timezone_name=timezone_name,
        )
    )

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    _configured = True


def set_runtime_log_level(level):
    """Update root logger and attached handlers for the current process."""
    level_name = str(level or "").upper()
    level_value = getattr(logging, level_name, logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level_value)
    for handler in root_logger.handlers:
        handler.setLevel(level_value)
    return level_name


def set_runtime_log_timezone(timezone_name):
    """Update attached formatters for the current worker process."""
    normalized_name, _ = _resolve_timezone(timezone_name)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        formatter = handler.formatter
        if formatter and hasattr(formatter, "set_timezone"):
            formatter.set_timezone(normalized_name)
    return normalized_name


def get_logger(name):
    """Return a logger for the given module name."""
    return logging.getLogger(name)
