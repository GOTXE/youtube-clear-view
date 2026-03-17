"""Authentication endpoint tests."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app import create_app
from app.extensions import db
from app.models import User, UserPasskey
from app.services.totp_auth import generate_totp_code


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
    FRONTEND_URL = "http://localhost"
    PASSKEY_RP_ID = "localhost"
    PASSKEY_ORIGIN = "http://localhost"

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


def test_login_persists_hashed_session_only(client, app):
    client.post("/api/auth/login", json={"username": "alice"})

    with app.app_context():
        user = User.query.filter_by(username="alice").first()
        assert user.session_token is None
        assert user.session_token_hash


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


def test_login_with_totp_enabled_returns_mfa_challenge(client, app):
    with app.app_context():
        user = User(username="mfa-login", display_name="MFA Login")
        user.totp_secret = "JBSWY3DPEHPK3PXP"
        user.totp_enabled = True
        db.session.add(user)
        db.session.commit()

    response = client.post("/api/auth/login", json={"username": "mfa-login"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["authenticated"] is False
    assert data["mfa_required"] is True
    assert data["user_id"]

    cookie = response.headers.get("Set-Cookie", "")
    assert "ytcv_session=" in cookie
    assert "Max-Age=0" in cookie or "expires=" in cookie.lower()

    current_response = client.get("/api/auth/current")
    current_data = current_response.get_json()
    assert current_data["mfa_required"] is True
    assert current_data["user_id"] == data["user_id"]


def test_current_user_returns_profile(client):
    client.post("/api/auth/login", json={"username": "bob"})
    response = client.get("/api/auth/current")
    assert response.status_code == 200
    data = response.get_json()
    assert data["username"] == "bob"
    assert data["authenticated"] is True


def test_verify_mfa_challenge_with_totp_creates_session(client, app):
    with app.app_context():
        user = User(username="mfa-verify", display_name="MFA Verify")
        user.totp_secret = "JBSWY3DPEHPK3PXP"
        user.totp_enabled = True
        db.session.add(user)
        db.session.commit()

    client.post("/api/auth/login", json={"username": "mfa-verify"})
    response = client.post(
        "/api/auth/mfa/verify",
        json={"method": "totp", "code": generate_totp_code("JBSWY3DPEHPK3PXP")},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["authenticated"] is True
    assert data["username"] == "mfa-verify"
    assert "ytcv_session=" in response.headers.get("Set-Cookie", "")


def test_verify_mfa_challenge_with_recovery_code_consumes_code(client):
    client.post("/api/auth/login", json={"username": "mfa-recovery-login"})
    setup_data = client.post("/api/auth/totp/setup").get_json()
    confirm_data = client.post(
        "/api/auth/totp/confirm",
        json={"code": generate_totp_code(setup_data["secret"])},
    ).get_json()
    recovery_code = confirm_data["recovery_codes"][0]
    client.post("/api/auth/logout")

    login_response = client.post("/api/auth/login", json={"username": "mfa-recovery-login"})
    assert login_response.get_json()["mfa_required"] is True

    verify_response = client.post(
        "/api/auth/mfa/verify",
        json={"method": "recovery_code", "code": recovery_code},
    )
    assert verify_response.status_code == 200
    assert verify_response.get_json()["authenticated"] is True

    with client.session_transaction() as sess:
        assert "mfa_challenge" not in sess


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
        assert user.session_token_hash is None


def test_current_user_migrates_legacy_session_token(client, app):
    with app.app_context():
        user = User(username="legacy", display_name="Legacy", session_token="legacy-token")
        db.session.add(user)
        db.session.commit()

    client.set_cookie("ytcv_session", "legacy-token")
    response = client.get("/api/auth/current")

    assert response.status_code == 200
    assert response.get_json()["authenticated"] is True

    with app.app_context():
        user = User.query.filter_by(username="legacy").first()
        assert user.session_token is None
        assert user.session_token_hash


def test_google_tokens_are_encrypted_at_rest(client, app):
    with app.app_context():
        user = User(
            username="secure@gmail.com",
            display_name="Secure",
            email="secure@gmail.com",
            auth_provider="google",
        )
        user.google_access_token = "access-token"
        user.google_refresh_token = "refresh-token"
        user.google_scopes = "openid email profile"
        db.session.add(user)
        db.session.commit()

        stored = User.query.filter_by(username="secure@gmail.com").first()
        assert stored._google_access_token != "access-token"
        assert stored._google_refresh_token != "refresh-token"
        assert stored._google_scopes != "openid email profile"
        assert stored.google_access_token == "access-token"
        assert stored.google_refresh_token == "refresh-token"
        assert stored.google_scopes == "openid email profile"


def test_passkey_registration_persists_credential(client, app, monkeypatch):
    client.post("/api/auth/login", json={"username": "alice"})

    response = client.post("/api/auth/passkeys/register/options", json={"label": "Laptop"})
    assert response.status_code == 200
    assert "publicKey" in response.get_json()

    def fake_verify_registration(credential, expected_challenge):
        assert expected_challenge
        return SimpleNamespace(
            credential_id=b"credential-1",
            credential_public_key=b"public-key-1",
            sign_count=1,
            aaguid="aaguid-1",
            credential_device_type=SimpleNamespace(value="single_device"),
            credential_backed_up=False,
        )

    monkeypatch.setattr("app.routes.auth.verify_registration_credential", fake_verify_registration)

    verify_response = client.post(
        "/api/auth/passkeys/register/verify",
        json={"credential": {"id": "ignored"}, "transports": ["internal"]},
    )
    assert verify_response.status_code == 200
    data = verify_response.get_json()
    assert data["passkey"]["label"] == "Laptop"
    assert data["passkey"]["transports"] == ["internal"]

    with app.app_context():
        user = User.query.filter_by(username="alice").first()
        assert len(user.passkeys) == 1
        assert user.passkeys[0].credential_id


def test_passkey_authentication_creates_session(client, app, monkeypatch):
    with app.app_context():
        user = User(username="passkey-user", display_name="Passkey User")
        passkey = UserPasskey(
            user=user,
            label="Phone",
            credential_id="credential-1",
            public_key="cHVibGljLWtleS0x",
            sign_count=7,
        )
        db.session.add_all([user, passkey])
        db.session.commit()

    options_response = client.post("/api/auth/passkeys/authenticate/options")
    assert options_response.status_code == 200
    assert "publicKey" in options_response.get_json()

    def fake_verify_authentication(credential, passkey, expected_challenge):
        assert credential["id"] == "credential-1"
        assert expected_challenge
        return SimpleNamespace(
            credential_id=b"credential-1",
            new_sign_count=8,
            credential_device_type=SimpleNamespace(value="single_device"),
            credential_backed_up=True,
            user_verified=True,
        )

    monkeypatch.setattr("app.routes.auth.verify_authentication_credential", fake_verify_authentication)

    verify_response = client.post(
        "/api/auth/passkeys/authenticate/verify",
        json={"credential": {"id": "credential-1"}},
    )
    assert verify_response.status_code == 200
    data = verify_response.get_json()
    assert data["authenticated"] is True
    assert data["username"] == "passkey-user"
    assert "ytcv_session=" in verify_response.headers.get("Set-Cookie", "")

    with app.app_context():
        stored_passkey = UserPasskey.query.filter_by(credential_id="credential-1").first()
        assert stored_passkey.sign_count == 8
        assert stored_passkey.credential_backed_up is True
        assert stored_passkey.last_used_at is not None


def test_list_and_delete_passkeys(client, app):
    with app.app_context():
        user = User(username="owner", display_name="Owner")
        db.session.add(user)
        db.session.commit()
        passkey = UserPasskey(
            user_id=user.id,
            label="Tablet",
            credential_id="credential-abc",
            public_key="cHVibGljLWtleQ",
            sign_count=0,
        )
        db.session.add(passkey)
        db.session.commit()

    client.post("/api/auth/login", json={"username": "owner"})

    list_response = client.get("/api/auth/passkeys")
    assert list_response.status_code == 200
    payload = list_response.get_json()
    assert len(payload["passkeys"]) == 1
    passkey_id = payload["passkeys"][0]["id"]

    delete_response = client.delete(f"/api/auth/passkeys/{passkey_id}")
    assert delete_response.status_code == 200
    assert delete_response.get_json()["deleted"] is True

    with app.app_context():
        assert UserPasskey.query.filter_by(id=passkey_id).first() is None


def test_google_accounts_returns_known_accounts_for_browser(client_google, app_google):
    with app_google.app_context():
        user_a = User(
            username="alice@gmail.com",
            display_name="Alice",
            email="alice@gmail.com",
            auth_provider="google",
            google_user_id="sub-alice",
            session_token="token-alice",
            google_auth_status="active",
        )
        user_b = User(
            username="bob@gmail.com",
            display_name="Bob",
            email="bob@gmail.com",
            auth_provider="google",
            google_user_id="sub-bob",
            google_auth_status="active",
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
            google_auth_status="active",
        )
        user_b = User(
            username="bob@gmail.com",
            display_name="Bob",
            email="bob@gmail.com",
            auth_provider="google",
            google_user_id="sub-bob",
            google_auth_status="active",
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
        assert user_b.session_token is None
        assert user_b.session_token_hash


def test_google_switch_account_with_totp_enabled_returns_mfa_challenge(client_google, app_google):
    with app_google.app_context():
        user_b = User(
            username="bob+mfa@gmail.com",
            display_name="Bob MFA",
            email="bob+mfa@gmail.com",
            auth_provider="google",
            google_user_id="sub-bob-mfa",
            google_auth_status="active",
        )
        user_b.totp_secret = "JBSWY3DPEHPK3PXP"
        user_b.totp_enabled = True
        db.session.add(user_b)
        db.session.commit()
        bob_id = user_b.id

    with client_google.session_transaction() as sess:
        sess["known_google_user_ids"] = [bob_id]

    response = client_google.post("/api/auth/switch", json={"user_id": bob_id})
    assert response.status_code == 200
    data = response.get_json()
    assert data["authenticated"] is False
    assert data["mfa_required"] is True
    assert data["user_id"] == bob_id


def test_pairing_flow_start_approve_claim(client, app):
    with app.app_context():
        user = User(username="pair-owner", display_name="Pair Owner")
        db.session.add(user)
        db.session.commit()

    start_response = client.post("/api/auth/pairing/start", json={"device_identifier": "living-room-tv"})
    assert start_response.status_code == 200
    start_data = start_response.get_json()
    assert start_data["status"] == "pending"
    assert start_data["pairing_code"]
    assert start_data["public_id"]

    client.post("/api/auth/login", json={"username": "pair-owner"})
    approve_response = client.post(
        "/api/auth/pairing/approve",
        json={"code": start_data["pairing_code"]},
    )
    assert approve_response.status_code == 200
    assert approve_response.get_json()["status"] == "approved"

    claim_client = app.test_client()
    claim_response = claim_client.post(
        "/api/auth/pairing/claim",
        json={"public_id": start_data["public_id"]},
    )
    assert claim_response.status_code == 200
    claim_data = claim_response.get_json()
    assert claim_data["authenticated"] is True
    assert claim_data["pairing_claimed"] is True
    assert claim_data["username"] == "pair-owner"
    assert "ytcv_session=" in claim_response.headers.get("Set-Cookie", "")


def test_pairing_claim_returns_pending_until_approved(client):
    start_data = client.post("/api/auth/pairing/start").get_json()
    claim_response = client.post("/api/auth/pairing/claim", json={"public_id": start_data["public_id"]})
    assert claim_response.status_code == 200
    assert claim_response.get_json()["status"] == "pending"


def test_pairing_claim_is_single_use(client, app):
    with app.app_context():
        user = User(username="pair-once", display_name="Pair Once")
        db.session.add(user)
        db.session.commit()

    start_data = client.post("/api/auth/pairing/start").get_json()
    client.post("/api/auth/login", json={"username": "pair-once"})
    client.post("/api/auth/pairing/approve", json={"code": start_data["pairing_code"]})

    claim_client = app.test_client()
    first_claim = claim_client.post("/api/auth/pairing/claim", json={"public_id": start_data["public_id"]})
    assert first_claim.status_code == 200

    second_claim = claim_client.post("/api/auth/pairing/claim", json={"public_id": start_data["public_id"]})
    assert second_claim.status_code == 409


def test_pairing_expiry_is_enforced(client, app):
    start_data = client.post("/api/auth/pairing/start").get_json()

    with app.app_context():
        from app.models import LoginPairing

        pairing = LoginPairing.query.filter_by(public_id=start_data["public_id"]).first()
        pairing.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()

    claim_response = client.post("/api/auth/pairing/claim", json={"public_id": start_data["public_id"]})
    assert claim_response.status_code == 410


def test_google_unlink_clears_tokens_and_sets_revoked(client_google, app_google, monkeypatch):
    with app_google.app_context():
        user = User(
            username="unlink@gmail.com",
            display_name="Unlink",
            email="unlink@gmail.com",
            auth_provider="google",
            google_user_id="sub-unlink",
            google_auth_status="active",
        )
        user.google_access_token = "access-token"
        user.google_refresh_token = "refresh-token"
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    monkeypatch.setattr("app.routes.auth.revoke_google_tokens", lambda token: True)

    response = client_google.post("/api/auth/switch", json={"user_id": user_id})
    assert response.status_code == 403

    with client_google.session_transaction() as sess:
        sess["known_google_user_ids"] = [user_id]

    response = client_google.post("/api/auth/switch", json={"user_id": user_id})
    assert response.status_code == 200

    response = client_google.post("/api/auth/google/unlink")
    assert response.status_code == 200
    data = response.get_json()
    assert data["google_auth_status"] == "revoked"

    with app_google.app_context():
        user = User.query.filter_by(id=user_id).first()
        assert user.google_access_token is None
        assert user.google_refresh_token is None
        assert user.google_auth_status == "revoked"


def test_totp_enrollment_and_recovery_codes(client, app):
    client.post("/api/auth/login", json={"username": "mfa-user"})

    setup_response = client.post("/api/auth/totp/setup")
    assert setup_response.status_code == 200
    setup_data = setup_response.get_json()
    assert setup_data["secret"]
    assert setup_data["otpauth_url"].startswith("otpauth://totp/")

    confirm_response = client.post(
        "/api/auth/totp/confirm",
        json={"code": generate_totp_code(setup_data["secret"])},
    )
    assert confirm_response.status_code == 200
    confirm_data = confirm_response.get_json()
    assert confirm_data["totp_enabled"] is True
    assert len(confirm_data["recovery_codes"]) == 8

    status_response = client.get("/api/auth/mfa/status")
    assert status_response.status_code == 200
    status_data = status_response.get_json()
    assert status_data["totp_enabled"] is True
    assert status_data["totp_pending"] is False
    assert status_data["recovery_codes_remaining"] == 8

    with app.app_context():
        user = User.query.filter_by(username="mfa-user").first()
        assert user.totp_enabled is True
        assert user.totp_secret == setup_data["secret"]
        assert user._totp_secret != setup_data["secret"]


def test_recovery_code_can_be_consumed_once(client):
    client.post("/api/auth/login", json={"username": "recover-user"})
    setup_data = client.post("/api/auth/totp/setup").get_json()
    confirm_data = client.post(
        "/api/auth/totp/confirm",
        json={"code": generate_totp_code(setup_data["secret"])},
    ).get_json()
    recovery_code = confirm_data["recovery_codes"][0]

    consume_response = client.post("/api/auth/recovery-codes/consume", json={"code": recovery_code})
    assert consume_response.status_code == 200
    assert consume_response.get_json()["recovery_codes_remaining"] == 7

    second_response = client.post("/api/auth/recovery-codes/consume", json={"code": recovery_code})
    assert second_response.status_code == 400


def test_recovery_codes_regenerate_requires_valid_totp(client):
    client.post("/api/auth/login", json={"username": "rotate-user"})
    setup_data = client.post("/api/auth/totp/setup").get_json()
    client.post(
        "/api/auth/totp/confirm",
        json={"code": generate_totp_code(setup_data["secret"])},
    )

    bad_response = client.post("/api/auth/recovery-codes/regenerate", json={"code": "000000"})
    assert bad_response.status_code == 400

    good_response = client.post(
        "/api/auth/recovery-codes/regenerate",
        json={"code": generate_totp_code(setup_data["secret"])},
    )
    assert good_response.status_code == 200
    assert len(good_response.get_json()["recovery_codes"]) == 8
