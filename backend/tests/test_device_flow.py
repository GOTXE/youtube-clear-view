"""Tests for the Google Device Flow endpoints."""

from unittest.mock import patch

import pytest

from app.extensions import db
from app.models import User


class TestDeviceFlowStart:
    """Tests for POST /api/auth/google/device/start."""

    def test_start_returns_user_code_and_url(self, client, app):
        app.config["GOOGLE_CLIENT_ID"] = "test-client-id"
        app.config["GOOGLE_CLIENT_SECRET"] = "test-secret"

        mock_response = {
            "device_code": "device-code-123",
            "user_code": "ABCD-EFGH",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1800,
            "interval": 5,
        }

        with patch("app.routes.auth.request_device_code", return_value=mock_response):
            resp = client.post(
                "/api/auth/google/device/start",
                json={"intent": "login"},
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user_code"] == "ABCD-EFGH"
        assert data["verification_url"] == "https://www.google.com/device"
        assert data["expires_in"] == 1800
        assert data["interval"] == 5

    def test_start_returns_qr_code(self, client, app):
        app.config["GOOGLE_CLIENT_ID"] = "test-client-id"
        app.config["GOOGLE_CLIENT_SECRET"] = "test-secret"

        mock_response = {
            "device_code": "device-code-123",
            "user_code": "ABCD-EFGH",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1800,
            "interval": 5,
        }

        with patch("app.routes.auth.request_device_code", return_value=mock_response):
            resp = client.post(
                "/api/auth/google/device/start",
                json={"intent": "login"},
            )

        data = resp.get_json()
        assert data["qr_code"] is not None
        assert data["qr_code"].startswith("data:image/svg+xml;base64,")

    def test_start_fails_without_config(self, client):
        resp = client.post(
            "/api/auth/google/device/start",
            json={"intent": "login"},
        )
        assert resp.status_code == 500

    def test_start_fails_when_google_returns_error(self, client, app):
        app.config["GOOGLE_CLIENT_ID"] = "test-client-id"
        app.config["GOOGLE_CLIENT_SECRET"] = "test-secret"

        with patch("app.routes.auth.request_device_code", return_value=None):
            resp = client.post(
                "/api/auth/google/device/start",
                json={"intent": "login"},
            )

        assert resp.status_code == 500


class TestDeviceFlowStatus:
    """Tests for GET /api/auth/google/device/status."""

    def test_status_returns_400_without_session(self, client):
        resp = client.get("/api/auth/google/device/status")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "no_device_flow"

    def test_status_returns_pending(self, client, app):
        app.config["GOOGLE_CLIENT_ID"] = "test-client-id"
        app.config["GOOGLE_CLIENT_SECRET"] = "test-secret"

        # Start a device flow to set up the session.
        mock_start = {
            "device_code": "device-code-123",
            "user_code": "ABCD-EFGH",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1800,
            "interval": 5,
        }

        with patch("app.routes.auth.request_device_code", return_value=mock_start):
            client.post("/api/auth/google/device/start", json={"intent": "login"})

        with patch("app.routes.auth.poll_device_token", return_value={"pending": True}):
            resp = client.get("/api/auth/google/device/status")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "pending"

    def test_status_returns_error_on_expiry(self, client, app):
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

        with patch(
            "app.routes.auth.poll_device_token",
            return_value={"error": "expired_token"},
        ):
            resp = client.get("/api/auth/google/device/status")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "error"
        assert data["error"] == "expired_token"

    def test_status_returns_authenticated_for_existing_user(self, client, app):
        app.config["GOOGLE_CLIENT_ID"] = "test-client-id"
        app.config["GOOGLE_CLIENT_SECRET"] = "test-secret"

        with app.app_context():
            user = User(
                username="existing",
                display_name="Existing User",
                google_user_id="google-sub-123",
                auth_provider="google",
                is_active=True,
                setup_completed=True,
            )
            user.set_password("test1234")
            db.session.add(user)
            db.session.commit()

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
            "sub": "google-sub-123",
            "email": "existing@example.com",
            "name": "Existing User",
            "picture": "https://example.com/avatar.jpg",
        }

        with (
            patch("app.routes.auth.poll_device_token", return_value=mock_tokens),
            patch("app.routes.auth.fetch_user_info", return_value=mock_userinfo),
        ):
            resp = client.get("/api/auth/google/device/status")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "authenticated"
        assert data["user"]["username"] == "existing"
        assert data["setup_completed"] is True

    def test_status_returns_new_user_for_unknown_google_id(self, client, app):
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
        }
        mock_userinfo = {
            "sub": "brand-new-google-id",
            "email": "newuser@example.com",
            "name": "New User",
            "picture": "",
        }

        with (
            patch("app.routes.auth.poll_device_token", return_value=mock_tokens),
            patch("app.routes.auth.fetch_user_info", return_value=mock_userinfo),
        ):
            resp = client.get("/api/auth/google/device/status")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "new_user"
        assert data["google_identity"]["email"] == "newuser@example.com"

    def test_status_returns_confirm_link_for_email_match(self, client, app):
        app.config["GOOGLE_CLIENT_ID"] = "test-client-id"
        app.config["GOOGLE_CLIENT_SECRET"] = "test-secret"

        with app.app_context():
            user = User(
                username="local_user",
                display_name="Local User",
                email="shared@example.com",
                auth_provider="local",
                is_active=True,
                setup_completed=True,
            )
            user.set_password("test1234")
            db.session.add(user)
            db.session.commit()

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
        }
        mock_userinfo = {
            "sub": "different-google-id",
            "email": "shared@example.com",
            "name": "Same Email User",
            "picture": "",
        }

        with (
            patch("app.routes.auth.poll_device_token", return_value=mock_tokens),
            patch("app.routes.auth.fetch_user_info", return_value=mock_userinfo),
        ):
            resp = client.get("/api/auth/google/device/status")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "confirm_link"
        assert data["existing_username"] == "local_user"
