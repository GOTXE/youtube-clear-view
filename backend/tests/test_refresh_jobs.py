"""Refresh job recovery tests."""

from app.extensions import db
from app.models import RefreshJob, User
from app.services.refresh_jobs import (
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    recover_interrupted_refresh_jobs,
)


def test_recover_interrupted_refresh_jobs_marks_queued_and_running_as_failed(app):
    with app.app_context():
        user = User(username="job-user", display_name="Job User")
        user.set_password("testpassword123")
        db.session.add(user)
        db.session.flush()

        queued = RefreshJob(user_id=user.id, kind="manual", status=STATUS_QUEUED, message="queued")
        running = RefreshJob(user_id=user.id, kind="manual", status=STATUS_RUNNING, message="running")
        done = RefreshJob(user_id=user.id, kind="manual", status="completed", message="done")
        db.session.add_all([queued, running, done])
        db.session.commit()

        recovered = recover_interrupted_refresh_jobs()
        db.session.refresh(queued)
        db.session.refresh(running)
        db.session.refresh(done)

        assert recovered == 2
        assert queued.status == STATUS_FAILED
        assert running.status == STATUS_FAILED
        assert queued.finished_at is not None
        assert running.finished_at is not None
        assert queued.message == "Refresh interrumpido por reinicio del backend"
        assert running.message == "Refresh interrumpido por reinicio del backend"
        assert done.status == "completed"
