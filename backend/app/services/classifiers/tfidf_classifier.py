"""TF-IDF classifier using precision-first text and video evidence.

Pure Python implementation — no external dependencies.
Equivalent to sklearn's TfidfVectorizer(lowercase=True, stop_words="english")
+ cosine_similarity, but using only stdlib (math, collections).
"""

import math
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

# Common English stop words to ignore during tokenization
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "its", "be", "was", "are",
    "were", "been", "have", "has", "had", "do", "does", "did", "not",
    "this", "that", "these", "those", "as", "if", "so", "up", "out",
    "my", "your", "his", "her", "our", "their", "we", "you", "he", "she",
    "they", "i", "me", "him", "us", "them",
})


def _tokenize(text: str) -> list:
    """Lowercase, split on whitespace, remove stop words."""
    return [t for t in text.lower().split() if t not in _STOP_WORDS]


def _cosine_similarity(vec_a: dict, vec_b: dict) -> float:
    """Cosine similarity between two sparse TF-IDF vectors (dicts)."""
    dot = sum(vec_a.get(k, 0.0) * v for k, v in vec_b.items())
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


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
        self._categories: list = []
        self._category_vectors: list = []
        self._idf: dict = {}
        self._n_docs: int = 0
        self._initialized = False

    def _initialize(self):
        """Lazy initialization: build TF-IDF vectors from category keyword corpus."""
        if self._initialized:
            return

        category_texts = []
        for category, keywords in self.category_keywords.items():
            category_texts.append(" ".join(keywords))
            self._categories.append(category)

        n = len(category_texts)
        tokenized = [_tokenize(doc) for doc in category_texts]

        # Document frequency: how many category docs contain each term
        df: Counter = Counter()
        for tokens in tokenized:
            for term in set(tokens):
                df[term] += 1

        # Smooth IDF — same formula as sklearn's TfidfVectorizer(smooth_idf=True)
        self._idf = {
            term: math.log((n + 1) / (count + 1)) + 1
            for term, count in df.items()
        }
        self._n_docs = n

        # Build category vectors using this IDF
        for tokens in tokenized:
            tf = Counter(tokens)
            total = len(tokens) or 1
            vec = {
                term: (count / total) * self._idf[term]
                for term, count in tf.items()
            }
            self._category_vectors.append(vec)

        self._initialized = True
        logger.info("TF-IDF classifier initialized (pure Python, no external deps)")

    def _vectorize(self, text: str) -> dict:
        """Transform text into a TF-IDF vector using the corpus IDF.

        Terms not seen in the category corpus get a high IDF (rare = informative),
        matching sklearn's behavior for out-of-vocabulary terms.
        """
        tokens = _tokenize(text)
        if not tokens:
            return {}
        tf = Counter(tokens)
        total = len(tokens)
        # Unknown terms: treated as appearing in 0 category docs → max IDF
        default_idf = math.log((self._n_docs + 1) / 1) + 1
        return {
            term: (count / total) * self._idf.get(term, default_idf)
            for term, count in tf.items()
        }

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

        text = self._build_channel_text(channel)
        if not text or len(text.strip()) < 10:
            logger.debug(f"Channel {channel.yt_channel_id} has insufficient text")
            return None

        try:
            channel_vec = self._vectorize(text)
            if not channel_vec:
                return None

            similarities = [
                _cosine_similarity(channel_vec, cat_vec)
                for cat_vec in self._category_vectors
            ]

            ranked = sorted(enumerate(similarities), key=lambda x: x[1], reverse=True)
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
        """Return the classification method name."""
        return "tfidf"
