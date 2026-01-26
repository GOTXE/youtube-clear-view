# Development

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Create `.env` in `backend/` based on `.env.example`.

## Run Backend

```bash
cd backend
python -c "from app import create_app; create_app(); print('OK')"
python -m flask --app app run --port 5550
```

## Run Tests

```bash
pytest backend/tests -v
```

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

1. Create a feature branch: `desarrollo_paso_<n>`.
2. Implement changes and run tests.
3. Commit and push.
4. Open a PR if needed.
