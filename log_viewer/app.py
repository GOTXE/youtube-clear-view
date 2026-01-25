"""Log viewer microservice with basic auth."""

import base64
import os
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables for local usage.
load_dotenv()

LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")
LOG_VIEWER_USER = os.getenv("LOG_VIEWER_USER")
LOG_VIEWER_PASSWORD = os.getenv("LOG_VIEWER_PASSWORD")


def _unauthorized():
    """Return a 401 response for unauthorized access."""
    return (
        "Unauthorized",
        401,
        {"WWW-Authenticate": 'Basic realm="Log Viewer"'},
    )


def _check_auth():
    """Validate HTTP Basic Authentication credentials."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return False

    try:
        decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False

    username, _, password = decoded.partition(":")
    expected_user = app.config.get("LOG_VIEWER_USER") or LOG_VIEWER_USER or ""
    expected_password = app.config.get("LOG_VIEWER_PASSWORD") or LOG_VIEWER_PASSWORD or ""
    return username == expected_user and password == expected_password


def require_basic_auth(func):
    """Decorator for Basic Auth protected routes."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not _check_auth():
            return _unauthorized()
        return func(*args, **kwargs)

    return wrapper


def _read_log_entries():
    """Read log file entries as a list of lines."""
    log_file = app.config.get("LOG_FILE") or LOG_FILE
    if not os.path.exists(log_file):
        return [], False

    return _tail_lines(log_file, 5000)


def _tail_lines(log_file, count):
    """Read the last N lines from a log file efficiently."""
    count = max(count, 1)
    buffer = b""
    line_count = 0
    more_available = False

    with open(log_file, "rb") as file_handle:
        file_handle.seek(0, os.SEEK_END)
        position = file_handle.tell()

        while position > 0 and line_count <= count:
            read_size = min(4096, position)
            position -= read_size
            file_handle.seek(position)
            buffer = file_handle.read(read_size) + buffer
            line_count = buffer.count(b"\n")

        more_available = position > 0

    lines = buffer.splitlines()
    if len(lines) > count:
        lines = lines[-count:]

    decoded = [line.decode("utf-8", errors="ignore") for line in lines]
    return decoded, more_available


def _filter_entries(entries, levels=None, search=None, tracking_id=None):
    """Filter log entries based on level, search text, and tracking ID."""
    filtered = []
    for entry in entries:
        if levels:
            if not any(f"[{level}]" in entry for level in levels):
                continue
        if tracking_id and tracking_id not in entry:
            continue
        if search and search.lower() not in entry.lower():
            continue
        filtered.append(entry)
    return filtered


@app.get("/")
@require_basic_auth
def root():
    """Redirect root to the log viewer page."""
    return redirect("/logs")


@app.get("/logs")
@require_basic_auth
def logs_page():
    """Render the log viewer page."""
    return render_template("logs.html")


@app.get("/logs/api/entries")
@require_basic_auth
def log_entries():
    """Return log entries with optional filtering and pagination."""
    levels_param = request.args.get("level", "")
    search = request.args.get("search")
    tracking_id = request.args.get("tracking_id")

    try:
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"error": "Invalid pagination values."}), 400

    if limit <= 0 or offset < 0:
        return jsonify({"error": "Invalid pagination values."}), 400

    levels = [level.strip().upper() for level in levels_param.split(",") if level.strip()]
    entries, more_available = _read_log_entries()
    filtered = _filter_entries(entries, levels=levels, search=search, tracking_id=tracking_id)

    total = len(filtered)
    end = max(total - offset, 0)
    start = max(end - limit, 0)
    sliced = list(reversed(filtered[start:end]))

    has_more = total - offset > limit or more_available
    next_offset = offset + limit if has_more else None

    return jsonify({"entries": sliced, "has_more": has_more, "next_offset": next_offset})


@app.get("/logs/api/stats")
@require_basic_auth
def log_stats():
    """Return basic log statistics for dashboards."""
    entries, _ = _read_log_entries()
    levels = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
    recent_errors = []

    for entry in entries:
        for level in levels:
            if f"[{level}]" in entry:
                levels[level] += 1
                if level in ("ERROR", "CRITICAL"):
                    recent_errors.append(entry)
                break

    return jsonify({"levels": levels, "recent_errors": list(reversed(recent_errors[-20:]))})


def create_app():
    """Create the log viewer Flask application."""
    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5551, debug=True)
