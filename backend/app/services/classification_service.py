"""Precision-first channel classification service."""

from datetime import datetime
from typing import List, Optional, Tuple

from app.extensions import db
from app.logging.logger import get_logger
from app.models import Category, Channel, ChannelCategory

from .classifiers import TFIDFClassifier, YouTubeTopicsClassifier

logger = get_logger(__name__)


class ClassificationService:
    """Service for classifying channels with deterministic-first rules."""

    def __init__(self):
        """Initialize the classification service with all classifiers."""
        self.classifiers = [YouTubeTopicsClassifier(), TFIDFClassifier()]
        self._category_cache = {}

    def classify_channel(self, channel: Channel) -> Optional[ChannelCategory]:
        """
        Classify a single channel using the cascade of classifiers.

        Args:
            channel: Channel to classify

        Returns:
            ChannelCategory if successful, None otherwise
        """
        # Check if already classified
        existing = ChannelCategory.query.filter_by(channel_id=channel.id).first()
        if existing and not existing.is_auto_classified:
            # Manual classification, don't override
            logger.debug(
                f"Channel {channel.yt_channel_id} has manual classification, skipping"
            )
            return existing

        # Try each classifier in cascade
        result = None
        method_used = None

        for classifier in self.classifiers:
            try:
                if not classifier.can_classify(channel):
                    continue

                classification = classifier.classify(channel)
                if classification:
                    category_name, confidence = classification
                    result = (category_name, confidence)
                    method_used = classifier.method_name
                    break

            except Exception as e:
                logger.error(
                    f"Classifier {classifier.method_name} error for "
                    f"{channel.yt_channel_id}: {e}"
                )
                continue

        if not result:
            logger.warning(f"No classifier could categorize {channel.yt_channel_id}")
            return None

        category_name, confidence = result

        # Get category from database
        category = self._get_category(category_name)
        if not category:
            logger.error(f"Category {category_name} not found in database")
            return None

        # Create or update ChannelCategory
        now = datetime.utcnow()

        if existing:
            existing.category_id = category.id
            existing.is_auto_classified = True
            existing.classification_method = method_used
            existing.confidence_score = confidence
            existing.last_updated_at = now
            channel_category = existing
        else:
            channel_category = ChannelCategory(
                channel_id=channel.id,
                category_id=category.id,
                is_auto_classified=True,
                classification_method=method_used,
                confidence_score=confidence,
                classified_at=now,
                last_updated_at=now,
            )
            db.session.add(channel_category)

        try:
            db.session.commit()
            logger.info(
                f"Classified {channel.yt_channel_id} as {category_name} "
                f"using {method_used} (confidence: {confidence:.2f})"
            )
            return channel_category
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to save classification for {channel.yt_channel_id}: {e}")
            return None

    def classify_channels(
        self, channels: List[Channel], skip_existing: bool = True
    ) -> List[ChannelCategory]:
        """
        Classify multiple channels.

        Args:
            channels: List of channels to classify
            skip_existing: If True, skip channels that already have a classification

        Returns:
            List of ChannelCategory objects for successfully classified channels
        """
        results = []
        total = len(channels)

        for i, channel in enumerate(channels):
            logger.info(f"Classifying channel {i + 1}/{total}: {channel.yt_channel_id}")

            if skip_existing:
                existing = ChannelCategory.query.filter_by(channel_id=channel.id).first()
                if existing:
                    results.append(existing)
                    continue

            channel_category = self.classify_channel(channel)
            if channel_category:
                results.append(channel_category)

        logger.info(f"Classified {len(results)}/{total} channels")
        return results

    def reclassify_channel(self, channel: Channel) -> Optional[ChannelCategory]:
        """
        Force reclassification of a channel, overriding existing classification.

        Args:
            channel: Channel to reclassify

        Returns:
            ChannelCategory if successful, None otherwise
        """
        # Delete existing classification first
        existing = ChannelCategory.query.filter_by(channel_id=channel.id).first()
        if existing:
            db.session.delete(existing)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Failed to delete existing classification: {e}")
                return None

        return self.classify_channel(channel)

    def manually_classify(
        self, channel: Channel, category_name: str
    ) -> Optional[ChannelCategory]:
        """
        Manually assign a category to a channel.

        Args:
            channel: Channel to classify
            category_name: Name of the category to assign

        Returns:
            ChannelCategory if successful, None otherwise
        """
        category = self._get_category(category_name)
        if not category:
            logger.error(f"Category {category_name} not found")
            return None

        now = datetime.utcnow()
        existing = ChannelCategory.query.filter_by(channel_id=channel.id).first()

        if existing:
            existing.category_id = category.id
            existing.is_auto_classified = False
            existing.classification_method = "manual"
            existing.confidence_score = 1.0
            existing.last_updated_at = now
            channel_category = existing
        else:
            channel_category = ChannelCategory(
                channel_id=channel.id,
                category_id=category.id,
                is_auto_classified=False,
                classification_method="manual",
                confidence_score=1.0,
                classified_at=now,
                last_updated_at=now,
            )
            db.session.add(channel_category)

        try:
            db.session.commit()
            logger.info(
                f"Manually classified {channel.yt_channel_id} as {category_name}"
            )
            return channel_category
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to save manual classification: {e}")
            return None

    def get_channel_category(self, channel: Channel) -> Optional[ChannelCategory]:
        """Get the category assignment for a channel."""
        return ChannelCategory.query.filter_by(channel_id=channel.id).first()

    def _get_category(self, name: str) -> Optional[Category]:
        """Get category by name with caching."""
        if name not in self._category_cache:
            self._category_cache[name] = Category.query.filter_by(name=name).first()
        return self._category_cache[name]

    def get_classifier_status(self) -> dict:
        """Get status of all classifiers."""
        status = {}
        for classifier in self.classifiers:
            name = classifier.method_name
            available = hasattr(classifier, "is_available") and classifier.is_available
            if not hasattr(classifier, "is_available"):
                available = True  # Assume available if no check
            status[name] = {"available": available}
        return status
