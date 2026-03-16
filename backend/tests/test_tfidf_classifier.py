"""Tests for TF-IDF classifier."""

import pytest


class MockChannel:
    """Mock channel object for testing."""

    def __init__(self, yt_channel_id, title=None, description=None, keywords=None):
        self.yt_channel_id = yt_channel_id
        self.title = title
        self.description = description
        self.keywords = keywords
        self.topic_ids = None


def test_classify_by_title():
    """Test classification by channel title."""
    from app.services.classifiers import TFIDFClassifier

    classifier = TFIDFClassifier()
    channel = MockChannel(
        yt_channel_id="tech-title",
        title="TechWithTim - Python Programming Tutorials",
        description="Learn coding",
    )

    result = classifier.classify(channel)

    assert result is not None
    category, confidence = result
    assert category in ["Technology", "Education"]
    assert confidence > 0


def test_classify_by_description():
    """Test classification by channel description."""
    from app.services.classifiers import TFIDFClassifier

    classifier = TFIDFClassifier()
    channel = MockChannel(
        yt_channel_id="gaming-desc",
        title="Gaming Channel",
        description="We play video games, review new releases, stream Minecraft and Fortnite gameplay walkthroughs",
    )

    result = classifier.classify(channel)

    assert result is not None
    category, confidence = result
    assert category == "Gaming"
    assert confidence > 0


def test_classify_by_keywords():
    """Test classification using channel keywords."""
    from app.services.classifiers import TFIDFClassifier

    classifier = TFIDFClassifier()
    channel = MockChannel(
        yt_channel_id="music-keywords",
        title="My Channel",
        description="Welcome to my channel",
        keywords="music songs cover band singer concert guitar",
    )

    result = classifier.classify(channel)

    assert result is not None
    category, confidence = result
    assert category == "Music"


def test_confidence_scores():
    """Test that confidence scores are reasonable."""
    from app.services.classifiers import TFIDFClassifier

    classifier = TFIDFClassifier()
    channel = MockChannel(
        yt_channel_id="fitness-channel",
        title="Fitness Workout Channel",
        description="Daily workout routines, gym exercises, fitness training, health tips",
    )

    result = classifier.classify(channel)

    assert result is not None
    category, confidence = result
    assert 0 < confidence <= 1.0


def test_insufficient_text_returns_none():
    """Test that insufficient text returns None."""
    from app.services.classifiers import TFIDFClassifier

    classifier = TFIDFClassifier()
    channel = MockChannel(
        yt_channel_id="short-text",
        title="Hi",
        description="",
    )

    result = classifier.classify(channel)

    assert result is None


def test_can_classify_with_text():
    """Test can_classify returns True when sufficient text."""
    from app.services.classifiers import TFIDFClassifier

    classifier = TFIDFClassifier()
    channel = MockChannel(
        yt_channel_id="has-text",
        title="My Technology Channel",
        description="Tech reviews and tutorials",
    )

    assert classifier.can_classify(channel) is True


def test_can_classify_without_text():
    """Test can_classify returns False when no text."""
    from app.services.classifiers import TFIDFClassifier

    classifier = TFIDFClassifier()
    channel = MockChannel(
        yt_channel_id="no-text",
        title="",
        description="",
    )

    assert classifier.can_classify(channel) is False


def test_method_name():
    """Test method_name property."""
    from app.services.classifiers import TFIDFClassifier

    classifier = TFIDFClassifier()
    assert classifier.method_name == "tfidf"


def test_spanish_keywords():
    """Test classification with Spanish keywords."""
    from app.services.classifiers import TFIDFClassifier

    classifier = TFIDFClassifier()
    channel = MockChannel(
        yt_channel_id="spanish-channel",
        title="Cocina con Maria",
        description="Recetas de cocina, comida casera, gastronomia mexicana",
    )

    result = classifier.classify(channel)

    assert result is not None
    category, confidence = result
    assert category == "Food"
