# Docker Setup — Local Development

> **Maintainer note:** If the container architecture, build process, or
> deployment tooling changes, this file MUST be updated so that any AI
> assistant or developer has an accurate reference.

## Compose file

```
infra/compose/compose.v020.yaml
```

Run all commands from the repo root:

```bash
docker compose -f infra/compose/compose.v020.yaml <command>
```

For repetitive local tasks there is also a helper script:

```bash
./scripts/dev_docker.sh up
./scripts/dev_docker.sh up --build --reset-db
./scripts/dev_docker.sh db-reset --backup
```

By default the helper script starts the full dev stack:
- `backend`
- `proxy`

## Containers

| Service | Image / Build | Ports | Purpose |
|---|---|---|---|
| **proxy** | Caddy 2.8 (multi-stage: builds frontend then serves via Caddy) | `8080 → 8080` | Serves the **frontend** static files, reverse-proxies `/api*` to backend, and redirects `/logs*` to `gestor`. |
| **backend** | Python 3.11-slim + Gunicorn | `5550` (internal) | Flask REST API + SQLite database. |

## How the frontend is served

The **proxy** container is a two-stage Docker build (`infra/docker/proxy/Dockerfile`):

1. **Stage 1 — frontend-build:** Copies `frontend/`, runs `npm install` and
   `build-dist.sh` to produce minified assets in `frontend/dist/`.
2. **Stage 2 — Caddy:** Copies the built assets into `/srv` and the
   `Caddyfile` into `/etc/caddy/`.

**Key consequence:** Frontend files are baked into the proxy image at build
time. There are no volume mounts for frontend files.

## When to rebuild each container

| What changed | Command |
|---|---|
| Frontend files (`frontend/css/`, `frontend/js/`, `frontend/index.html`, `frontend/sw.js`, etc.) | `docker compose -f infra/compose/compose.v020.yaml build proxy && docker compose -f infra/compose/compose.v020.yaml up -d proxy` |
| Caddyfile (`infra/proxy/Caddyfile`) | Same as above (rebuild proxy). |
| Backend code (`backend/app/`, `backend/requirements.txt`) | `docker compose -f infra/compose/compose.v020.yaml build backend && docker compose -f infra/compose/compose.v020.yaml up -d backend` |
| Backend `.env` only (no code changes) | `docker compose -f infra/compose/compose.v020.yaml up -d backend` (restart, no rebuild needed). |
| Everything | `docker compose -f infra/compose/compose.v020.yaml up -d --build` |

If you want the frontend "new version" banner to react to backend-only
deploys, set a stable `YTCV_BACKEND_BUILD_ID` in the backend environment and
change it only for real releases/deploys. Do not use a per-start timestamp,
or multi-worker Gunicorn instances may generate false update banners.

Relevant backend refresh environment variables:

- `VIDEO_REFRESH_MODE`
  - `hybrid`: RSS discovery first, API fallback if the feed fails
  - `rss_preferred`: RSS discovery first, skip API fallback if the feed fails
  - `api_only`: keep the legacy API-only refresh path
- `YT_REFRESH_COST`
  - quota units consumed by the legacy full channel API refresh path
- `YT_RSS_COMPLETION_COST`
  - quota units consumed when RSS-discovered videos need targeted metadata completion

## Service Worker cache

The frontend uses a Service Worker (`frontend/sw.js`) with a **cache-first**
strategy. The cache version is stored in the `CACHE_VERSION` constant.

**After any frontend change**, bump `CACHE_VERSION` in `frontend/sw.js`
(e.g. `ytcv-v15` → `ytcv-v16`) so browsers discard the old cache. Without
this bump, users will keep seeing stale assets even after rebuilding the
proxy container.

## Volumes

| Volume | Mounted in | Purpose |
|---|---|---|
| `ytcv_data` | backend → `/data` | SQLite database file. |
| `ytcv_logs` | backend → `/logs` | Application log file. |

## Caddyfile routing (`infra/proxy/Caddyfile`)

| Path | Target |
|---|---|
| `/api*` | `reverse_proxy backend:5550` |
| `/logs*` | `308 → /gestor/#logs` |
| Everything else | Static files from `/srv` (frontend), with SPA fallback to `index.html`. |

### Cache headers set by Caddy

- **Static assets** (`.js`, `.css`, images, fonts — except `sw.js`): `Cache-Control: public, max-age=31536000, immutable`
- **`sw.js`**: `Cache-Control: no-cache` (browser always revalidates)
- **HTML & i18n JSON**: `Cache-Control: no-cache`

## Key files

| File | Description |
|---|---|
| `infra/compose/compose.v020.yaml` | Main compose file. |
| `infra/docker/proxy/Dockerfile` | Multi-stage: frontend build + Caddy. |
| `infra/docker/backend/Dockerfile` | Backend image. |
| `infra/proxy/Caddyfile` | Caddy reverse proxy + static file config. |
| `frontend/sw.js` | Service Worker with `CACHE_VERSION`. |
