"""Log viewer basic auth tests."""

import base64
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from log_viewer.app import app


@pytest.fixture()
def client(monkeypatch, tmp_path):
    log_path = tmp_path / "app.log"
    log_path.write_text("[INFO] Test\n[ERROR] Boom\n")
    monkeypatch.setenv("LOG_VIEWER_USER", "admin")
    monkeypatch.setenv("LOG_VIEWER_PASSWORD", "secret")
    monkeypatch.setenv("LOG_FILE", str(log_path))
    app.config.update(TESTING=True)
    app.config["LOG_VIEWER_USER"] = "admin"
    app.config["LOG_VIEWER_PASSWORD"] = "secret"
    app.config["LOG_FILE"] = str(log_path)
    return app.test_client()


def _auth_header():
    token = base64.b64encode(b"admin:secret").decode("utf-8")
    return {"Authorization": f"Basic {token}"}


def test_requires_auth(client):
    response = client.get("/logs")
    assert response.status_code == 401


def test_entries(client):
    response = client.get("/logs/api/entries", headers=_auth_header())
    assert response.status_code == 200
    data = response.get_json()
    assert data["entries"][0].startswith("[ERROR]")


def test_stats(client):
    response = client.get("/logs/api/stats", headers=_auth_header())
    assert response.status_code == 200
    data = response.get_json()
    assert data["levels"]["ERROR"] == 1
