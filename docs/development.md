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

## Git Workflow

1. Create a feature branch: `desarrollo_paso_<n>`.
2. Implement changes and run tests.
3. Commit and push.
4. Open a PR if needed.
