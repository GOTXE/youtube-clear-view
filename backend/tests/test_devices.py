"""Device route tests."""

import pytest

from app import create_app
from app.extensions import db


class TestConfig:
    """Minimal configuration for device tests."""

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

    @staticmethod
    def validate():
        return None


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client, username):
    return client.post("/api/auth/login", json={"username": username})


def test_register_and_list_devices(client):
    _login(client, "alice")
    response = client.post(
        "/api/devices/register",
        json={"device_identifier": "abc", "user_agent": "ua"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["device_type"] in ("desktop", "tv", "tablet", "mobile")
    assert data["device_type_confirmed"] is False

    response = client.get("/api/devices")
    assert response.status_code == 200
    devices = response.get_json()
    assert len(devices) == 1


def test_update_device_type(client):
    _login(client, "bob")
    response = client.post(
        "/api/devices/register",
        json={"device_identifier": "dev", "user_agent": "ua"},
    )
    device_id = response.get_json()["id"]

    response = client.put(
        f"/api/devices/{device_id}/type",
        json={"device_type": "tv"},
    )
    assert response.status_code == 200
    assert response.get_json()["device_type"] == "tv"
    assert response.get_json()["device_type_confirmed"] is True


def test_register_device_returns_confirmation_state_for_existing_device(client):
    _login(client, "bob")
    response = client.post(
        "/api/devices/register",
        json={"device_identifier": "dev", "user_agent": "ua"},
    )
    device_id = response.get_json()["id"]

    client.put(
        f"/api/devices/{device_id}/type",
        json={"device_type": "tv"},
    )

    response = client.post(
        "/api/devices/register",
        json={"device_identifier": "dev", "user_agent": "ua"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["device_type"] == "tv"
    assert data["device_type_confirmed"] is True


def test_detect_device(client):
    _login(client, "carol")
    response = client.post(
        "/api/devices/detect",
        json={"screen_width": 1920, "screen_height": 1080},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["suggested_type"] == "tv"


def test_detect_device_invalid_tracking_id(client):
    _login(client, "carol")
    response = client.post(
        "/api/devices/detect",
        json={"screen_width": "bad", "screen_height": 0},
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data.get("tracking_id")


def test_update_device_preferences(client):
    _login(client, "gina")
    response = client.post(
        "/api/devices/register",
        json={"device_identifier": "prefs", "user_agent": "ua"},
    )
    device_id = response.get_json()["id"]

    response = client.put(
        f"/api/devices/{device_id}/preferences",
        json={
            "frontend_mode": "tv",
            "tv_scale": "XL",
            "screen_size_inches": 55,
            "viewing_distance_m": 2.8,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["frontend_mode"] == "tv"
    assert data["tv_scale"] == "XL"
    assert data["tv_scale_confirmed_at"] is not None
    assert data["screen_size_inches"] == 55
    assert data["viewing_distance_m"] == 2.8


def test_non_tv_preferences_clear_tv_scale_confirmation(client):
    _login(client, "helen")
    response = client.post(
        "/api/devices/register",
        json={"device_identifier": "prefs3", "user_agent": "ua"},
    )
    device_id = response.get_json()["id"]

    client.put(
        f"/api/devices/{device_id}/preferences",
        json={
            "frontend_mode": "tv",
            "tv_scale": "L",
            "screen_size_inches": 55,
            "viewing_distance_m": 2.2,
        },
    )

    response = client.put(
        f"/api/devices/{device_id}/preferences",
        json={"frontend_mode": "desktop_tablet", "tv_scale": None},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["frontend_mode"] == "desktop_tablet"
    assert data["tv_scale_confirmed_at"] is None


def test_update_device_preferences_invalid_mode(client):
    _login(client, "hugo")
    response = client.post(
        "/api/devices/register",
        json={"device_identifier": "prefs2", "user_agent": "ua"},
    )
    device_id = response.get_json()["id"]

    response = client.put(
        f"/api/devices/{device_id}/preferences",
        json={"frontend_mode": "cinema"},
    )
    assert response.status_code == 400


def test_delete_device(client):
    _login(client, "dave")
    response = client.post(
        "/api/devices/register",
        json={"device_identifier": "del", "user_agent": "ua"},
    )
    device_id = response.get_json()["id"]

    response = client.delete(f"/api/devices/{device_id}")
    assert response.status_code == 204


def test_device_user_isolation(client):
    _login(client, "erin")
    response = client.post(
        "/api/devices/register",
        json={"device_identifier": "iso", "user_agent": "ua"},
    )
    device_id = response.get_json()["id"]

    client.post("/api/auth/login", json={"username": "frank"})
    response = client.put(
        f"/api/devices/{device_id}/type",
        json={"device_type": "mobile"},
    )
    assert response.status_code == 404
