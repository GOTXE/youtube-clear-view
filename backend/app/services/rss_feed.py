"""RSS/Atom discovery helpers for YouTube channel feeds."""

from dataclasses import dataclass
from datetime import datetime
from xml.etree import ElementTree

import requests

from app.logging.logger import get_logger
from app.logging.tracking import generate_tracking_id

logger = get_logger(__name__)

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


@dataclass
class FeedEntry:
    """Normalized feed entry payload used by the refresh pipeline."""

    video_id: str
    channel_id: str | None
    title: str | None
    published_at: str | None
    updated_at: str | None
    channel_title: str | None
    link: str | None


def build_feed_url(channel_id):
    """Build the canonical YouTube channel feed URL."""
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def parse_feed_entries(xml_text):
    """Parse YouTube Atom feed XML into normalized entries."""
    if not xml_text:
        return []

    root = ElementTree.fromstring(xml_text)
    entries = []

    for entry in root.findall("atom:entry", ATOM_NS):
        author = entry.find("atom:author", ATOM_NS)
        link = entry.find("atom:link", ATOM_NS)
        entries.append(
            FeedEntry(
                video_id=_text(entry.find("yt:videoId", ATOM_NS)),
                channel_id=_text(entry.find("yt:channelId", ATOM_NS)),
                title=_text(entry.find("atom:title", ATOM_NS)),
                published_at=_text(entry.find("atom:published", ATOM_NS)),
                updated_at=_text(entry.find("atom:updated", ATOM_NS)),
                channel_title=_text(author.find("atom:name", ATOM_NS)) if author is not None else None,
                link=link.get("href") if link is not None else None,
            )
        )

    return [entry for entry in entries if entry.video_id]


def fetch_channel_feed(channel_id, timeout=10):
    """Fetch a YouTube channel feed and parse it into normalized entries."""
    url = build_feed_url(channel_id)
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as error:
        logger.warning(
            "Failed to fetch channel feed: %s",
            error,
            extra={"tracking_id": generate_tracking_id(), "channel_id": channel_id},
        )
        return {"success": False, "entries": [], "status_code": _status_code(error)}

    try:
        entries = parse_feed_entries(response.text)
    except ElementTree.ParseError as error:
        logger.warning(
            "Failed to parse channel feed: %s",
            error,
            extra={"tracking_id": generate_tracking_id(), "channel_id": channel_id},
        )
        return {"success": False, "entries": [], "status_code": response.status_code}

    return {"success": True, "entries": entries, "status_code": response.status_code}


def _text(node):
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def _status_code(error):
    response = getattr(error, "response", None)
    return getattr(response, "status_code", None)
