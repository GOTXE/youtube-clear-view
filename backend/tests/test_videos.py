"""Video route tests."""

from datetime import datetime, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import Channel, Theme, ThemeChannel, User, UserChannel, Video, VideoProgress, WatchedVideo


class TestConfig:
    """Minimal configuration for video tests."""

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


def _seed_data(app):
    with app.app_context():
        user = User(username="alice", display_name="Alice")
        db.session.add(user)
        db.session.flush()

        channel = Channel(yt_channel_id="chan", title="Channel")
        db.session.add(channel)
        db.session.flush()

        subscription = UserChannel(user_id=user.id, channel_id=channel.id)
        db.session.add(subscription)

        video1 = Video(
            yt_video_id="vid1",
            channel_id=channel.id,
            title="Video 1",
            published_at=datetime.utcnow() - timedelta(days=1),
        )
        video2 = Video(
            yt_video_id="vid2",
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
    assert data["videos"][0]["video"]["yt_video_id"] == "vid2"
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
    assert data["videos"][0]["channel"]["yt_channel_id"] == "chan"


def test_watch_and_unwatch(client, app):
    _seed_data(app)
    _login(client, "alice")
    with app.app_context():
        video = Video.query.filter_by(yt_video_id="vid1").first()
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


def test_search_requires_query_tracking_id(client, app):
    _seed_data(app)
    _login(client, "alice")
    response = client.get("/api/videos/search")
    assert response.status_code == 400
    data = response.get_json()
    assert data.get("tracking_id")


# ── Video progress tests ─────────────────────────────────────────────


def test_save_progress(client, app):
    _seed_data(app)
    _login(client, "alice")
    with app.app_context():
        video = Video.query.filter_by(yt_video_id="vid1").first()
        video_id = video.id

    response = client.put(
        f"/api/videos/{video_id}/progress",
        json={"position_seconds": 120, "duration_seconds": 600},
    )
    assert response.status_code == 204

    # Verify progress appears in latest videos
    response = client.get("/api/videos/latest?limit=10&offset=0")
    data = response.get_json()
    vid1_entry = next(v for v in data["videos"] if v["video"]["yt_video_id"] == "vid1")
    assert vid1_entry["progress"] == 120


def test_save_progress_upsert(client, app):
    _seed_data(app)
    _login(client, "alice")
    with app.app_context():
        video = Video.query.filter_by(yt_video_id="vid1").first()
        video_id = video.id

    client.put(f"/api/videos/{video_id}/progress", json={"position_seconds": 60, "duration_seconds": 600})
    client.put(f"/api/videos/{video_id}/progress", json={"position_seconds": 300, "duration_seconds": 600})

    response = client.get("/api/videos/latest?limit=10&offset=0")
    data = response.get_json()
    vid1_entry = next(v for v in data["videos"] if v["video"]["yt_video_id"] == "vid1")
    assert vid1_entry["progress"] == 300

    # Only one record in DB
    with app.app_context():
        count = VideoProgress.query.filter_by(video_id=video_id).count()
        assert count == 1


def test_clear_progress(client, app):
    _seed_data(app)
    _login(client, "alice")
    with app.app_context():
        video = Video.query.filter_by(yt_video_id="vid1").first()
        video_id = video.id

    client.put(f"/api/videos/{video_id}/progress", json={"position_seconds": 120, "duration_seconds": 600})
    response = client.delete(f"/api/videos/{video_id}/progress")
    assert response.status_code == 204

    response = client.get("/api/videos/latest?limit=10&offset=0")
    data = response.get_json()
    vid1_entry = next(v for v in data["videos"] if v["video"]["yt_video_id"] == "vid1")
    assert vid1_entry.get("progress") is None


def test_mark_watched_clears_progress(client, app):
    _seed_data(app)
    _login(client, "alice")
    with app.app_context():
        video = Video.query.filter_by(yt_video_id="vid1").first()
        video_id = video.id

    client.put(f"/api/videos/{video_id}/progress", json={"position_seconds": 120, "duration_seconds": 600})
    client.post(f"/api/videos/{video_id}/watch", json={})

    with app.app_context():
        progress = VideoProgress.query.filter_by(video_id=video_id).first()
        assert progress is None


def test_save_progress_invalid_position(client, app):
    _seed_data(app)
    _login(client, "alice")
    with app.app_context():
        video = Video.query.filter_by(yt_video_id="vid1").first()
        video_id = video.id

    response = client.put(f"/api/videos/{video_id}/progress", json={"position_seconds": -10})
    assert response.status_code == 400


def test_save_progress_video_not_found(client, app):
    _seed_data(app)
    _login(client, "alice")
    response = client.put("/api/videos/99999/progress", json={"position_seconds": 60})
    assert response.status_code == 404
    data = response.get_json()
    assert data.get("tracking_id")
