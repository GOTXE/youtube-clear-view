# API Reference

## Base URL

All API endpoints are served under the `/api` prefix via the reverse proxy.

```
https://apiyt.mi-nas.me/api
```

## Authentication

Authentication uses httpOnly cookies. The frontend never stores or reads tokens.

- Cookie name: `ytcv_session`
- Set by `POST /api/auth/login`
- Cleared by `POST /api/auth/logout`

If the cookie is missing or invalid, the API responds with `401 Unauthorized` and a tracking ID.

## Error Response Format

```json
{
  "error": "Bad request.",
  "tracking_id": "ERR-20240101-ABC123",
  "status": 400
}
```

## Pagination Format

Endpoints that return lists of videos respond with:

```json
{
  "videos": [
    {
      "video": { "id": 1, "youtube_video_id": "abc" },
      "channel": { "id": 1, "title": "Channel" },
      "watched": false
    }
  ],
  "has_more": true,
  "next_offset": 20
}
```

## Rate Limiting

The API does not enforce explicit rate limits, but reverse proxies or upstream services may return `429` responses. Clients should retry with exponential backoff.

---

## Health

### GET /api/health

Returns a basic health status for monitoring.

Response:

```json
{
  "status": "ok"
}
```

---

## Authentication

### POST /api/auth/login

Logs in or creates a user and sets a secure cookie.

Request:

```json
{ "username": "alice" }
```

Response:

```json
{
  "user_id": 1,
  "username": "alice",
  "display_name": "alice",
  "theme_preference": "light"
}
```

### POST /api/auth/logout

Clears the session cookie.

Response:

```json
{ "message": "Logged out" }
```

### GET /api/auth/users

Returns all users for the login selector.

Response:

```json
[
  { "id": 1, "username": "alice", "display_name": "Alice" }
]
```

### GET /api/auth/current

Returns the authenticated user's profile.

Response:

```json
{
  "user_id": 1,
  "username": "alice",
  "display_name": "Alice",
  "theme_preference": "dark"
}
```

### PUT /api/auth/profile

Updates display name and theme preference.

Request:

```json
{ "display_name": "Alice", "theme_preference": "dark" }
```

Response:

```json
{
  "user_id": 1,
  "username": "alice",
  "display_name": "Alice",
  "theme_preference": "dark"
}
```

---

## Channels

### GET /api/channels

Returns subscribed channels for the current user.

Response:

```json
[
  {
    "id": 1,
    "youtube_channel_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
    "title": "Google Developers",
    "thumbnail_url": "https://...",
    "description": "...",
    "subscribed_at": "2024-01-01T00:00:00"
  }
]
```

### POST /api/channels/subscribe

Subscribes the user to a YouTube channel.

Request:

```json
{ "youtube_channel_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw" }
```

Response:

```json
{
  "id": 1,
  "youtube_channel_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
  "title": "Google Developers"
}
```

### DELETE /api/channels/<channel_id>/unsubscribe

Unsubscribes the user from a channel.

Response: `204 No Content`

### POST /api/channels/refresh

Refreshes videos for one channel or all channels.

Request (optional):

```json
{ "channel_id": 1 }
```

Response:

```json
{ "new_videos": 5 }
```

### GET /api/channels/<channel_id>/videos

Returns videos for a channel.

Query params:
- `limit`
- `offset`

Response:

```json
{
  "videos": [
    { "video": { "id": 1 }, "watched": false }
  ],
  "has_more": false,
  "next_offset": null
}
```

---

## Videos

### GET /api/videos/latest

Returns latest videos from subscribed channels.

Query params:
- `limit`
- `offset`

Response:

```json
{
  "videos": [
    { "video": { "id": 1, "title": "Video" }, "channel": { "title": "Channel" }, "watched": false }
  ],
  "has_more": true,
  "next_offset": 20
}
```

### GET /api/videos/by-theme/<theme_id>

Returns videos for channels in a theme.

Query params:
- `limit`
- `offset`

Response: Same format as latest videos.

### POST /api/videos/<video_id>/watch

Marks a video as watched.

Request (optional):

```json
{ "device_id": 1 }
```

Response: `204 No Content`

### DELETE /api/videos/<video_id>/unwatch

Removes watched status.

Response: `204 No Content`

### GET /api/videos/search

Searches videos by title/description.

Query params:
- `q` (required)
- `limit`
- `offset`
- `channel_id` (optional)
- `theme_id` (optional)

Response: Same format as latest videos.

---

## Themes

### GET /api/themes

Returns themes with associated channels.

Response:

```json
[
  {
    "id": 1,
    "name": "Education",
    "color": "var(--primary)",
    "channels": [
      { "id": 1, "title": "Channel" }
    ]
  }
]
```

### POST /api/themes

Creates a theme.

Request:

```json
{ "name": "Education", "color": "var(--primary)" }
```

### PUT /api/themes/<theme_id>

Updates a theme.

Request:

```json
{ "name": "Education", "color": "var(--secondary)" }
```

### DELETE /api/themes/<theme_id>

Deletes a theme.

Response: `204 No Content`

### POST /api/themes/<theme_id>/channels

Adds a channel to a theme.

Request:

```json
{ "channel_id": 1 }
```

### DELETE /api/themes/<theme_id>/channels/<channel_id>

Removes a channel from a theme.

Response: `204 No Content`

---

## Devices

### POST /api/devices/register

Registers a device for the current user and updates `last_used_at`.

Request:

```json
{ "device_identifier": "dev-abc", "user_agent": "Mozilla/5.0" }
```

Response:

```json
{ "id": 1, "device_type": "desktop" }
```

### GET /api/devices

Lists registered devices.

Response:

```json
[
  {
    "id": 1,
    "device_identifier": "dev-abc",
    "device_type": "desktop",
    "user_agent": "Mozilla/5.0",
    "last_used_at": "2024-01-01T00:00:00",
    "created_at": "2024-01-01T00:00:00"
  }
]
```

### POST /api/devices/detect

Suggests a device type based on screen size.

Request:

```json
{ "screen_width": 1920, "screen_height": 1080 }
```

Response:

```json
{ "suggested_type": "tv", "confidence": 0.9 }
```

### PUT /api/devices/<device_id>/type

Updates device type.

Request:

```json
{ "device_type": "tv" }
```

### DELETE /api/devices/<device_id>

Deletes a device.

Response: `204 No Content`
