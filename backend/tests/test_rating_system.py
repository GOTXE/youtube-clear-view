"""Tests for channel rating system."""

import pytest
from datetime import datetime

from app.extensions import db
from app.models import Channel, User, UserChannel


def test_channel_rating_creation(app):
    """Test rating a channel."""
    with app.app_context():
        user = User(username="rater", display_name="Rater User")
        channel = Channel(yt_channel_id="rate-test", title="Rating Test")
        db.session.add_all([user, channel])
        db.session.commit()

        subscription = UserChannel(
            user_id=user.id,
            channel_id=channel.id,
            rating=5,
            rated_at=datetime.utcnow(),
        )
        db.session.add(subscription)
        db.session.commit()

        saved = UserChannel.query.filter_by(user_id=user.id, channel_id=channel.id).first()
        assert saved.rating == 5
        assert saved.rated_at is not None


def test_rating_valid_range(app):
    """Test valid rating values (1-5)."""
    with app.app_context():
        user = User(username="range-tester", display_name="Range Tester")
        db.session.add(user)
        db.session.commit()

        valid_ratings = [1, 2, 3, 4, 5]
        for rating in valid_ratings:
            channel = Channel(yt_channel_id=f"rate-{rating}", title=f"Rating {rating}")
            db.session.add(channel)
            db.session.commit()

            subscription = UserChannel(
                user_id=user.id,
                channel_id=channel.id,
                rating=rating,
            )
            db.session.add(subscription)
            db.session.commit()

            saved = UserChannel.query.filter_by(channel_id=channel.id).first()
            assert saved.rating == rating


def test_rating_nullable(app):
    """Test that rating can be null (no rating)."""
    with app.app_context():
        user = User(username="nullable-tester", display_name="Nullable Tester")
        channel = Channel(yt_channel_id="no-rate", title="No Rating")
        db.session.add_all([user, channel])
        db.session.commit()

        subscription = UserChannel(
            user_id=user.id,
            channel_id=channel.id,
        )
        db.session.add(subscription)
        db.session.commit()

        saved = UserChannel.query.filter_by(channel_id=channel.id).first()
        assert saved.rating is None
        assert saved.rated_at is None


def test_rating_update(app):
    """Test updating a rating."""
    with app.app_context():
        user = User(username="updater", display_name="Rating Updater")
        channel = Channel(yt_channel_id="update-rate", title="Update Rating")
        db.session.add_all([user, channel])
        db.session.commit()

        subscription = UserChannel(
            user_id=user.id,
            channel_id=channel.id,
            rating=3,
        )
        db.session.add(subscription)
        db.session.commit()

        # Update rating
        subscription.rating = 5
        subscription.rated_at = datetime.utcnow()
        db.session.commit()

        saved = UserChannel.query.filter_by(channel_id=channel.id).first()
        assert saved.rating == 5


def test_rating_clear(app):
    """Test clearing a rating."""
    with app.app_context():
        user = User(username="clearer", display_name="Rating Clearer")
        channel = Channel(yt_channel_id="clear-rate", title="Clear Rating")
        db.session.add_all([user, channel])
        db.session.commit()

        subscription = UserChannel(
            user_id=user.id,
            channel_id=channel.id,
            rating=4,
            rated_at=datetime.utcnow(),
        )
        db.session.add(subscription)
        db.session.commit()

        # Clear rating
        subscription.rating = None
        subscription.rated_at = None
        db.session.commit()

        saved = UserChannel.query.filter_by(channel_id=channel.id).first()
        assert saved.rating is None


def test_rating_to_dict(app):
    """Test rating fields in UserChannel serialization."""
    with app.app_context():
        user = User(username="serializer", display_name="Serializer")
        channel = Channel(yt_channel_id="serialize-rate", title="Serialize Rating")
        db.session.add_all([user, channel])
        db.session.commit()

        subscription = UserChannel(
            user_id=user.id,
            channel_id=channel.id,
            rating=4,
            rated_at=datetime.utcnow(),
        )
        db.session.add(subscription)
        db.session.commit()

        data = subscription.to_dict()
        assert data["rating"] == 4
        assert "rated_at" in data
        assert data["rated_at"] is not None


def test_rating_index_query(app):
    """Test querying by rating (using index)."""
    with app.app_context():
        user = User(username="indexer", display_name="Index Tester")
        db.session.add(user)
        db.session.commit()

        # Create channels with different ratings
        ratings = [1, 2, 3, 4, 5, None, None, 3, 5]
        for i, rating in enumerate(ratings):
            channel = Channel(yt_channel_id=f"index-{i}", title=f"Index Test {i}")
            db.session.add(channel)
            db.session.commit()

            subscription = UserChannel(
                user_id=user.id,
                channel_id=channel.id,
                rating=rating,
            )
            db.session.add(subscription)
            db.session.commit()

        # Query channels with rating >= 4
        high_rated = UserChannel.query.filter(
            UserChannel.user_id == user.id,
            UserChannel.rating >= 4
        ).all()
        assert len(high_rated) == 3  # 4, 5, 5

        # Query channels with rating 3
        rated_3 = UserChannel.query.filter(
            UserChannel.user_id == user.id,
            UserChannel.rating == 3
        ).all()
        assert len(rated_3) == 2  # 3, 3

        # Query unrated channels
        unrated = UserChannel.query.filter(
            UserChannel.user_id == user.id,
            UserChannel.rating.is_(None)
        ).all()
        assert len(unrated) == 2


def test_sample_subscription_no_rating(sample_subscription, app):
    """Test that sample_subscription fixture has no rating by default."""
    with app.app_context():
        subscription = UserChannel.query.get(sample_subscription["id"])
        assert subscription.rating is None
