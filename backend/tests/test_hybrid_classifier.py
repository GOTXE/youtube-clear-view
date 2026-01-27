"""Tests for Hybrid semantic classifier."""

import pytest


class MockChannel:
    """Mock channel object for testing."""

    def __init__(self, yt_channel_id, title=None, description=None, keywords=None):
        self.yt_channel_id = yt_channel_id
        self.title = title
        self.description = description
        self.keywords = keywords
        self.topic_ids = None


def test_classifier_initialization():
    """Test that classifier initializes correctly."""
    from app.services.classifiers import HybridClassifier

    classifier = HybridClassifier()
    assert classifier.method_name == "hybrid"


def test_is_available_property():
    """Test that is_available property works."""
    from app.services.classifiers import HybridClassifier

    classifier = HybridClassifier()
    # Will be True or False depending on sentence-transformers installation
    available = classifier.is_available
    assert isinstance(available, bool)


def test_can_classify_checks_availability():
    """Test can_classify respects availability."""
    from app.services.classifiers import HybridClassifier

    classifier = HybridClassifier()
    channel = MockChannel(
        yt_channel_id="test-channel",
        title="Test Title",
        description="Test description for classification",
    )

    can = classifier.can_classify(channel)

    # If available, should be able to classify
    # If not available, should return False
    if classifier.is_available:
        assert can is True
    else:
        assert can is False


def test_classify_returns_none_when_unavailable():
    """Test that classify returns None when sentence-transformers not available."""
    from app.services.classifiers import HybridClassifier

    classifier = HybridClassifier()
    channel = MockChannel(
        yt_channel_id="test-channel",
        title="Gaming Videos",
        description="We play video games and do game reviews",
    )

    result = classifier.classify(channel)

    # Result depends on whether sentence-transformers is available
    if classifier.is_available:
        assert result is not None
    else:
        assert result is None


@pytest.mark.skipif(
    True,  # Skip by default since sentence-transformers may not be installed
    reason="Requires sentence-transformers to be installed"
)
def test_semantic_classification():
    """Test semantic classification with real model."""
    from app.services.classifiers import HybridClassifier

    classifier = HybridClassifier()
    if not classifier.is_available:
        pytest.skip("sentence-transformers not available")

    channel = MockChannel(
        yt_channel_id="science-channel",
        title="Physics Explained",
        description="Quantum mechanics, astronomy, scientific research and experiments",
    )

    result = classifier.classify(channel)

    assert result is not None
    category, confidence = result
    assert category == "Science"
    assert confidence > 0.3


def test_insufficient_text():
    """Test handling of insufficient text."""
    from app.services.classifiers import HybridClassifier

    classifier = HybridClassifier()
    channel = MockChannel(
        yt_channel_id="no-text",
        title="X",
        description="",
    )

    result = classifier.classify(channel)

    # Should return None due to insufficient text
    assert result is None


def test_method_name():
    """Test method_name property."""
    from app.services.classifiers import HybridClassifier

    classifier = HybridClassifier()
    assert classifier.method_name == "hybrid"
