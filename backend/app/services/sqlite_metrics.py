"""Process-local SQLite observability helpers."""

from __future__ import annotations

from collections import deque
from threading import Lock
from time import perf_counter

from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.logging.logger import get_logger


logger = get_logger(__name__)

_state_lock = Lock()
_initialized = False
_enabled = False
_slow_write_ms = 100
_recent_writes = deque(maxlen=50)
_metrics = {
    "write_count": 0,
    "write_time_ms_total": 0.0,
    "write_time_ms_max": 0.0,
    "slow_write_count": 0,
    "lock_error_count": 0,
}


def _is_sqlite_connection(conn):
    return conn.engine.dialect.name == "sqlite"


def _is_write_statement(statement):
    if not statement:
        return False
    normalized = statement.lstrip().upper()
    return normalized.startswith(("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP"))


def initialize_sqlite_metrics(enabled=False, slow_write_ms=100):
    """Initialize SQLAlchemy event hooks exactly once."""
    global _initialized, _enabled, _slow_write_ms
    _enabled = bool(enabled)
    _slow_write_ms = max(int(slow_write_ms or 100), 1)
    if _initialized:
        return

    @event.listens_for(Engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if not _is_sqlite_connection(conn) or not _is_write_statement(statement):
            return
        context._ytcv_write_started_at = perf_counter()
        context._ytcv_write_statement = statement

    @event.listens_for(Engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if not _is_sqlite_connection(conn):
            return
        started_at = getattr(context, "_ytcv_write_started_at", None)
        if started_at is None:
            return

        duration_ms = (perf_counter() - started_at) * 1000
        record = {
            "duration_ms": round(duration_ms, 2),
            "statement": (getattr(context, "_ytcv_write_statement", "") or "").split(None, 1)[0].upper(),
        }

        with _state_lock:
            _metrics["write_count"] += 1
            _metrics["write_time_ms_total"] += duration_ms
            _metrics["write_time_ms_max"] = max(_metrics["write_time_ms_max"], duration_ms)
            if duration_ms >= _slow_write_ms:
                _metrics["slow_write_count"] += 1
                if _enabled:
                    logger.warning(
                        "SQLite slow write detected: %sms %s",
                        round(duration_ms, 2),
                        record["statement"],
                    )
            if _enabled:
                _recent_writes.append(record)

    @event.listens_for(Engine, "handle_error")
    def _handle_error(exception_context):
        if exception_context.engine.dialect.name != "sqlite":
            return
        original = exception_context.original_exception
        message = str(original).lower()
        if "database is locked" not in message:
            return
        with _state_lock:
            _metrics["lock_error_count"] += 1
        if _enabled:
            logger.warning("SQLite lock error observed.")

    _initialized = True


def set_sqlite_metrics_enabled(enabled):
    """Toggle detailed SQLite metrics capture."""
    global _enabled
    _enabled = bool(enabled)
    return _enabled


def get_sqlite_metrics_snapshot():
    """Return the current SQLite metrics snapshot."""
    with _state_lock:
        write_count = _metrics["write_count"]
        average_ms = _metrics["write_time_ms_total"] / write_count if write_count else 0.0
        return {
            "enabled": _enabled,
            "slow_write_threshold_ms": _slow_write_ms,
            "write_count": write_count,
            "write_time_ms_total": round(_metrics["write_time_ms_total"], 2),
            "write_time_ms_avg": round(average_ms, 2),
            "write_time_ms_max": round(_metrics["write_time_ms_max"], 2),
            "slow_write_count": _metrics["slow_write_count"],
            "lock_error_count": _metrics["lock_error_count"],
            "recent_writes": list(_recent_writes),
        }


def reset_sqlite_metrics_for_tests():
    """Reset process-local metrics state for tests."""
    with _state_lock:
        _metrics["write_count"] = 0
        _metrics["write_time_ms_total"] = 0.0
        _metrics["write_time_ms_max"] = 0.0
        _metrics["slow_write_count"] = 0
        _metrics["lock_error_count"] = 0
        _recent_writes.clear()
