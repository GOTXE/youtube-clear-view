"""TF-IDF classifier using keyword-based analysis."""

from typing import Optional, Tuple

from app.logging.logger import get_logger

logger = get_logger(__name__)

# Category keywords for TF-IDF matching
CATEGORY_KEYWORDS = {
    "Gaming": [
        "game", "gaming", "gameplay", "gamer", "minecraft", "fortnite",
        "streamer", "playthrough", "walkthrough", "let's play", "ps5",
        "xbox", "nintendo", "steam", "esports", "twitch", "speedrun",
        "videogame", "juego", "juegos", "gaming", "partida"
    ],
    "Technology": [
        "tech", "technology", "programming", "code", "software", "hardware",
        "developer", "coding", "python", "javascript", "ai", "artificial",
        "intelligence", "computer", "tutorial", "review", "gadget",
        "smartphone", "app", "tecnologia", "programacion", "informatica"
    ],
    "Education": [
        "learn", "learning", "tutorial", "course", "education", "lesson",
        "teaching", "teacher", "how to", "guide", "explained", "for beginners",
        "study", "academic", "university", "school", "educacion", "aprender",
        "curso", "tutorial", "clase"
    ],
    "Music": [
        "music", "song", "singer", "band", "album", "concert", "musician",
        "cover", "lyrics", "hip hop", "rap", "rock", "pop", "electronic",
        "dj", "producer", "musica", "cancion", "cantante", "banda"
    ],
    "Food": [
        "food", "cooking", "recipe", "kitchen", "chef", "baking", "cuisine",
        "restaurant", "cook", "meal", "delicious", "tasty", "eat",
        "comida", "cocina", "receta", "cocinero", "gastronomia"
    ],
    "Fitness": [
        "fitness", "workout", "exercise", "gym", "health", "training",
        "muscle", "weight", "cardio", "yoga", "pilates", "bodybuilding",
        "fit", "healthy", "ejercicio", "entrenamiento", "gimnasio", "salud"
    ],
    "Travel": [
        "travel", "trip", "vacation", "tour", "explore", "adventure",
        "destination", "tourist", "backpacking", "hotel", "flight",
        "viaje", "turismo", "aventura", "destino", "viajar"
    ],
    "Fashion": [
        "fashion", "style", "clothing", "outfit", "makeup", "beauty",
        "model", "designer", "trend", "wardrobe", "haul", "lookbook",
        "moda", "estilo", "ropa", "maquillaje", "belleza"
    ],
    "News": [
        "news", "breaking", "politics", "economy", "world", "report",
        "journalist", "media", "update", "current events", "analysis",
        "noticias", "politica", "economia", "actualidad", "informacion"
    ],
    "Entertainment": [
        "entertainment", "comedy", "funny", "humor", "movie", "film",
        "celebrity", "show", "series", "tv", "television", "sketch",
        "entretenimiento", "comedia", "humor", "pelicula", "serie"
    ],
    "Vlogs": [
        "vlog", "daily", "life", "day in the life", "routine", "lifestyle",
        "personal", "diary", "my day", "follow me", "day with me",
        "vlog", "diario", "vida", "rutina", "dia a dia"
    ],
    "Sports": [
        "sports", "football", "soccer", "basketball", "tennis", "golf",
        "baseball", "nfl", "nba", "fifa", "athlete", "championship",
        "match", "deportes", "futbol", "baloncesto", "partido"
    ],
    "Art": [
        "art", "artist", "drawing", "painting", "illustration", "creative",
        "design", "graphic", "digital art", "sketch", "artwork",
        "arte", "artista", "dibujo", "pintura", "diseno"
    ],
    "Science": [
        "science", "scientific", "research", "experiment", "physics",
        "chemistry", "biology", "space", "nasa", "astronomy", "discovery",
        "ciencia", "investigacion", "experimento", "fisica", "quimica"
    ],
}


class TFIDFClassifier:
    """Classifier using TF-IDF keyword-based analysis."""

    def __init__(self):
        """Initialize the classifier with keyword corpus."""
        self.category_keywords = CATEGORY_KEYWORDS
        self._vectorizer = None
        self._category_vectors = None
        self._initialized = False

    def _initialize(self):
        """Lazy initialization of TF-IDF vectorizer."""
        if self._initialized:
            return

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            self._sklearn_available = True
            self._cosine_similarity = cosine_similarity
            self._np = np

            # Create corpus for each category
            category_texts = []
            self._categories = []
            for category, keywords in self.category_keywords.items():
                category_texts.append(" ".join(keywords))
                self._categories.append(category)

            # Fit vectorizer on category keywords
            self._vectorizer = TfidfVectorizer(
                lowercase=True,
                stop_words="english",
                ngram_range=(1, 2),
            )
            self._category_vectors = self._vectorizer.fit_transform(category_texts)
            self._initialized = True
            logger.info("TF-IDF classifier initialized with sklearn")

        except ImportError:
            self._sklearn_available = False
            self._initialized = True
            logger.warning("sklearn not available, TF-IDF classifier will use fallback")

    def classify(self, channel) -> Optional[Tuple[str, float]]:
        """
        Classify a channel based on TF-IDF analysis of its text content.

        Args:
            channel: Channel object with title, description, and keywords

        Returns:
            Tuple of (category_name, confidence_score) or None if no match
        """
        self._initialize()

        if not self._sklearn_available:
            return self._fallback_classify(channel)

        # Build text from channel data
        text = self._build_channel_text(channel)
        if not text or len(text.strip()) < 10:
            logger.debug(f"Channel {channel.yt_channel_id} has insufficient text")
            return None

        try:
            # Transform channel text
            channel_vector = self._vectorizer.transform([text])

            # Calculate similarity with each category
            similarities = self._cosine_similarity(
                channel_vector, self._category_vectors
            ).flatten()

            # Get best match
            best_idx = self._np.argmax(similarities)
            best_score = similarities[best_idx]

            # Minimum threshold for confidence
            if best_score < 0.1:
                logger.debug(
                    f"Channel {channel.yt_channel_id} TF-IDF score too low: {best_score}"
                )
                return None

            category = self._categories[best_idx]
            confidence = min(best_score, 1.0)

            logger.info(
                f"Classified channel {channel.yt_channel_id} as {category} "
                f"(confidence: {confidence:.2f}) using TF-IDF"
            )
            return (category, confidence)

        except Exception as e:
            logger.error(f"TF-IDF classification error: {e}")
            return None

    def _fallback_classify(self, channel) -> Optional[Tuple[str, float]]:
        """Simple keyword matching fallback when sklearn is not available."""
        text = self._build_channel_text(channel).lower()

        if not text:
            return None

        best_category = None
        best_score = 0

        for category, keywords in self.category_keywords.items():
            score = sum(1 for kw in keywords if kw.lower() in text)
            if score > best_score:
                best_score = score
                best_category = category

        if best_category and best_score >= 2:
            confidence = min(best_score / 10, 0.8)
            return (best_category, confidence)

        return None

    def _build_channel_text(self, channel) -> str:
        """Build text representation from channel data."""
        parts = []

        if channel.title:
            parts.append(channel.title)
            parts.append(channel.title)  # Weight title double

        if channel.description:
            parts.append(channel.description[:500])  # Limit description length

        if channel.keywords:
            parts.append(channel.keywords)

        return " ".join(parts)

    def can_classify(self, channel) -> bool:
        """Check if this classifier can handle the channel."""
        text = self._build_channel_text(channel)
        return len(text.strip()) >= 10

    @property
    def method_name(self) -> str:
        """Return the classification method name."""
        return "tfidf"
