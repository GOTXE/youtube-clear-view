"""Tests for the bootstrap window timeout mechanism."""

import pytest

from app.extensions import db
from app.models import SiteSetting
from app.services.admin_bootstrap import (
    BOOTSTRAP_WINDOW_STARTED_AT_KEY,
    clear_bootstrap_window,
    get_bootstrap_window_info,
    is_bootstrap_locked,
    is_bootstrap_required,
    reset_bootstrap_window,
)


@pytest.fixture(autouse=True)
def _ensure_bootstrap_window(app):
    """Re-create the bootstrap window record after conftest wipes the DB."""
    with app.app_context():
        reset_bootstrap_window()


def test_bootstrap_status_includes_window_info(client):
    """GET /api/bootstrap/status returns bootstrap_window when bootstrap is required."""
    response = client.get("/api/bootstrap/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["bootstrap_required"] is True
    assert "bootstrap_window" in data
    window = data["bootstrap_window"]
    assert "remaining_seconds" in window
    assert "locked" in window
    assert window["locked"] is False
    assert window["remaining_seconds"] > 0


def test_bootstrap_window_expires_after_timeout(app):
    """After the timeout, the bootstrap window should be locked."""
    with app.app_context():
        # Simulate window that started 600 seconds ago (timeout is 300)
        from datetime import datetime, timedelta
        from app.utils.time import utc_now

        past = utc_now() - timedelta(seconds=600)
        record = SiteSetting.query.filter_by(
            setting_key=BOOTSTRAP_WINDOW_STARTED_AT_KEY
        ).first()
        if record:
            record.setting_value = past.isoformat()
        else:
            record = SiteSetting(
                setting_key=BOOTSTRAP_WINDOW_STARTED_AT_KEY,
                setting_value=past.isoformat(),
            )
            db.session.add(record)
        db.session.commit()

        assert is_bootstrap_required() is True
        assert is_bootstrap_locked() is True
        info = get_bootstrap_window_info()
        assert info["locked"] is True
        assert info["remaining_seconds"] == 0


def test_bootstrap_admin_returns_423_when_locked(client, app):
    """POST /api/bootstrap/admin returns 423 when the window has expired."""
    with app.app_context():
        from datetime import timedelta
        from app.utils.time import utc_now

        past = utc_now() - timedelta(seconds=600)
        record = SiteSetting.query.filter_by(
            setting_key=BOOTSTRAP_WINDOW_STARTED_AT_KEY
        ).first()
        if record:
            record.setting_value = past.isoformat()
        else:
            record = SiteSetting(
                setting_key=BOOTSTRAP_WINDOW_STARTED_AT_KEY,
                setting_value=past.isoformat(),
            )
            db.session.add(record)
        db.session.commit()

    response = client.post(
        "/api/bootstrap/admin",
        json={
            "username": "admin",
            "password": "Strongpass123",
            "confirm_password": "Strongpass123",
        },
    )
    assert response.status_code == 423
    data = response.get_json()
    assert data["locked"] is True


def test_bootstrap_admin_succeeds_within_window(client):
    """POST /api/bootstrap/admin works while the window is still open."""
    response = client.post(
        "/api/bootstrap/admin",
        json={
            "username": "admin",
            "display_name": "Administrator",
            "password": "Strongpass123",
            "confirm_password": "Strongpass123",
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["is_admin"] is True


def test_bootstrap_window_cleared_after_admin_created(client, app):
    """After successful bootstrap, the window timer is removed."""
    client.post(
        "/api/bootstrap/admin",
        json={
            "username": "admin",
            "password": "Strongpass123",
            "confirm_password": "Strongpass123",
        },
    )
    with app.app_context():
        record = SiteSetting.query.filter_by(
            setting_key=BOOTSTRAP_WINDOW_STARTED_AT_KEY
        ).first()
        assert record is None


def test_reset_bootstrap_window_creates_fresh_timestamp(app):
    """reset_bootstrap_window sets a new timestamp each time."""
    with app.app_context():
        reset_bootstrap_window()
        info1 = get_bootstrap_window_info()
        assert info1["locked"] is False
        assert info1["remaining_seconds"] > 0

        # Reset again — should still work
        reset_bootstrap_window()
        info2 = get_bootstrap_window_info()
        assert info2["locked"] is False


def test_auth_provider_includes_window_when_bootstrap_required(client):
    """GET /api/auth/provider includes bootstrap_window when no admin exists."""
    response = client.get("/api/auth/provider")
    assert response.status_code == 200
    data = response.get_json()
    assert data["bootstrap_required"] is True
    assert "bootstrap_window" in data
    assert data["bootstrap_window"]["locked"] is False


def test_auth_provider_no_window_after_bootstrap(client):
    """GET /api/auth/provider has no bootstrap_window after admin creation."""
    client.post(
        "/api/bootstrap/admin",
        json={
            "username": "admin",
            "password": "Strongpass123",
            "confirm_password": "Strongpass123",
        },
    )
    response = client.get("/api/auth/provider")
    data = response.get_json()
    assert data["bootstrap_required"] is False
    assert "bootstrap_window" not in data
