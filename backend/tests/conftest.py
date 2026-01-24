"""Pytest configuration and shared fixtures."""

from datetime import datetime, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import Channel, Theme, ThemeChannel, User, UserChannel, Video, WatchedVideo


class TestConfig:
    """Minimal configuration shared across tests."""

    FLASK_SECRET_KEY = "test"
    YOUTUBE_API_KEY = "test"
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


@pytest.fixture()
def auth_client(client):
    client.post("/api/auth/login", json={"username": "tester"})
    return client


@pytest.fixture()
def sample_user(app):
    with app.app_context():
        user = User(username="sample_user", display_name="Sample User")
        db.session.add(user)
        db.session.commit()
        return {"id": user.id, "username": user.username}


@pytest.fixture()
def sample_channel(app):
    with app.app_context():
        channel = Channel(youtube_channel_id="chan-sample", title="Sample Channel")
        db.session.add(channel)
        db.session.commit()
        return {"id": channel.id, "youtube_channel_id": channel.youtube_channel_id}


@pytest.fixture()
def sample_video(app, sample_channel):
    with app.app_context():
        video = Video(
            youtube_video_id="video-sample",
            channel_id=sample_channel["id"],
            title="Sample Video",
            description="Sample description",
            published_at=datetime.utcnow() - timedelta(days=1),
            duration=62,
        )
        db.session.add(video)
        db.session.commit()
        return {"id": video.id, "youtube_video_id": video.youtube_video_id}


@pytest.fixture()
def sample_theme(app, sample_user):
    with app.app_context():
        theme = Theme(user_id=sample_user["id"], name="Sample Theme", color=None)
        db.session.add(theme)
        db.session.commit()
        return {"id": theme.id, "name": theme.name}


@pytest.fixture()
def sample_subscription(app, sample_user, sample_channel):
    with app.app_context():
        subscription = UserChannel(
            user_id=sample_user["id"],
            channel_id=sample_channel["id"],
        )
        db.session.add(subscription)
        db.session.commit()
        return {"id": subscription.id}


@pytest.fixture()
def sample_theme_channel(app, sample_theme, sample_channel):
    with app.app_context():
        link = ThemeChannel(theme_id=sample_theme["id"], channel_id=sample_channel["id"])
        db.session.add(link)
        db.session.commit()
        return {"id": link.id}


@pytest.fixture()
def sample_watched_video(app, sample_user, sample_video):
    with app.app_context():
        watched = WatchedVideo(user_id=sample_user["id"], video_id=sample_video["id"])
        db.session.add(watched)
        db.session.commit()
        return {"id": watched.id}


@pytest.fixture()
def mock_youtube_service(monkeypatch):
    class FakeYouTubeService:
        """Fake YouTube service for deterministic tests."""

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
            return {
                "videos": [
                    {
                        "video_id": "vid-1",
                        "title": "Test Video",
                        "description": "Desc",
                        "thumbnail": "http://thumb",
                        "published_at": "2024-01-01T00:00:00Z",
                        "duration": 62,
                    }
                ],
                "next_page_token": None,
            }

    monkeypatch.setattr("app.routes.channels.YouTubeService", FakeYouTubeService)
    return FakeYouTubeService
