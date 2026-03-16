# Development

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install
```

Create `.env` in `backend/` based on `.env.example`.

## Run the App Locally

```bash
python -c "from app import create_app; create_app(); print('OK')"
./scripts/run_local.sh
```

This starts:
- frontend on `http://localhost:8080`
- backend on `http://localhost:5550`
- log viewer on `http://localhost:5551/logs`

## Container Baseline (v0.2.0)

The v0.2.0 architecture baseline introduces repo-level infrastructure files in
`infra/`:

- `infra/docker/backend/Dockerfile`
- `infra/docker/log_viewer/Dockerfile`
- `infra/docker/proxy/Dockerfile`
- `infra/proxy/Caddyfile`
- `infra/compose/compose.v020.yaml`

This baseline is meant to move the app toward:

- same-origin frontend + API delivery through the proxy
- repo-level deployment topology
- an optional log viewer service
- a persistent SQLite volume managed by containers

It does not replace the local developer scripts yet.

LAN testing from another device:
- run `DEV_HOST=192.168.1.50 ./scripts/run_local.sh`
- `DEV_HOST` must be the LAN IP or hostname of the development PC
- the frontend will be reachable at `http://192.168.1.50:8080`
- the generated frontend config will point API calls to `http://192.168.1.50:5550`

Google OAuth local development must use:
- `GOOGLE_REDIRECT_URI=http://localhost:5550/api/auth/google/callback`
- `FRONTEND_URL=http://localhost:8080`

Google OAuth for web apps does not work reliably with raw private IP redirect URIs.
For OAuth from other devices, use one of these:
- keep OAuth local on `localhost`
- expose the dev app through an HTTPS hostname or tunnel
- test LAN browsing without OAuth and log in only from the development machine

For plain LAN browsing without Google OAuth:
- `FRONTEND_URL` may stay on `localhost`
- `CORS_ORIGINS` should still include the LAN frontend origin if frontend and API are split during development

## Google Account Switching

When `AUTH_MODE=google`, the app can switch between Google users already authenticated in the same browser.

- The backend keeps the active API session in the `ytcv_session` httpOnly cookie.
- The browser also keeps a signed list of known Google accounts via the Flask session cookie.
- The hamburger menu opens a switch-account modal that lists those known accounts.
- Selecting an existing account switches the backend session and reloads channels, videos, watched state, and settings for that user.
- Choosing a new account starts the normal Google OAuth flow and adds that account to the browser-known list after callback.

## Device Type Persistence

- Device state is stored per `user_id + device_identifier` in `user_devices`.
- The frontend keeps only the latest device row id in local storage; the confirmed device type remains authoritative in the backend.
- The device modal now auto-opens only when the current user's device is not yet confirmed.
- The hamburger menu also exposes a manual `Device type` action that reopens the same modal on demand.

## Subscription Sidebar Search

- The subscriptions sidebar has its own local search field above the channel list.
- This filter is independent from the main video search and only narrows the visible channels in the sidebar.
- `Escape` clears the sidebar search.
- The overlaid broom action clears the sidebar search and keeps focus on the same field.

## Header Context Panel

- The header keeps the brand block on the left, a centered contextual summary panel, and the hamburger menu on the far right.
- The centered panel shows a global summary by default and switches to selected-channel context when a sidebar channel is active.
- Refresh progress is rendered in a detached header status bar below the main header row so it does not compete with the `Videos` title block.

## Channel Classification

- The app now uses a precision-first classifier set with only two active methods:
  - `youtube_topics`
  - `tfidf`
- `Hybrid` and `Ollama` are no longer part of the runtime classification path.
- The app taxonomy now includes direct YouTube-native categories that were missing
  from the original product taxonomy:
  - `Automotive`
  - `Animals`
- Bare subscription import no longer auto-classifies channels from weak snippet data alone.
- Classification happens after stronger evidence exists:
  - channel enrichment (`topic_ids`, keywords, country)
  - or recent local channel videos fetched during refresh
- Recent local videos are now the primary practical evidence source because many
  channels do not expose useful `topic_ids`, `keywords`, or `country`.
- Stored video evidence now includes:
  - `video_category_id`
  - `tags`
  - refreshed title/description/thumbnail/duration metadata on already known videos
- Manual reclassification first enriches unclassified channels with recent video
  evidence and only then runs full reclassification.
- Deterministic recent-video-category heuristics run before TF-IDF text
  similarity when the signal is clear enough.
- `TF-IDF` is intentionally stricter and may abstain instead of forcing a weak label.

## Run Tests

```bash
pytest backend/tests -v
./scripts/test_frontend.sh
./scripts/test_fast.sh
./scripts/test_full.sh
```

Frontend tests use `Vitest` + `jsdom` and live under `frontend/tests/`.

## Project Structure

- `backend/`: Flask API + SQLite
- `log_viewer/`: log monitoring service
- `frontend/`: static UI
- `infra/`: repo-level Docker, compose, and proxy baseline for v0.2.0
- `frontend/i18n/`: UI translation JSON files (EN/ES)
- `docs/`: public docs
- `tech_docs/`: local notes (gitignored)

## Adding New Endpoints

1. Create a new blueprint in `backend/app/routes/`.
2. Add tests in `backend/tests/`.
3. Register the blueprint in `backend/app/routes/__init__.py`.
4. Document the endpoint in `docs/api-reference.md`.

## Code Style

- Python: PEP 8, 4-space indentation.
- JS/CSS: readable, descriptive names.
- Comments and docs in English.
- Pull requests and reviewer-facing technical writeups in English.

## Commit Format

Use Conventional Commits:
- `feat: ...`
- `fix: ...`
- `docs: ...`
- `test: ...`
- `chore: ...`

## Localization (i18n)

- Language is auto-detected from the browser.
- Override with `?lang=es` or `?lang=en`.
- Translation files live in `frontend/i18n/`.
- Add a new language by creating `frontend/i18n/<lang>.json` and adding the code to `SUPPORTED` in `frontend/js/i18n.js`.

The UI waits for translations to load before rendering to avoid a brief flash of the default language.

## Log Viewer UX

- Severity filters, auto-refresh, and highlighted newest entries are available in the log viewer UI.
- Access via `/logs` on the log viewer service.

## Git Workflow

1. Create a feature branch, for example `feat/web-ui-ux`.
2. Implement changes and run tests.
3. Commit and push.
4. Open a PR against `develop` unless the change is a release or hotfix for `main`.

## Branching Policy

- `develop`: main integration branch for ongoing work
- `main`: stable/release branch
- feature branches should branch from and merge back into `develop`
- release tags should be created from the release commit after merge into `main`
