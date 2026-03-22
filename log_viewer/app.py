"""Log viewer microservice with admin database authentication."""

from datetime import UTC, datetime, timedelta
import os
import sqlite3
import time
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from dotenv import load_dotenv
from werkzeug.security import check_password_hash

app = Flask(__name__, static_url_path="/logs/static")
app.config["SESSION_COOKIE_NAME"] = "ytcv_log_viewer"
app.config["SESSION_COOKIE_PATH"] = "/logs"

# Load environment variables for local usage.
load_dotenv()

LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")
DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///yt_clear_view.db")
YT_DAILY_QUOTA = int(os.getenv("YT_DAILY_QUOTA", "10000"))
YT_QUOTA_CAP_RATIO = float(os.getenv("YT_QUOTA_CAP_RATIO", "0.8"))
MANUAL_REFRESH_RESERVED_QUOTA_RATIO = float(os.getenv("MANUAL_REFRESH_RESERVED_QUOTA_RATIO", "0.1"))
YT_REFRESH_COST = int(os.getenv("YT_REFRESH_COST", "2"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_MAX_SIZE = int(os.getenv("LOG_MAX_SIZE", str(10 * 1024 * 1024)))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

app.secret_key = os.getenv("FLASK_SECRET_KEY", "ytcv-log-viewer")
app.config["DATABASE_URI"] = DATABASE_URI
app.config["LOG_FILE"] = LOG_FILE
app.config["LOG_LEVEL"] = LOG_LEVEL
app.config["LOG_MAX_SIZE"] = LOG_MAX_SIZE
app.config["LOG_BACKUP_COUNT"] = LOG_BACKUP_COUNT


def _preferred_language():
    """Return the preferred UI language for the current request."""
    header = (request.headers.get("Accept-Language") or "").lower()
    return "es" if header.startswith("es") or ",es" in header else "en"


def _login_strings():
    """Return localized strings for the log viewer login."""
    if _preferred_language() == "es":
        return {
            "title": "YT Clear View - Logs",
            "brand": "Logs YT Clear View",
            "app_name": "YT CLEAR VIEW",
            "subtitle": "Accede con una cuenta administradora para usar el visor de logs.",
            "username": "Usuario",
            "password": "Contrasena",
            "submit": "Abrir logs",
            "invalid_credentials": "Credenciales de administrador no validas.",
            "report_issue": "Reportar problema",
        }
    return {
        "title": "YT Clear View - Logs",
        "brand": "YT Clear View Logs",
        "app_name": "YT CLEAR VIEW",
        "subtitle": "Sign in with an administrator account to view system logs.",
        "username": "Username",
        "password": "Password",
        "submit": "Open logs",
        "invalid_credentials": "Invalid administrator credentials.",
        "report_issue": "Report issue",
    }


def _database_path():
    """Return the SQLite file path from DATABASE_URI."""
    database_uri = app.config.get("DATABASE_URI") or DATABASE_URI
    if database_uri.startswith("sqlite:///"):
        path = database_uri.removeprefix("sqlite:///")
        if path.startswith("/"):
            return path
        return os.path.join(app.root_path, "..", path)
    raise ValueError("Only sqlite DATABASE_URI is supported by log viewer.")


def _db_connect():
    """Open a read-only SQLite connection."""
    connection = sqlite3.connect(_database_path())
    connection.row_factory = sqlite3.Row
    return connection


def _utc_now():
    """Return a naive UTC datetime."""
    return datetime.now(UTC).replace(tzinfo=None)


def _next_quota_reset_utc():
    """Return the next daily quota reset time in UTC."""
    now = _utc_now()
    tomorrow = (now + timedelta(days=1)).date()
    return datetime.combine(tomorrow, datetime.min.time())


def _server_timezone_label():
    """Return a human-readable local timezone label for log timestamps."""
    local_now = datetime.now().astimezone()
    offset = local_now.utcoffset() or timedelta(0)
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    tz_name = local_now.tzname() or "Local"
    return f"{tz_name} (UTC{sign}{hours:02d}:{minutes:02d})"


def _get_reserved_quota_units():
    """Return quota units reserved for scheduled updates."""
    reserved = int(YT_DAILY_QUOTA * MANUAL_REFRESH_RESERVED_QUOTA_RATIO)
    return max(reserved, YT_REFRESH_COST)


def _get_quota_snapshot():
    """Return aggregated quota information from user_settings."""
    today = _utc_now().date().isoformat()
    used = 0
    with _db_connect() as connection:
        rows = connection.execute(
            "SELECT quota_date, quota_used FROM user_settings"
        ).fetchall()

    for row in rows:
        if row["quota_date"] == today:
            used += int(row["quota_used"] or 0)

    app_cap = int(YT_DAILY_QUOTA * YT_QUOTA_CAP_RATIO)
    remaining_daily = max(YT_DAILY_QUOTA - used, 0)
    remaining_app_cap = max(app_cap - used, 0)
    return {
        "date": today,
        "used": used,
        "daily_limit": YT_DAILY_QUOTA,
        "app_cap": app_cap,
        "remaining_daily": remaining_daily,
        "remaining_app_cap": remaining_app_cap,
        "reserved_for_scheduled": _get_reserved_quota_units(),
        "reset_at_utc": _next_quota_reset_utc().isoformat(),
    }


def _get_log_runtime_meta():
    """Return current logging runtime metadata."""
    return {
        "level": app.config.get("LOG_LEVEL", LOG_LEVEL),
        "rotate_enabled": int(app.config.get("LOG_BACKUP_COUNT", LOG_BACKUP_COUNT)) > 0,
        "max_size_bytes": int(app.config.get("LOG_MAX_SIZE", LOG_MAX_SIZE)),
        "backup_count": int(app.config.get("LOG_BACKUP_COUNT", LOG_BACKUP_COUNT)),
        "timestamps_timezone": _server_timezone_label(),
        "timestamps_are_utc": time.tzname[0] == "UTC" and time.localtime().tm_isdst == 0,
    }


def _find_admin_user(username):
    """Return the active admin user row for the provided username."""
    with _db_connect() as connection:
        return connection.execute(
            """
            SELECT id, username, display_name, password_hash, is_admin, is_active
            FROM users
            WHERE lower(username) = lower(?)
            LIMIT 1
            """,
            (username,),
        ).fetchone()


def _authenticate_admin(username, password):
    """Validate admin credentials against the main database."""
    if not username or not password:
        return None
    row = _find_admin_user(username.strip())
    if row is None or not row["is_admin"] or not row["is_active"] or not row["password_hash"]:
        return None
    if not check_password_hash(row["password_hash"], password):
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"] or row["username"],
    }


def _current_admin():
    """Return the authenticated log viewer admin session."""
    admin_id = session.get("log_viewer_admin_id")
    username = session.get("log_viewer_admin_username")
    if not admin_id or not username:
        return None
    return {
        "id": admin_id,
        "username": username,
        "display_name": session.get("log_viewer_admin_display_name") or username,
    }


def require_admin_session(func):
    """Decorator for log viewer routes protected by admin session."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not _current_admin():
            if request.path.startswith("/logs/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login_page", next=request.full_path or request.path))
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
def root():
    """Redirect root to the log viewer page."""
    return redirect("/logs")


@app.get("/logs/login")
def login_page():
    """Render the log viewer login page."""
    if _current_admin():
        return redirect("/logs")
    return render_template("login.html", error=request.args.get("error"), ui=_login_strings())


@app.post("/logs/login")
def login_submit():
    """Authenticate an admin against the main database."""
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    user = _authenticate_admin(username, password)
    if user is None:
        return render_template(
            "login.html",
            error=_login_strings()["invalid_credentials"],
            ui=_login_strings(),
        ), 401

    session.clear()
    session["log_viewer_admin_id"] = user["id"]
    session["log_viewer_admin_username"] = user["username"]
    session["log_viewer_admin_display_name"] = user["display_name"]
    return redirect("/logs")


@app.post("/logs/logout")
@require_admin_session
def logout_submit():
    """Clear the current log viewer session."""
    session.clear()
    return redirect("/logs/login")


@app.get("/logs")
@require_admin_session
def logs_page():
    """Render the log viewer page."""
    return render_template("logs.html", current_admin=_current_admin())


@app.get("/logs/api/entries")
@require_admin_session
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
@require_admin_session
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


@app.get("/logs/api/meta")
@require_admin_session
def log_meta():
    """Return log viewer operational metadata."""
    return jsonify(
        {
            "log_runtime": _get_log_runtime_meta(),
            "quota": _get_quota_snapshot(),
            "current_admin": _current_admin(),
        }
    )


def create_app():
    """Create the log viewer Flask application."""
    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5551, debug=True)
