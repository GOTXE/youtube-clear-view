"""Category domain models for automatic channel classification."""

from datetime import datetime

from app.extensions import db


class Category(db.Model):
    """Predefined category for channel classification."""

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    display_name_es = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(7), nullable=False)
    icon = db.Column(db.String(10))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    channel_categories = db.relationship(
        "ChannelCategory", back_populates="category", cascade="all, delete-orphan"
    )

    def to_dict(self):
        """Serialize the category for JSON responses."""
        return {
            "id": self.id,
            "name": self.name,
            "display_name_es": self.display_name_es,
            "color": self.color,
            "icon": self.icon,
            "description": self.description,
        }


class ChannelCategory(db.Model):
    """Classification link between channels and categories."""

    __tablename__ = "channel_categories"

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(
        db.Integer, db.ForeignKey("channels.id"), nullable=False, unique=True, index=True
    )
    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True
    )
    is_auto_classified = db.Column(db.Boolean, nullable=False, default=True)
    classification_method = db.Column(db.String(20))
    confidence_score = db.Column(db.Float)
    classified_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    channel = db.relationship("Channel", back_populates="channel_category")
    category = db.relationship("Category", back_populates="channel_categories")

    __table_args__ = (
        db.CheckConstraint(
            "classification_method IN ('youtube_topics', 'tfidf', 'manual')",
            name="ck_classification_method",
        ),
        db.CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_confidence_score_range",
        ),
    )

    def to_dict(self):
        """Serialize the channel-category link for JSON responses."""
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "category_id": self.category_id,
            "category": self.category.to_dict() if self.category else None,
            "is_auto_classified": self.is_auto_classified,
            "classification_method": self.classification_method,
            "confidence_score": self.confidence_score,
            "classified_at": self.classified_at.isoformat() if self.classified_at else None,
            "last_updated_at": self.last_updated_at.isoformat() if self.last_updated_at else None,
        }


# Predefined categories seeded into every local database
PREDEFINED_CATEGORIES = [
    {"name": "Gaming", "display_name_es": "Gaming", "color": "#9c27b0", "icon": "🎮"},
    {"name": "Technology", "display_name_es": "Tecnología", "color": "#2196f3", "icon": "💻"},
    {"name": "Education", "display_name_es": "Educación", "color": "#795548", "icon": "📚"},
    {"name": "Music", "display_name_es": "Música", "color": "#e91e63", "icon": "🎵"},
    {"name": "Automotive", "display_name_es": "Automoción", "color": "#546e7a", "icon": "🚗"},
    {"name": "Food", "display_name_es": "Cocina", "color": "#ff6f00", "icon": "🍳"},
    {"name": "Fitness", "display_name_es": "Fitness", "color": "#8bc34a", "icon": "💪"},
    {"name": "Travel", "display_name_es": "Viajes", "color": "#00bcd4", "icon": "✈️"},
    {"name": "Fashion", "display_name_es": "Moda", "color": "#e91e63", "icon": "💄"},
    {"name": "News", "display_name_es": "Noticias", "color": "#f44336", "icon": "📰"},
    {"name": "Entertainment", "display_name_es": "Entretenimiento", "color": "#ff9800", "icon": "🎭"},
    {"name": "Vlogs", "display_name_es": "Vlogs", "color": "#4caf50", "icon": "📹"},
    {"name": "Sports", "display_name_es": "Deportes", "color": "#ff5722", "icon": "⚽"},
    {"name": "Art", "display_name_es": "Arte", "color": "#9c27b0", "icon": "🎨"},
    {"name": "Animals", "display_name_es": "Animales", "color": "#689f38", "icon": "🐾"},
    {"name": "Science", "display_name_es": "Ciencia", "color": "#3f51b5", "icon": "🔬"},
]
