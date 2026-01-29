"""Channel route tests with mocked YT service."""

from datetime import datetime, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import User, Video, WatchedVideo


class TestConfig:
    """Minimal configuration for channel tests."""

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


class FakeYTService:
    """Fake YT service for deterministic tests."""

    def __init__(self, api_key):
        self.api_key = api_key

    def get_channel_info(self, channel_id):
        return {
            "channel_id": channel_id,
            "title": "Test Channel",
            "description": "Demo",
            "thumbnail": "http://thumb",
        }

    def get_channel_videos(self, channel_id, max_results=50, page_token=None):
        published_at = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "videos": [
                {
                    "video_id": "vid-1",
                    "title": "Test Video",
                    "description": "Desc",
                    "thumbnail": "http://thumb",
                    "published_at": published_at,
                    "duration": 62,
                }
            ],
            "next_page_token": None,
        }


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setattr("app.routes.channels.YTService", FakeYTService)
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


def test_list_channels_empty(client):
    _login(client, "alice")
    response = client.get("/api/channels")
    assert response.status_code == 200
    assert response.get_json() == []


def test_subscribe_requires_channel_id_tracking_id(client):
    _login(client, "alex")
    response = client.post("/api/channels/subscribe", json={})
    assert response.status_code == 400
    data = response.get_json()
    assert data.get("tracking_id")


def test_subscribe_and_list(client):
    _login(client, "bob")
    response = client.post("/api/channels/subscribe", json={"yt_channel_id": "chan"})
    assert response.status_code == 201
    data = response.get_json()
    assert data["yt_channel_id"] == "chan"

    response = client.get("/api/channels")
    channels = response.get_json()
    assert len(channels) == 1


def test_unsubscribe(client):
    _login(client, "carol")
    response = client.post("/api/channels/subscribe", json={"yt_channel_id": "chan"})
    channel_id = response.get_json()["id"]

    response = client.delete(f"/api/channels/{channel_id}/unsubscribe")
    assert response.status_code == 204

    response = client.get("/api/channels")
    assert response.get_json() == []


def test_refresh_and_videos(client, app):
    _login(client, "dave")
    response = client.post("/api/channels/subscribe", json={"yt_channel_id": "chan"})
    channel_id = response.get_json()["id"]

    response = client.post("/api/channels/refresh", json={"channel_id": channel_id})
    assert response.status_code == 200
    assert response.get_json()["new_videos"] == 1

    response = client.post("/api/channels/refresh", json={"channel_id": channel_id})
    assert response.get_json()["new_videos"] == 0

    with app.app_context():
        user = User.query.filter_by(username="dave").first()
        video = Video.query.filter_by(yt_video_id="vid-1").first()
        watched = WatchedVideo(user_id=user.id, video_id=video.id)
        db.session.add(watched)
        db.session.commit()

    response = client.get(f"/api/channels/{channel_id}/videos?limit=10&offset=0")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["videos"][0]["watched"] is True
