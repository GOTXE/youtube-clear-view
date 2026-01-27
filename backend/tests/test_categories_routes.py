"""Tests for Category routes."""

import json
import pytest

from app.extensions import db
from app.models import Category, Channel, ChannelCategory, UserChannel, Video


def test_get_categories(app, sample_user, sample_channel_category):
    """Test listing all categories."""
    with app.app_context():
        with app.test_client() as client:
            # Login
            response = client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )
            assert response.status_code == 200

            # Get categories
            response = client.get("/api/categories")
            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) >= 14  # 14 predefined categories

            # Each category should have required fields
            for cat in data:
                assert "id" in cat
                assert "name" in cat
                assert "channel_count" in cat


def test_get_category_details(app, sample_user, sample_channel_category):
    """Test getting details for a specific category."""
    with app.app_context():
        with app.test_client() as client:
            # Login
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            # Get the Gaming category (from sample_channel_category)
            category = Category.query.filter_by(name="Gaming").first()
            assert category is not None

            response = client.get(f"/api/categories/{category.id}")
            assert response.status_code == 200
            data = response.get_json()
            assert data["name"] == "Gaming"
            assert "channel_count" in data


def test_get_category_not_found(app, sample_user):
    """Test getting a non-existent category."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.get("/api/categories/99999")
            assert response.status_code == 404


def test_get_category_channels(app, sample_user, sample_channel_category):
    """Test getting channels in a category."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            category = Category.query.filter_by(name="Gaming").first()
            response = client.get(f"/api/categories/{category.id}/channels")
            assert response.status_code == 200
            data = response.get_json()
            assert "channels" in data
            assert "has_more" in data
            assert "next_offset" in data


def test_get_category_channels_pagination(app, sample_user):
    """Test channel pagination in categories."""
    with app.app_context():
        from app.models import User

        # Create multiple channels
        category = Category.query.filter_by(name="Technology").first()
        user = User.query.filter_by(id=sample_user["id"]).first()

        for i in range(5):
            channel = Channel(
                yt_channel_id=f"tech-channel-{i}",
                title=f"Tech Channel {i}",
            )
            db.session.add(channel)
            db.session.flush()

            subscription = UserChannel(user_id=user.id, channel_id=channel.id)
            db.session.add(subscription)

            channel_cat = ChannelCategory(
                channel_id=channel.id,
                category_id=category.id,
            )
            db.session.add(channel_cat)
        db.session.commit()

        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            # Test pagination
            response = client.get(f"/api/categories/{category.id}/channels?limit=2&offset=0")
            assert response.status_code == 200
            data = response.get_json()
            assert len(data["channels"]) == 2
            assert data["has_more"] is True


def test_get_category_videos(app, sample_user, sample_channel_category):
    """Test getting videos from channels in a category."""
    with app.app_context():
        # Create video for the channel
        channel_cat = ChannelCategory.query.first()
        channel = Channel.query.filter_by(id=channel_cat.channel_id).first()

        video = Video(
            yt_video_id="test-video-cat",
            channel_id=channel.id,
            title="Test Video",
        )
        db.session.add(video)
        db.session.commit()

        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            category = Category.query.filter_by(name="Gaming").first()
            response = client.get(f"/api/categories/{category.id}/videos")
            assert response.status_code == 200
            data = response.get_json()
            assert "videos" in data
            assert "has_more" in data


def test_reclassify_all(app, sample_user, sample_channel_category):
    """Test reclassifying all user's channels."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.post("/api/categories/reclassify-all")
            assert response.status_code == 200
            data = response.get_json()
            assert "reclassified" in data
            assert "total" in data
            assert "message" in data


def test_reclassify_all_no_channels(app, sample_user):
    """Test reclassifying when user has no channels."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.post("/api/categories/reclassify-all")
            assert response.status_code == 200
            data = response.get_json()
            assert data["reclassified"] == 0
            assert data["total"] == 0


def test_get_classifier_status(app, sample_user):
    """Test getting classifier status."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.get("/api/categories/status")
            assert response.status_code == 200
            data = response.get_json()
            assert "youtube_topics" in data
            assert "tfidf" in data
            assert "hybrid" in data
            assert "ollama" in data


def test_categories_require_auth(app):
    """Test that category endpoints require authentication."""
    with app.app_context():
        with app.test_client() as client:
            response = client.get("/api/categories")
            assert response.status_code == 401

            response = client.get("/api/categories/1")
            assert response.status_code == 401

            response = client.post("/api/categories/reclassify-all")
            assert response.status_code == 401
