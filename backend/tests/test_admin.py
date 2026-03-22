"""Admin observability route tests."""

import pytest

from app import create_app
from app.extensions import db
from app.models import Channel, User, UserChannel, UserDevice, Video
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
    LOCAL_SIGNUP_ENABLED = True
    PASSWORD_POLICY = "simple"

    CSRF_ENABLED = False
    RATE_LIMIT_ENABLED = False

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
    headers = {"X-YTCV-Surface": "gestor"}
    # Try to register first. Then always perform a dedicated gestor login so
    # the admin-scoped cookie is issued after any role changes.
    reg = client.post(
        "/api/auth/register",
        json={"username": username, "password": "testpassword123"},
        headers=headers,
    )
    if username == "admin":
        with client.application.app_context():
            user = User.query.filter_by(username="admin").first()
            user.is_admin = True
            db.session.commit()
    if reg.status_code not in {201, 409}:
        return reg
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": "testpassword123"},
        headers=headers,
    )


def test_sqlite_observability_requires_admin(client):
    _login(client, "alice")
    response = client.get("/api/admin/observability/sqlite")
    assert response.status_code == 401


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
    _login(client, "alice")
    client.post(
        "/api/devices/register",
        json={"device_identifier": "runtime-alice", "user_agent": "ua"},
    )
    _login(client, "admin")

    response = client.get("/api/admin/runtime-state")
    assert response.status_code == 200
    data = response.get_json()
    assert "users" in data
    assert any(user["username"] == "admin" for user in data["users"])
    assert any(user["device_count"] >= 1 for user in data["users"])


def test_admin_can_read_summary_metrics(client):
    _login(client, "admin")
    _login(client, "alice")
    _login(client, "admin")

    with client.application.app_context():
        channel = Channel(yt_channel_id="chan-1", title="Channel One")
        db.session.add(channel)
        db.session.flush()
        db.session.add(UserChannel(user_id=1, channel_id=channel.id, feed_error_count=2))
        db.session.add(
            Video(
                channel_id=channel.id,
                yt_video_id="vid-1",
                title="Video One",
                discovered_via="rss",
                metadata_incomplete=True,
            )
        )
        db.session.add(
            UserDevice(
                user_id=1,
                device_identifier="admin-tv",
                device_type="tv",
                user_agent="ua",
            )
        )
        db.session.commit()

    response = client.get("/api/admin/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["users_total"] >= 2
    assert data["users_admin"] >= 1
    assert data["devices_total"] >= 1
    assert data["channels_total"] >= 1
    assert data["videos_total"] >= 1
    assert "channels_unclassified" in data
    assert "active_refreshes" in data
    assert data["videos_rss_incomplete"] >= 1
    assert data["channels_feed_errors"] >= 1
    assert data["video_refresh_mode"] in {"hybrid", "rss_preferred", "api_only"}


def test_sqlite_observability_rejects_invalid_toggle_payload(client):
    _login(client, "admin")
    response = client.put("/api/admin/observability/sqlite", json={"enabled": "yes"})
    assert response.status_code == 400


def test_admin_can_read_and_update_password_policy(client):
    _login(client, "admin")

    response = client.get("/api/admin/security/password-policy")
    assert response.status_code == 200
    data = response.get_json()
    assert data["password_policy"] == "simple"
    assert any(option["value"] == "unbreakable" for option in data["options"])

    response = client.put(
        "/api/admin/security/password-policy",
        json={"password_policy": "unbreakable"},
    )
    assert response.status_code == 200
    assert response.get_json()["password_policy"] == "unbreakable"


def test_admin_can_read_and_update_global_refresh_schedule(client):
    _login(client, "admin")

    response = client.get("/api/admin/refresh-schedule")
    assert response.status_code == 200
    data = response.get_json()
    assert data["schedule_hours"] == [7, 12, 17, 21]
    assert data["timezone"] == "Europe/Madrid"

    response = client.put(
        "/api/admin/refresh-schedule",
        json={
            "schedule_hours": [6, 14, 22],
            "timezone": "UTC",
        },
    )
    assert response.status_code == 200
    updated = response.get_json()
    assert updated["schedule_hours"] == [6, 14, 22]
    assert updated["timezone"] == "UTC"


def test_admin_can_read_and_update_video_refresh_mode(client):
    _login(client, "admin")

    response = client.get("/api/admin/video-refresh-mode")
    assert response.status_code == 200
    data = response.get_json()
    assert data["video_refresh_mode"] in {"hybrid", "rss_preferred", "api_only"}
    assert any(option["value"] == "rss_preferred" for option in data["options"])

    response = client.put(
        "/api/admin/video-refresh-mode",
        json={"video_refresh_mode": "rss_preferred"},
    )
    assert response.status_code == 200
    assert response.get_json()["video_refresh_mode"] == "rss_preferred"


def test_admin_can_list_users(client):
    _login(client, "admin")
    _login(client, "alice")
    _login(client, "admin")

    response = client.get("/api/admin/users")
    assert response.status_code == 200
    users = response.get_json()["users"]
    assert any(user["username"] == "admin" and user["is_admin"] is True for user in users)
    assert any(user["username"] == "alice" for user in users)


def test_admin_can_disable_and_enable_user(client):
    _login(client, "admin")
    _login(client, "alice")
    _login(client, "admin")

    with client.application.app_context():
        alice = User.query.filter_by(username="alice").first()
        alice_id = alice.id

    response = client.post(f"/api/admin/users/{alice_id}/disable")
    assert response.status_code == 200
    assert response.get_json()["is_active"] is False

    client.post("/api/auth/logout")
    blocked_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "testpassword123"},
    )
    assert blocked_login.status_code == 403

    _login(client, "admin")
    response = client.post(f"/api/admin/users/{alice_id}/enable")
    assert response.status_code == 200
    assert response.get_json()["is_active"] is True


def test_admin_can_reset_password_and_force_change(client):
    _login(client, "admin")
    _login(client, "alice")
    _login(client, "admin")

    with client.application.app_context():
        alice = User.query.filter_by(username="alice").first()
        alice_id = alice.id

    response = client.post(
        f"/api/admin/users/{alice_id}/reset-password",
        json={"temporary_password": "TempPassword123"},
    )
    assert response.status_code == 200
    assert response.get_json()["must_change_password"] is True

    client.post("/api/auth/logout")
    login_response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "TempPassword123"},
    )
    assert login_response.status_code == 200
    assert login_response.get_json()["password_change_required"] is True
