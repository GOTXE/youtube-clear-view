"""Admin observability route tests."""

import pytest

from app import create_app
from app.extensions import db
from app.services.sqlite_metrics import reset_sqlite_metrics_for_tests, set_sqlite_metrics_enabled


class TestConfig:
    """Minimal configuration for admin observability tests."""

    FLASK_SECRET_KEY = "test"
    YT_API_KEY = "test"
    DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_DATABASE_URI = DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = "http://localhost"
    LOG_LEVEL = "INFO"
    LOG_FILE = "logs/test.log"
    LOG_MAX_SIZE = 1024 * 1024
    LOG_BACKUP_COUNT = 1
    LOG_VIEWER_USER = "test"
    LOG_VIEWER_PASSWORD = "test"
    LOG_VIEWER_PORT = 5551
    GUNICORN_WORKERS = 1
    ADMIN_USERNAMES = "admin"
    SQLITE_METRICS_ENABLED = False

    @staticmethod
    def validate():
        return None


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        reset_sqlite_metrics_for_tests()
        set_sqlite_metrics_enabled(False)
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client, username):
    return client.post("/api/auth/login", json={"username": username})


def test_sqlite_observability_requires_admin(client):
    _login(client, "alice")
    response = client.get("/api/admin/observability/sqlite")
    assert response.status_code == 403


def test_admin_can_read_and_toggle_sqlite_observability(client):
    _login(client, "admin")

    response = client.get("/api/admin/observability/sqlite")
    assert response.status_code == 200
    data = response.get_json()
    assert data["enabled"] is False
    assert "write_count" in data
    assert "lock_error_count" in data
    assert "active_manual_refreshes" in data

    response = client.put("/api/admin/observability/sqlite", json={"enabled": True})
    assert response.status_code == 200
    toggled = response.get_json()
    assert toggled["enabled"] is True


def test_admin_can_inspect_runtime_state(client):
    _login(client, "admin")
    client.post(
        "/api/devices/register",
        json={"device_identifier": "runtime-admin", "user_agent": "ua"},
    )
    client.post("/api/auth/login", json={"username": "alice"})
    client.post(
        "/api/devices/register",
        json={"device_identifier": "runtime-alice", "user_agent": "ua"},
    )
    client.post("/api/auth/login", json={"username": "admin"})

    response = client.get("/api/admin/runtime-state")
    assert response.status_code == 200
    data = response.get_json()
    assert "users" in data
    assert any(user["username"] == "admin" for user in data["users"])
    assert any(user["device_count"] >= 1 for user in data["users"])


def test_sqlite_observability_rejects_invalid_toggle_payload(client):
    _login(client, "admin")
    response = client.put("/api/admin/observability/sqlite", json={"enabled": "yes"})
    assert response.status_code == 400
