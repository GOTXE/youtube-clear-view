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

Google OAuth local development must use:
- `GOOGLE_REDIRECT_URI=http://localhost:5550/api/auth/google/callback`
- `FRONTEND_URL=http://localhost:8080`

## Google Account Switching

When `AUTH_MODE=google`, the app can switch between Google users already authenticated in the same browser.

- The backend keeps the active API session in the `ytcv_session` httpOnly cookie.
- The browser also keeps a signed list of known Google accounts via the Flask session cookie.
- The hamburger menu opens a switch-account modal that lists those known accounts.
- Selecting an existing account switches the backend session and reloads channels, videos, watched state, and settings for that user.
- Choosing a new account starts the normal Google OAuth flow and adds that account to the browser-known list after callback.

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
4. Open a PR if needed.
