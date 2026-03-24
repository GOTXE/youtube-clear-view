"""Tests for Google account revocation and relinking via device flow."""

from unittest.mock import patch

from app.extensions import db
from app.models import User


def _create_google_user(app, username="guser", google_user_id="google-sub-1"):
    """Create a user with Google linked and return user dict."""
    with app.app_context():
        user = User(
            username=username,
            display_name=username.title(),
            email=f"{username}@example.com",
            google_user_id=google_user_id,
            auth_provider="google",
            is_active=True,
            setup_completed=True,
        )
        user.set_password("pass1234")
        db.session.add(user)
        db.session.commit()
        return {"id": user.id, "username": user.username}


def _login(client, username, password="pass1234"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def _inject_device_flow_session(client, google_user_id, email):
    """Inject device flow tokens and identity directly into the session."""
    with client.session_transaction() as sess:
        sess["_device_flow_tokens"] = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "scope": "openid email profile",
        }
        sess["_device_flow_identity"] = {
            "google_user_id": google_user_id,
            "email": email,
            "name": "Relinked",
            "picture": "",
        }


class TestRelink:
    """Tests for POST /api/auth/google/device/relink."""

    def test_relink_updates_tokens(self, client, app):
        user_data = _create_google_user(app)
        _login(client, user_data["username"])
        _inject_device_flow_session(client, "google-sub-1", "guser@example.com")

        resp = client.post("/api/auth/google/device/relink", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["google_auth_status"] == "active"

        with app.app_context():
            user = db.session.get(User, user_data["id"])
            assert user.google_auth_status == "active"

    def test_relink_fails_without_pending_flow(self, client, app):
        user_data = _create_google_user(app)
        _login(client, user_data["username"])

        resp = client.post("/api/auth/google/device/relink", json={})
        assert resp.status_code == 400

    def test_relink_fails_if_google_id_belongs_to_another_user(self, client, app):
        user_data = _create_google_user(app, username="user_a", google_user_id="sub-a")
        _create_google_user(app, username="user_b", google_user_id="sub-b")
        _login(client, user_data["username"])

        # Try to relink user_a with user_b's google identity.
        _inject_device_flow_session(client, "sub-b", "userb@example.com")

        resp = client.post("/api/auth/google/device/relink", json={})
        assert resp.status_code == 409

    def test_relink_cleans_up_session_data(self, client, app):
        user_data = _create_google_user(app)
        _login(client, user_data["username"])
        _inject_device_flow_session(client, "google-sub-1", "guser@example.com")

        client.post("/api/auth/google/device/relink", json={})

        with client.session_transaction() as sess:
            assert "_device_flow_tokens" not in sess
            assert "_device_flow_identity" not in sess


class TestNeedsReauth:
    """Tests that ensure_access_token marks needs_reauth on invalid_grant."""

    def test_invalid_grant_marks_needs_reauth(self, app):
        from app.services.google_oauth import ensure_access_token

        with app.app_context():
            user = User(
                username="expuser",
                display_name="Exp",
                google_user_id="google-exp",
                auth_provider="google",
                is_active=True,
                setup_completed=True,
                google_auth_status="active",
            )
            user.set_password("pass1234")
            user.google_refresh_token = "old-refresh"
            user.google_token_expires_at = None
            user.google_access_token = None
            db.session.add(user)
            db.session.commit()

            with patch(
                "app.services.google_oauth.refresh_access_token",
                return_value={"error": "invalid_grant"},
            ):
                result = ensure_access_token(user)

            assert result is None
            assert user.google_auth_status == "needs_reauth"
