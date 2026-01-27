"""Tests for Rating routes."""

import json
import pytest

from app.extensions import db
from app.models import Channel, UserChannel


def test_rate_channel(app, sample_user, sample_subscription):
    """Test rating a channel."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.put(
                f"/api/channels/{sample_subscription['channel_id']}/rating",
                json={"rating": 5},
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["rating"] == 5
            assert data["channel_id"] == sample_subscription["channel_id"]
            assert "rated_at" in data


def test_rate_channel_all_values(app, sample_user, sample_subscription):
    """Test rating a channel with all valid values (1-5)."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            for rating in range(1, 6):
                response = client.put(
                    f"/api/channels/{sample_subscription['channel_id']}/rating",
                    json={"rating": rating},
                )
                assert response.status_code == 200
                data = response.get_json()
                assert data["rating"] == rating


def test_rate_channel_invalid_value_too_low(app, sample_user, sample_subscription):
    """Test rating with invalid value (0)."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.put(
                f"/api/channels/{sample_subscription['channel_id']}/rating",
                json={"rating": 0},
            )
            assert response.status_code == 400


def test_rate_channel_invalid_value_too_high(app, sample_user, sample_subscription):
    """Test rating with invalid value (6)."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.put(
                f"/api/channels/{sample_subscription['channel_id']}/rating",
                json={"rating": 6},
            )
            assert response.status_code == 400


def test_rate_channel_invalid_value_string(app, sample_user, sample_subscription):
    """Test rating with non-numeric value."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.put(
                f"/api/channels/{sample_subscription['channel_id']}/rating",
                json={"rating": "five"},
            )
            assert response.status_code == 400


def test_rate_channel_missing_rating(app, sample_user, sample_subscription):
    """Test rating without rating value."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.put(
                f"/api/channels/{sample_subscription['channel_id']}/rating",
                json={},
            )
            assert response.status_code == 400


def test_rate_channel_not_subscribed(app, sample_user):
    """Test rating a channel user is not subscribed to."""
    with app.app_context():
        channel = Channel(
            yt_channel_id="not-subscribed-rating",
            title="Not Subscribed Channel",
        )
        db.session.add(channel)
        db.session.commit()

        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.put(
                f"/api/channels/{channel.id}/rating",
                json={"rating": 5},
            )
            assert response.status_code == 404


def test_update_rating(app, sample_user, sample_subscription):
    """Test updating an existing rating."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            # First rating
            response = client.put(
                f"/api/channels/{sample_subscription['channel_id']}/rating",
                json={"rating": 3},
            )
            assert response.status_code == 200
            first_rated_at = response.get_json()["rated_at"]

            # Update rating
            response = client.put(
                f"/api/channels/{sample_subscription['channel_id']}/rating",
                json={"rating": 5},
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["rating"] == 5
            # rated_at should be updated
            assert data["rated_at"] >= first_rated_at


def test_delete_rating(app, sample_user, sample_subscription):
    """Test removing a rating."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            # First add a rating
            client.put(
                f"/api/channels/{sample_subscription['channel_id']}/rating",
                json={"rating": 4},
            )

            # Delete rating
            response = client.delete(f"/api/channels/{sample_subscription['channel_id']}/rating")
            assert response.status_code == 200
            data = response.get_json()
            assert data["rating"] is None


def test_delete_rating_not_subscribed(app, sample_user):
    """Test deleting rating for unsubscribed channel."""
    with app.app_context():
        channel = Channel(
            yt_channel_id="not-subscribed-delete",
            title="Not Subscribed Channel",
        )
        db.session.add(channel)
        db.session.commit()

        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.delete(f"/api/channels/{channel.id}/rating")
            assert response.status_code == 404


def test_list_channels_includes_rating(app, sample_user, sample_subscription):
    """Test that list channels includes rating information."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            # Add rating
            client.put(
                f"/api/channels/{sample_subscription['channel_id']}/rating",
                json={"rating": 4},
            )

            # List channels
            response = client.get("/api/channels")
            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, list)
            if data:
                channel = next((c for c in data if c["id"] == sample_subscription["channel_id"]), None)
                assert channel is not None
                assert "rating" in channel
                assert channel["rating"] == 4


def test_rating_routes_require_auth(app):
    """Test that rating endpoints require authentication."""
    with app.app_context():
        with app.test_client() as client:
            response = client.put("/api/channels/1/rating", json={"rating": 5})
            assert response.status_code == 401

            response = client.delete("/api/channels/1/rating")
            assert response.status_code == 401
