"""TF-IDF classifier using precision-first text and video evidence."""

from collections import Counter
from typing import Optional, Tuple

from app.logging.logger import get_logger
from app.models import Video

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
    "Automotive": [
        "car", "cars", "auto", "automotive", "vehicle", "vehicles", "driving",
        "driver", "road", "track", "motor", "engine", "garage", "racing",
        "tesla", "bmw", "audi", "porsche", "4x4", "offroad", "off-road",
        "coche", "coches", "motor", "motores", "conduccion", "vehiculo",
        "vehiculos", "camion", "moto", "motos"
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
    "Animals": [
        "animal", "animals", "pet", "pets", "dog", "dogs", "cat", "cats",
        "puppy", "kitten", "veterinary", "vet", "wildlife", "bird", "birds",
        "horse", "horses", "rescue", "farm animal", "mascota", "mascotas",
        "perro", "perros", "gato", "gatos", "veterinario", "animales"
    ],
    "Science": [
        "science", "scientific", "research", "experiment", "physics",
        "chemistry", "biology", "space", "nasa", "astronomy", "discovery",
        "ciencia", "investigacion", "experimento", "fisica", "quimica"
    ],
}

VIDEO_CATEGORY_TO_CANDIDATES = {
    "1": ["Entertainment"],
    "2": ["Automotive"],
    "10": ["Music"],
    "15": ["Animals"],
    "17": ["Sports"],
    "19": ["Travel"],
    "20": ["Gaming"],
    "22": ["Vlogs"],
    "23": ["Entertainment"],
    "24": ["Entertainment"],
    "25": ["News"],
    "27": ["Education"],
    "28": ["Technology", "Science"],
}


class TFIDFClassifier:
    """Classifier using TF-IDF keyword-based analysis."""

    MIN_CONFIDENCE = 0.18
    MIN_MARGIN = 0.03
    MIN_FALLBACK_SCORE = 3
    MIN_FALLBACK_MARGIN = 1
    MIN_VIDEO_EVIDENCE = 4
    MIN_VIDEO_SHARE = 0.6
    MIN_VIDEO_MARGIN = 2

    # Relaxed thresholds for channels with sparse data
    MIN_CONFIDENCE_SPARSE = 0.12
    MIN_MARGIN_SPARSE = 0.02
    MIN_FALLBACK_SCORE_SPARSE = 2
    MIN_FALLBACK_MARGIN_SPARSE = 1
    MIN_VIDEO_EVIDENCE_SPARSE = 2
    MIN_VIDEO_SHARE_SPARSE = 0.50

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
        video_category_match = self._classify_from_video_categories(channel)
        if video_category_match:
            return video_category_match

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
            ranked = sorted(
                enumerate(similarities),
                key=lambda item: item[1],
                reverse=True,
            )
            best_idx, best_score = ranked[0]
            second_score = ranked[1][1] if len(ranked) > 1 else 0.0

            sparse = self._is_sparse(channel)
            min_conf = self.MIN_CONFIDENCE_SPARSE if sparse else self.MIN_CONFIDENCE
            min_marg = self.MIN_MARGIN_SPARSE if sparse else self.MIN_MARGIN
            if best_score < min_conf or (best_score - second_score) < min_marg:
                logger.debug(
                    "Channel %s TF-IDF signal too weak (best=%s, second=%s)",
                    channel.yt_channel_id,
                    best_score,
                    second_score,
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

        scores = {}

        for category, keywords in self.category_keywords.items():
            scores[category] = sum(1 for kw in keywords if kw.lower() in text)

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_category, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0

        sparse = self._is_sparse(channel)
        min_fb_score = self.MIN_FALLBACK_SCORE_SPARSE if sparse else self.MIN_FALLBACK_SCORE
        min_fb_margin = self.MIN_FALLBACK_MARGIN_SPARSE if sparse else self.MIN_FALLBACK_MARGIN
        if (
            best_category
            and best_score >= min_fb_score
            and (best_score - second_score) >= min_fb_margin
        ):
            confidence = min(best_score / 10, 0.8)
            return (best_category, confidence)

        return None

    def _classify_from_video_categories(self, channel) -> Optional[Tuple[str, float]]:
        """Use dominant recent YouTube video categories when the signal is clear."""
        if not getattr(channel, "id", None):
            return None

        recent_videos = (
            Video.query.filter_by(channel_id=channel.id)
            .filter(Video.video_category_id.isnot(None))
            .order_by(Video.published_at.desc())
            .limit(12)
            .all()
        )
        if not recent_videos:
            return None

        counts = Counter()
        mapped_total = 0

        for video in recent_videos:
            candidates = VIDEO_CATEGORY_TO_CANDIDATES.get(str(video.video_category_id))
            if not candidates:
                continue
            if len(candidates) != 1:
                continue
            counts[candidates[0]] += 1
            mapped_total += 1

        sparse = self._is_sparse(channel)
        min_vid_ev = self.MIN_VIDEO_EVIDENCE_SPARSE if sparse else self.MIN_VIDEO_EVIDENCE
        if mapped_total < min_vid_ev or not counts:
            return None

        ranked = counts.most_common()
        best_category, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0
        share = best_score / mapped_total if mapped_total else 0.0

        min_vid_share = self.MIN_VIDEO_SHARE_SPARSE if sparse else self.MIN_VIDEO_SHARE
        if share < min_vid_share or (best_score - second_score) < self.MIN_VIDEO_MARGIN:
            return None

        confidence = min(0.9, 0.7 + (share * 0.2))
        logger.info(
            "Classified channel %s as %s using recent video categories (share=%.2f, votes=%s/%s)",
            channel.yt_channel_id,
            best_category,
            share,
            best_score,
            mapped_total,
        )
        return best_category, confidence

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
            parts.append(channel.keywords)

        if getattr(channel, "id", None):
            recent_videos = (
                Video.query.filter_by(channel_id=channel.id)
                .order_by(Video.published_at.desc())
                .limit(12)
                .all()
            )
            for video in recent_videos:
                if video.title:
                    parts.append(video.title)
                    parts.append(video.title)
                if video.description:
                    parts.append(video.description[:180])
                if video.tags:
                    parts.append(video.tags)
                    parts.append(video.tags)

        return " ".join(parts)

    def _is_sparse(self, channel) -> bool:
        """Return True when a channel has limited metadata for classification."""
        desc_len = len(channel.description or "") if channel.description else 0
        video_count = 0
        if getattr(channel, "id", None):
            video_count = Video.query.filter_by(channel_id=channel.id).count()
        return desc_len < 100 and video_count < 4

    def can_classify(self, channel) -> bool:
        """Check if this classifier can handle the channel."""
        text = self._build_channel_text(channel)
        if len(text.strip()) >= 10:
            return True
        return self._classify_from_video_categories(channel) is not None

    @property
    def method_name(self) -> str:
        return "tfidf"

    @property
    def method_name(self) -> str:
        """Return the classification method name."""
        return "tfidf"
