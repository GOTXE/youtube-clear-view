"""YouTube Topics classifier using ambiguity-aware topic resolution."""

import json
from collections import Counter
from typing import Optional, Tuple

from app.logging.logger import get_logger

logger = get_logger(__name__)

# A single YouTube topic id can legitimately point at multiple app categories.
# We keep the ambiguity explicit instead of relying on duplicate dict keys.
TOPIC_ID_TO_CATEGORIES = {
    "/m/04rlf": ["Music"],
    "/m/064t9": ["Music"],
    "/m/02lkt": ["Music"],
    "/m/0glt670": ["Music"],
    "/m/05rwpb": ["Music"],
    "/m/03_d0": ["Music"],
    "/m/028sqc": ["Music"],
    "/m/0dq0md": ["Music"],
    "/m/0bzvm2": ["Gaming"],
    "/m/025zzc": ["Gaming"],
    "/m/02ntfj": ["Gaming"],
    "/m/01sjng": ["Gaming"],
    "/m/0403l3g": ["Gaming"],
    "/m/021bp2": ["Gaming", "Art"],
    "/m/07c1v": ["Technology"],
    "/m/01k8wb": ["Technology", "Education", "Science"],
    "/m/0kt51": ["Technology", "Entertainment", "News", "Art"],
    "/m/01mf_": ["Technology"],
    "/m/06ntj": ["Sports"],
    "/m/02jjt": ["Sports", "Entertainment"],
    "/m/018jz": ["Sports"],
    "/m/03tmr": ["Sports"],
    "/m/018w8": ["Sports"],
    "/m/0410tth": ["Sports"],
    "/m/07bs0": ["Sports"],
    "/m/07_53": ["Sports"],
    "/m/01cgz": ["Sports"],
    "/m/04rjg": ["Education"],
    "/m/02vxn": ["Entertainment"],
    "/m/09kqc": ["Entertainment"],
    "/m/0f2f9": ["Entertainment", "Art"],
    "/m/019_rr": ["Entertainment", "Fitness", "Vlogs"],
    "/m/098wr": ["Entertainment", "News", "Vlogs"],
    "/m/01h7lh": ["Entertainment", "Fitness"],
    "/m/02wbm": ["Food"],
    "/m/01mtb": ["Food"],
    "/m/02y_9m3": ["Food"],
    "/m/027x7n": ["Fitness"],
    "/m/07bxq": ["Travel"],
    "/m/0g6c": ["Travel"],
    "/m/032tl": ["Fashion"],
    "/m/033d7": ["Fashion"],
    "/m/05qt0": ["News"],
    "/m/01h6rj": ["News"],
    "/m/017_4m": ["Art"],
    "/m/06mq7": ["Science"],
    "/m/05qjt": ["Science"],
    "/m/01lhf": ["Science"],
}

CATEGORY_PRIORITY = [
    "Technology",
    "Science",
    "Education",
    "Gaming",
    "Music",
    "Sports",
    "Food",
    "Fitness",
    "Travel",
    "Fashion",
    "News",
    "Art",
    "Entertainment",
    "Vlogs",
]


class YouTubeTopicsClassifier:
    """Classifier using YouTube topic ids with ambiguity-aware voting."""

    def __init__(self):
        self.topic_mapping = TOPIC_ID_TO_CATEGORIES
        self.category_priority = CATEGORY_PRIORITY

    def classify(self, channel) -> Optional[Tuple[str, float]]:
        topic_ids = self._get_topic_ids(channel)
        if not topic_ids:
            logger.debug("Channel %s has no topic IDs", channel.yt_channel_id)
            return None

        scores = Counter()
        ambiguous_only = True

        for topic_id in topic_ids:
            categories = self.topic_mapping.get(topic_id)
            if not categories:
                continue

            if len(categories) == 1:
                ambiguous_only = False
                scores[categories[0]] += 2
            else:
                for category in categories:
                    scores[category] += 1

        if not scores:
            logger.debug("Channel %s topic IDs not in mapping", channel.yt_channel_id)
            return None

        ordered = sorted(
            scores.items(),
            key=lambda item: (
                -item[1],
                self.category_priority.index(item[0]) if item[0] in self.category_priority else 999,
            ),
        )
        best_category, best_score = ordered[0]
        second_score = ordered[1][1] if len(ordered) > 1 else 0

        if ambiguous_only and best_score == second_score:
            logger.debug(
                "Channel %s has only ambiguous topic evidence; abstaining",
                channel.yt_channel_id,
            )
            return None

        if best_score <= second_score:
            logger.debug(
                "Channel %s topic evidence is tied (%s vs %s); abstaining",
                channel.yt_channel_id,
                best_score,
                second_score,
            )
            return None

        confidence = 0.95 if second_score == 0 else 0.85
        logger.info(
            "Classified channel %s as %s using YouTube Topics (score=%s, second=%s)",
            channel.yt_channel_id,
            best_category,
            best_score,
            second_score,
        )
        return best_category, confidence

    def _get_topic_ids(self, channel) -> list:
        if not channel.topic_ids:
            return []

        if isinstance(channel.topic_ids, list):
            return channel.topic_ids

        if isinstance(channel.topic_ids, str):
            try:
                return json.loads(channel.topic_ids)
            except (json.JSONDecodeError, TypeError):
                return []

        return []

    def can_classify(self, channel) -> bool:
        return len(self._get_topic_ids(channel)) > 0

    @property
    def method_name(self) -> str:
        return "youtube_topics"
