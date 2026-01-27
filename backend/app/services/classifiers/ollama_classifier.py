"""Ollama LLM classifier for channel categorization."""

import json
import os
from typing import Optional, Tuple

import requests

from app.logging.logger import get_logger

logger = get_logger(__name__)

# Valid category names
VALID_CATEGORIES = [
    "Gaming", "Technology", "Education", "Music", "Food",
    "Fitness", "Travel", "Fashion", "News", "Entertainment",
    "Vlogs", "Sports", "Art", "Science",
]

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2:1b"


class OllamaClassifier:
    """Classifier using Ollama LLM for intelligent categorization."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize the Ollama classifier.

        Args:
            api_url: Ollama API URL (default: http://localhost:11434)
            model: Ollama model name (default: llama3.2:1b)
        """
        self.api_url = api_url or os.getenv("OLLAMA_API_URL", DEFAULT_OLLAMA_URL)
        self.model = model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
        self.valid_categories = VALID_CATEGORIES
        self._available = None

    def classify(self, channel) -> Optional[Tuple[str, float]]:
        """
        Classify a channel using Ollama LLM.

        Args:
            channel: Channel object with title and description

        Returns:
            Tuple of (category_name, confidence_score) or None if not available
        """
        if not self.is_available:
            logger.debug("Ollama classifier not available")
            return None

        # Build prompt
        prompt = self._build_prompt(channel)
        if not prompt:
            return None

        try:
            response = requests.post(
                f"{self.api_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 50,
                    },
                },
                timeout=30,
            )
            response.raise_for_status()

            result = response.json()
            raw_response = result.get("response", "").strip()

            # Parse response to extract category
            category = self._parse_response(raw_response)

            if not category:
                logger.warning(
                    f"Ollama returned invalid category for {channel.yt_channel_id}: {raw_response}"
                )
                return None

            # LLM classification has high confidence
            confidence = 0.9

            logger.info(
                f"Classified channel {channel.yt_channel_id} as {category} "
                f"(confidence: {confidence}) using Ollama LLM"
            )
            return (category, confidence)

        except requests.Timeout:
            logger.warning(f"Ollama request timeout for {channel.yt_channel_id}")
            return None
        except requests.RequestException as e:
            logger.error(f"Ollama request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Ollama classification error: {e}")
            return None

    def _build_prompt(self, channel) -> Optional[str]:
        """Build classification prompt for Ollama."""
        title = channel.title or ""
        description = (channel.description or "")[:500]

        if not title and not description:
            return None

        categories_str = ", ".join(self.valid_categories)

        prompt = f"""Classify this YouTube channel into ONE of these categories: {categories_str}

Channel Title: {title}
Channel Description: {description}

Respond with ONLY the category name, nothing else.

Category:"""

        return prompt

    def _parse_response(self, response: str) -> Optional[str]:
        """Parse LLM response to extract category name."""
        response = response.strip()

        # Direct match
        for category in self.valid_categories:
            if response.lower() == category.lower():
                return category

        # Partial match (category name in response)
        for category in self.valid_categories:
            if category.lower() in response.lower():
                return category

        return None

    def can_classify(self, channel) -> bool:
        """Check if this classifier can handle the channel."""
        if not self.is_available:
            return False
        return bool(channel.title or channel.description)

    @property
    def is_available(self) -> bool:
        """Check if Ollama is available and responding."""
        if self._available is not None:
            return self._available

        try:
            response = requests.get(f"{self.api_url}/api/tags", timeout=5)
            if response.status_code == 200:
                # Check if model is available
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]

                # Check for exact match or partial match (with tags)
                model_available = any(
                    self.model in name or name.startswith(self.model.split(":")[0])
                    for name in model_names
                )

                if model_available:
                    self._available = True
                    logger.info(f"Ollama available with model {self.model}")
                else:
                    self._available = False
                    logger.warning(
                        f"Ollama running but model {self.model} not found. "
                        f"Available: {model_names}"
                    )
            else:
                self._available = False
        except requests.RequestException:
            self._available = False
            logger.debug("Ollama not available")

        return self._available

    @property
    def method_name(self) -> str:
        """Return the classification method name."""
        return "ollama"
