"""Video ingest pruning tests."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from app.extensions import db
from app.models import Channel, RefreshJob, User, UserChannel, Video, VideoProgress
from app.services.refresh_jobs import KIND_MANUAL, STATUS_FAILED, _execute_job
from app.services.video_ingest import _prune_range


def test_prune_range_deletes_video_progress_with_pruned_videos(app):
    with app.app_context():
        user = User(username="prune-user", display_name="Prune User")
        user.set_password("testpassword123")
        db.session.add(user)
        db.session.flush()

        channel = Channel(yt_channel_id="prune-channel", title="Prune Channel")
        db.session.add(channel)
        db.session.flush()

        db.session.add(UserChannel(user_id=user.id, channel_id=channel.id))

        newest_video = Video(
            yt_video_id="prune-new",
            channel_id=channel.id,
            title="Newest",
            published_at=datetime.now(UTC).replace(tzinfo=None),
            duration=600,
        )
        oldest_video = Video(
            yt_video_id="prune-old",
            channel_id=channel.id,
            title="Oldest",
            published_at=(datetime.now(UTC) - timedelta(days=2)).replace(tzinfo=None),
            duration=600,
        )
        db.session.add_all([newest_video, oldest_video])
        db.session.flush()

        progress_entry = VideoProgress(
            user_id=user.id,
            video_id=oldest_video.id,
            position_seconds=42,
            duration_seconds=600,
            is_continue_watching=False,
        )
        db.session.add(progress_entry)
        db.session.commit()

        _prune_range(channel.id, start=None, end=None, is_short=False, cap=1)
        db.session.commit()

        assert db.session.get(Video, newest_video.id) is not None
        assert db.session.get(Video, oldest_video.id) is None
        assert db.session.get(VideoProgress, progress_entry.id) is None


def test_execute_job_marks_refresh_as_failed_when_refresh_thread_raises(app, monkeypatch):
    with app.app_context():
        user = User(username="job-failure-user", display_name="Job Failure User")
        user.set_password("testpassword123")
        db.session.add(user)
        db.session.flush()

        channel = Channel(yt_channel_id="job-failure-channel", title="Job Failure Channel")
        db.session.add(channel)
        db.session.flush()

        db.session.add(UserChannel(user_id=user.id, channel_id=channel.id))
        job = RefreshJob(user_id=user.id, kind=KIND_MANUAL, status="queued", message="queued")
        db.session.add(job)
        db.session.commit()
        user_id = user.id
        job_id = job.id

    @contextmanager
    def fake_manual_refresh(user_id, channel_id=None, now=None):
        yield {"acquired": True}

    def raise_refresh_error(*args, **kwargs):
        raise RuntimeError("boom")
        yield

    class FakeYTService:
        def __init__(self, api_key):
            self.api_key = api_key

    monkeypatch.setattr("app.services.refresh_jobs.acquire_manual_refresh", fake_manual_refresh)
    monkeypatch.setattr("app.services.refresh_jobs.iter_refresh_user_channels", raise_refresh_error)
    monkeypatch.setattr("app.services.refresh_jobs.YTService", FakeYTService)

    _execute_job(app, job_id, user_id, KIND_MANUAL)

    with app.app_context():
        failed_job = db.session.get(RefreshJob, job_id)
        assert failed_job is not None
        assert failed_job.status == STATUS_FAILED
        assert failed_job.finished_at is not None
        assert failed_job.message == "Refresh failed due to an internal error"
