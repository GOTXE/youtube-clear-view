# API Reference

All endpoints listed below are served by the backend service.

## Base URL

In production, the backend is typically exposed behind an HTTPS reverse proxy.

Recommended (same-origin) setup:

```
https://<your-host>/api
```

Local development example:

```
http://localhost:5550/api
```

## Authentication

Authentication uses httpOnly cookies. The frontend never stores or reads access tokens.

- Session cookie name: `ytcv_session`
- OAuth state cookie name: `ytcv_oauth_state`

Notes:
- Cookies are scoped to the `/api` path.
- `AUTH_MODE` controls which login methods are available (`local` or `google`).
- In Google mode, the backend also remembers browser-known Google accounts in the signed Flask session so the UI can switch accounts without a manual logout.

### Auth modes

`GET /api/auth/provider` returns:

```json
{
  "auth_mode": "google",
  "google_login_url": "/api/auth/google"
}
```

When `AUTH_MODE=google`, local-only endpoints such as `POST /api/auth/login` return `403`.

## Error response format

```json
{
  "error": "Bad request.",
  "tracking_id": "ERR-YYYYMMDD-ABC123",
  "status": 400
}
```

## Pagination format (videos)

Endpoints that return lists of videos respond with:

```json
{
  "videos": [
    {
      "video": { "id": 1, "yt_video_id": "abc" },
      "channel": { "id": 1, "title": "Channel" },
      "watched": false
    }
  ],
  "has_more": true,
  "next_offset": 20
}
```

---

## Health

### GET /api/health

Returns a basic health status for monitoring.

Response:

```json
{ "status": "ok" }
```

---

## Authentication

### POST /api/auth/login

Local login (only when `AUTH_MODE=local`).

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
  "auth_provider": "local",
  "email": null,
  "google_avatar_url": null,
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

Returns all users for the local login selector (only when `AUTH_MODE=local`).

Response:

```json
[
  { "id": 1, "username": "alice", "display_name": "Alice" }
]
```

### GET /api/auth/current

Returns the authenticated user's profile, or `authenticated: false` if no session exists.

Response (authenticated):

```json
{
  "authenticated": true,
  "user_id": 1,
  "username": "alice",
  "display_name": "Alice",
  "email": "alice@example.com",
  "auth_provider": "google",
  "google_avatar_url": "https://...",
  "theme_preference": "dark"
}
```

Response (no session):

```json
{ "authenticated": false }
```

### GET /api/auth/accounts

Returns the Google accounts already authenticated in this browser session.
Only available when `AUTH_MODE=google`.

Response:

```json
{
  "current_user_id": 1,
  "accounts": [
    {
      "id": 1,
      "username": "alice@gmail.com",
      "display_name": "Alice",
      "email": "alice@gmail.com",
      "auth_provider": "google",
      "google_avatar_url": "https://...",
      "is_current": true
    },
    {
      "id": 2,
      "username": "bob@gmail.com",
      "display_name": "Bob",
      "email": "bob@gmail.com",
      "auth_provider": "google",
      "google_avatar_url": "https://...",
      "is_current": false
    }
  ]
}
```

### POST /api/auth/switch

Switches the active backend session to another Google account already known in this browser.
Only available when `AUTH_MODE=google`.

Request:

```json
{ "user_id": 2 }
```

Response:

```json
{
  "authenticated": true,
  "user_id": 2,
  "username": "bob@gmail.com",
  "display_name": "Bob",
  "email": "bob@gmail.com",
  "auth_provider": "google",
  "google_avatar_url": null,
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

### GET /api/auth/google

Starts the Google OAuth flow (only when `AUTH_MODE=google`).
This endpoint redirects the browser to the consent screen.

### GET /api/auth/google/callback

OAuth callback endpoint. Google redirects here after user consent.
On success, the backend sets a session cookie, remembers that Google account for this browser, and redirects the browser to `FRONTEND_URL`.

If authentication fails, the backend redirects to `FRONTEND_URL` with `?auth_error=<code>`.

---

## Settings (presets, schedule, quota)

### GET /api/settings

Returns the current user's refresh settings, preset definitions, and quota status.

Response (example):

```json
{
  "preset": "standard",
  "schedule_hours": [7, 12, 17, 21],
  "timezone": "Europe/Madrid",
  "backfill_active": false,
  "backfill_cursor": null,
  "last_schedule_run_at": "2026-01-28T18:06:56.357000",
  "quota_date": "2026-01-28",
  "quota_used": 0,
  "quota_cap": 8000,
  "presets": {
    "minimal": { "recent_days": 7, "older_min_days": 7, "older_max_days": 30 },
    "standard": { "recent_days": 7, "older_min_days": 7, "older_max_days": 30 },
    "rich": { "recent_days": 7, "older_min_days": 7, "older_max_days": 30 }
  },
  "quota": {
    "daily_limit": 10000,
    "cap_ratio": 0.8,
    "cap": 8000,
    "used": 0,
    "remaining": 8000
  }
}
```

### PUT /api/settings

Updates preset and schedule settings.

Request fields:
- `preset` (optional): `minimal|standard|rich`
- `schedule_hours` (optional): list of up to 4 values (`0..23` or `null`/`"off"`)
- `timezone` (optional): IANA timezone (e.g., `Europe/Madrid`)
- `start_backfill` (optional, boolean): start a controlled backfill when preset changes
- `run_now` (optional, boolean): run a refresh immediately when schedule/preset changes

Response:
- Returns the updated settings object (same shape as `settings.to_dict()`).

---

## Channels

### GET /api/channels

Returns subscribed channels for the current user, enriched with UI-ready metadata.

Response (example item):

```json
[
  {
    "id": 1,
    "yt_channel_id": "UCxxxxxxxxxxxxxxxx",
    "title": "Example Channel",
    "thumbnail_url": "https://...",
    "thumbnail_local_url": "/api/channels/1/thumbnail",
    "description": "...",
    "subscribed_at": "2026-01-01T00:00:00",
    "last_refreshed_at": "2026-01-28T18:06:29",
    "last_checked_at": "2026-01-28T18:06:29",
    "latest_video_at": "2026-01-28T12:00:00",
    "recent_total_7": 3,
    "recent_unwatched_7": 2,
    "recent_total_30": 10,
    "recent_unwatched_30": 7,
    "unwatched_total": 50,
    "rating": 4,
    "rated_at": "2026-01-10T10:00:00",
    "category": null
  }
]
```

### GET /api/channels/<channel_id>/thumbnail

Returns the cached channel thumbnail (shared across users).
If not cached yet, the server may redirect to the original `thumbnail_url`.

Response:
- `200` image payload, or `302` redirect, or `404` if missing.

### POST /api/channels/subscribe

Subscribes the user to a YT channel.

Request:

```json
{ "yt_channel_id": "UCxxxxxxxxxxxxxxxx" }
```

Response:
- `201` with the created subscription/channel payload.

### DELETE /api/channels/<channel_id>/unsubscribe

Unsubscribes the user from a channel.

Response: `204 No Content`

### POST /api/channels/import

Imports YT subscriptions for the authenticated Google account.
Requires `AUTH_MODE=google` and a valid OAuth session.

Request (optional):

```json
{ "page_token": null, "max_results": 50 }
```

Response:

```json
{
  "imported": 12,
  "new_channels": 10,
  "new_subscriptions": 12,
  "classified": 8,
  "next_page_token": "NEXT",
  "total_results": 120,
  "finished": false
}
```

### POST /api/channels/refresh

Refreshes one subscribed channel or all channels for the current user.

Request (optional):

```json
{ "channel_id": 12, "backfill": false }
```

Response:

```json
{
  "new_videos": 3,
  "refreshed_at": "2026-03-15T01:46:18.221000"
}
```

### GET /api/channels/refresh/stream

Streams refresh progress as Server-Sent Events (SSE). This is intended for the
web client so visible content can update incrementally while the backend keeps
processing channels.

Query params:
- `channel_id` (optional): refresh only one subscribed channel
- `backfill=true` (optional): ignore the last refresh watermark for this run

Response headers:
- `Content-Type: text/event-stream`
- `Cache-Control: no-cache`

Event stream format:

```text
event: refresh
data: {"type":"stream_opened","refreshed_at":"2026-03-15T01:46:18.221000"}

event: refresh
data: {"type":"start","processed_channels":0,"total_channels":12,"new_videos":0}

event: refresh
data: {"type":"channel_started","channel_id":7,"channel_title":"Example","current_channel":1,"total_channels":12}

event: refresh
data: {"type":"channel_complete","channel_id":7,"channel_new_videos":2,"new_videos":2,"processed_channels":1,"total_channels":12,"success":true}

event: refresh
data: {"type":"complete","new_videos":8,"processed_channels":12,"total_channels":12,"rate_limited":false}
```

Notes:
- The backend persists progress per channel, so new videos may become visible
  before the full refresh completes.
- The frontend should treat SSE as the source of refresh progress and use the
  final `complete` event as the end-of-run signal.

### POST /api/channels/refresh

Refreshes videos for one channel or all channels.

Request (optional):

```json
{ "channel_id": 1, "backfill": false }
```

Notes:
- `backfill=true` forces a refresh that ignores `last_refreshed_at` and re-scans within the preset window.

Response:

```json
{ "new_videos": 5, "refreshed_at": "2026-01-28T18:06:56.357000" }
```

### GET /api/channels/<channel_id>/videos

Returns videos for a channel (paginated).

Query params:
- `limit`
- `offset`

Response:

```json
{
  "videos": [{ "video": { "id": 1 }, "watched": false }],
  "has_more": false,
  "next_offset": null
}
```

### GET /api/channels/<channel_id>/category

Returns the category assigned to a channel (if any) plus classification metadata.

### PUT /api/channels/<channel_id>/category

Manually assigns a category to a channel.

Request:
- `category_id` (preferred) or `category_name`

### DELETE /api/channels/<channel_id>/category

Removes manual override and triggers auto-classification.

### PUT /api/channels/<channel_id>/rating

Sets a per-user rating for a channel.

Request:

```json
{ "rating": 1 }
```

Response:

```json
{ "channel_id": 1, "rating": 1, "rated_at": "2026-01-28T18:06:56.357000" }
```

### DELETE /api/channels/<channel_id>/rating

Removes a channel rating for the current user.

### POST /api/channels/enrich

Fetches additional channel metadata from the YT API (topic IDs, keywords, country),
used by automatic classification.

Request (optional):

```json
{ "channel_id": 1, "limit": 50 }
```

Response:

```json
{ "enriched": 10, "errors": 0, "remaining": 200, "message": "Enriched 10 channels with topic data." }
```

### POST /api/channels/enrich-video-evidence

Fetches recent video metadata for subscribed channels and stores it locally so
classification can use stronger evidence than channel snippet text alone.

This endpoint is the practical recovery path for channels that remain
unclassified because `topic_ids` and `keywords` are missing from the YouTube
channel resource.

Request (optional):

```json
{
  "channel_id": 1,
  "limit": 25,
  "max_results": 12,
  "only_unclassified": true
}
```

Response:

```json
{
  "channels_processed": 12,
  "videos_created": 48,
  "videos_updated": 15,
  "classified": 7,
  "errors": 0,
  "remaining_unclassified": 143,
  "message": "Processed 12 channels with recent video evidence."
}
```

---

## Videos

### GET /api/videos/latest

Returns videos from subscribed channels (paginated).

Query params:
- `limit`
- `offset`
- `channel_id` (optional)
- `yt_channel_id` (optional; must match `channel_id` if both are provided)
- `content_type` (optional: `video` or `short`)
- `since_days` (optional: integer)
- `older_than_days` (optional: integer)
- `only_unwatched` (optional: boolean)
- `randomize` (optional: boolean; stable per-day shuffle)

Response: see Pagination format.

### GET /api/videos/by-theme/<theme_id>

Returns videos for channels associated with a theme (paginated).

Query params:
- `limit`
- `offset`
- `content_type` (optional: `video` or `short`)
- `since_days` (optional: integer)
- `older_than_days` (optional: integer)
- `only_unwatched` (optional: boolean)

### GET /api/videos/summary

Returns counts of unwatched videos and shorts in the last N days.

Query params:
- `days` (optional, default 7)
- `channel_id` (optional)
- `yt_channel_id` (optional)

Response:

```json
{ "videos": 45, "shorts": 81, "days": 7 }
```

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

Response: same shape as `GET /api/videos/latest`.

---

## Categories

### GET /api/categories

Returns the category catalog, including how many of the current user's channels are in each category.

### GET /api/categories/<category_id>

Returns a single category (with `channel_count` for the current user).

### GET /api/categories/<category_id>/channels

Returns channels in a category for the current user (paginated).

### GET /api/categories/<category_id>/videos

Returns videos from channels in a category (paginated).

### POST /api/categories/reclassify-all

Triggers a reclassification attempt for all channels of the current user.

### GET /api/categories/status

Returns the status of the active classification methods currently used by the app:

- `youtube_topics`
- `tfidf`

---

## Themes

Themes are user-owned and separate from categories.

### GET /api/themes

Returns themes with associated channels.

### POST /api/themes

Creates a theme.

### PUT /api/themes/<theme_id>

Updates a theme.

### DELETE /api/themes/<theme_id>

Deletes a theme.

### POST /api/themes/<theme_id>/channels

Adds a channel to a theme.

### DELETE /api/themes/<theme_id>/channels/<channel_id>

Removes a channel from a theme.

---

## Devices

### POST /api/devices/register

Registers a device for the current user and updates `last_used_at`.

Response example:

```json
{
  "id": 3,
  "device_type": "tv",
  "device_type_confirmed": true
}
```

### GET /api/devices

Lists registered devices.

### PUT /api/devices/<device_id>/type

Updates device type and marks it as explicitly confirmed for that user/device pair.

### DELETE /api/devices/<device_id>

Deletes a device.

### POST /api/devices/detect

Suggests a device type based on screen size.
