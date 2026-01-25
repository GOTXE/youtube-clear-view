# Architecture

## Overview

YT Clear View is split into three services that communicate via HTTPS through a reverse proxy:

1. **Frontend**: static HTML/CSS/JS served from Synology Web Station.
2. **Backend API**: Flask microservice with SQLite and YT Data API integration.
3. **Log Viewer**: separate Flask microservice for viewing log files.

## Text-Based Architecture Diagram

```
[Browser]
   | HTTPS
   v
[Reverse Proxy]
   | /api  -> Backend API (Gunicorn :5550)
   | /logs -> Log Viewer (Gunicorn :5551)
   v
[Synology Web Station]
   | serves /volume1/web/yt-clear-view/
```

## Components

### Frontend
- Vanilla HTML/CSS/JS.
- Authentication via httpOnly cookies (no tokens stored in JS), with local or Google OAuth login.
- Device detection, theme switching, infinite carousels.

### Backend API
- Flask app factory, modular blueprints.
- SQLAlchemy + SQLite for persistence.
- YT Data API v3 integration with caching.
- Centralized error handling with tracking IDs.

### Log Viewer
- Separate Flask app reading backend log files.
- HTTP Basic Auth for access control.

## Data Flow

1. User logs in via `/api/auth/login` (local) or `/api/auth/google` (OAuth).
2. Backend sets a secure cookie (`ytcv_session`).
3. Frontend uses `/api/auth/current` to load user profile.
4. Videos are fetched from `/api/videos/latest` and `/api/videos/by-theme/<id>`.
5. Mark-as-watched operations call `/api/videos/<id>/watch`.

## Technology Stack

- **Backend**: Python 3.11, Flask, SQLAlchemy, Gunicorn
- **Frontend**: Vanilla HTML/CSS/JS
- **Database**: SQLite
- **Infra**: Synology NAS, reverse proxy (Nginx/Synology)

## Security Architecture

- HTTPS enforced by reverse proxy.
- Backend and log viewer ports are internal only.
- Authentication uses secure, httpOnly cookies.
- CORS configured explicitly in `.env`.
- Error responses never expose internal stack traces.

## Logging Architecture

- JSON logs with tracking IDs.
- Rotating file handler to `logs/app.log`.
- Log viewer reads the shared log volume.
