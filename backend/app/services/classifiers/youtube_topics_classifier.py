"""YouTube Topics classifier using topic IDs from YouTube Data API."""

import json
from typing import Optional, Tuple

from app.logging.logger import get_logger

logger = get_logger(__name__)

# Mapping of YouTube topic IDs to category names
# Topic IDs from YouTube Data API topicDetails.topicIds
TOPIC_ID_TO_CATEGORY = {
    # Music
    "/m/04rlf": "Music",
    "/m/064t9": "Music",
    "/m/02lkt": "Music",
    "/m/0glt670": "Music",
    "/m/05rwpb": "Music",
    "/m/03_d0": "Music",
    "/m/028sqc": "Music",
    "/m/0dq0md": "Music",

    # Gaming
    "/m/0bzvm2": "Gaming",
    "/m/025zzc": "Gaming",
    "/m/02ntfj": "Gaming",
    "/m/01sjng": "Gaming",
    "/m/0403l3g": "Gaming",
    "/m/021bp2": "Gaming",

    # Technology
    "/m/07c1v": "Technology",
    "/m/01k8wb": "Technology",
    "/m/0kt51": "Technology",
    "/m/01mf_": "Technology",

    # Sports
    "/m/06ntj": "Sports",
    "/m/02jjt": "Sports",
    "/m/018jz": "Sports",
    "/m/03tmr": "Sports",
    "/m/018w8": "Sports",
    "/m/0410tth": "Sports",
    "/m/07bs0": "Sports",
    "/m/07_53": "Sports",
    "/m/01cgz": "Sports",

    # Education
    "/m/01k8wb": "Education",
    "/m/04rjg": "Education",

    # Entertainment
    "/m/02vxn": "Entertainment",
    "/m/09kqc": "Entertainment",
    "/m/02jjt": "Entertainment",
    "/m/0f2f9": "Entertainment",
    "/m/019_rr": "Entertainment",
    "/m/098wr": "Entertainment",
    "/m/01h7lh": "Entertainment",
    "/m/0kt51": "Entertainment",

    # Food
    "/m/02wbm": "Food",
    "/m/01mtb": "Food",
    "/m/02y_9m3": "Food",

    # Fitness
    "/m/027x7n": "Fitness",
    "/m/019_rr": "Fitness",
    "/m/01h7lh": "Fitness",

    # Travel
    "/m/07bxq": "Travel",
    "/m/0g6c": "Travel",

    # Fashion
    "/m/032tl": "Fashion",
    "/m/033d7": "Fashion",

    # News
    "/m/098wr": "News",
    "/m/0kt51": "News",
    "/m/05qt0": "News",
    "/m/01h6rj": "News",

    # Vlogs
    "/m/098wr": "Vlogs",
    "/m/019_rr": "Vlogs",

    # Art
    "/m/0f2f9": "Art",
    "/m/021bp2": "Art",
    "/m/0kt51": "Art",
    "/m/017_4m": "Art",

    # Science
    "/m/06mq7": "Science",
    "/m/01k8wb": "Science",
    "/m/05qjt": "Science",
    "/m/01lhf": "Science",
}

# Priority mapping when a topic maps to multiple categories
CATEGORY_PRIORITY = [
    "Gaming",
    "Music",
    "Technology",
    "Science",
    "Education",
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
    """Classifier using YouTube topic IDs for categorization."""

    def __init__(self):
        """Initialize the classifier."""
        self.topic_mapping = TOPIC_ID_TO_CATEGORY
        self.category_priority = CATEGORY_PRIORITY

    def classify(self, channel) -> Optional[Tuple[str, float]]:
        """
        Classify a channel based on its YouTube topic IDs.

        Args:
            channel: Channel object with topic_ids field (JSON string or list)

        Returns:
            Tuple of (category_name, confidence_score) or None if no match
        """
        topic_ids = self._get_topic_ids(channel)

        if not topic_ids:
            logger.debug(f"Channel {channel.yt_channel_id} has no topic IDs")
            return None

        # Map topic IDs to categories
        categories = []
        for topic_id in topic_ids:
            if topic_id in self.topic_mapping:
                category = self.topic_mapping[topic_id]
                if category not in categories:
                    categories.append(category)

        if not categories:
            logger.debug(f"Channel {channel.yt_channel_id} topic IDs not in mapping")
            return None

        # Select category based on priority
        selected_category = None
        for priority_cat in self.category_priority:
            if priority_cat in categories:
                selected_category = priority_cat
                break

        if not selected_category:
            selected_category = categories[0]

        # Confidence is 1.0 for exact match, reduced if multiple categories
        confidence = 1.0 if len(categories) == 1 else 0.9

        logger.info(
            f"Classified channel {channel.yt_channel_id} as {selected_category} "
            f"(confidence: {confidence}) using YouTube Topics"
        )
        return (selected_category, confidence)

    def _get_topic_ids(self, channel) -> list:
        """Extract topic IDs from channel, handling JSON string or list."""
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
        """Check if this classifier can handle the channel."""
        topic_ids = self._get_topic_ids(channel)
        return len(topic_ids) > 0

    @property
    def method_name(self) -> str:
        """Return the classification method name."""
        return "youtube_topics"
