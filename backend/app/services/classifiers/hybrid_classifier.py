"""Hybrid semantic classifier using sentence transformers."""

from typing import Optional, Tuple

from app.logging.logger import get_logger

logger = get_logger(__name__)

# Category descriptions for semantic matching
CATEGORY_DESCRIPTIONS = {
    "Gaming": "Video games, gaming content, esports, game reviews, gameplay walkthroughs, streamers, lets plays",
    "Technology": "Technology, programming, software development, coding tutorials, tech reviews, gadgets, computers",
    "Education": "Educational content, tutorials, courses, learning, teaching, how-to guides, academic",
    "Music": "Music, songs, musicians, bands, covers, concerts, music production, singers",
    "Food": "Cooking, recipes, food reviews, restaurants, cuisine, chefs, baking",
    "Fitness": "Fitness, workout routines, exercise, gym, health, bodybuilding, yoga, training",
    "Travel": "Travel vlogs, destinations, tourism, adventure, exploring, trips, vacation",
    "Fashion": "Fashion, style, clothing, makeup, beauty tutorials, outfit ideas, trends",
    "News": "News, current events, politics, journalism, breaking news, analysis",
    "Entertainment": "Entertainment, comedy, movies, TV shows, celebrities, humor, sketches",
    "Vlogs": "Daily vlogs, lifestyle content, day in the life, personal content, routines",
    "Sports": "Sports, football, basketball, soccer, athletes, matches, championships",
    "Art": "Art, drawing, painting, digital art, illustration, creative content, design",
    "Science": "Science, research, experiments, physics, chemistry, biology, space, astronomy",
}


class HybridClassifier:
    """Classifier using semantic embeddings with sentence transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the classifier.

        Args:
            model_name: Name of the sentence-transformers model to use
        """
        self.model_name = model_name
        self.category_descriptions = CATEGORY_DESCRIPTIONS
        self._model = None
        self._category_embeddings = None
        self._categories = None
        self._initialized = False
        self._available = False

    def _initialize(self):
        """Lazy initialization of sentence transformer model."""
        if self._initialized:
            return

        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np

            self._np = np

            # Load model
            logger.info(f"Loading sentence-transformers model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)

            # Pre-compute category embeddings
            self._categories = list(self.category_descriptions.keys())
            descriptions = list(self.category_descriptions.values())
            self._category_embeddings = self._model.encode(
                descriptions, convert_to_numpy=True
            )

            self._available = True
            self._initialized = True
            logger.info("Hybrid classifier initialized successfully")

        except ImportError:
            self._available = False
            self._initialized = True
            logger.warning(
                "sentence-transformers not available, Hybrid classifier disabled"
            )
        except Exception as e:
            self._available = False
            self._initialized = True
            logger.error(f"Failed to initialize Hybrid classifier: {e}")

    def classify(self, channel) -> Optional[Tuple[str, float]]:
        """
        Classify a channel using semantic similarity.

        Args:
            channel: Channel object with title and description

        Returns:
            Tuple of (category_name, confidence_score) or None if not available
        """
        self._initialize()

        if not self._available:
            logger.debug("Hybrid classifier not available")
            return None

        # Build text from channel data
        text = self._build_channel_text(channel)
        if not text or len(text.strip()) < 10:
            logger.debug(f"Channel {channel.yt_channel_id} has insufficient text")
            return None

        try:
            # Encode channel text
            channel_embedding = self._model.encode([text], convert_to_numpy=True)[0]

            # Calculate cosine similarity with each category
            similarities = self._cosine_similarity(
                channel_embedding, self._category_embeddings
            )

            # Get best match
            best_idx = self._np.argmax(similarities)
            best_score = similarities[best_idx]

            # Minimum threshold
            if best_score < 0.3:
                logger.debug(
                    f"Channel {channel.yt_channel_id} semantic score too low: {best_score}"
                )
                return None

            category = self._categories[best_idx]
            confidence = float(best_score)

            logger.info(
                f"Classified channel {channel.yt_channel_id} as {category} "
                f"(confidence: {confidence:.2f}) using Hybrid semantic"
            )
            return (category, confidence)

        except Exception as e:
            logger.error(f"Hybrid classification error: {e}")
            return None

    def _cosine_similarity(self, vec1, vec2_matrix):
        """Calculate cosine similarity between a vector and a matrix of vectors."""
        # Normalize vectors
        vec1_norm = vec1 / self._np.linalg.norm(vec1)
        vec2_norms = vec2_matrix / self._np.linalg.norm(
            vec2_matrix, axis=1, keepdims=True
        )
        # Dot product
        return self._np.dot(vec2_norms, vec1_norm)

    def _build_channel_text(self, channel) -> str:
        """Build text representation from channel data."""
        parts = []

        if channel.title:
            parts.append(channel.title)

        if channel.description:
            # Use first 500 chars for efficiency
            parts.append(channel.description[:500])

        if channel.keywords:
            parts.append(channel.keywords)

        return " ".join(parts)

    def can_classify(self, channel) -> bool:
        """Check if this classifier can handle the channel."""
        self._initialize()
        if not self._available:
            return False
        text = self._build_channel_text(channel)
        return len(text.strip()) >= 10

    @property
    def method_name(self) -> str:
        """Return the classification method name."""
        return "hybrid"

    @property
    def is_available(self) -> bool:
        """Check if the classifier is available."""
        self._initialize()
        return self._available
