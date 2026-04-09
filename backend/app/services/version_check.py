"""Version check against GitHub tags with in-process caching."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

REPO_OWNER = "GOTXE"
REPO_NAME = "youtube-clear-view"
GITHUB_API_TAGS_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/tags"
GITHUB_REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}"
CACHE_TTL = timedelta(hours=24)
REQUEST_TIMEOUT_SECONDS = 5
SEMVER_RE = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?$"
)


@dataclass(frozen=True)
class ParsedVersion:
    major: int
    minor: int
    patch: int
    pre: tuple[tuple[int, int | str], ...]


_cache_lock = threading.Lock()
_cache_data: dict = {
    "checked_at": None,
    "latest_tag": None,
    "latest_tag_url": None,
    "error": None,
}


def _normalize_tag(tag: str | None) -> str | None:
    if not tag:
        return None
    return tag.strip()


def _parse_pre(pre: str | None) -> tuple[tuple[int, int | str], ...]:
    if not pre:
        return ()
    parts = []
    for token in pre.split("."):
        if token.isdigit():
            parts.append((0, int(token)))
        else:
            parts.append((1, token.lower()))
    return tuple(parts)


def _parse_version(value: str | None) -> ParsedVersion | None:
    if not value:
        return None
    match = SEMVER_RE.match(value.strip())
    if not match:
        return None
    return ParsedVersion(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        pre=_parse_pre(match.group("pre")),
    )


def _is_newer(a: ParsedVersion, b: ParsedVersion) -> bool:
    if (a.major, a.minor, a.patch) != (b.major, b.minor, b.patch):
        return (a.major, a.minor, a.patch) > (b.major, b.minor, b.patch)
    if not a.pre and b.pre:
        return True
    if a.pre and not b.pre:
        return False
    return a.pre > b.pre


def _build_compare_url(current_tag: str, latest_tag: str) -> str:
    return f"{GITHUB_REPO_URL}/compare/{current_tag}...{latest_tag}"


def _fetch_latest_tag() -> tuple[str | None, str | None]:
    response = requests.get(
        GITHUB_API_TAGS_URL,
        params={"per_page": 100},
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"Accept": "application/vnd.github+json"},
    )
    response.raise_for_status()
    payload = response.json() or []

    best_tag = None
    best_parsed = None
    for entry in payload:
        tag_name = _normalize_tag((entry or {}).get("name"))
        parsed = _parse_version(tag_name)
        if not tag_name or not parsed:
            continue
        if best_parsed is None or _is_newer(parsed, best_parsed):
            best_tag = tag_name
            best_parsed = parsed

    if not best_tag:
        return None, None
    return best_tag, f"{GITHUB_REPO_URL}/releases/tag/{best_tag}"


def _cache_is_stale(now: datetime) -> bool:
    checked_at = _cache_data.get("checked_at")
    if not checked_at:
        return True
    return now - checked_at >= CACHE_TTL


def _ensure_cache_fresh(now: datetime) -> None:
    if not _cache_is_stale(now):
        return

    try:
        latest_tag, latest_tag_url = _fetch_latest_tag()
        _cache_data.update({
            "checked_at": now,
            "latest_tag": latest_tag,
            "latest_tag_url": latest_tag_url,
            "error": None,
        })
    except Exception as exc:  # pragma: no cover - defensive runtime behavior
        _cache_data.update({
            "checked_at": now,
            "error": str(exc),
        })


def get_version_status(current_version: str | None) -> dict:
    """Return current vs latest version information from GitHub tags."""
    now = datetime.now(timezone.utc)
    current_version = _normalize_tag(current_version)
    current_parsed = _parse_version(current_version)

    with _cache_lock:
        _ensure_cache_fresh(now)
        latest_tag = _cache_data.get("latest_tag")
        latest_tag_url = _cache_data.get("latest_tag_url")
        checked_at = _cache_data.get("checked_at")
        fetch_error = _cache_data.get("error")

    latest_parsed = _parse_version(latest_tag)
    update_available = bool(
        current_parsed and latest_parsed and _is_newer(latest_parsed, current_parsed)
    )
    changelog_url = None
    compare_url = None
    if update_available and latest_tag_url:
        changelog_url = latest_tag_url
    if update_available and current_version and latest_tag:
        compare_url = _build_compare_url(current_version, latest_tag)

    return {
        "current_version": current_version,
        "latest_version": latest_tag,
        "latest_version_url": latest_tag_url,
        "changelog_url": changelog_url,
        "compare_url": compare_url,
        "update_available": update_available,
        "checked_at": checked_at.isoformat() if checked_at else None,
        "check_error": fetch_error,
    }
