"""Authentication endpoint tests."""

import pytest

from app import create_app
from app.extensions import db
from app.models import User


class TestConfig:
    """Minimal configuration for auth tests."""

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

    @staticmethod
    def validate():
        return None


class GoogleTestConfig(TestConfig):
    AUTH_MODE = "google"


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


@pytest.fixture()
def app_google():
    app = create_app(GoogleTestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client_google(app_google):
    return app_google.test_client()


def test_login_creates_user_and_cookie(client):
    response = client.post("/api/auth/login", json={"username": "alice"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["username"] == "alice"
    assert "session_token" not in data

    cookie = response.headers.get("Set-Cookie", "")
    assert "ytcv_session=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=Lax" in cookie


def test_login_requires_username_tracking_id(client):
    response = client.post("/api/auth/login", json={"username": ""})
    assert response.status_code == 400
    data = response.get_json()
    assert data.get("tracking_id")


def test_current_user_requires_cookie(client):
    response = client.get("/api/auth/current")
    assert response.status_code == 200
    data = response.get_json()
    assert data["authenticated"] is False


def test_current_user_returns_profile(client):
    client.post("/api/auth/login", json={"username": "bob"})
    response = client.get("/api/auth/current")
    assert response.status_code == 200
    data = response.get_json()
    assert data["username"] == "bob"
    assert data["authenticated"] is True


def test_auth_provider_defaults_local(client):
    response = client.get("/api/auth/provider")
    assert response.status_code == 200
    data = response.get_json()
    assert data["auth_mode"] == "local"


def test_list_users(client):
    client.post("/api/auth/login", json={"username": "carol"})
    response = client.get("/api/auth/users")
    assert response.status_code == 200
    data = response.get_json()
    assert any(user["username"] == "carol" for user in data)


def test_update_profile(client, app):
    client.post("/api/auth/login", json={"username": "dave"})
    response = client.put(
        "/api/auth/profile",
        json={"display_name": "Dave", "theme_preference": "dark"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["display_name"] == "Dave"
    assert data["theme_preference"] == "dark"

    with app.app_context():
        user = User.query.filter_by(username="dave").first()
        assert user.display_name == "Dave"
        assert user.theme_preference == "dark"


def test_logout_clears_token(client, app):
    client.post("/api/auth/login", json={"username": "erin"})
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    cookie = response.headers.get("Set-Cookie", "")
    assert "Max-Age=0" in cookie or "expires=" in cookie.lower()

    with app.app_context():
        user = User.query.filter_by(username="erin").first()
        assert user.session_token is None


def test_google_accounts_returns_known_accounts_for_browser(client_google, app_google):
    with app_google.app_context():
        user_a = User(
            username="alice@gmail.com",
            display_name="Alice",
            email="alice@gmail.com",
            auth_provider="google",
            google_user_id="sub-alice",
            session_token="token-alice",
        )
        user_b = User(
            username="bob@gmail.com",
            display_name="Bob",
            email="bob@gmail.com",
            auth_provider="google",
            google_user_id="sub-bob",
        )
        db.session.add_all([user_a, user_b])
        db.session.commit()

        alice_id = user_a.id
        bob_id = user_b.id

    with client_google.session_transaction() as sess:
        sess["known_google_user_ids"] = [bob_id, alice_id]

    client_google.set_cookie("ytcv_session", "token-alice")

    response = client_google.get("/api/auth/accounts")
    assert response.status_code == 200
    data = response.get_json()

    assert data["current_user_id"] == alice_id
    assert [account["id"] for account in data["accounts"]] == [bob_id, alice_id]
    assert data["accounts"][1]["is_current"] is True


def test_google_switch_account_sets_new_session_cookie(client_google, app_google):
    with app_google.app_context():
        user_a = User(
            username="alice@gmail.com",
            display_name="Alice",
            email="alice@gmail.com",
            auth_provider="google",
            google_user_id="sub-alice",
        )
        user_b = User(
            username="bob@gmail.com",
            display_name="Bob",
            email="bob@gmail.com",
            auth_provider="google",
            google_user_id="sub-bob",
        )
        db.session.add_all([user_a, user_b])
        db.session.commit()
        bob_id = user_b.id

    with client_google.session_transaction() as sess:
        sess["known_google_user_ids"] = [bob_id]

    response = client_google.post("/api/auth/switch", json={"user_id": bob_id})
    assert response.status_code == 200
    data = response.get_json()
    assert data["authenticated"] is True
    assert data["user_id"] == bob_id

    cookie = response.headers.get("Set-Cookie", "")
    assert "ytcv_session=" in cookie

    with app_google.app_context():
        user_b = User.query.filter_by(id=bob_id).first()
        assert user_b.session_token
