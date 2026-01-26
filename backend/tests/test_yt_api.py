"""Tests for YT API service using mocked client."""

from app.services.yt_api import YTService


class FakeRequest:
    """Mock request that returns a fixed response."""

    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class FakeChannels:
    """Mock channels endpoint."""

    def list(self, part, id):
        if part == "contentDetails":
            return FakeRequest(
                {
                    "items": [
                        {
                            "contentDetails": {
                                "relatedPlaylists": {"uploads": "UPLOADS_PLAYLIST"}
                            }
                        }
                    ]
                }
            )
        return FakeRequest(
            {
                "items": [
                    {
                        "snippet": {
                            "title": "Test Channel",
                            "description": "Demo",
                            "thumbnails": {"high": {"url": "http://img"}},
                        }
                    }
                ]
            }
        )


class FakeSearch:
    """Mock search endpoint."""

    def list(self, **_kwargs):
        return FakeRequest(
            {
                "items": [
                    {
                        "id": {"videoId": "vid1"},
                        "snippet": {
                            "title": "Test Video",
                            "description": "Desc",
                            "thumbnails": {"high": {"url": "http://thumb"}},
                            "publishedAt": "2024-01-01T00:00:00Z",
                        },
                    }
                ],
                "nextPageToken": "NEXT",
            }
        )


class FakeVideos:
    """Mock videos endpoint."""

    def list(self, part, id):
        return FakeRequest(
            {
                "items": [
                    {
                        "id": "vid1",
                        "snippet": {
                            "title": "Test Video",
                            "description": "Desc",
                            "thumbnails": {"high": {"url": "http://thumb"}},
                            "publishedAt": "2024-01-01T00:00:00Z",
                        },
                        "contentDetails": {"duration": "PT1M2S"},
                        "statistics": {"viewCount": "10"},
                    }
                ]
            }
        )


class FakeYTClient:
    """Mock YT client wrapper."""

    def channels(self):
        return FakeChannels()

    def search(self):
        return FakeSearch()

    def playlistItems(self):
        return FakePlaylistItems()

    def videos(self):
        return FakeVideos()


class FakePlaylistItems:
    """Mock playlistItems endpoint."""

    def list(self, **_kwargs):
        return FakeRequest(
            {
                "items": [
                    {
                        "contentDetails": {"videoId": "vid1"},
                        "snippet": {
                            "title": "Test Video",
                            "description": "Desc",
                            "thumbnails": {"high": {"url": "http://thumb"}},
                            "publishedAt": "2024-01-01T00:00:00Z",
                        },
                    }
                ],
                "nextPageToken": "NEXT",
            }
        )


def test_get_channel_info(monkeypatch):
    """Channel info returns expected data."""
    monkeypatch.setattr("app.services.yt_api.build", lambda *args, **kwargs: FakeYTClient())
    service = YTService("key")
    info = service.get_channel_info("channel")
    assert info["title"] == "Test Channel"
    assert info["thumbnail"] == "http://img"


def test_get_channel_videos(monkeypatch):
    """Channel videos returns videos and page token."""
    monkeypatch.setattr("app.services.yt_api.build", lambda *args, **kwargs: FakeYTClient())
    service = YTService("key")
    response = service.get_channel_videos("channel", max_results=1)
    assert response["videos"][0]["video_id"] == "vid1"
    assert response["next_page_token"] == "NEXT"


def test_search_videos(monkeypatch):
    """Search returns a list of videos."""
    monkeypatch.setattr("app.services.yt_api.build", lambda *args, **kwargs: FakeYTClient())
    service = YTService("key")
    results = service.search_videos("query")
    assert results[0]["video_id"] == "vid1"
    assert results[0]["duration"] == 62


def test_get_video_details(monkeypatch):
    """Video details include statistics and duration."""
    monkeypatch.setattr("app.services.yt_api.build", lambda *args, **kwargs: FakeYTClient())
    service = YTService("key")
    details = service.get_video_details("vid1")
    assert details["video_id"] == "vid1"
    assert details["duration"] == 62
    assert details["statistics"]["viewCount"] == "10"
