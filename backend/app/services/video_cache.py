"""Simple thread-safe in-memory cache with TTL support."""

import threading
import time


class VideoCache:
    """In-memory cache for API responses with TTL expiration."""

    def __init__(self):
        self._lock = threading.Lock()
        self._data = {}

    def get(self, key):
        """Return cached value if present and not expired."""
        now = time.time()
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if expires_at is not None and expires_at <= now:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key, value, ttl=None):
        """Store value with optional TTL in seconds."""
        expires_at = None
        if ttl is not None:
            expires_at = time.time() + ttl
        with self._lock:
            self._data[key] = (expires_at, value)

    def invalidate(self, key):
        """Remove a single cache entry."""
        with self._lock:
            self._data.pop(key, None)

    def clear(self):
        """Clear all cached entries."""
        with self._lock:
            self._data.clear()
