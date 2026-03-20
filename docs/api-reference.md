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
- When the browser supports WebAuthn and the user has registered at least one passkey, the frontend can also start a recurring sign-in flow with `POST /api/auth/passkeys/authenticate/options` and `POST /api/auth/passkeys/authenticate/verify`.
- Authenticated users can manage passkeys and TOTP enrollment from the hamburger menu in the web UI.
- Newly issued sessions are stored in the database as a hash of the cookie token, not the raw token.
- Stored Google access tokens, refresh tokens, and OAuth scopes are encrypted at rest.

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
      "watched": false,
      "progress": 120
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

## Admin Observability

These endpoints are admin-only and require the authenticated user's username or email
to be present in `ADMIN_USERNAMES`.

### GET /api/admin/observability/sqlite

Returns process-local SQLite observability metrics.

Response example:

```json
{
  "enabled": false,
  "slow_write_threshold_ms": 100,
  "write_count": 12,
  "write_time_ms_total": 45.3,
  "write_time_ms_avg": 3.78,
  "write_time_ms_max": 12.4,
  "slow_write_count": 0,
  "lock_error_count": 0,
  "recent_writes": [],
  "active_manual_refreshes": {
    "1": {
      "scope": { "type": "all_channels", "channel_id": null },
      "started_at": "2026-03-16T23:50:00"
    }
  }
}
```

### PUT /api/admin/observability/sqlite

Enables or disables detailed SQLite metrics capture at runtime.

Request:

```json
{ "enabled": true }
```

Response:

Returns the same payload shape as `GET /api/admin/observability/sqlite`.

### GET /api/admin/runtime-state

Returns the admin-visible runtime state for current sessions and registered devices.

Response example:

```json
{
  "users": [
    {
      "id": 1,
      "username": "admin",
      "display_name": "Admin",
      "email": "admin@example.com",
      "auth_provider": "google",
      "google_auth_status": "active",
      "totp_enabled": true,
      "has_active_session": true,
      "session_created_at": "2026-03-17T12:40:00",
      "device_count": 1,
      "devices": [
        {
          "id": 7,
          "device_identifier": "dev-admin",
          "device_type": "tv",
          "frontend_mode": "tv",
          "tv_scale": "XL"
        }
      ]
    }
  ]
}
```

---

## Authentication

### POST /api/auth/register

Creates a new local user account with username and password.

Rate-limited per IP address.

Request:

```json
{
  "username": "alice",
  "password": "secret123",
  "display_name": "Alice"
}
```

- `username` (required): 3-64 characters
- `password` (required): minimum 8 characters
- `display_name` (optional): defaults to `username`

Response (`201`):

```json
{
  "authenticated": true,
  "user_id": 1,
  "username": "alice",
  "display_name": "Alice",
  "auth_provider": "local",
  "email": null,
  "google_avatar_url": null,
  "google_auth_status": "not_linked",
  "totp_enabled": false,
  "theme_preference": "light"
}
```

Error responses:
- `400` if username or password requirements are not met
- `409` if the username is already taken
- `429` if rate limit is exceeded

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
  "google_auth_status": "not_linked",
  "totp_enabled": false,
  "theme_preference": "light"
}
```

### POST /api/auth/fallback-login

Recurring login fallback for returning users.

Accepts a username or email plus either:
- a current TOTP code
- a recovery code

Request:

```json
{
  "identifier": "alice@example.com",
  "method": "totp",
  "code": "123456"
}
```

`method` can be `totp` or `recovery_code`.

Success response:

```json
{
  "authenticated": true,
  "user_id": 1,
  "username": "alice@example.com",
  "display_name": "Alice",
  "email": "alice@example.com",
  "auth_provider": "google",
  "google_auth_status": "active",
  "totp_enabled": true
}
```

Failure response:

```json
{
  "error": "Unauthorized.",
  "tracking_id": "ERR-20260317-XXXXXX",
  "status": 401
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
  "google_auth_status": "active",
  "totp_enabled": true,
  "is_admin": false,
  "theme_preference": "dark"
}
```

Response (no session):

```json
{ "authenticated": false }
```

Response (pending MFA challenge):

```json
{
  "authenticated": false,
  "mfa_required": true,
  "user_id": 2,
  "display_name": "Bob",
  "email": "bob@example.com",
  "auth_provider": "google",
  "available_methods": ["totp", "recovery_code"]
}
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
      "google_auth_status": "active",
      "is_current": true
    },
    {
      "id": 2,
      "username": "bob@gmail.com",
      "display_name": "Bob",
      "email": "bob@gmail.com",
      "auth_provider": "google",
      "google_avatar_url": "https://...",
      "google_auth_status": "active",
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
  "google_auth_status": "active",
  "totp_enabled": true,
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

### POST /api/auth/profile/password

Requires an authenticated session.

Changes the password for the current user.

Request:

```json
{
  "current_password": "old-pass",
  "new_password": "new-pass-123"
}
```

- `current_password` (required if the user already has a password set)
- `new_password` (required): validated against the active password policy selected by the site admin (`simple`, `strong`, or `unbreakable`)

Response:

```json
{ "message": "Password updated." }
```

If the user has not yet set a password, `current_password` can be omitted.
Setting a password also marks `setup_completed = true` if it was previously false.

### GET /api/auth/google

Starts the Google OAuth flow (only when `AUTH_MODE=google`).
This endpoint redirects the browser to the consent screen.

### GET /api/auth/google/link

Requires an authenticated session.

Starts the Google OAuth flow with a "link" intent, allowing the current user to
attach YouTube/Google credentials to their existing account. Redirects the
browser to the Google consent screen.

On callback, the backend stores OAuth tokens against the authenticated user
instead of creating a new account.

This endpoint is intentionally kept for development, migration, and recovery
scenarios even when the main public sign-up flow is Google-first.

### GET /api/auth/google/callback

OAuth callback endpoint. Google redirects here after user consent.
On success, the backend sets a session cookie, remembers that Google account for this browser, and redirects the browser to `FRONTEND_URL`.

If authentication fails, the backend redirects to `FRONTEND_URL` with `?auth_error=<code>`.

### POST /api/auth/google/complete-setup

Requires an authenticated session.

Completes first-time setup for a user who registered via Google OAuth. Allows
the user to choose a custom username and set the local password required for
later LAN or fallback logins.

Request:

```json
{
  "username": "alice",
  "password": "correct-horse-battery-staple"
}
```

- `username` (required): 3-64 characters, must be unique, and may contain only letters, numbers, `.`, `_`, or `-`
- `password` (required): validated against the active site-wide password policy

Response:

```json
{
  "authenticated": true,
  "setup_completed": true,
  "user_id": 1,
  "username": "alice",
  "display_name": "Alice",
  "email": "alice@example.com",
  "auth_provider": "google",
  "google_avatar_url": "https://...",
  "google_auth_status": "active",
  "totp_enabled": false,
  "theme_preference": "light",
  "has_password": true,
  "username_suggestion": "alice"
}
```

### GET /api/admin/security/password-policy

Requires an authenticated admin session.

Returns the active global password policy and the allowed options.

Response:

```json
{
  "password_policy": "strong",
  "options": [
    { "value": "simple", "label": "Simple" },
    { "value": "strong", "label": "Strong" },
    { "value": "unbreakable", "label": "Unbreakable" }
  ]
}
```

### PUT /api/admin/security/password-policy

Requires an authenticated admin session.

Updates the global password policy used by:
- local registration when enabled
- post-Google account setup
- password changes

Request:

```json
{
  "password_policy": "unbreakable"
}
```

### POST /api/auth/google/unlink

Requires an authenticated Google session.

Clears stored Google OAuth credentials for the current user and marks the link as revoked.

Response:

```json
{
  "user_id": 1,
  "auth_provider": "google",
  "google_auth_status": "revoked"
}
```

### POST /api/auth/mfa/verify

Completes a pending MFA challenge created after primary auth for a user with TOTP enabled.

Request:

```json
{
  "method": "totp",
  "code": "123456"
}
```

`method` can be `totp` or `recovery_code`.

Response:

```json
{
  "authenticated": true,
  "user_id": 2,
  "username": "bob@example.com",
  "display_name": "Bob",
  "email": "bob@example.com",
  "auth_provider": "google",
  "google_avatar_url": null,
  "google_auth_status": "active",
  "totp_enabled": true,
  "theme_preference": "dark"
}
```

This endpoint completes the second factor only after a primary auth step has already succeeded.
For direct recurring fallback login, use `POST /api/auth/fallback-login`.

### POST /api/auth/pairing/start

Starts a short-lived pairing request for a secondary device.

Request:

```json
{
  "device_identifier": "living-room-tv"
}
```

Response:

```json
{
  "status": "pending",
  "public_id": "b8J6x4...",
  "pairing_code": "ABCD-EFGH",
  "expires_at": "2026-03-17T11:05:00"
}
```

### POST /api/auth/pairing/approve

Requires an authenticated session.

Approves a pairing code for the current user.

Request:

```json
{
  "code": "ABCD-EFGH"
}
```

Response:

```json
{
  "status": "approved",
  "public_id": "b8J6x4...",
  "pairing_code": "ABCD-EFGH",
  "expires_at": "2026-03-17T11:05:00",
  "approved_at": "2026-03-17T10:58:00",
  "used_at": null
}
```

### POST /api/auth/pairing/claim

Claims a pairing request from the original device.

- If the request is still waiting for approval, the endpoint returns `status: pending`.
- If approved and unused, it issues a normal backend session cookie and returns the authenticated user payload.

Request:

```json
{
  "public_id": "b8J6x4..."
}
```

### GET /api/auth/passkeys

Requires an authenticated session.

Response:

```json
{
  "passkeys": [
    {
      "id": 1,
      "label": "MacBook Pro",
      "credential_id": "base64url-credential-id",
      "transports": ["internal"],
      "aaguid": "00000000-0000-0000-0000-000000000000",
      "credential_device_type": "single_device",
      "credential_backed_up": false,
      "last_used_at": "2026-03-17T10:08:00.000000",
      "created_at": "2026-03-17T10:05:00.000000",
      "updated_at": "2026-03-17T10:08:00.000000"
    }
  ]
}
```

### POST /api/auth/passkeys/register/options

Requires an authenticated session.

Starts passkey registration for the current user and returns WebAuthn creation options.

Request:

```json
{ "label": "MacBook Pro" }
```

Response:

```json
{
  "publicKey": {
    "challenge": "...",
    "rp": { "name": "YT Clear View", "id": "localhost" },
    "user": { "name": "alice@example.com", "displayName": "Alice", "id": "MQ" }
  }
}
```

### POST /api/auth/passkeys/register/verify

Requires an authenticated session.

Verifies the browser registration response and persists the passkey.

Request:

```json
{
  "credential": {
    "id": "base64url-credential-id",
    "rawId": "base64url-credential-id",
    "response": {
      "clientDataJSON": "...",
      "attestationObject": "..."
    },
    "type": "public-key"
  },
  "label": "MacBook Pro",
  "transports": ["internal"]
}
```

Response:

```json
{
  "passkey": {
    "id": 1,
    "label": "MacBook Pro",
    "credential_id": "base64url-credential-id"
  }
}
```

### DELETE /api/auth/passkeys/<id>

Requires an authenticated session.

Deletes one passkey owned by the current user.

Response:

```json
{
  "deleted": true,
  "passkey_id": 1
}
```

### POST /api/auth/passkeys/authenticate/options

Public endpoint.

Returns WebAuthn request options for a discoverable passkey authentication ceremony.

Response:

```json
{
  "publicKey": {
    "challenge": "...",
    "rpId": "localhost",
    "userVerification": "preferred"
  }
}
```

### POST /api/auth/passkeys/authenticate/verify

Public endpoint.

Verifies a passkey assertion, creates a backend session, and returns the authenticated user payload.

Request:

```json
{
  "credential": {
    "id": "base64url-credential-id",
    "rawId": "base64url-credential-id",
    "response": {
      "authenticatorData": "...",
      "clientDataJSON": "...",
      "signature": "...",
      "userHandle": "..."
    },
    "type": "public-key"
  }
}
```

Response:

```json
{
  "authenticated": true,
  "user_id": 1,
  "username": "alice",
  "display_name": "Alice",
  "email": "alice@example.com",
  "auth_provider": "google",
  "google_auth_status": "active",
  "totp_enabled": true,
  "theme_preference": "dark"
}
```

### GET /api/auth/mfa/status

Requires an authenticated session.

Response:

```json
{
  "totp_enabled": true,
  "totp_pending": false,
  "recovery_codes_remaining": 8
}
```

### POST /api/auth/totp/setup

Requires an authenticated session.

Creates a pending TOTP secret for the current user.

Response:

```json
{
  "secret": "JBSWY3DPEHPK3PXP...",
  "otpauth_url": "otpauth://totp/YT%20Clear%20View:alice%40example.com?secret=...",
  "qr_code": "data:image/svg+xml;base64,..."
}
```

`qr_code` is a base64-encoded SVG data URL suitable for rendering in an `<img>` tag.
It may be `null` if the server-side QR generation library is unavailable.

### POST /api/auth/totp/confirm

Requires an authenticated session.

Request:

```json
{ "code": "123456" }
```

Response:

```json
{
  "totp_enabled": true,
  "recovery_codes": ["ABCD-EFGH", "JKMN-PQRS"]
}
```

### DELETE /api/auth/totp

Requires an authenticated session with TOTP enabled.

Disables TOTP for the current user and removes all recovery codes.
Requires either a valid TOTP code or the user's password for confirmation.

Request:

```json
{ "code": "123456" }
```

or:

```json
{ "password": "user-password" }
```

Response:

```json
{ "totp_enabled": false }
```

### POST /api/auth/recovery-codes/regenerate

Requires an authenticated session with TOTP enabled.

Request:

```json
{ "code": "123456" }
```

Response:

```json
{
  "recovery_codes": ["ABCD-EFGH", "JKMN-PQRS"]
}
```

### POST /api/auth/recovery-codes/consume

Requires an authenticated session.

Request:

```json
{ "code": "ABCD-EFGH" }
```

Response:

```json
{
  "accepted": true,
  "recovery_codes_remaining": 7
}
```

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
Manual refresh is governed by the backend:
- full-library refresh has a stricter cooldown
- channel refresh has a lighter cooldown
- only one manual refresh may be active per user at a time

Request (optional):

```json
{ "channel_id": 12, "backfill": false }
```

Response:

```json
{
  "status": "accepted",
  "scope": { "type": "channel", "channel_id": 12 },
  "new_videos": 3,
  "refreshed_at": "2026-03-15T01:46:18.221000"
}
```

Blocked response example:

```json
{
  "error": "Refresh cooldown active.",
  "status": 429,
  "blocked": true,
  "reason": "cooldown_active",
  "scope": { "type": "channel", "channel_id": 12 },
  "cooldown_seconds": 1800,
  "last_activity_at": "2026-03-16T22:00:00",
  "next_allowed_at": "2026-03-16T22:30:00",
  "retry_after_seconds": 900
}
```

Another blocked response reason is `refresh_in_progress`, which returns `409`
with the active scope metadata.

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

Blocked event example:

```text
event: refresh
data: {"type":"blocked","reason":"cooldown_active","scope":{"type":"all_channels","channel_id":null},"retry_after_seconds":900}
```

Notes:
- The backend persists progress per channel, so new videos may become visible
  before the full refresh completes.
- The frontend should treat SSE as the source of refresh progress and use the
  final `complete` or `blocked` event as the end-of-run signal.
- `backfill=true` forces a refresh that ignores `last_refreshed_at` and re-scans within the preset window.

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

### PUT /api/videos/<video_id>/progress

Saves playback position for resume functionality (upsert).

Request:
```json
{ "position_seconds": 120, "duration_seconds": 600 }
```

- `position_seconds` (required, integer >= 0)
- `duration_seconds` (optional, integer > 0)

Response: `204 No Content`

### DELETE /api/videos/<video_id>/progress

Clears saved playback position.

Response: `204 No Content`

Notes:
- Marking a video as watched (`POST .../watch`) automatically clears any saved progress.
- Video listings include a `progress` field (integer, seconds) when a saved position exists.

### GET /api/videos/in-progress

Requires an authenticated session.

Returns videos with saved playback progress for the current user, ordered by
most recently updated first.

Query params:
- `limit` (optional, default 20, max 100)
- `offset` (optional, default 0)

Response: see Pagination format. Each entry includes a `progress` field with the
saved position in seconds.

### GET /api/videos/watched

Requires an authenticated session.

Returns watched videos for the current user, ordered by most recently watched first.

Query params:
- `limit` (optional, default 20)
- `offset` (optional, default 0)
- `channel_id` (optional)
- `yt_channel_id` (optional)
- `content_type` (optional: `video` or `short`)

Response: same shape as `GET /api/videos/latest`.

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
  "device_identifier": "dev-abc123",
  "display_name": "📺 TV salón",
  "device_type": "tv",
  "device_type_confirmed": true,
  "frontend_mode": "tv",
  "tv_scale": "XL",
  "screen_size_inches": 55,
  "viewing_distance_m": 2.8
}
```

### GET /api/devices

Lists registered devices.

Notes:
- Each device now exposes a user-facing `display_name`.
- New devices receive an automatic friendly name derived from `device_type`, such as `📺 TV`, `🖥️ Pantalla PC`, `📟 Tablet`, or `📱 Móvil`.
- Existing devices without a stored `display_name` are backfilled automatically when listed or re-registered.

### PUT /api/devices/<device_id>/type

Updates device type and marks it as explicitly confirmed for that user/device pair.

If the current `display_name` was auto-generated, it is refreshed to match the new type.

### PUT /api/devices/<device_id>/name

Updates the friendly device name shown in the account panel.

Request example:

```json
{ "display_name": "📺 TV salón" }
```

Rules:
- `display_name` is required
- maximum length: `128`

### PUT /api/devices/<device_id>/preferences

Updates frontend mode and TV calibration preferences for the current user's device.

Response example:

```json
{
  "id": 7,
  "device_identifier": "dev-123",
  "device_type": "tv",
  "device_type_confirmed": true,
  "frontend_mode": "tv",
  "tv_scale": "XL",
  "tv_scale_confirmed_at": "2026-03-17T12:30:00",
  "screen_size_inches": 55,
  "viewing_distance_m": 2.8
}
```

Updates persisted frontend display preferences for the current user/device pair.

Request example:

```json
{
  "frontend_mode": "tv",
  "tv_scale": "XL",
  "screen_size_inches": 55,
  "viewing_distance_m": 2.8
}
```

Rules:
- `frontend_mode` must be one of `phone`, `desktop_tablet`, `tv`
- `tv_scale` must be one of `M`, `L`, `XL`, `XXL`
- `screen_size_inches` is optional and must be between `20` and `150`
- `viewing_distance_m` is optional and must be greater than `0` and at most `20`

Response example:

```json
{
  "id": 3,
  "device_identifier": "dev-abc123",
  "display_name": "📺 TV salón",
  "device_type": "tv",
  "device_type_confirmed": true,
  "frontend_mode": "tv",
  "tv_scale": "XL",
  "screen_size_inches": 55,
  "viewing_distance_m": 2.8,
  "user_agent": "Mozilla/5.0 ...",
  "last_used_at": "2026-03-16T22:00:00",
  "created_at": "2026-03-16T20:00:00"
}
```

### DELETE /api/devices/<device_id>

Deletes a device.

### POST /api/devices/detect

Suggests a device type based on screen size.
