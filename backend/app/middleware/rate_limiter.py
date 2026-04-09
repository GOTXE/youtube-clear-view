"""Simple in-memory IP-based rate limiter for auth endpoints."""

import threading
import time


class _InMemoryRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._buckets = {}  # key -> [timestamp, ...]

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Return True if the request is allowed, False if rate-limited."""
        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            timestamps = [t for t in self._buckets.get(key, []) if t > cutoff]
            if len(timestamps) >= max_requests:
                self._buckets[key] = timestamps
                return False
            timestamps.append(now)
            self._buckets[key] = timestamps
            return True

    def reset(self, key: str) -> None:
        """Clear all records for a key (e.g. after successful login)."""
        with self._lock:
            self._buckets.pop(key, None)

    def cleanup(self, window_seconds: int = 3600) -> None:
        """Evict buckets that have been idle longer than window_seconds."""
        cutoff = time.monotonic() - window_seconds
        with self._lock:
            stale = [k for k, ts in self._buckets.items() if not any(t > cutoff for t in ts)]
            for k in stale:
                del self._buckets[k]


_limiter = _InMemoryRateLimiter()


def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """Return True if allowed, False if limited. Thread-safe.

    Skipped (always allowed) when Flask config RATE_LIMIT_ENABLED is False.
    """
    try:
        from flask import current_app
        if not current_app.config.get("RATE_LIMIT_ENABLED", True):
            return True
    except RuntimeError:
        pass  # No application context — allow by default
    return _limiter.is_allowed(key, max_requests, window_seconds)


def reset_rate_limit(key: str) -> None:
    """Reset the rate limit counter for a key."""
    _limiter.reset(key)
