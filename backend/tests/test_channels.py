"""Channel route tests with mocked YT service."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app import create_app
from app.extensions import db
from app.migrations import ensure_category_schema
from app.models import User, UserChannel, Video, WatchedVideo


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
    GUNICORN_WORKERS = 1
    MANUAL_REFRESH_FULL_COOLDOWN_SECONDS = 0
    MANUAL_REFRESH_CHANNEL_COOLDOWN_SECONDS = 0
    LOCAL_SIGNUP_ENABLED = True
    PASSWORD_POLICY = "simple"

    CSRF_ENABLED = False
    RATE_LIMIT_ENABLED = False

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
        published_at = (datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "videos": [
                {
                    "video_id": "vid-1",
                    "title": "Test Video",
                    "description": "Desc",
                    "video_category_id": "20",
                    "tags": ["gaming", "walkthrough"],
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
    monkeypatch.setattr("app.config.Config.MANUAL_REFRESH_FULL_COOLDOWN_SECONDS", 0, raising=False)
    monkeypatch.setattr("app.config.Config.MANUAL_REFRESH_CHANNEL_COOLDOWN_SECONDS", 0, raising=False)
    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        ensure_category_schema()
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


def test_refresh_stream_emits_incremental_events(client):
    _login(client, "erin")
    response = client.post("/api/channels/subscribe", json={"yt_channel_id": "chan"})
    channel_id = response.get_json()["id"]

    response = client.get(f"/api/channels/refresh/stream?channel_id={channel_id}")
    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"

    body = response.get_data(as_text=True)
    assert '"type": "stream_opened"' in body
    assert '"type": "start"' in body
    assert '"type": "channel_started"' in body
    assert '"type": "channel_complete"' in body
    assert '"type": "complete"' in body
    assert '"channel_new_videos": 1' in body


def test_refresh_blocked_by_cooldown(client, app):
    _login(client, "frank")
    response = client.post("/api/channels/subscribe", json={"yt_channel_id": "chan"})
    channel_id = response.get_json()["id"]

    with app.app_context():
        user = User.query.filter_by(username="frank").first()
        subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
        subscription.last_checked_at = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).replace(tzinfo=None)
        db.session.commit()

    response = client.post("/api/channels/refresh", json={"channel_id": channel_id})
    assert response.status_code == 429
    data = response.get_json()
    assert data["blocked"] is True
    assert data["reason"] == "cooldown_active"
    assert data["scope"]["type"] == "channel"


def test_refresh_stream_emits_blocked_event_when_cooldown_active(client, app):
    _login(client, "george")
    response = client.post("/api/channels/subscribe", json={"yt_channel_id": "chan"})
    channel_id = response.get_json()["id"]

    with app.app_context():
        user = User.query.filter_by(username="george").first()
        subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
        subscription.last_checked_at = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).replace(tzinfo=None)
        db.session.commit()

    response = client.get(f"/api/channels/refresh/stream?channel_id={channel_id}")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '"type": "blocked"' in body
    assert '"reason": "cooldown_active"' in body


def test_refresh_updates_existing_video_evidence(client, app, monkeypatch):
    """Refreshing should update evidence on already stored videos."""
    class StatefulYTService(FakeYTService):
        def __init__(self, api_key):
            super().__init__(api_key)
            self.call_count = 0

        def get_channel_videos(self, channel_id, max_results=50, page_token=None):
            self.call_count += 1
            published_at = (datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            if self.call_count == 1:
                return {
                    "videos": [
                        {
                            "video_id": "vid-1",
                            "title": "Original Title",
                            "description": "Original description",
                            "video_category_id": "20",
                            "tags": ["gaming"],
                            "thumbnail": "http://thumb",
                            "published_at": published_at,
                            "duration": 62,
                        }
                    ],
                    "next_page_token": None,
                    "success": True,
                }
            return {
                "videos": [
                    {
                        "video_id": "vid-1",
                        "title": "Updated Title",
                        "description": "Updated description",
                        "video_category_id": "27",
                        "tags": ["education", "tutorial"],
                        "thumbnail": "http://thumb-2",
                        "published_at": published_at,
                        "duration": 70,
                    }
                ],
                "next_page_token": None,
                "success": True,
            }

    service = StatefulYTService("test")
    monkeypatch.setattr("app.routes.channels._get_service", lambda: service)

    _login(client, "frank")
    response = client.post("/api/channels/subscribe", json={"yt_channel_id": "chan"})
    channel_id = response.get_json()["id"]

    first_refresh = client.post("/api/channels/refresh", json={"channel_id": channel_id})
    assert first_refresh.status_code == 200
    assert first_refresh.get_json()["new_videos"] == 1

    second_refresh = client.post("/api/channels/refresh", json={"channel_id": channel_id})
    assert second_refresh.status_code == 200
    assert second_refresh.get_json()["new_videos"] == 0

    with app.app_context():
        video = Video.query.filter_by(yt_video_id="vid-1").first()
        assert video.title == "Updated Title"
        assert video.description == "Updated description"
        assert video.video_category_id == "27"
        assert video.tags == "education tutorial"
        assert video.thumbnail_url == "http://thumb-2"
        assert video.duration == 70


def test_enrich_video_evidence_classifies_unclassified_channel(client, app, monkeypatch):
    """Manual video-evidence enrichment should classify channels without topic metadata."""
    class EvidenceService(FakeYTService):
        def get_channel_videos(self, channel_id, max_results=50, page_token=None):
            published_at = (datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return {
                "videos": [
                    {
                        "video_id": f"gaming-{idx}",
                        "title": f"Gameplay {idx}",
                        "description": "Weekly highlights and commentary",
                        "video_category_id": "20",
                        "tags": ["gaming", "walkthrough"],
                        "thumbnail": "http://thumb",
                        "published_at": published_at,
                        "duration": 120,
                    }
                    for idx in range(5)
                ],
                "next_page_token": None,
                "success": True,
            }

    monkeypatch.setattr("app.routes.channels._get_service", lambda: EvidenceService("test"))

    _login(client, "grace")
    response = client.post("/api/channels/subscribe", json={"yt_channel_id": "chan"})
    channel_id = response.get_json()["id"]

    response = client.post(
        "/api/channels/enrich-video-evidence",
        json={"channel_id": channel_id, "max_results": 5},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["channels_processed"] == 1
    assert data["videos_created"] == 5
    assert data["classified"] == 1

    with app.app_context():
        from app.models import ChannelCategory

        channel_category = ChannelCategory.query.first()
        assert channel_category is not None
