"""Tests for YouTube Topics classifier."""

import json
import pytest

from app.services.classifiers import YouTubeTopicsClassifier


class MockChannel:
    """Mock channel object for testing."""

    def __init__(self, yt_channel_id, topic_ids=None, title=None, description=None):
        self.yt_channel_id = yt_channel_id
        self.topic_ids = json.dumps(topic_ids) if topic_ids else None
        self.title = title
        self.description = description
        self.keywords = None


def test_classify_gaming_channel():
    """Test classification of a gaming channel."""
    classifier = YouTubeTopicsClassifier()
    channel = MockChannel(
        yt_channel_id="gaming-test",
        topic_ids=["/m/0bzvm2", "/m/025zzc"],
    )

    result = classifier.classify(channel)

    assert result is not None
    category, confidence = result
    assert category == "Gaming"
    assert confidence >= 0.9


def test_classify_music_channel():
    """Test classification of a music channel."""
    classifier = YouTubeTopicsClassifier()
    channel = MockChannel(
        yt_channel_id="music-test",
        topic_ids=["/m/04rlf", "/m/064t9"],
    )

    result = classifier.classify(channel)

    assert result is not None
    category, confidence = result
    assert category == "Music"
    assert confidence >= 0.9


def test_classify_technology_channel():
    """Test classification of a technology channel."""
    classifier = YouTubeTopicsClassifier()
    channel = MockChannel(
        yt_channel_id="tech-test",
        topic_ids=["/m/07c1v"],
    )

    result = classifier.classify(channel)

    assert result is not None
    category, confidence = result
    assert category == "Technology"
    assert confidence == 0.95


def test_no_topics_returns_none():
    """Test that channel without topic IDs returns None."""
    classifier = YouTubeTopicsClassifier()
    channel = MockChannel(yt_channel_id="no-topics")

    result = classifier.classify(channel)

    assert result is None


def test_unknown_topics_returns_none():
    """Test that channel with unknown topic IDs returns None."""
    classifier = YouTubeTopicsClassifier()
    channel = MockChannel(
        yt_channel_id="unknown-topics",
        topic_ids=["/m/unknown1", "/m/unknown2"],
    )

    result = classifier.classify(channel)

    assert result is None


def test_can_classify_with_topics():
    """Test can_classify returns True when topics exist."""
    classifier = YouTubeTopicsClassifier()
    channel = MockChannel(
        yt_channel_id="has-topics",
        topic_ids=["/m/04rlf"],
    )

    assert classifier.can_classify(channel) is True


def test_can_classify_without_topics():
    """Test can_classify returns False when no topics."""
    classifier = YouTubeTopicsClassifier()
    channel = MockChannel(yt_channel_id="no-topics")

    assert classifier.can_classify(channel) is False


def test_method_name():
    """Test method_name property."""
    classifier = YouTubeTopicsClassifier()
    assert classifier.method_name == "youtube_topics"


def test_priority_when_multiple_categories():
    """Test that strong evidence beats ambiguous topic mappings."""
    classifier = YouTubeTopicsClassifier()
    channel = MockChannel(
        yt_channel_id="multi-topics",
        topic_ids=["/m/0bzvm2", "/m/02jjt"],  # Gaming plus ambiguous sports/entertainment
    )

    result = classifier.classify(channel)

    assert result is not None
    category, confidence = result
    assert category == "Gaming"
    assert confidence >= 0.8


def test_ambiguous_topics_abstain():
    """Ambiguous topics without a clear winner should abstain."""
    classifier = YouTubeTopicsClassifier()
    channel = MockChannel(
        yt_channel_id="ambiguous-only",
        topic_ids=["/m/019_rr"],  # Entertainment / Fitness / Vlogs
    )

    result = classifier.classify(channel)

    assert result is None


def test_topic_ids_as_list():
    """Test handling topic_ids when already a list (not JSON string)."""
    classifier = YouTubeTopicsClassifier()

    class ChannelWithList:
        yt_channel_id = "list-topics"
        topic_ids = ["/m/04rlf"]
        title = None
        description = None
        keywords = None

    channel = ChannelWithList()
    result = classifier.classify(channel)

    assert result is not None
    category, _ = result
    assert category == "Music"
