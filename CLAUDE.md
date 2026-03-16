# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YT Clear View (YTCV) is a self-hosted YouTube subscription viewer that removes algorithmic recommendations, providing a chronological feed of videos only from channels you subscribe to.

**Tech Stack:**
- Backend: Flask (Python 3.11+), SQLAlchemy, SQLite (WAL mode)
- Frontend: Vanilla HTML/CSS/JavaScript
- Auth: YouTube Data API v3 (OAuth) or local authentication
- Deployment: Gunicorn + reverse proxy (Nginx/Synology)

## Repository Conventions

- Write code, comments, PR text, and developer-facing documentation in English.
- Use `develop` as the main integration branch.
- Target feature branches and PRs to `develop` unless the change is an explicit release or hotfix for `main`.

## VibeCoding

This repo uses a local overlay in `vibecoding/`.

Before working on code changes:
1. Read `vibecoding/project.yaml`
2. Read `vibecoding/docs/ia/00_core/00_index_maestro_ia.spec`
3. Load only the profiles and documents needed for the task

Operational flow:
- use `quick` for small changes
- use `full` for structural or multi-module changes
- persist evidence in `vibecoding/runs/<task-id>/`

Runner:
- `./vibecoding/orchestration/runner/vibecoding_runner.sh`

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Create .env file from example
cp backend/.env.example backend/.env
# Edit backend/.env with your configuration
```

### Running the Application
```bash
# Smoke test the app factory
python -c "from app import create_app; create_app(); print('OK')"

# Run backend development server
cd backend
python -m flask --app app run --port 5550

# Run with Gunicorn (production-like)
cd backend && ./run_app.sh
```

### Testing
```bash
# Run all tests
pytest backend/tests -v

# Run specific test file
pytest backend/tests/test_auth.py -v

# Run with markers
pytest backend/tests -v -m "not slow"
```

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
- `OLLAMA_HOST`, `OLLAMA_MODEL`: LLM-based classification
- `CLASSIFICATION_METHOD`: `auto`, `youtube_topics`, `tfidf`, `ollama`, or `hybrid`

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

## Important Notes

- **Database**: SQLite with WAL mode enabled for better concurrency. Schema migrations run automatically on startup.
- **Authentication**: Uses httpOnly session cookies (no JWT in frontend). OAuth tokens are stored encrypted in the database.
- **YouTube API Quota**: Daily quota is tracked per user. Refresh operations respect `YT_QUOTA_CAP_RATIO` to avoid hitting limits.
- **Classification**: The system can auto-classify channels using YouTube metadata, TF-IDF analysis of descriptions, or an optional Ollama LLM. Manual overrides take precedence.
- **Scheduler**: If enabled, the scheduler runs refresh operations at configured hours and performs controlled backfills.
- **CORS**: In production, frontend and backend should ideally be served from the same origin (via reverse proxy at `/` and `/api` paths) to avoid cookie/CORS issues, especially on smart TVs.
- **Error Handling**: All errors return a tracking ID. Stack traces are logged but not exposed to clients.
- **Testing**: Use `pytest` with fixtures from `conftest.py`. External API calls should be mocked.

## Coding Conventions

- **Language**: Code and comments in English
- **Python**: PEP 8, 4-space indentation, `snake_case` for functions/variables, `PascalCase` for classes
- **JavaScript**: Readable, modular code with descriptive names
- **Commits**: Use Conventional Commits format (`feat:`, `fix:`, `docs:`, `test:`, `chore:`)
- **No hardcoded secrets**: Use environment variables and `.env` files (never commit `.env`)

## Troubleshooting

- **OAuth errors**: Check `GOOGLE_REDIRECT_URI` matches the configured callback in Google Cloud Console
- **Quota exceeded**: Review `user_settings.quota_used` and adjust `schedule_hours` or preset
- **Lock errors**: SQLite busy timeout is configured; concurrent writes are handled via WAL mode
- **Classification not working**: Verify `CLASSIFICATION_METHOD` is set and required data is enriched (`POST /api/channels/enrich`)
