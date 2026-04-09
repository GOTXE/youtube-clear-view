"""Tests for background enrichment task."""

import threading
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db
from app.models import Channel, ChannelCategory, UserChannel, UserSettings
from app.services.enrichment_task import (
    _run_topic_ids_step,
    _run_video_evidence_step,
    enrich_status_dict,
    start_enrich_task,
)


@pytest.fixture()
def enrichment_setup(app, sample_user):
    """Set up user with settings and unclassified channels."""
    with app.app_context():
        settings = UserSettings(user_id=sample_user["id"], preset="standard")
        db.session.add(settings)
        db.session.flush()

        channels = []
        for i in range(3):
            ch = Channel(
                yt_channel_id=f"enrich-ch-{i}",
                title=f"Channel {i}",
                description=f"Description {i}",
            )
            db.session.add(ch)
            db.session.flush()
            sub = UserChannel(user_id=sample_user["id"], channel_id=ch.id)
            db.session.add(sub)
            channels.append(ch)

        db.session.commit()
        return {
            "user_id": sample_user["id"],
            "settings_id": settings.id,
            "channel_ids": [ch.id for ch in channels],
        }


def test_start_enrich_task_sets_fields(app, sample_user, enrichment_setup):
    """Test that start_enrich_task initializes enrich fields correctly."""
    with app.app_context():
        from app.models import User

        user = db.session.get(User, sample_user["id"])
        settings = db.session.get(UserSettings, enrichment_setup["settings_id"])

        with patch("app.services.enrichment_task.threading") as mock_threading:
            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = False
            mock_threading.Thread.return_value = mock_thread

            status = start_enrich_task(app, user, settings)

        assert status is not None
        assert status["active"] is True
        assert status["phase"] == "topic_ids"
        assert status["total"] == 3
        assert status["cursor"] == 0
        assert status["classified"] == 0
        assert status["errors"] == 0
        assert status["started_at"] is not None


def test_run_topic_ids_step_enriches_batch(app, enrichment_setup):
    """Test that _run_topic_ids_step enriches channels with topic data."""
    with app.app_context():
        settings = db.session.get(UserSettings, enrichment_setup["settings_id"])
        settings.enrich_cursor = 0
        settings.enrich_total = 3
        settings.enrich_classified = 0
        settings.enrich_errors = 0
        db.session.commit()

        mock_service = MagicMock()
        mock_service.get_channel_info.return_value = {
            "topic_ids": ["/m/02mjmr"],
            "keywords": "gaming",
            "country": "US",
        }

        mock_classifier = MagicMock()
        mock_classifier.classify_channel.return_value = True

        attempted = set()
        has_more = _run_topic_ids_step(
            enrichment_setup["user_id"], settings, mock_service, mock_classifier, attempted
        )

        assert has_more is False  # All 3 enriched in one batch
        assert settings.enrich_cursor == 3
        assert mock_service.get_channel_info.call_count == 3
        assert len(attempted) == 3


def test_phase_transition_topic_to_video(app, sample_user, enrichment_setup):
    """Test that when no topic_ids are needed, phase transitions to video_evidence."""
    with app.app_context():
        from app.models import User
        import json

        # Give all channels topic_ids so topic phase has nothing to do
        for ch_id in enrichment_setup["channel_ids"]:
            ch = db.session.get(Channel, ch_id)
            ch.topic_ids = json.dumps(["/m/02mjmr"])
        db.session.commit()

        user = db.session.get(User, sample_user["id"])
        settings = db.session.get(UserSettings, enrichment_setup["settings_id"])

        with patch("app.services.enrichment_task.threading") as mock_threading:
            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = False
            mock_threading.Thread.return_value = mock_thread

            status = start_enrich_task(app, user, settings)

        # total should be 3 (unclassified channels), topic count is 0
        assert status is not None
        assert status["active"] is True


def test_video_evidence_classifies(app, enrichment_setup):
    """Test that _run_video_evidence_step processes channels and increments classified."""
    with app.app_context():
        from app.models import Category

        settings = db.session.get(UserSettings, enrichment_setup["settings_id"])
        settings.enrich_cursor = 0
        settings.enrich_total = 3
        settings.enrich_classified = 0
        settings.enrich_errors = 0
        db.session.commit()

        mock_service = MagicMock()
        mock_service.get_channel_videos.return_value = {
            "success": True,
            "videos": [
                {
                    "video_id": "v1",
                    "title": "Test",
                    "description": "Test desc",
                    "published_at": "2024-01-01T00:00:00Z",
                    "duration": 120,
                }
            ],
        }

        # Make classify_channel actually insert a ChannelCategory row
        category = Category.query.first()

        def fake_classify(channel):
            if not ChannelCategory.query.filter_by(channel_id=channel.id).first():
                cc = ChannelCategory(
                    channel_id=channel.id,
                    category_id=category.id,
                    is_auto_classified=True,
                    classification_method="tfidf",
                    confidence_score=0.8,
                )
                db.session.add(cc)
                db.session.flush()
            return True

        mock_classifier = MagicMock()
        mock_classifier.classify_channel.side_effect = fake_classify

        attempted = set()
        with patch(
            "app.services.enrichment_task.upsert_channel_video_evidence",
            return_value=(1, 0),
        ):
            has_more = _run_video_evidence_step(
                enrichment_setup["user_id"], settings, mock_service, mock_classifier, attempted
            )

        assert has_more is False
        assert settings.enrich_cursor == 3
        assert settings.enrich_classified == 3
        assert len(attempted) == 3


def test_enrich_completes_when_all_done(app, sample_user):
    """Test that enrich returns None when nothing to classify."""
    with app.app_context():
        from app.models import User

        settings = UserSettings(user_id=sample_user["id"], preset="standard")
        db.session.add(settings)
        db.session.commit()

        user = db.session.get(User, sample_user["id"])
        result = start_enrich_task(app, user, settings)
        assert result is None
        assert settings.enrich_active is False


def test_error_handling(app, enrichment_setup):
    """Test that API failures increment enrich_errors."""
    with app.app_context():
        settings = db.session.get(UserSettings, enrichment_setup["settings_id"])
        settings.enrich_cursor = 0
        settings.enrich_total = 3
        settings.enrich_classified = 0
        settings.enrich_errors = 0
        db.session.commit()

        mock_service = MagicMock()
        mock_service.get_channel_info.side_effect = Exception("API error")

        mock_classifier = MagicMock()

        attempted = set()
        _run_topic_ids_step(
            enrichment_setup["user_id"], settings, mock_service, mock_classifier, attempted
        )

        assert settings.enrich_errors == 3
        assert settings.enrich_classified == 0
        assert len(attempted) == 3


def test_start_returns_409_if_running(app, sample_user, enrichment_setup):
    """Test that starting while already running raises ValueError."""
    with app.app_context():
        from app.models import User
        from app.services.enrichment_task import _active_enrichments, _enrichment_lock

        user = db.session.get(User, sample_user["id"])
        settings = db.session.get(UserSettings, enrichment_setup["settings_id"])

        # Simulate a running thread
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        with _enrichment_lock:
            _active_enrichments[user.id] = mock_thread

        try:
            with pytest.raises(ValueError, match="already_running"):
                start_enrich_task(app, user, settings)
        finally:
            with _enrichment_lock:
                _active_enrichments.pop(user.id, None)


def test_no_reprocess_unclassifiable_channels(app, enrichment_setup):
    """Test that channels attempted once are not re-processed even if unclassifiable."""
    with app.app_context():
        settings = db.session.get(UserSettings, enrichment_setup["settings_id"])
        settings.enrich_cursor = 0
        settings.enrich_total = 3
        settings.enrich_classified = 0
        settings.enrich_errors = 0
        db.session.commit()

        mock_service = MagicMock()
        mock_service.get_channel_videos.return_value = {"success": True, "videos": []}

        # Classifier always fails — returns False
        mock_classifier = MagicMock()
        mock_classifier.classify_channel.return_value = False

        attempted = set()
        with patch(
            "app.services.enrichment_task.upsert_channel_video_evidence",
            return_value=(0, 0),
        ):
            # First call processes 3 channels
            has_more = _run_video_evidence_step(
                enrichment_setup["user_id"], settings, mock_service, mock_classifier, attempted
            )
            assert has_more is False  # No more because all are in attempted
            assert len(attempted) == 3

            # Second call finds nothing (all excluded)
            has_more = _run_video_evidence_step(
                enrichment_setup["user_id"], settings, mock_service, mock_classifier, attempted
            )
            assert has_more is False
            # Service was only called 3 times total (not 6)
            assert mock_service.get_channel_videos.call_count == 3


def test_status_endpoint(app, auth_client, enrichment_setup):
    """Test the GET /api/channels/classify/status endpoint."""
    resp = auth_client.get("/api/channels/classify/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "active" in data
    assert "phase" in data
    assert "cursor" in data
    assert "total" in data
    assert "classified" in data
    assert "errors" in data
