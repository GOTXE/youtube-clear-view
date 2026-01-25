"""YouTube Data API helper using OAuth access tokens."""

import requests

from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id

SUBSCRIPTIONS_URL = "https://www.googleapis.com/youtube/v3/subscriptions"

logger = get_logger(__name__)


def fetch_subscriptions_page(access_token, page_token=None, max_results=50):
    """Fetch a single page of subscriptions for the authenticated YouTube account."""
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
        response = requests.get(
            SUBSCRIPTIONS_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=10,
        )
    except requests.RequestException as error:
        logger.warning(
            "YouTube subscriptions request failed: %s",
            error,
            extra={"tracking_id": generate_tracking_id()},
        )
        return None, 502, None

    if not response.ok:
        logger.warning(
            "YouTube subscriptions returned %s",
            response.status_code,
            extra={"tracking_id": generate_tracking_id()},
        )
        return None, response.status_code, None

    payload = response.json()
    items = payload.get("items", [])
    next_token = payload.get("nextPageToken")
    total_results = payload.get("pageInfo", {}).get("totalResults")
    return items, None, {"next_page_token": next_token, "total_results": total_results}
