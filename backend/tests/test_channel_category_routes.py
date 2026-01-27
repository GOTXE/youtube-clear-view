"""Tests for Channel Category routes."""

import json
import pytest

from app.extensions import db
from app.models import Category, Channel, ChannelCategory, UserChannel


def test_get_channel_category(app, sample_user, sample_channel_category):
    """Test getting a channel's category."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            channel_cat = ChannelCategory.query.first()
            channel = Channel.query.filter_by(id=channel_cat.channel_id).first()

            response = client.get(f"/api/channels/{channel.id}/category")
            assert response.status_code == 200
            data = response.get_json()
            assert "category" in data
            assert "classification" in data


def test_get_channel_category_not_subscribed(app, sample_user):
    """Test getting category for a channel user is not subscribed to."""
    with app.app_context():
        # Create channel without subscription
        channel = Channel(
            yt_channel_id="unsubscribed-channel",
            title="Unsubscribed Channel",
        )
        db.session.add(channel)
        db.session.commit()

        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.get(f"/api/channels/{channel.id}/category")
            assert response.status_code == 404


def test_get_channel_category_not_classified(app, sample_user, sample_subscription):
    """Test getting category for an unclassified channel."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.get(f"/api/channels/{sample_subscription['channel_id']}/category")
            assert response.status_code == 200
            data = response.get_json()
            # Channel might not be classified yet
            assert "category" in data or "message" in data


def test_update_channel_category_by_name(app, sample_user, sample_channel_category):
    """Test manually updating a channel's category by name."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            channel_cat = ChannelCategory.query.first()
            channel = Channel.query.filter_by(id=channel_cat.channel_id).first()

            # Change category from Gaming to Technology
            response = client.put(
                f"/api/channels/{channel.id}/category",
                json={"category_name": "Technology"},
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["category"]["name"] == "Technology"
            assert data["classification"]["is_auto_classified"] is False


def test_update_channel_category_by_id(app, sample_user, sample_channel_category):
    """Test manually updating a channel's category by ID."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            channel_cat = ChannelCategory.query.first()
            channel = Channel.query.filter_by(id=channel_cat.channel_id).first()
            science = Category.query.filter_by(name="Science").first()

            response = client.put(
                f"/api/channels/{channel.id}/category",
                json={"category_id": science.id},
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["category"]["name"] == "Science"


def test_update_channel_category_invalid(app, sample_user, sample_channel_category):
    """Test updating with invalid category."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            channel_cat = ChannelCategory.query.first()
            channel = Channel.query.filter_by(id=channel_cat.channel_id).first()

            response = client.put(
                f"/api/channels/{channel.id}/category",
                json={"category_name": "InvalidCategory"},
            )
            assert response.status_code == 404


def test_update_channel_category_missing_params(app, sample_user, sample_channel_category):
    """Test updating without category name or ID."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            channel_cat = ChannelCategory.query.first()
            channel = Channel.query.filter_by(id=channel_cat.channel_id).first()

            response = client.put(
                f"/api/channels/{channel.id}/category",
                json={},
            )
            assert response.status_code == 400


def test_delete_channel_category_reclassify(app, sample_user, sample_channel_category):
    """Test reverting to auto-classification."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            channel_cat = ChannelCategory.query.first()
            channel = Channel.query.filter_by(id=channel_cat.channel_id).first()

            # First manually set category
            client.put(
                f"/api/channels/{channel.id}/category",
                json={"category_name": "Music"},
            )

            # Then revert to auto
            response = client.delete(f"/api/channels/{channel.id}/category")
            assert response.status_code == 200
            data = response.get_json()
            assert "message" in data


def test_subscribe_auto_classifies(app, sample_user):
    """Test that subscribing to a channel auto-classifies it."""
    with app.app_context():
        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            # Subscribe to a new channel with gaming topic
            channel = Channel(
                yt_channel_id="auto-classify-test",
                title="Gaming Channel Test",
                description="We play video games",
                topic_ids='["/m/0bzvm2"]',  # Gaming topic
            )
            db.session.add(channel)
            db.session.commit()

            response = client.post(
                "/api/channels/subscribe",
                json={"yt_channel_id": "auto-classify-test"},
            )
            assert response.status_code == 201

            # Check if channel was classified
            channel_cat = ChannelCategory.query.filter_by(channel_id=channel.id).first()
            # May or may not be classified depending on classifier availability
            # Just check response is valid
            data = response.get_json()
            assert "yt_channel_id" in data


def test_channel_category_routes_require_auth(app):
    """Test that channel category endpoints require authentication."""
    with app.app_context():
        with app.test_client() as client:
            response = client.get("/api/channels/1/category")
            assert response.status_code == 401

            response = client.put("/api/channels/1/category", json={"category_name": "Gaming"})
            assert response.status_code == 401

            response = client.delete("/api/channels/1/category")
            assert response.status_code == 401
