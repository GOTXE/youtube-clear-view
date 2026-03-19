# Repository Guidelines

## Project Overview

YT Clear View (YTCV) is a self-hosted YouTube subscription viewer that removes algorithmic recommendations, providing a chronological feed of videos only from channels you subscribe to.

**Tech Stack:**
- Backend: Flask (Python 3.11+), SQLAlchemy, SQLite (WAL mode)
- Frontend: Vanilla HTML/CSS/JavaScript
- Auth: YouTube Data API v3 (OAuth) or local authentication
- Deployment: Gunicorn + reverse proxy (Nginx/Synology)

## Project Structure & Module Organization

This repository is currently a scaffold/design workspace. The intended target layout is:

- `backend/`: Python (Flask) REST API + SQLite
  - `backend/app/`: app factory (`create_app`), routes, models, services, logging
  - `backend/tests/`: `pytest` suite (`test_*.py`)
- `log_viewer/`: separate Flask microservice for viewing logs
- `frontend/`: vanilla HTML/CSS/JS client (plus `frontend/assets/`)
- `docs/`: public documentation (API, deployment, development)
- `tech_docs/`: private/local notes (gitignored; not synced to GitHub)

## VibeCoding

This repo uses a local overlay in `vibecoding/`.

Before working on code changes:
1. Read `vibecoding/project.yaml`
2. Read `vibecoding/system/docs/ia/00_core/00_index_maestro_ia.spec`
3. Load only the profiles and documents needed for the task

Operational flow:
- use `quick` for small changes
- use `full` for structural or multi-module changes
- persist evidence in `vibecoding/runs/<task-id>/`

Runner:
- `./vibecoding/system/orchestration/runner/vibecoding_runner.sh`

## Docker & Deployment

The app runs locally as 3 Docker containers (proxy/Caddy, backend, log_viewer).
Frontend files are baked into the proxy image — **any frontend change requires rebuilding the proxy container** and bumping `CACHE_VERSION` in `frontend/sw.js`.

Full details: [`docs/deployment.md`](docs/deployment.md)

## Build, Test, and Development Commands

Commands below apply once `backend/` and related modules exist:

- Create venv: `python3 -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r backend/requirements.txt`
- Run tests: `pytest backend/tests -v`
- Run specific test file: `pytest backend/tests/test_auth.py -v`
- Run with markers: `pytest backend/tests -v -m "not slow"`
- Smoke check app factory: `python -c "from app import create_app; create_app(); print('OK')"`
- Run dev server: `cd backend && python -m flask --app app run --port 5550`
- Deployment scripts (NAS): `backend/run_app.sh`, `log_viewer/run_log_viewer.sh`

## Architecture

### Application Structure

**Backend (`backend/app/`):**
- `__init__.py`: App factory using `create_app()` pattern
- `config.py`: Configuration loading from environment variables
- `extensions.py`: Flask extension initialization (SQLAlchemy, CORS)
- `models/`: SQLAlchemy models (User, Channel, Video, Category, Theme, etc.)
- `routes/`: Flask blueprints for API endpoints (auth, channels, videos, categories, themes, devices, settings)
- `services/`: Business logic layer
  - `yt_api.py`: YouTube Data API integration
  - `google_oauth.py`, `yt_oauth.py`: OAuth flow handlers
  - `video_ingest.py`: Video fetch and storage logic
  - `classification_service.py`: Channel classification orchestration
  - `classifiers/`: Multiple classification strategies (TF-IDF, YouTube Topics, Ollama LLM, Hybrid)
  - `scheduler.py`: Automatic refresh scheduling
  - `quota.py`: YouTube API quota tracking
  - `presets.py`: Refresh preset definitions (minimal/standard/rich)
- `middleware/`: Error handling with tracking IDs
- `logging/`: Centralized logging with rotation
- `migrations.py`: Schema migration functions (run on app startup)

**Frontend (`frontend/`):**
- `index.html`: Single-page application
- `js/`: Modular JavaScript (API client, carousels, theme switcher, i18n)
- `css/`: Responsive styling
- `i18n/`: Translations (EN/ES)
- `config.js`: Frontend configuration (API URL)

### Data Model (Key Tables)

- `users`: User accounts + OAuth credentials metadata
- `channels`: Global channel catalog (shared across users)
- `user_channels`: Per-user subscriptions with metadata (`subscribed_at`, `last_refreshed_at`, `rating`)
- `videos`: Videos from subscribed channels (bounded by preset caps)
- `watched_videos`: Per-user watch markers
- `categories` + `channel_categories`: Automatic channel classification + manual overrides
- `themes` + `theme_channels`: User-defined channel groupings
- `user_settings`: Per-user presets, schedule hours, quota tracking
- `devices`: Registered devices for watch sync

### Key Data Flows

1. **Authentication**: OAuth flow (`/api/auth/google` → callback) or local login
2. **Import Subscriptions**: `POST /api/channels/import` (paginated, OAuth required)
3. **Refresh Videos**: `POST /api/channels/refresh` (manual or scheduled)
4. **Browsing**: `GET /api/videos/latest` with filters (content type, date ranges, watched status)
5. **Classification**: Automatic classification via YouTube Topics/TF-IDF/Ollama, manual overrides via `PUT /api/channels/<id>/category`

## Configuration

**Required Environment Variables** (in `backend/.env`):
- `FLASK_SECRET_KEY`: Session encryption key
- `YT_API_KEY`: YouTube Data API key
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: OAuth credentials (if using Google auth)
- `GOOGLE_REDIRECT_URI`: OAuth callback URL
- `FRONTEND_URL`: Frontend origin for CORS
- `AUTH_MODE`: `local` or `google`
- `DATABASE_URI`: SQLite path (default: `sqlite:///yt_clear_view.db`)

**Optional:**
- `SCHEDULER_ENABLED`: Enable automatic refresh scheduler
- `AUTH_TOKEN_ENCRYPTION_KEY`: Fernet key for encrypting stored OAuth tokens (derived from SECRET_KEY if not set)
- `PASSKEY_RP_NAME`, `PASSKEY_RP_ID`, `PASSKEY_ORIGIN`: WebAuthn/passkey configuration
- `ADMIN_USERNAMES`: Comma-separated admin usernames for admin endpoints
- `SQLITE_METRICS_ENABLED`: Enable SQLite write metrics (default: false)
- `MANUAL_REFRESH_FULL_COOLDOWN_SECONDS`: Cooldown between full refreshes (default: 7200)
- `MANUAL_REFRESH_CHANNEL_COOLDOWN_SECONDS`: Per-channel refresh cooldown (default: 1800)

## Coding Style & Naming Conventions

- Write code and comments in English.
- Write pull requests, issue-facing technical summaries, and public developer documentation in English.
- Python: 4-space indentation, PEP 8 naming (`snake_case`, `PascalCase` for classes).
- Frontend: keep JS/CSS readable and modular; prefer descriptive names (e.g., `theme-switcher.js`).
- Configuration: do not hardcode URLs/keys; use `.env` and keep templates in `.env.example`.

## Testing Guidelines

- Use `pytest`; name tests `test_*.py` and keep tests independent.
- Mock external YT API calls; tests must not require real API keys.
- Use fixtures from `conftest.py`.

## Commit & Pull Request Guidelines

- Current commit history is informal (e.g., "inicio", "correccion carpeta"). Going forward, prefer Conventional Commits:
  - `feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, `chore: ...`
- Use `develop` as the main integration branch for ongoing work.
- Target feature PRs to `develop` unless the change is a release/hotfix explicitly meant for `main`.
- PRs should include: purpose, how to test, and screenshots for UI changes. Link related issues when applicable.
- PR text should be written in English.
- Release tags: follow SemVer guidance in `tech_docs/yt-curator-guide.md` (use annotated tags like `v0.X.Y-beta.N` and never retag).

## Adding Features

### New API Endpoint
1. Create route in `backend/app/routes/<module>.py` or add to existing blueprint
2. Register blueprint in `backend/app/routes/__init__.py` (if new)
3. Add tests in `backend/tests/test_<module>.py`
4. Document in `docs/api-reference.md`

### New Database Column
1. Add migration function in `backend/app/migrations.py`
2. Call migration in `create_app()` (within `app_context()`)
3. Update relevant model in `backend/app/models/`
4. Add tests for the new field

### New Service
1. Create module in `backend/app/services/`
2. Import in `backend/app/services/__init__.py`
3. Use dependency injection via `db` and `current_app.config`
4. Mock external dependencies in tests

## Security & Configuration Tips

- Never commit secrets (`.env`, keys, tokens). Follow `.gitignore` and add new sensitive patterns if needed.
- Prefer HTTPS-only assumptions in code and docs (reverse proxy terminates TLS).

## Important Notes

- **Database**: SQLite with WAL mode enabled for better concurrency. Schema migrations run automatically on startup.
- **Authentication**: Uses httpOnly session cookies (no JWT in frontend). OAuth tokens are stored encrypted in the database.
- **YouTube API Quota**: Daily quota is tracked per user. Refresh operations respect `YT_QUOTA_CAP_RATIO` to avoid hitting limits.
- **Classification**: The system can auto-classify channels using YouTube metadata, TF-IDF analysis of descriptions, or an optional Ollama LLM. Manual overrides take precedence.
- **Scheduler**: If enabled, the scheduler runs refresh operations at configured hours and performs controlled backfills.
- **CORS**: In production, frontend and backend should ideally be served from the same origin (via reverse proxy at `/` and `/api` paths) to avoid cookie/CORS issues, especially on smart TVs.
- **Error Handling**: All errors return a tracking ID. Stack traces are logged but not exposed to clients.
- **Testing**: Use `pytest` with fixtures from `conftest.py`. External API calls should be mocked.

## Troubleshooting

- **OAuth errors**: Check `GOOGLE_REDIRECT_URI` matches the configured callback in Google Cloud Console
- **Quota exceeded**: Review `user_settings.quota_used` and adjust `schedule_hours` or preset
- **Lock errors**: SQLite busy timeout is configured; concurrent writes are handled via WAL mode
- **Classification not working**: Verify `CLASSIFICATION_METHOD` is set and required data is enriched (`POST /api/channels/enrich`)
