# Repository Guidelines

## Project Structure & Module Organization

This repository is currently a scaffold/design workspace. The intended target layout (see `tech_docs/yt-curator-guide.md`) is:

- `backend/`: Python (Flask) REST API + SQLite
  - `backend/app/`: app factory (`create_app`), routes, models, services, logging
  - `backend/tests/`: `pytest` suite (`test_*.py`)
- `log_viewer/`: separate Flask microservice for viewing logs
- `frontend/`: vanilla HTML/CSS/JS client (plus `frontend/assets/`)
- `docs/`: public documentation (API, deployment, development)
- `tech_docs/`: private/local notes (intended to be gitignored)

## Build, Test, and Development Commands

Commands below apply once `backend/` and related modules exist:

- Create venv: `python3 -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r backend/requirements.txt`
- Run tests: `pytest backend/tests -v`
- Smoke check app factory: `python -c "from app import create_app; create_app(); print('OK')"`
- Deployment scripts (NAS): `backend/run_app.sh`, `log_viewer/run_log_viewer.sh`

## Coding Style & Naming Conventions

- Write code and comments in English.
- Python: 4-space indentation, PEP 8 naming (`snake_case`, `PascalCase` for classes).
- Frontend: keep JS/CSS readable and modular; prefer descriptive names (e.g., `theme-switcher.js`).
- Configuration: do not hardcode URLs/keys; use `.env` and keep templates in `.env.example`.

## Testing Guidelines

- Use `pytest`; name tests `test_*.py` and keep tests independent.
- Mock external YT API calls; tests must not require real API keys.

## Commit & Pull Request Guidelines

- Current commit history is informal (e.g., “inicio”, “correccion carpeta”). Going forward, prefer Conventional Commits:
  - `feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, `chore: ...`
- PRs should include: purpose, how to test, and screenshots for UI changes. Link related issues when applicable.
- Release tags: follow SemVer guidance in `tech_docs/yt-curator-guide.md` (use annotated tags like `v0.X.Y-beta.N` and never retag).

## Security & Configuration Tips

- Never commit secrets (`.env`, keys, tokens). Follow `.gitignore` and add new sensitive patterns if needed.
- Prefer HTTPS-only assumptions in code and docs (reverse proxy terminates TLS).
