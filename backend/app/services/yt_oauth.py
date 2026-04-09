"""YT Data API helper using OAuth access tokens."""

import requests

from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id
from app.services.quota import mark_quota_exhausted, record_quota_event

SUBSCRIPTIONS_URL = "https://www.googleapis.com/youtube/v3/subscriptions"

logger = get_logger(__name__)


def _record_quota_event_safe(**kwargs):
    """Persist quota telemetry without breaking the OAuth request path."""
    try:
        record_quota_event(**kwargs)
    except Exception as error:
        logger.warning(
            "Failed to persist quota event: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )


def fetch_subscriptions_page(access_token, page_token=None, max_results=50, user_id=None):
    """Fetch a single page of subscriptions for the authenticated YT account."""
    if not access_token:
        return None, 401, None

    params = {
        "part": "snippet",
        "mine": "true",
        "maxResults": max_results,
    }
    if page_token:
        params["pageToken"] = page_token

    try:
        _record_quota_event_safe(
            api_method="subscriptions.list",
            units=1,
            source="subscriptions_import",
            user_id=user_id,
        )
        response = requests.get(
            SUBSCRIPTIONS_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=10,
        )
    except requests.RequestException as error:
        logger.warning(
            "YT subscriptions request failed: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )
        return None, 502, None

    if not response.ok:
        quota_exhausted = False
        try:
            payload = response.json()
            errors = payload.get("error", {}).get("errors", [])
            quota_exhausted = any(
                error.get("reason") in {"quotaExceeded", "dailyLimitExceeded"}
                for error in errors
            )
        except ValueError:
            quota_exhausted = False
        if quota_exhausted:
            mark_quota_exhausted(None)
        logger.warning(
            "YT subscriptions returned %s",
            response.status_code,
            extra={"tracking_id": generate_tracking_id()},
        )
        return None, response.status_code, None

    payload = response.json()
    items = payload.get("items", [])
    next_token = payload.get("nextPageToken")
    total_results = payload.get("pageInfo", {}).get("totalResults")
    return items, None, {"next_page_token": next_token, "total_results": total_results}
