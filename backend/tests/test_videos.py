"""Video route tests."""

from datetime import datetime, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import Channel, Theme, ThemeChannel, User, UserChannel, Video, WatchedVideo


class TestConfig:
    """Minimal configuration for video tests."""

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


def _login(client, username):
    return client.post("/api/auth/login", json={"username": username})


def _seed_data(app):
    with app.app_context():
        user = User(username="alice", display_name="Alice")
        db.session.add(user)
        db.session.flush()

        channel = Channel(youtube_channel_id="chan", title="Channel")
        db.session.add(channel)
        db.session.flush()

        subscription = UserChannel(user_id=user.id, channel_id=channel.id)
        db.session.add(subscription)

        video1 = Video(
            youtube_video_id="vid1",
            channel_id=channel.id,
            title="Video 1",
            published_at=datetime.utcnow() - timedelta(days=1),
        )
        video2 = Video(
            youtube_video_id="vid2",
            channel_id=channel.id,
            title="Video 2",
            published_at=datetime.utcnow(),
        )
        db.session.add_all([video1, video2])
        db.session.flush()

        watched = WatchedVideo(user_id=user.id, video_id=video2.id)
        db.session.add(watched)

        theme = Theme(user_id=user.id, name="Theme", color="#fff")
        db.session.add(theme)
        db.session.flush()
        db.session.add(ThemeChannel(theme_id=theme.id, channel_id=channel.id))

        db.session.commit()


def test_latest_videos(client, app):
    _seed_data(app)
    _login(client, "alice")
    response = client.get("/api/videos/latest?limit=10&offset=0")
    assert response.status_code == 200
    data = response.get_json()
    assert data["has_more"] is False
    assert len(data["videos"]) == 2
    assert data["videos"][0]["video"]["youtube_video_id"] == "vid2"
    assert data["videos"][0]["watched"] is True


def test_videos_by_theme(client, app):
    _seed_data(app)
    _login(client, "alice")
    with app.app_context():
        theme = Theme.query.first()
        theme_id = theme.id

    response = client.get(f"/api/videos/by-theme/{theme_id}?limit=10&offset=0")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["videos"]) == 2
    assert data["videos"][0]["channel"]["youtube_channel_id"] == "chan"


def test_watch_and_unwatch(client, app):
    _seed_data(app)
    _login(client, "alice")
    with app.app_context():
        video = Video.query.filter_by(youtube_video_id="vid1").first()
        video_id = video.id

    response = client.post(f"/api/videos/{video_id}/watch", json={})
    assert response.status_code == 204

    response = client.delete(f"/api/videos/{video_id}/unwatch")
    assert response.status_code == 204


def test_search_videos(client, app):
    _seed_data(app)
    _login(client, "alice")
    response = client.get("/api/videos/search?q=Video&limit=10&offset=0")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["videos"]) == 2
