"""Hybrid RSS/API refresh tests."""

from datetime import UTC, datetime
import logging

from app.extensions import db
from app.config import Config
from app.models import Channel, User, UserChannel, UserSettings, Video
from app.services.video_ingest import refresh_user_channels


class FakeHybridService:
    """Fake service exposing the API methods used by refresh."""

    def __init__(self, api_items=None, completion_items=None):
        self.api_items = api_items or []
        self.completion_items = completion_items or []
        self.channel_video_calls = 0
        self.video_ids_calls = 0
        self.last_quota_session = None

    def get_channel_videos(self, channel_id):
        self.channel_video_calls += 1
        return {"success": True, "videos": list(self.api_items), "next_page_token": None}

    def get_videos_by_ids(self, video_ids, quota_session=None):
        self.video_ids_calls += 1
        self.last_quota_session = quota_session
        selected = [item for item in self.completion_items if item["video_id"] in set(video_ids)]
        return {"success": True, "videos": selected}


def _seed_user_and_channel(app):
    with app.app_context():
        user = User(username="alice", display_name="Alice")
        user.set_password("testpassword123")
        db.session.add(user)
        db.session.flush()

        channel = Channel(yt_channel_id="UC_TEST_RSS", title="RSS Channel")
        db.session.add(channel)
        db.session.flush()

        subscription = UserChannel(user_id=user.id, channel_id=channel.id)
        db.session.add(subscription)

        settings = UserSettings(user_id=user.id, preset="standard")
        settings.quota_date = "2026-03-22"
        settings.quota_used = 0
        settings.quota_cap = 8000
        db.session.add(settings)

        db.session.commit()
        return user.id, channel.id


def test_refresh_uses_rss_and_completes_new_video(app, monkeypatch, caplog):
    user_id, channel_id = _seed_user_and_channel(app)

    class FeedEntry:
        video_id = "rss-1"
        channel_id = "UC_TEST_RSS"
        title = "RSS Video"
        published_at = "2026-03-22T10:00:00+00:00"
        updated_at = "2026-03-22T10:05:00+00:00"
        channel_title = "RSS Channel"
        link = "https://www.youtube.com/watch?v=rss-1"

    monkeypatch.setattr(
        "app.services.video_ingest.fetch_channel_feed",
        lambda channel_id: {"success": True, "entries": [FeedEntry()]},
    )

    service = FakeHybridService(
        completion_items=[
            {
                "video_id": "rss-1",
                "title": "RSS Video",
                "description": "Completed description",
                "thumbnail": "http://thumb/rss-1.jpg",
                "published_at": "2026-03-22T10:00:00Z",
                "duration": 125,
                "video_category_id": "22",
                "tags": ["travel", "rss"],
            }
        ]
    )

    with app.app_context():
        caplog.set_level(logging.INFO)
        user = db.session.get(User, user_id)
        settings = UserSettings.query.filter_by(user_id=user.id).first()
        summary = refresh_user_channels(
            user,
            settings,
            service,
            now=datetime(2026, 3, 22, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None),
        )

        video = Video.query.filter_by(yt_video_id="rss-1", channel_id=channel_id).first()
        assert summary["new_videos"] == 1
        assert video is not None
        assert video.discovered_via == "rss"
        assert video.metadata_incomplete is False
        assert video.duration == 125
        assert video.description == "Completed description"
        assert service.channel_video_calls == 0
        assert service.video_ids_calls == 1
        assert service.last_quota_session is not None
        assert "path=rss+api_completion" in caplog.text


def test_refresh_falls_back_to_api_when_feed_fails(app, monkeypatch, caplog):
    user_id, channel_id = _seed_user_and_channel(app)

    monkeypatch.setattr(
        "app.services.video_ingest.fetch_channel_feed",
        lambda channel_id: {"success": False, "entries": [], "status_code": 500},
    )

    service = FakeHybridService(
        api_items=[
            {
                "video_id": "api-1",
                "title": "API Video",
                "description": "API Desc",
                "thumbnail": "http://thumb/api-1.jpg",
                "published_at": "2026-03-22T08:00:00Z",
                "duration": 301,
                "video_category_id": "24",
                "tags": ["api"],
            }
        ]
    )

    with app.app_context():
        caplog.set_level(logging.INFO)
        user = db.session.get(User, user_id)
        settings = UserSettings.query.filter_by(user_id=user.id).first()
        summary = refresh_user_channels(
            user,
            settings,
            service,
            now=datetime(2026, 3, 22, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None),
        )

        video = Video.query.filter_by(yt_video_id="api-1", channel_id=channel_id).first()
        subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
        assert summary["new_videos"] == 1
        assert video is not None
        assert video.discovered_via == "api"
        assert service.channel_video_calls == 1
        assert service.video_ids_calls == 0
        assert subscription.last_feed_checked_at is not None
        assert subscription.last_feed_error_at is not None
        assert subscription.feed_error_count == 1
        assert "path=api_fallback" in caplog.text


def test_refresh_resets_feed_error_count_after_success(app, monkeypatch):
    user_id, channel_id = _seed_user_and_channel(app)

    class FeedEntry:
        video_id = "rss-2"
        channel_id = "UC_TEST_RSS"
        title = "Recovered RSS Video"
        published_at = "2026-03-22T11:00:00+00:00"
        updated_at = "2026-03-22T11:01:00+00:00"
        channel_title = "RSS Channel"
        link = "https://www.youtube.com/watch?v=rss-2"

    monkeypatch.setattr(
        "app.services.video_ingest.fetch_channel_feed",
        lambda channel_id: {"success": True, "entries": [FeedEntry()]},
    )

    service = FakeHybridService(
        completion_items=[
            {
                "video_id": "rss-2",
                "title": "Recovered RSS Video",
                "description": "Recovered description",
                "thumbnail": "http://thumb/rss-2.jpg",
                "published_at": "2026-03-22T11:00:00Z",
                "duration": 91,
                "video_category_id": "10",
                "tags": ["rss"],
            }
        ]
    )

    with app.app_context():
        user = db.session.get(User, user_id)
        settings = UserSettings.query.filter_by(user_id=user.id).first()
        subscription = UserChannel.query.filter_by(user_id=user.id, channel_id=channel_id).first()
        subscription.feed_error_count = 3
        db.session.commit()

        refresh_user_channels(
            user,
            settings,
            service,
            now=datetime(2026, 3, 22, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None),
        )

        db.session.refresh(subscription)
        assert subscription.last_feed_checked_at is not None
        assert subscription.last_feed_success_at is not None
        assert subscription.feed_error_count == 0


def test_rss_preferred_skips_api_fallback_when_feed_fails(app, monkeypatch, caplog):
    user_id, channel_id = _seed_user_and_channel(app)

    monkeypatch.setattr(
        "app.services.video_ingest.fetch_channel_feed",
        lambda channel_id: {"success": False, "entries": [], "status_code": 500},
    )

    service = FakeHybridService(
        api_items=[
            {
                "video_id": "api-skipped",
                "title": "API Skipped",
                "description": "Should not be fetched",
                "thumbnail": "http://thumb/api-skipped.jpg",
                "published_at": "2026-03-22T08:00:00Z",
                "duration": 301,
                "video_category_id": "24",
                "tags": ["api"],
            }
        ]
    )

    original_mode = Config.VIDEO_REFRESH_MODE
    Config.VIDEO_REFRESH_MODE = "rss_preferred"
    try:
        with app.app_context():
            caplog.set_level(logging.INFO)
            user = db.session.get(User, user_id)
            settings = UserSettings.query.filter_by(user_id=user.id).first()
            summary = refresh_user_channels(
                user,
                settings,
                service,
                now=datetime(2026, 3, 22, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None),
            )

            video = Video.query.filter_by(channel_id=channel_id).first()
            assert summary["new_videos"] == 0
            assert video is None
            assert service.channel_video_calls == 0
            assert "path=rss_failed_no_api_fallback" in caplog.text
    finally:
        Config.VIDEO_REFRESH_MODE = original_mode


def test_refresh_logs_api_only_path(app, monkeypatch, caplog):
    user_id, channel_id = _seed_user_and_channel(app)

    monkeypatch.setattr(
        "app.services.video_ingest.fetch_channel_feed",
        lambda channel_id: {"success": True, "entries": []},
    )

    service = FakeHybridService(
        api_items=[
            {
                "video_id": "api-only-1",
                "title": "API Only Video",
                "description": "API only desc",
                "thumbnail": "http://thumb/api-only-1.jpg",
                "published_at": "2026-03-22T08:00:00Z",
                "duration": 180,
                "video_category_id": "24",
                "tags": ["api-only"],
            }
        ]
    )

    original_mode = Config.VIDEO_REFRESH_MODE
    Config.VIDEO_REFRESH_MODE = "api_only"
    try:
        with app.app_context():
            caplog.set_level(logging.INFO)
            user = db.session.get(User, user_id)
            settings = UserSettings.query.filter_by(user_id=user.id).first()
            summary = refresh_user_channels(
                user,
                settings,
                service,
                now=datetime(2026, 3, 22, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None),
            )

            video = Video.query.filter_by(yt_video_id="api-only-1", channel_id=channel_id).first()
            assert summary["new_videos"] == 1
            assert video is not None
            assert service.channel_video_calls == 1
            assert "path=api_only" in caplog.text
    finally:
        Config.VIDEO_REFRESH_MODE = original_mode
