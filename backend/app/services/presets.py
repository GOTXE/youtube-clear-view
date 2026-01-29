"""Preset definitions for refresh limits."""

PRESETS = {
    "minimal": {
        "recent_days": 7,
        "older_min_days": 8,
        "older_max_days": 30,
        "recent_video_cap": 1,
        "recent_short_cap": 1,
        "older_video_cap": 2,
        "older_short_cap": 2,
    },
    "standard": {
        "recent_days": 7,
        "older_min_days": 8,
        "older_max_days": 30,
        "recent_video_cap": 2,
        "recent_short_cap": 2,
        "older_video_cap": 3,
        "older_short_cap": 3,
    },
    "rich": {
        "recent_days": 7,
        "older_min_days": 8,
        "older_max_days": 30,
        "recent_video_cap": 3,
        "recent_short_cap": 3,
        "older_video_cap": 4,
        "older_short_cap": 4,
    },
}

DEFAULT_PRESET = "standard"


def get_preset(name):
    """Return preset limits or the default."""
    return PRESETS.get(name, PRESETS[DEFAULT_PRESET])
