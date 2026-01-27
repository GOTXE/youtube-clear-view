"""Tests for Ollama LLM classifier."""

import pytest
from unittest.mock import patch, MagicMock


class MockChannel:
    """Mock channel object for testing."""

    def __init__(self, yt_channel_id, title=None, description=None):
        self.yt_channel_id = yt_channel_id
        self.title = title
        self.description = description
        self.keywords = None
        self.topic_ids = None


def test_classifier_initialization():
    """Test that classifier initializes with defaults."""
    from app.services.classifiers import OllamaClassifier

    classifier = OllamaClassifier()
    assert classifier.api_url == "http://localhost:11434"
    assert classifier.model == "llama3.2:1b"
    assert classifier.method_name == "ollama"


def test_classifier_custom_config():
    """Test that classifier accepts custom configuration."""
    from app.services.classifiers import OllamaClassifier

    classifier = OllamaClassifier(
        api_url="http://custom:11434",
        model="custom-model",
    )
    assert classifier.api_url == "http://custom:11434"
    assert classifier.model == "custom-model"


def test_fallback_when_unavailable():
    """Test that classifier returns None when Ollama is unavailable."""
    from app.services.classifiers import OllamaClassifier
    import requests

    with patch("app.services.classifiers.ollama_classifier.requests.get") as mock_get:
        mock_get.side_effect = requests.RequestException("Connection refused")

        classifier = OllamaClassifier()
        # Reset cached availability
        classifier._available = None

        channel = MockChannel(
            yt_channel_id="test-channel",
            title="Gaming Channel",
            description="We play games",
        )

        # is_available should return False
        assert classifier.is_available is False
        # classify should return None
        result = classifier.classify(channel)
        assert result is None


def test_is_available_when_running():
    """Test is_available returns True when Ollama responds."""
    from app.services.classifiers import OllamaClassifier

    with patch("app.services.classifiers.ollama_classifier.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3.2:1b"}]
        }
        mock_get.return_value = mock_response

        classifier = OllamaClassifier()
        assert classifier.is_available is True


def test_is_available_model_not_found():
    """Test is_available returns False when model not available."""
    from app.services.classifiers import OllamaClassifier

    with patch("app.services.classifiers.ollama_classifier.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "other-model"}]
        }
        mock_get.return_value = mock_response

        classifier = OllamaClassifier()
        assert classifier.is_available is False


def test_classification_with_mock():
    """Test classification with mocked Ollama response."""
    from app.services.classifiers import OllamaClassifier

    with patch("app.services.classifiers.ollama_classifier.requests.get") as mock_get, patch("app.services.classifiers.ollama_classifier.requests.post") as mock_post:
        # Mock availability check
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "models": [{"name": "llama3.2:1b"}]
        }
        mock_get.return_value = mock_get_response

        # Mock classification response
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {
            "response": "Gaming"
        }
        mock_post_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_post_response

        classifier = OllamaClassifier()
        channel = MockChannel(
            yt_channel_id="gaming-channel",
            title="Gamer Pro",
            description="We play video games every day",
        )

        result = classifier.classify(channel)

        assert result is not None
        category, confidence = result
        assert category == "Gaming"
        assert confidence == 0.9


def test_parse_response_direct_match():
    """Test parsing response with direct category match."""
    from app.services.classifiers import OllamaClassifier

    classifier = OllamaClassifier()

    assert classifier._parse_response("Gaming") == "Gaming"
    assert classifier._parse_response("Technology") == "Technology"
    assert classifier._parse_response("gaming") == "Gaming"  # case insensitive


def test_parse_response_partial_match():
    """Test parsing response with partial category match."""
    from app.services.classifiers import OllamaClassifier

    classifier = OllamaClassifier()

    assert classifier._parse_response("The category is Gaming.") == "Gaming"
    assert classifier._parse_response("I think this is Technology related") == "Technology"


def test_parse_response_invalid():
    """Test parsing invalid response."""
    from app.services.classifiers import OllamaClassifier

    classifier = OllamaClassifier()

    assert classifier._parse_response("Invalid category") is None
    assert classifier._parse_response("") is None


def test_can_classify():
    """Test can_classify method."""
    from app.services.classifiers import OllamaClassifier

    with patch("app.services.classifiers.ollama_classifier.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3.2:1b"}]
        }
        mock_get.return_value = mock_response

        classifier = OllamaClassifier()

        channel_with_text = MockChannel(
            yt_channel_id="with-text",
            title="Test Channel",
        )
        assert classifier.can_classify(channel_with_text) is True

        channel_no_text = MockChannel(yt_channel_id="no-text")
        assert classifier.can_classify(channel_no_text) is False


def test_timeout_handling():
    """Test handling of request timeout."""
    from app.services.classifiers import OllamaClassifier
    import requests

    with patch("app.services.classifiers.ollama_classifier.requests.get") as mock_get, patch("app.services.classifiers.ollama_classifier.requests.post") as mock_post:
        # Mock availability check
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "models": [{"name": "llama3.2:1b"}]
        }
        mock_get.return_value = mock_get_response

        # Mock timeout
        mock_post.side_effect = requests.Timeout()

        classifier = OllamaClassifier()
        channel = MockChannel(
            yt_channel_id="timeout-test",
            title="Test Channel",
        )

        result = classifier.classify(channel)
        assert result is None
