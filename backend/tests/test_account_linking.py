"""Tests for device flow account linking and creation endpoints."""

from unittest.mock import patch

from app.extensions import db
from app.models import User


def _start_device_flow_and_authorize(client, app, google_user_id, email, name="Test User"):
    """Helper: start a device flow and simulate successful authorization."""
    app.config["GOOGLE_CLIENT_ID"] = "test-client-id"
    app.config["GOOGLE_CLIENT_SECRET"] = "test-secret"

    mock_start = {
        "device_code": "device-code-123",
        "user_code": "ABCD-EFGH",
        "verification_url": "https://www.google.com/device",
        "expires_in": 1800,
        "interval": 5,
    }
    with patch("app.routes.auth.request_device_code", return_value=mock_start):
        client.post("/api/auth/google/device/start", json={"intent": "login"})

    mock_tokens = {
        "access_token": "access-123",
        "refresh_token": "refresh-123",
        "expires_in": 3600,
        "scope": "openid email profile",
    }
    mock_userinfo = {
        "sub": google_user_id,
        "email": email,
        "name": name,
        "picture": "https://example.com/avatar.jpg",
    }
    with (
        patch("app.routes.auth.poll_device_token", return_value=mock_tokens),
        patch("app.routes.auth.fetch_user_info", return_value=mock_userinfo),
    ):
        return client.get("/api/auth/google/device/status")


class TestConfirmLink:
    """Tests for POST /api/auth/google/device/confirm-link."""

    def test_confirm_link_attaches_google_to_existing_user(self, client, app):
        with app.app_context():
            user = User(
                username="local_jane",
                display_name="Jane",
                email="jane@example.com",
                auth_provider="local",
                is_active=True,
                setup_completed=True,
            )
            user.set_password("pass1234")
            db.session.add(user)
            db.session.commit()

        status_resp = _start_device_flow_and_authorize(
            client, app,
            google_user_id="google-jane-sub",
            email="jane@example.com",
            name="Jane Doe",
        )
        assert status_resp.get_json()["status"] == "confirm_link"

        resp = client.post("/api/auth/google/device/confirm-link", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "authenticated"
        assert data["user"]["username"] == "local_jane"

        with app.app_context():
            linked = User.query.filter_by(username="local_jane").first()
            assert linked.google_user_id == "google-jane-sub"
            assert linked.google_auth_status == "active"

    def test_confirm_link_fails_without_pending_flow(self, client):
        resp = client.post("/api/auth/google/device/confirm-link", json={})
        assert resp.status_code == 400

    def test_confirm_link_fails_if_user_not_found(self, client, app):
        """If the email-matched user was deleted between status and confirm."""
        status_resp = _start_device_flow_and_authorize(
            client, app,
            google_user_id="google-orphan",
            email="orphan@example.com",
        )
        # The status endpoint returned new_user (no email match), not confirm_link.
        # Force session state as if confirm_link was returned.
        with client.session_transaction() as sess:
            sess["_device_flow_identity"] = {
                "google_user_id": "google-orphan",
                "email": "orphan@example.com",
                "name": "Ghost",
                "picture": "",
            }
            sess["_device_flow_tokens"] = {
                "access_token": "x",
                "refresh_token": "y",
                "expires_in": 3600,
                "scope": "openid",
            }

        resp = client.post("/api/auth/google/device/confirm-link", json={})
        assert resp.status_code == 404


class TestCreateAccount:
    """Tests for POST /api/auth/google/device/create-account."""

    def test_create_account_succeeds(self, client, app):
        status_resp = _start_device_flow_and_authorize(
            client, app,
            google_user_id="google-new-sub",
            email="new@example.com",
            name="New User",
        )
        assert status_resp.get_json()["status"] == "new_user"

        resp = client.post(
            "/api/auth/google/device/create-account",
            json={
                "username": "newuser",
                "password": "Secure1234",
                "confirm_password": "Secure1234",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "authenticated"
        assert data["user"]["username"] == "newuser"

        with app.app_context():
            user = User.query.filter_by(username="newuser").first()
            assert user is not None
            assert user.google_user_id == "google-new-sub"
            assert user.email == "new@example.com"
            assert user.google_auth_status == "active"
            assert user.setup_completed is True

    def test_create_account_fails_password_mismatch(self, client, app):
        _start_device_flow_and_authorize(
            client, app,
            google_user_id="google-new-sub",
            email="new@example.com",
        )

        resp = client.post(
            "/api/auth/google/device/create-account",
            json={
                "username": "newuser",
                "password": "Secure1234",
                "confirm_password": "Different5678",
            },
        )
        assert resp.status_code == 400

    def test_create_account_fails_username_taken(self, client, app):
        with app.app_context():
            existing = User(username="taken", display_name="Taken")
            existing.set_password("test1234")
            db.session.add(existing)
            db.session.commit()

        _start_device_flow_and_authorize(
            client, app,
            google_user_id="google-new-sub2",
            email="another@example.com",
        )

        resp = client.post(
            "/api/auth/google/device/create-account",
            json={
                "username": "taken",
                "password": "Secure1234",
                "confirm_password": "Secure1234",
            },
        )
        assert resp.status_code == 409

    def test_create_account_fails_without_pending_flow(self, client):
        resp = client.post(
            "/api/auth/google/device/create-account",
            json={
                "username": "newuser",
                "password": "Secure1234",
                "confirm_password": "Secure1234",
            },
        )
        assert resp.status_code == 400

    def test_session_tokens_cleared_after_create(self, client, app):
        _start_device_flow_and_authorize(
            client, app,
            google_user_id="google-cleanup-sub",
            email="cleanup@example.com",
        )

        client.post(
            "/api/auth/google/device/create-account",
            json={
                "username": "cleanup",
                "password": "Secure1234",
                "confirm_password": "Secure1234",
            },
        )

        with client.session_transaction() as sess:
            assert "_device_flow_tokens" not in sess
            assert "_device_flow_identity" not in sess
