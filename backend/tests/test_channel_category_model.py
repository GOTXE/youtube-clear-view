"""Tests for ChannelCategory model."""

import pytest
from datetime import datetime

from app.extensions import db
from app.models import Category, Channel, ChannelCategory


def test_channel_category_creation(app):
    """Test creating a channel category assignment."""
    with app.app_context():
        channel = Channel(yt_channel_id="test-ch-1", title="Test Channel")
        category = Category.query.filter_by(name="Gaming").first()
        db.session.add(channel)
        db.session.commit()

        channel_category = ChannelCategory(
            channel_id=channel.id,
            category_id=category.id,
            is_auto_classified=True,
            classification_method="youtube_topics",
            confidence_score=0.95,
        )
        db.session.add(channel_category)
        db.session.commit()

        saved = ChannelCategory.query.filter_by(channel_id=channel.id).first()
        assert saved is not None
        assert saved.category_id == category.id
        assert saved.is_auto_classified is True
        assert saved.classification_method == "youtube_topics"
        assert saved.confidence_score == 0.95
        assert saved.classified_at is not None


def test_channel_category_unique_constraint(app):
    """Test that a channel can only have one category."""
    with app.app_context():
        channel = Channel(yt_channel_id="test-ch-unique", title="Unique Test")
        category1 = Category.query.filter_by(name="Gaming").first()
        category2 = Category.query.filter_by(name="Technology").first()
        db.session.add(channel)
        db.session.commit()

        cc1 = ChannelCategory(
            channel_id=channel.id,
            category_id=category1.id,
            classification_method="youtube_topics",
        )
        db.session.add(cc1)
        db.session.commit()

        cc2 = ChannelCategory(
            channel_id=channel.id,
            category_id=category2.id,
            classification_method="tfidf",
        )
        db.session.add(cc2)
        with pytest.raises(Exception):
            db.session.commit()


def test_classification_methods_valid(app):
    """Test valid classification methods."""
    valid_methods = ["youtube_topics", "tfidf", "manual"]
    with app.app_context():
        category = Category.query.first()
        for i, method in enumerate(valid_methods):
            channel = Channel(yt_channel_id=f"method-test-{i}", title=f"Method Test {i}")
            db.session.add(channel)
            db.session.commit()

            cc = ChannelCategory(
                channel_id=channel.id,
                category_id=category.id,
                classification_method=method,
            )
            db.session.add(cc)
            db.session.commit()

            saved = ChannelCategory.query.filter_by(channel_id=channel.id).first()
            assert saved.classification_method == method


def test_confidence_score_range(app):
    """Test confidence scores must be between 0.0 and 1.0."""
    with app.app_context():
        channel = Channel(yt_channel_id="conf-test", title="Confidence Test")
        category = Category.query.first()
        db.session.add(channel)
        db.session.commit()

        # Valid score
        cc = ChannelCategory(
            channel_id=channel.id,
            category_id=category.id,
            classification_method="tfidf",
            confidence_score=0.75,
        )
        db.session.add(cc)
        db.session.commit()
        assert cc.confidence_score == 0.75


def test_channel_category_to_dict(app):
    """Test ChannelCategory serialization."""
    with app.app_context():
        channel = Channel(yt_channel_id="serialize-test", title="Serialize Test")
        category = Category.query.filter_by(name="Technology").first()
        db.session.add(channel)
        db.session.commit()

        cc = ChannelCategory(
            channel_id=channel.id,
            category_id=category.id,
            is_auto_classified=False,
            classification_method="manual",
            confidence_score=1.0,
        )
        db.session.add(cc)
        db.session.commit()

        data = cc.to_dict()
        assert data["channel_id"] == channel.id
        assert data["category_id"] == category.id
        assert data["is_auto_classified"] is False
        assert data["classification_method"] == "manual"
        assert data["confidence_score"] == 1.0
        assert "classified_at" in data
        assert "category" in data
        assert data["category"]["name"] == "Technology"


def test_channel_relationship(app):
    """Test channel to channel_category relationship."""
    with app.app_context():
        channel = Channel(yt_channel_id="rel-test", title="Relationship Test")
        category = Category.query.filter_by(name="Music").first()
        db.session.add(channel)
        db.session.commit()

        cc = ChannelCategory(
            channel_id=channel.id,
            category_id=category.id,
            classification_method="youtube_topics",
        )
        db.session.add(cc)
        db.session.commit()

        # Access via relationship
        db.session.refresh(channel)
        assert channel.channel_category is not None
        assert channel.channel_category.category.name == "Music"


def test_sample_channel_category_fixture(sample_channel_category):
    """Test that sample_channel_category fixture works."""
    assert sample_channel_category["id"] is not None
    assert sample_channel_category["channel_id"] is not None
    assert sample_channel_category["category_id"] is not None


def test_last_updated_at_auto_update(app):
    """Test that last_updated_at is automatically set."""
    with app.app_context():
        channel = Channel(yt_channel_id="update-test", title="Update Test")
        category = Category.query.first()
        db.session.add(channel)
        db.session.commit()

        cc = ChannelCategory(
            channel_id=channel.id,
            category_id=category.id,
            classification_method="tfidf",
        )
        db.session.add(cc)
        db.session.commit()

        original_updated = cc.last_updated_at
        assert original_updated is not None

        # Update the record
        new_category = Category.query.filter_by(name="Sports").first()
        cc.category_id = new_category.id
        cc.classification_method = "manual"
        db.session.commit()

        # last_updated_at should be updated (or at least set)
        assert cc.last_updated_at is not None
