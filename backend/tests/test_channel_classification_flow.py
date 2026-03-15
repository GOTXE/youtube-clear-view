"""Tests for channel classification timing and enrichment flow."""

from app.extensions import db
from app.models import Channel, ChannelCategory, User, UserChannel


def test_import_defers_classification_until_enrichment(app, sample_user, monkeypatch):
    """Subscription import should not auto-classify channels from bare snippet data."""
    with app.app_context():
        user = db.session.get(User, sample_user["id"])
        user.auth_provider = "google"
        user.google_sub = "sub-1"
        db.session.commit()

        monkeypatch.setattr("app.routes.channels.ensure_access_token", lambda user: "token")
        monkeypatch.setattr(
            "app.routes.channels.fetch_subscriptions_page",
            lambda access_token, page_token=None, max_results=50: (
                [
                    {
                        "snippet": {
                            "title": "Starter Story",
                            "description": "Founder interviews",
                            "publishedAt": "2024-01-01T00:00:00Z",
                            "resourceId": {"channelId": "starter-story-yt"},
                            "thumbnails": {"default": {"url": "http://thumb"}},
                        }
                    }
                ],
                None,
                {"next_page_token": None, "total_results": 1},
            ),
        )

        with app.test_client() as client:
            client.post("/api/auth/login", json={"username": user.username, "password": "testpass123"})

            response = client.post("/api/channels/import", json={"max_results": 1})
            assert response.status_code == 200

            data = response.get_json()
            assert data["classified"] == 0

            channel = Channel.query.filter_by(yt_channel_id="starter-story-yt").first()
            assert channel is not None
            assert ChannelCategory.query.filter_by(channel_id=channel.id).first() is None


def test_enrich_classifies_channel_after_metadata_fetch(app, sample_user, monkeypatch):
    """Enrichment should classify once topic data is available."""
    with app.app_context():
        user = db.session.get(User, sample_user["id"])
        user.auth_provider = "google"

        channel = Channel(
            yt_channel_id="needs-enrichment",
            title="Needs Enrichment",
            description="",
        )
        db.session.add(channel)
        db.session.flush()
        db.session.add(UserChannel(user_id=user.id, channel_id=channel.id))
        db.session.commit()

        class FakeService:
            def get_channel_info(self, channel_id):
                return {
                    "channel_id": channel_id,
                    "title": "Needs Enrichment",
                    "description": "Latest devices and programming videos",
                    "thumbnail": "http://thumb",
                    "topic_ids": ["/m/07c1v"],
                    "keywords": "technology programming gadgets",
                    "country": "ES",
                }

        monkeypatch.setattr("app.routes.channels._get_service", lambda: FakeService())

        with app.test_client() as client:
            client.post(
                "/api/auth/login",
                json={"username": sample_user["username"], "password": "testpass123"},
            )

            response = client.post("/api/channels/enrich", json={"channel_id": channel.id})
            assert response.status_code == 200

            data = response.get_json()
            assert data["enriched"] == 1
            assert data["classified"] == 1

            channel_category = ChannelCategory.query.filter_by(channel_id=channel.id).first()
            assert channel_category is not None
            assert channel_category.classification_method == "youtube_topics"
