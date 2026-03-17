"""Theme route tests."""

import pytest

from app import create_app
from app.extensions import db
from app.models import Channel, Theme, ThemeChannel, User, UserChannel


class TestConfig:
    """Minimal configuration for theme tests."""

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
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client, username):
    # Try to register (creates + logs in for fresh users).
    # Fall back to legacy login for users pre-created without a password.
    reg = client.post("/api/auth/register", json={"username": username, "password": "testpassword123"})
    if reg.status_code == 201:
        return reg
    return client.post("/api/auth/login", json={"username": username, "password": "testpassword123"})


def _seed_channel(app, username):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, display_name=username)
            db.session.add(user)
            db.session.flush()
        channel = Channel(yt_channel_id="chan", title="Channel")
        db.session.add(channel)
        db.session.flush()
        db.session.add(UserChannel(user_id=user.id, channel_id=channel.id))
        db.session.commit()
        return user.id, channel.id


def test_create_and_list_themes(client, app):
    _login(client, "alice")
    response = client.post("/api/themes", json={"name": "Focus", "color": "#fff"})
    assert response.status_code == 201
    theme = response.get_json()
    assert theme["name"] == "Focus"

    response = client.get("/api/themes")
    themes = response.get_json()
    assert len(themes) == 1


def test_create_theme_requires_name_tracking_id(client):
    _login(client, "alice")
    response = client.post("/api/themes", json={})
    assert response.status_code == 400
    data = response.get_json()
    assert data.get("tracking_id")


def test_update_theme(client, app):
    _login(client, "bob")
    response = client.post("/api/themes", json={"name": "Old", "color": "#000"})
    theme_id = response.get_json()["id"]

    response = client.put(
        f"/api/themes/{theme_id}",
        json={"name": "New", "color": "#111"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["name"] == "New"


def test_add_remove_channel(client, app):
    _login(client, "carol")
    _, channel_id = _seed_channel(app, "carol")

    response = client.post("/api/themes", json={"name": "Theme", "color": "#123"})
    theme_id = response.get_json()["id"]

    response = client.post(
        f"/api/themes/{theme_id}/channels",
        json={"channel_id": channel_id},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["channels"][0]["id"] == channel_id

    response = client.delete(f"/api/themes/{theme_id}/channels/{channel_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["channels"] == []


def test_delete_theme(client, app):
    _login(client, "dave")
    response = client.post("/api/themes", json={"name": "Theme", "color": "#abc"})
    theme_id = response.get_json()["id"]

    response = client.delete(f"/api/themes/{theme_id}")
    assert response.status_code == 204

    response = client.get("/api/themes")
    assert response.get_json() == []


def test_user_isolation(client, app):
    _login(client, "erin")
    response = client.post("/api/themes", json={"name": "Secret", "color": "#fff"})
    theme_id = response.get_json()["id"]

    _login(client, "frank")
    response = client.put(f"/api/themes/{theme_id}", json={"name": "Hack"})
    assert response.status_code == 404
