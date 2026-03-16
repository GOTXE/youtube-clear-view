"""Tests for Classification service."""

import json

from app.extensions import db
from app.models import Category, Channel, Video
from app.services import ClassificationService


def test_classify_channel_with_topics(app):
    """Test classification using YouTube Topics (highest priority)."""
    with app.app_context():
        # Create channel with topic IDs
        channel = Channel(
            yt_channel_id="topics-test",
            title="Gaming Channel",
            description="We play video games",
            topic_ids=json.dumps(["/m/0bzvm2"]),  # Gaming topic
        )
        db.session.add(channel)
        db.session.commit()

        service = ClassificationService()
        result = service.classify_channel(channel)

        assert result is not None
        assert result.classification_method == "youtube_topics"
        assert result.is_auto_classified is True


def test_classify_channel_fallback_to_tfidf(app):
    """Test fallback to TF-IDF when no topics."""
    with app.app_context():
        # Create channel without topics but with descriptive text
        channel = Channel(
            yt_channel_id="tfidf-test",
            title="TechReviews - Technology and Programming",
            description="Tech tutorials, coding guides, software reviews, programming tips",
        )
        db.session.add(channel)
        db.session.commit()

        service = ClassificationService()
        result = service.classify_channel(channel)

        assert result is not None
        assert result.classification_method == "tfidf"


def test_batch_classification(app):
    """Test batch classification of multiple channels."""
    with app.app_context():
        channels = []
        for i in range(3):
            channel = Channel(
                yt_channel_id=f"batch-test-{i}",
                title=f"Channel {i}",
                description="Gaming and video games content",
                topic_ids=json.dumps(["/m/0bzvm2"]),
            )
            db.session.add(channel)
            channels.append(channel)
        db.session.commit()

        service = ClassificationService()
        results = service.classify_channels(channels)

        assert len(results) == 3


def test_skip_existing_classification(app):
    """Test that existing classifications are skipped."""
    with app.app_context():
        channel = Channel(
            yt_channel_id="existing-test",
            title="Test Channel",
            topic_ids=json.dumps(["/m/0bzvm2"]),
        )
        db.session.add(channel)
        db.session.commit()

        # First classification
        service = ClassificationService()
        result1 = service.classify_channel(channel)

        # Second classification should return existing
        result2 = service.classify_channel(channel)

        assert result1.id == result2.id


def test_manual_classification_override(app):
    """Test manual classification."""
    with app.app_context():
        channel = Channel(
            yt_channel_id="manual-test",
            title="Test Channel",
        )
        db.session.add(channel)
        db.session.commit()

        service = ClassificationService()
        result = service.manually_classify(channel, "Science")

        assert result is not None
        assert result.is_auto_classified is False
        assert result.classification_method == "manual"
        assert result.confidence_score == 1.0

        # Verify category
        category = Category.query.filter_by(id=result.category_id).first()
        assert category.name == "Science"


def test_manual_classification_not_overridden(app):
    """Test that manual classification is not overridden by auto."""
    with app.app_context():
        channel = Channel(
            yt_channel_id="no-override-test",
            title="Gaming Channel",
            topic_ids=json.dumps(["/m/0bzvm2"]),
        )
        db.session.add(channel)
        db.session.commit()

        service = ClassificationService()

        # Manually classify as Science
        service.manually_classify(channel, "Science")

        # Try to auto-classify
        result = service.classify_channel(channel)

        # Should still be Science (manual classification preserved)
        category = Category.query.filter_by(id=result.category_id).first()
        assert category.name == "Science"
        assert result.is_auto_classified is False


def test_reclassify_channel(app):
    """Test force reclassification."""
    with app.app_context():
        channel = Channel(
            yt_channel_id="reclassify-test",
            title="Gaming Channel",
            topic_ids=json.dumps(["/m/0bzvm2"]),
        )
        db.session.add(channel)
        db.session.commit()

        service = ClassificationService()

        # First classify
        result1 = service.classify_channel(channel)
        assert result1 is not None

        # Force reclassify
        result2 = service.reclassify_channel(channel)

        # Should have reclassified successfully
        assert result2 is not None
        # Verify the channel still has a valid category
        category = Category.query.filter_by(id=result2.category_id).first()
        assert category is not None
        assert category.name == "Gaming"


def test_get_channel_category(app):
    """Test getting channel category."""
    with app.app_context():
        channel = Channel(
            yt_channel_id="get-cat-test",
            title="Test Channel",
            topic_ids=json.dumps(["/m/0bzvm2"]),
        )
        db.session.add(channel)
        db.session.commit()

        service = ClassificationService()
        service.classify_channel(channel)

        result = service.get_channel_category(channel)
        assert result is not None


def test_get_classifier_status(app):
    """Test getting classifier status."""
    with app.app_context():
        service = ClassificationService()
        status = service.get_classifier_status()

        assert "youtube_topics" in status
        assert "tfidf" in status

        # Each should have 'available' key
        for name, info in status.items():
            assert "available" in info


def test_classify_insufficient_data(app):
    """Test classification with insufficient data."""
    with app.app_context():
        channel = Channel(
            yt_channel_id="no-data-test",
            title="X",
            description="",
        )
        db.session.add(channel)
        db.session.commit()

        service = ClassificationService()
        result = service.classify_channel(channel)

        assert result is None


def test_manual_classify_invalid_category(app):
    """Test manual classification with invalid category."""
    with app.app_context():
        channel = Channel(
            yt_channel_id="invalid-cat-test",
            title="Test Channel",
        )
        db.session.add(channel)
        db.session.commit()

        service = ClassificationService()
        result = service.manually_classify(channel, "InvalidCategory")

        assert result is None


def test_classify_channel_uses_recent_video_evidence(app):
    """Recent video metadata should help classify channels with weak channel text."""
    with app.app_context():
        channel = Channel(
            yt_channel_id="recent-video-evidence",
            title="Starter Story",
            description="Interviews and breakdowns",
        )
        db.session.add(channel)
        db.session.flush()

        db.session.add_all([
            Video(
                yt_video_id="recent-video-1",
                channel_id=channel.id,
                title="How a founder built a software startup",
                description="business software startup programming product walkthrough",
            ),
            Video(
                yt_video_id="recent-video-2",
                channel_id=channel.id,
                title="Developer tools and app growth",
                description="technology code developer app startup review",
            ),
        ])
        db.session.commit()

        service = ClassificationService()
        result = service.classify_channel(channel)

        assert result is not None
        category = Category.query.filter_by(id=result.category_id).first()
        assert category.name == "Technology"


def test_classify_channel_uses_dominant_video_category_heuristic(app):
    """Recent YT video categories should classify channels when text is weak."""
    with app.app_context():
        channel = Channel(
            yt_channel_id="video-category-heuristic",
            title="Arcade Club",
            description="Weekly uploads",
        )
        db.session.add(channel)
        db.session.flush()

        for idx in range(5):
            db.session.add(
                Video(
                    yt_video_id=f"gaming-evidence-{idx}",
                    channel_id=channel.id,
                    title=f"Episode {idx}",
                    description="Highlights and commentary",
                    video_category_id="20",
                )
            )
        db.session.commit()

        service = ClassificationService()
        result = service.classify_channel(channel)

        assert result is not None
        assert result.classification_method == "tfidf"
        category = Category.query.filter_by(id=result.category_id).first()
        assert category.name == "Gaming"


def test_classify_channel_uses_automotive_video_category(app):
    """Direct YouTube Autos & Vehicles evidence should classify as Automotive."""
    with app.app_context():
        channel = Channel(
            yt_channel_id="automotive-evidence",
            title="Garage Club",
            description="Weekly uploads",
        )
        db.session.add(channel)
        db.session.flush()

        for idx in range(5):
            db.session.add(
                Video(
                    yt_video_id=f"auto-evidence-{idx}",
                    channel_id=channel.id,
                    title=f"Track day {idx}",
                    description="Cars, tuning and road tests",
                    video_category_id="2",
                )
            )
        db.session.commit()

        service = ClassificationService()
        result = service.classify_channel(channel)

        assert result is not None
        category = Category.query.filter_by(id=result.category_id).first()
        assert category.name == "Automotive"


def test_classify_channel_uses_animals_video_category(app):
    """Direct YouTube Pets & Animals evidence should classify as Animals."""
    with app.app_context():
        channel = Channel(
            yt_channel_id="animals-evidence",
            title="Happy Paws",
            description="Weekly uploads",
        )
        db.session.add(channel)
        db.session.flush()

        for idx in range(5):
            db.session.add(
                Video(
                    yt_video_id=f"animals-evidence-{idx}",
                    channel_id=channel.id,
                    title=f"Animal story {idx}",
                    description="Rescue and pet care episodes",
                    video_category_id="15",
                )
            )
        db.session.commit()

        service = ClassificationService()
        result = service.classify_channel(channel)

        assert result is not None
        category = Category.query.filter_by(id=result.category_id).first()
        assert category.name == "Animals"
