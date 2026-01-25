"""Seed the database with sample data."""

from datetime import datetime, timedelta

from app.extensions import db
from app.models import Channel, Theme, ThemeChannel, User, UserChannel, Video, WatchedVideo


CHANNEL_SEEDS = [
    {"id": "UC_x5XG1OV2P6uZZ5FSM9Ttw", "title": "Google Developers"},
    {"id": "UCYO_jab_esuFRV4b17AJtAw", "title": "3Blue1Brown"},
    {"id": "UCBR8-60-B28hp2BmDPdntcQ", "title": "YouTube Spotlight"},
]

THEME_SEEDS = [
    {"name": "Education", "color": "var(--primary)"},
    {"name": "Science", "color": "var(--secondary)"},
]


def get_or_create_user(username, display_name=None):
    user = User.query.filter_by(username=username).first()
    if user:
        return user

    user = User(username=username, display_name=display_name or username)
    db.session.add(user)
    db.session.flush()
    return user


def get_or_create_channel(channel_id, title):
    channel = Channel.query.filter_by(youtube_channel_id=channel_id).first()
    if channel:
        return channel

    channel = Channel(
        youtube_channel_id=channel_id,
        title=title,
        description="Seeded channel",
        thumbnail_url="https://img.youtube.com/vi/placeholder/hqdefault.jpg",
    )
    db.session.add(channel)
    db.session.flush()
    return channel


def get_or_create_theme(user_id, name, color):
    theme = Theme.query.filter_by(user_id=user_id, name=name).first()
    if theme:
        return theme

    theme = Theme(user_id=user_id, name=name, color=color)
    db.session.add(theme)
    db.session.flush()
    return theme


def ensure_subscription(user_id, channel_id):
    link = UserChannel.query.filter_by(user_id=user_id, channel_id=channel_id).first()
    if link:
        return link

    link = UserChannel(user_id=user_id, channel_id=channel_id)
    db.session.add(link)
    db.session.flush()
    return link


def ensure_theme_channel(theme_id, channel_id):
    link = ThemeChannel.query.filter_by(theme_id=theme_id, channel_id=channel_id).first()
    if link:
        return link

    link = ThemeChannel(theme_id=theme_id, channel_id=channel_id)
    db.session.add(link)
    db.session.flush()
    return link


def ensure_video(channel_id, youtube_video_id, title, published_at, duration=120):
    video = Video.query.filter_by(youtube_video_id=youtube_video_id).first()
    if video:
        return video

    video = Video(
        youtube_video_id=youtube_video_id,
        channel_id=channel_id,
        title=title,
        description="Seeded video",
        thumbnail_url=f"https://img.youtube.com/vi/{youtube_video_id}/hqdefault.jpg",
        published_at=published_at,
        duration=duration,
    )
    db.session.add(video)
    db.session.flush()
    return video


def ensure_watched(user_id, video_id):
    watched = WatchedVideo.query.filter_by(user_id=user_id, video_id=video_id).first()
    if watched:
        return watched

    watched = WatchedVideo(user_id=user_id, video_id=video_id)
    db.session.add(watched)
    db.session.flush()
    return watched


def seed_in_app():
    """Seed the database using the current app context."""
    db.create_all()

    user1 = get_or_create_user("user1", "User One")
    user2 = get_or_create_user("user2", "User Two")

    channels = []
    for entry in CHANNEL_SEEDS:
        channels.append(get_or_create_channel(entry["id"], entry["title"]))

    for channel in channels:
        ensure_subscription(user1.id, channel.id)
        ensure_subscription(user2.id, channel.id)

    themes = []
    for entry in THEME_SEEDS:
        themes.append(get_or_create_theme(user1.id, entry["name"], entry["color"]))

    for idx, theme in enumerate(themes):
        channel = channels[idx % len(channels)]
        ensure_theme_channel(theme.id, channel.id)

    now = datetime.utcnow()
    videos = []
    for index, channel in enumerate(channels):
        for offset in range(2):
            video_id = f"seed-{index}-{offset}"
            title = f"Seed Video {index}-{offset}"
            published_at = now - timedelta(days=offset + index)
            videos.append(ensure_video(channel.id, video_id, title, published_at, 90 + offset * 30))

    if videos:
        ensure_watched(user1.id, videos[0].id)
        ensure_watched(user1.id, videos[-1].id)

    db.session.commit()

    return {
        "status": "ok",
        "users": User.query.count(),
        "channels": Channel.query.count(),
        "themes": Theme.query.count(),
        "videos": Video.query.count(),
    }


def seed():
    from app import create_app

    app = create_app()
    with app.app_context():
        summary = seed_in_app()
        print("Seed data created successfully.")
        print(summary)


if __name__ == "__main__":
    seed()
