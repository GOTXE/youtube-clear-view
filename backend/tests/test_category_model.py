"""Tests for Category model."""

import pytest

from app.extensions import db
from app.migrations import ensure_category_schema
from app.models import Category, PREDEFINED_CATEGORIES


def test_category_creation(app):
    """Test creating a new category."""
    with app.app_context():
        category = Category(
            name="TestCategory",
            display_name_es="Categoria Test",
            color="#123456",
            icon="🔥",
            description="Test description",
        )
        db.session.add(category)
        db.session.commit()

        saved = Category.query.filter_by(name="TestCategory").first()
        assert saved is not None
        assert saved.name == "TestCategory"
        assert saved.display_name_es == "Categoria Test"
        assert saved.color == "#123456"
        assert saved.icon == "🔥"
        assert saved.description == "Test description"
        assert saved.created_at is not None


def test_category_unique_name(app):
    """Test that category names must be unique."""
    with app.app_context():
        cat1 = Category(name="UniqueTest", display_name_es="Test", color="#000000")
        db.session.add(cat1)
        db.session.commit()

        cat2 = Category(name="UniqueTest", display_name_es="Test 2", color="#ffffff")
        db.session.add(cat2)
        with pytest.raises(Exception):
            db.session.commit()


def test_category_to_dict(app):
    """Test category serialization."""
    with app.app_context():
        category = Category(
            name="SerializeTest",
            display_name_es="Test Serializar",
            color="#abcdef",
            icon="🧪",
            description="Serialize test",
        )
        db.session.add(category)
        db.session.commit()

        data = category.to_dict()
        assert data["name"] == "SerializeTest"
        assert data["display_name_es"] == "Test Serializar"
        assert data["color"] == "#abcdef"
        assert data["icon"] == "🧪"
        assert data["description"] == "Serialize test"
        assert "id" in data


def test_predefined_categories_count():
    """Test that we have exactly 16 predefined categories."""
    assert len(PREDEFINED_CATEGORIES) == 16


def test_predefined_categories_structure():
    """Test that predefined categories have required fields."""
    required_fields = ["name", "display_name_es", "color", "icon"]
    for cat in PREDEFINED_CATEGORIES:
        for field in required_fields:
            assert field in cat, f"Missing {field} in {cat.get('name', 'unknown')}"


def test_predefined_categories_names():
    """Test that predefined categories have expected names."""
    expected_names = [
        "Gaming", "Technology", "Education", "Music", "Automotive", "Food",
        "Fitness", "Travel", "Fashion", "News", "Entertainment",
        "Vlogs", "Sports", "Art", "Animals", "Science",
    ]
    actual_names = [cat["name"] for cat in PREDEFINED_CATEGORIES]
    assert sorted(actual_names) == sorted(expected_names)


def test_category_seed_creates_16_categories(app):
    """Test that seeding creates 16 categories in database."""
    with app.app_context():
        count = Category.query.count()
        assert count == 16, f"Expected 16 categories, got {count}"


def test_category_schema_backfills_missing_categories(app):
    """Existing databases should receive newly added predefined categories."""
    with app.app_context():
        Category.query.filter(Category.name.in_(["Automotive", "Animals"])).delete(
            synchronize_session=False
        )
        db.session.commit()

        assert Category.query.filter_by(name="Automotive").first() is None
        assert Category.query.filter_by(name="Animals").first() is None

        ensure_category_schema()

        assert Category.query.filter_by(name="Automotive").first() is not None
        assert Category.query.filter_by(name="Animals").first() is not None


def test_category_colors_are_valid_hex(app):
    """Test that all category colors are valid hex codes."""
    with app.app_context():
        categories = Category.query.all()
        import re
        hex_pattern = re.compile(r"^#[0-9a-fA-F]{6}$")
        for cat in categories:
            assert hex_pattern.match(cat.color), f"Invalid hex color: {cat.color}"


def test_sample_category_fixture(sample_category):
    """Test that sample_category fixture works."""
    assert sample_category["id"] is not None
    assert sample_category["name"] == "Gaming"
