"""Log viewer admin authentication and metadata tests."""

import sqlite3
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from log_viewer.app import app


def _init_database(db_path: Path):
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT,
            password_hash TEXT,
            is_admin BOOLEAN NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT 1
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE user_settings (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            quota_date TEXT,
            quota_used INTEGER DEFAULT 0
        )
        """
    )
    connection.execute(
        """
        INSERT INTO users (id, username, display_name, password_hash, is_admin, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, "admin", "Site Admin", generate_password_hash("secret"), 1, 1),
    )
    connection.execute(
        """
        INSERT INTO users (id, username, display_name, password_hash, is_admin, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (2, "viewer", "Viewer", generate_password_hash("secret"), 0, 1),
    )
    connection.execute(
        """
        INSERT INTO user_settings (id, user_id, quota_date, quota_used)
        VALUES (1, 1, date('now'), 123)
        """
    )
    connection.commit()
    connection.close()


@pytest.fixture()
def client(tmp_path):
    log_path = tmp_path / "app.log"
    log_path.write_text("[INFO] Test\n[ERROR] Boom\n")
    db_path = tmp_path / "yt_clear_view.db"
    _init_database(db_path)
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        LOG_FILE=str(log_path),
        DATABASE_URI=f"sqlite:///{db_path}",
        LOG_LEVEL="INFO",
        LOG_MAX_SIZE=1024,
        LOG_BACKUP_COUNT=3,
    )
    return app.test_client()


def test_requires_login_redirect(client):
    response = client.get("/logs")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/logs/login?next=/logs?")


def test_admin_can_login_and_open_logs(client):
    response = client.post(
        "/logs/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/logs")

    page = client.get("/logs")
    assert page.status_code == 200
    assert b"System Logs" in page.data


def test_non_admin_cannot_login(client):
    response = client.post(
        "/logs/login",
        data={"username": "viewer", "password": "secret"},
        follow_redirects=False,
    )
    assert response.status_code == 401


def test_entries(client):
    client.post("/logs/login", data={"username": "admin", "password": "secret"})
    response = client.get("/logs/api/entries")
    assert response.status_code == 200
    data = response.get_json()
    assert data["entries"][0].startswith("[ERROR]")


def test_stats_and_meta(client):
    client.post("/logs/login", data={"username": "admin", "password": "secret"})

    stats = client.get("/logs/api/stats")
    assert stats.status_code == 200
    assert stats.get_json()["levels"]["ERROR"] == 1

    meta = client.get("/logs/api/meta")
    assert meta.status_code == 200
    payload = meta.get_json()
    assert payload["log_runtime"]["rotate_enabled"] is True
    assert payload["quota"]["used"] == 123
