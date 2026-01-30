# Architecture

## Overview

YT Clear View (YTCV) is a small self-hosted stack for browsing subscribed channels with less noise.
It is designed to run on a PC/NAS as a server, and be consumed from multiple clients (PC, mobile, TV)
over LAN or via an HTTPS reverse proxy.

The system is composed of:

1. **Frontend**: static HTML/CSS/JS (vanilla).
2. **Backend API**: Flask service with SQLite persistence and YT Data API integration.
3. **Log Viewer (optional)**: separate Flask service for viewing log files.

## Deployment Topologies

### Topology A: Same-origin (recommended)

One hostname serves everything. This avoids most CORS and cookie pitfalls (especially on TVs).

```
[Browser/TV]
    | HTTPS
    v
[Reverse Proxy]
    | /      -> Frontend static
    | /api   -> Backend API (:5550)
    | /logs  -> Log Viewer (:5551)  (optional)
```

### Topology B: Split-host (advanced)

Frontend and API live on different hostnames. This requires strict CORS and cookie configuration.

```
[Browser/TV] --HTTPS--> [Frontend host] (static)
[Browser/TV] --HTTPS--> [API host]      (/api -> backend)
```

## Components

### Frontend
- Vanilla HTML/CSS/JS.
- Uses **httpOnly cookie sessions** (no tokens stored in JS).
- Supports local auth or Google OAuth (depending on `AUTH_MODE`).
- UI features: subscriptions sidebar, video/shorts/older carousels, filters, i18n (EN/ES), and category tools.

### Backend API
- Flask app factory (`create_app`) with modular blueprints.
- SQLAlchemy + SQLite for persistence.
- YT Data API integration:
  - Import subscriptions (OAuth).
  - Refresh videos with per-channel caps via presets.
  - Optional scheduler/backfill to keep content up-to-date while respecting quota.
- Server-side thumbnail caching:
  - Thumbnails are served via `/api/channels/<id>/thumbnail`.
  - Cache is stored on disk and refreshed periodically (configurable).
- Centralized error handling with tracking IDs.
- SQLite tuning to reduce lock contention (WAL + busy timeout).

### Log Viewer (optional)
- Separate Flask app reading backend log files.
- HTTP Basic Auth for access control.
- UI supports severity filters and auto-refresh of entries and recent errors.

## Data Model (high level)

- `users`: user accounts + OAuth credentials metadata.
- `channels`: global channel catalog (shared between users).
- `user_channels`: user subscriptions and per-user metadata:
  - `subscribed_at`, `last_refreshed_at`, `last_checked_at`
  - optional `rating` and `rated_at`
- `videos`: stored videos for subscribed channels (bounded by caps + date windows).
- `watched_videos`: per-user watched markers.
- `categories` + `channel_categories`: automatic classification + manual overrides.
- `themes` + `theme_channels`: legacy/custom themes (may coexist with categories).
- `user_settings`: per-user presets, schedule hours, and quota tracking.

## Key Data Flows

1. **Login**
   - Local: `POST /api/auth/login`
   - OAuth: `GET /api/auth/google` -> callback -> session cookie
2. **Import subscriptions (OAuth)**
   - `POST /api/channels/import` (paged)
3. **Refresh**
   - Manual: `POST /api/channels/refresh`
   - Scheduled/backfill: driven by `GET/PUT /api/settings` + server scheduler
4. **Browsing**
   - Carousels: `GET /api/videos/latest` with query params (`content_type`, `since_days`, `older_than_days`, `randomize`, etc.)
   - Mark watched: `POST /api/videos/<id>/watch` / `DELETE /api/videos/<id>/unwatch`
5. **Categories**
   - View: `GET /api/categories` + `GET /api/categories/<id>/videos`
   - Manual override: `PUT /api/channels/<id>/category`

## Technology Stack

- **Backend**: Python 3.11+, Flask, SQLAlchemy, Gunicorn
- **Frontend**: Vanilla HTML/CSS/JS
- **Database**: SQLite (WAL enabled)
- **Infra**: Reverse proxy (Synology or Nginx/Caddy), optional Docker

## Security Notes

- HTTPS is expected in production (reverse proxy terminates TLS).
- Authentication uses secure, httpOnly cookies.
- CORS must be explicitly configured (Topology B), and should match the exact `FRONTEND_URL`.
- Error responses return a generic message plus a tracking ID (no stack traces).

## Logging

- Rotating file logs with tracking IDs.
- Log viewer reads the shared log file path (mounted or shared directory).
