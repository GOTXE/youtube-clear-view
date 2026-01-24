"""Logging configuration helpers."""

import logging
import os
from logging.handlers import RotatingFileHandler

from colorlog import ColoredFormatter

_configured = False


class TrackingIdFilter(logging.Filter):
    """Ensure a tracking_id attribute exists on all log records."""

    def filter(self, record):
        if not hasattr(record, "tracking_id"):
            record.tracking_id = "-"
        return True


def configure_logging(level, log_file, max_bytes, backup_count):
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
        ColoredFormatter(
            "[%(asctime)s] [%(log_color)s%(levelname)s%(reset)s] "
            "[%(tracking_id)s] [%(name)s] %(message)s",
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
        logging.Formatter("[%(asctime)s] [%(levelname)s] [%(tracking_id)s] [%(name)s] %(message)s")
    )

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    _configured = True


def get_logger(name):
    """Return a logger for the given module name."""
    return logging.getLogger(name)
