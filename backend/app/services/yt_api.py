"""YT Data API v3 integration service."""

import os

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.services.video_cache import VideoCache


class YTService:
    """Service wrapper for YT Data API v3."""

    def __init__(self, api_key):
        """Initialize the API client and cache."""
        self.api_key = api_key
        self.logger = get_logger(__name__)
        self.cache = VideoCache()
        self.cache_ttl = int(os.getenv("CACHE_TTL", "3600"))
        self.client = None

        if not api_key:
            self.logger.error(
                "Missing YT_API_KEY.",
                extra={"tracking_id": generate_tracking_id()},
            )
            return

        try:
            self.client = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
        except Exception as error:
            self.logger.exception(
                "Failed to initialize YT API client: %s",
                error,
                extra={"tracking_id": generate_tracking_id()},
            )

    def _log_api_error(self, message, error):
        """Log an API error with a tracking ID."""
        self.logger.exception(
            message,
            error,
            extra={"tracking_id": generate_tracking_id()},
        )

    def _handle_http_error(self, error):
        """Handle HTTP errors and rate limits gracefully."""
        status = getattr(error, "status_code", None)
        if hasattr(error, "resp") and hasattr(error.resp, "status"):
            status = error.resp.status
        if status in (403, 429):
            self.logger.warning(
                "YT API rate limit encountered.",
                extra={"tracking_id": generate_tracking_id()},
            )
            return True
        return False

    def _parse_duration(self, duration):
        """Parse ISO 8601 duration into seconds."""
        if not duration or not duration.startswith("PT"):
            return None

        total_seconds = 0
        number = ""
        for char in duration[2:]:
            if char.isdigit():
                number += char
                continue
            if char == "H":
                total_seconds += int(number) * 3600
            elif char == "M":
                total_seconds += int(number) * 60
            elif char == "S":
                total_seconds += int(number)
            number = ""
        return total_seconds

    def _video_response_map(self, items):
        """Convert video API items into simplified dicts."""
        videos = []
        for item in items:
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = None
            if "high" in thumbnails:
                thumbnail_url = thumbnails["high"].get("url")
            elif "medium" in thumbnails:
                thumbnail_url = thumbnails["medium"].get("url")
            elif "default" in thumbnails:
                thumbnail_url = thumbnails["default"].get("url")

            videos.append(
                {
                    "video_id": item.get("id"),
                    "title": snippet.get("title"),
                    "description": snippet.get("description"),
                    "thumbnail": thumbnail_url,
                    "published_at": snippet.get("publishedAt"),
                    "duration": self._parse_duration(content.get("duration")),
                }
            )
        return videos

    def get_channel_info(self, channel_id):
        """Fetch channel information by channel ID."""
        if not self.client:
            return None

        cache_key = f"channel_info:{channel_id}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            response = (
                self.client.channels()
                .list(part="snippet", id=channel_id)
                .execute()
            )
            items = response.get("items", [])
            if not items:
                return None
            snippet = items[0].get("snippet", {})
            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = None
            if "high" in thumbnails:
                thumbnail_url = thumbnails["high"].get("url")
            elif "medium" in thumbnails:
                thumbnail_url = thumbnails["medium"].get("url")
            elif "default" in thumbnails:
                thumbnail_url = thumbnails["default"].get("url")
            channel_info = {
                "channel_id": channel_id,
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "thumbnail": thumbnail_url,
            }
            self.cache.set(cache_key, channel_info, self.cache_ttl)
            return channel_info
        except HttpError as error:
            if self._handle_http_error(error):
                return None
            self._log_api_error("Failed to fetch channel info: %s", error)
            return None
        except Exception as error:
            self._log_api_error("Failed to fetch channel info: %s", error)
            return None

    def get_channel_videos(self, channel_id, max_results=50, page_token=None):
        """Fetch recent videos for a channel with pagination support."""
        if not self.client:
            return {"videos": [], "next_page_token": None}

        uploads_playlist_id = self._get_uploads_playlist_id(channel_id)
        if not uploads_playlist_id:
            return {"videos": [], "next_page_token": None}

        cache_key = f"channel_videos:{channel_id}:{max_results}:{page_token}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            playlist_request = self.client.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=max_results,
                pageToken=page_token,
            )
            playlist_response = playlist_request.execute()
            items = playlist_response.get("items", [])
            video_ids = [
                item.get("contentDetails", {}).get("videoId")
                for item in items
                if item.get("contentDetails")
            ]
            if not video_ids:
                return {"videos": [], "next_page_token": None}

            videos_response = (
                self.client.videos()
                .list(part="snippet,contentDetails", id=",".join(video_ids))
                .execute()
            )
            videos = self._video_response_map(videos_response.get("items", []))
            result = {
                "videos": videos,
                "next_page_token": playlist_response.get("nextPageToken"),
            }
            self.cache.set(cache_key, result, self.cache_ttl)
            return result
        except HttpError as error:
            if self._handle_http_error(error):
                return {"videos": [], "next_page_token": None}
            self._log_api_error("Failed to fetch channel videos: %s", error)
            return {"videos": [], "next_page_token": None}
        except Exception as error:
            self._log_api_error("Failed to fetch channel videos: %s", error)
            return {"videos": [], "next_page_token": None}

    def _get_uploads_playlist_id(self, channel_id):
        """Fetch and cache the uploads playlist ID for a channel."""
        cache_key = f"uploads_playlist:{channel_id}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            response = (
                self.client.channels()
                .list(part="contentDetails", id=channel_id)
                .execute()
            )
            items = response.get("items", [])
            if not items:
                return None
            content = items[0].get("contentDetails", {})
            playlist_id = content.get("relatedPlaylists", {}).get("uploads")
            if playlist_id:
                self.cache.set(cache_key, playlist_id, self.cache_ttl)
            return playlist_id
        except HttpError as error:
            if self._handle_http_error(error):
                return None
            self._log_api_error("Failed to fetch uploads playlist: %s", error)
            return None
        except Exception as error:
            self._log_api_error("Failed to fetch uploads playlist: %s", error)
            return None

    def search_videos(self, query, channel_id=None, max_results=20):
        """Search videos by query text with optional channel filter."""
        if not self.client:
            return []

        cache_key = f"search:{query}:{channel_id}:{max_results}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            search_request = self.client.search().list(
                part="snippet",
                q=query,
                maxResults=max_results,
                type="video",
                channelId=channel_id,
            )
            search_response = search_request.execute()
            items = search_response.get("items", [])
            video_ids = [item.get("id", {}).get("videoId") for item in items if item.get("id")]
            if not video_ids:
                return []

            videos_response = (
                self.client.videos()
                .list(part="snippet,contentDetails", id=",".join(video_ids))
                .execute()
            )
            videos = self._video_response_map(videos_response.get("items", []))
            self.cache.set(cache_key, videos, self.cache_ttl)
            return videos
        except HttpError as error:
            if self._handle_http_error(error):
                return []
            self._log_api_error("Failed to search videos: %s", error)
            return []
        except Exception as error:
            self._log_api_error("Failed to search videos: %s", error)
            return []

    def get_video_details(self, video_id):
        """Fetch detailed information about a video by ID."""
        if not self.client:
            return None

        cache_key = f"video_details:{video_id}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            response = (
                self.client.videos()
                .list(part="snippet,contentDetails,statistics", id=video_id)
                .execute()
            )
            items = response.get("items", [])
            if not items:
                return None
            item = items[0]
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            stats = item.get("statistics", {})
            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = None
            if "high" in thumbnails:
                thumbnail_url = thumbnails["high"].get("url")
            elif "medium" in thumbnails:
                thumbnail_url = thumbnails["medium"].get("url")
            elif "default" in thumbnails:
                thumbnail_url = thumbnails["default"].get("url")
            details = {
                "video_id": video_id,
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "thumbnail": thumbnail_url,
                "published_at": snippet.get("publishedAt"),
                "duration": self._parse_duration(content.get("duration")),
                "statistics": stats,
            }
            self.cache.set(cache_key, details, self.cache_ttl)
            return details
        except HttpError as error:
            if self._handle_http_error(error):
                return None
            self._log_api_error("Failed to fetch video details: %s", error)
            return None
        except Exception as error:
            self._log_api_error("Failed to fetch video details: %s", error)
            return None
