"""RSS feed service tests."""

from app.services.rss_feed import build_feed_url, parse_feed_entries


SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
  <title>YouTube channel feed</title>
  <entry>
    <yt:videoId>abc123</yt:videoId>
    <yt:channelId>chan123</yt:channelId>
    <title>Video One</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc123"/>
    <media:group>
      <media:thumbnail url="https://i.ytimg.com/vi/abc123/hqdefault.jpg" width="480" height="360"/>
    </media:group>
    <author>
      <name>Channel Name</name>
    </author>
    <published>2026-03-21T10:00:00+00:00</published>
    <updated>2026-03-21T10:01:00+00:00</updated>
  </entry>
  <entry>
    <yt:videoId>def456</yt:videoId>
    <yt:channelId>chan123</yt:channelId>
    <title>Video Two</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=def456"/>
    <author>
      <name>Channel Name</name>
    </author>
    <published>2026-03-20T10:00:00+00:00</published>
    <updated>2026-03-20T10:01:00+00:00</updated>
  </entry>
</feed>
"""


def test_build_feed_url():
    assert (
        build_feed_url("UC123")
        == "https://www.youtube.com/feeds/videos.xml?channel_id=UC123"
    )


def test_parse_feed_entries():
    entries = parse_feed_entries(SAMPLE_FEED)

    assert len(entries) == 2
    assert entries[0].video_id == "abc123"
    assert entries[0].channel_id == "chan123"
    assert entries[0].title == "Video One"
    assert entries[0].channel_title == "Channel Name"
    assert entries[0].published_at == "2026-03-21T10:00:00+00:00"
    assert entries[0].updated_at == "2026-03-21T10:01:00+00:00"
    assert entries[0].link == "https://www.youtube.com/watch?v=abc123"
    assert entries[0].thumbnail == "https://i.ytimg.com/vi/abc123/hqdefault.jpg"
