# YouTube Clear View

Curated YouTube viewing without the recommendation algorithm.

## Features

- Flask REST API with SQLite persistence
- Separate log viewer microservice
- Vanilla HTML/CSS/JS frontend
- Device detection and responsive layout
- Light/dark theme with persistence
- Infinite carousel for videos
- YouTube Data API v3 integration
- HTTPS-only deployment behind reverse proxy

## Quick Start (Development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pytest backend/tests -v
```

Create `backend/.env` from `backend/.env.example`, then run:

```bash
cd backend
python -m flask --app app run --port 5550
```

## Documentation

- API reference: `docs/api-reference.md`
- Architecture: `docs/architecture.md`
- Deployment: `docs/deployment.md`
- Development: `docs/development.md`

## License

MIT. See `LICENSE`.
