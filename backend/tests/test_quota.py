"""Quota ledger and Pacific reset tests."""

from datetime import UTC, datetime

from app.extensions import db
from app.models import QuotaEvent, User, UserSettings
from app.services.quota import (
    get_current_quota_day_pt,
    get_global_quota_snapshot,
    mark_quota_exhausted,
    record_quota_event,
)


def _register_and_login(client, username="tester"):
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "testpassword123"},
    )
    if response.status_code not in {201, 409}:
        return response
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": "testpassword123"},
    )


def test_quota_day_uses_pacific_reset_boundary():
    before_reset = datetime(2026, 3, 22, 6, 59, 59, tzinfo=UTC)
    after_reset = datetime(2026, 3, 22, 7, 0, 0, tzinfo=UTC)

    assert get_current_quota_day_pt(before_reset) == "2026-03-21"
    assert get_current_quota_day_pt(after_reset) == "2026-03-22"


def test_quota_event_persists_even_if_session_rolls_back(app):
    with app.app_context():
        record_quota_event(
            api_method="videos.list",
            units=1,
            source="test",
            notes="rollback check",
        )
        db.session.rollback()

        stored = QuotaEvent.query.all()
        assert len(stored) == 1
        assert stored[0].api_method == "videos.list"
        assert stored[0].units == 1


def test_quota_event_uses_current_session_when_requested(app):
    with app.app_context():
        record_quota_event(
            api_method="videos.list",
            units=1,
            source="test",
            notes="session check",
            session=db.session,
        )
        db.session.rollback()

        stored = QuotaEvent.query.all()
        assert stored == []


def test_quota_status_uses_user_timezone_and_latest_ledger_total(app, client, monkeypatch):
    fixed_now = datetime(2026, 3, 22, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("app.services.quota.utc_now", lambda: fixed_now)

    login = _register_and_login(client)
    assert login.status_code == 200

    with app.app_context():
        user = User.query.filter_by(username="tester").first()
        settings = UserSettings.query.filter_by(user_id=user.id).first()
        if not settings:
            settings = UserSettings(user_id=user.id, preset="standard")
            db.session.add(settings)
        settings.timezone = "Europe/Madrid"
        db.session.commit()

        record_quota_event("subscriptions.list", 1, source="import", user_id=user.id, occurred_at=fixed_now)
        record_quota_event("videos.list", 3, source="refresh", user_id=user.id, occurred_at=fixed_now)

    response = client.get("/api/quota/status")
    assert response.status_code == 200

    data = response.get_json()
    assert data["used"] == 4
    assert data["quota_day_pt"] == "2026-03-22"
    assert data["official_timezone"] == "America/Los_Angeles"
    assert data["app_timezone"] == "Europe/Madrid"

    app_reset = datetime.fromisoformat(data["reset_at_app_timezone"])
    official_reset = datetime.fromisoformat(data["reset_at_pt"])

    assert app_reset.hour == 8
    assert official_reset.hour == 0


def test_quota_exhaustion_persists_until_next_pacific_reset(app, monkeypatch):
    before_reset = datetime(2026, 3, 22, 23, 55, 0, tzinfo=UTC)
    monkeypatch.setattr("app.services.quota.utc_now", lambda: before_reset)

    with app.app_context():
        mark_quota_exhausted(None)
        snapshot = get_global_quota_snapshot("Europe/Madrid")
        assert snapshot["quota_exhausted"] is True
        assert snapshot["quota_exhausted_until_pt"] is not None
        assert snapshot["quota_exhausted_until_app_timezone"] is not None


def test_quota_exhaustion_clears_after_next_pacific_reset(app, monkeypatch):
    before_reset = datetime(2026, 3, 22, 23, 55, 0, tzinfo=UTC)
    after_reset = datetime(2026, 3, 23, 7, 5, 0, tzinfo=UTC)

    monkeypatch.setattr("app.services.quota.utc_now", lambda: before_reset)
    with app.app_context():
        mark_quota_exhausted(None)

    monkeypatch.setattr("app.services.quota.utc_now", lambda: after_reset)
    with app.app_context():
        snapshot = get_global_quota_snapshot("Europe/Madrid")
        assert snapshot["quota_exhausted"] is False
        assert snapshot["quota_exhausted_until_pt"] is None
