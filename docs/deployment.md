# Deployment

## v0.2.0 Container Baseline

The repository now includes a repo-level container baseline under `infra/`:

- `infra/docker/backend/Dockerfile`
- `infra/docker/log_viewer/Dockerfile`
- `infra/docker/proxy/Dockerfile`
- `infra/proxy/Caddyfile`
- `infra/compose/compose.v020.yaml`

This baseline is the starting point for the v0.2.0 deployment architecture:

- the proxy serves the built frontend bundle
- `/api` is reverse-proxied to the backend
- `/logs` can be reverse-proxied to the optional log viewer
- the app is intended to run same-origin behind the proxy

This does not remove the current scripts or the older backend-local compose file yet.
It establishes the new repo-level shape that later tasks will refine.

## Prerequisites

- Synology NAS with Docker or Web Station
- Reverse proxy with HTTPS certificates
- SSH access to the NAS
- `.env` configured with production values

## Backend Deployment (Synology NAS)

### Option A: Run Script (systemd/manual)

1. Copy backend files to the NAS.
2. Ensure the `.env` file exists in `backend/`.
3. Run:

```bash
cd /volume1/Apps/yt-clear-view/backend
./run_app.sh
```

This installs dependencies, initializes the database, and launches Gunicorn on port `5550`.

### Option B: Docker Compose

From `backend/`:

```bash
docker compose up -d --build
```

Volumes:
- `backend_data` stores the SQLite DB.
- `logs` stores log files shared with the log viewer.

### Option C: Repo-level v0.2.0 compose baseline

From the repository root:

```bash
docker compose -f infra/compose/compose.v020.yaml up -d --build
```

Notes:

- this is the new repo-level baseline for the v0.2.0 architecture
- the proxy listens on `:8080` in the baseline file
- the frontend is built into the proxy image and served as same-origin
- backend SQLite data is mounted on a named volume
- the baseline compose includes `log_viewer` so `/logs` is always routed consistently
- later tasks may introduce profile-based variants once the proxy contract is split cleanly

## Log Viewer Deployment

### Run Script

```bash
cd /volume1/Apps/yt-clear-view/log_viewer
./run_log_viewer.sh
```

Runs the log viewer on port `5551`.

### Docker Compose

The log viewer is included in `backend/docker-compose.yml`.

## Reverse Proxy (Nginx / Synology)

- HTTP traffic must redirect to HTTPS.
- `/api/` -> backend on `127.0.0.1:5550`
- `/logs/` -> log viewer on `127.0.0.1:5551`

Use the example config in `backend/nginx-reverse-proxy.conf` and update:
- `server_name`
- certificate paths

For the v0.2.0 container baseline, the in-container proxy role is implemented by
`infra/proxy/Caddyfile`. An external reverse proxy may still terminate TLS and
forward traffic to the internal proxy container.

## Frontend Deployment

Build and deploy the production frontend bundle:

```bash
cd frontend
./deploy-to-synology.sh
```

The script:
- prompts for SSH user, host, and port if they are not already exported
- runs `npm run build`
- generates `frontend/dist/`
- syncs only `dist/` to the NAS target path

Default target path:

```bash
/volume1/web/yt-clear-view/
```

Supported environment variables:
- `DEPLOY_USER`
- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_PATH`

Only production assets are deployed from `dist/`. Development-only files such
as tests, `package.json`, and `vitest.config.mjs` are not part of the deployed
frontend payload.

In the v0.2.0 container baseline, the frontend is not deployed as a separate
runtime service. The proxy image builds the frontend and serves `dist/`
directly, which simplifies same-origin auth and API routing.

## Channel Thumbnail Cache

The backend caches channel thumbnails under `backend/instance/channel_thumbnails`.
This reduces API calls by reusing thumbnails across users. If you move or reset
the instance volume, the thumbnails will be re-downloaded on demand.

## HTTPS Certificates

- Use Let's Encrypt in Synology Control Panel.
- Assign certificates to the reverse proxy hostnames.

## Verification Checklist

- `/api/health` returns `{"status": "ok"}`
- `/logs` prompts for Basic Auth
- Frontend loads without console errors
- Login sets `ytcv_session` cookie (local or Google OAuth)
- New videos appear after refresh

## Google OAuth Setup

When using OAuth login (`AUTH_MODE=google`), configure the redirect URI in both
Google Cloud and your `.env`. The redirect URI must point to the backend callback
exactly.

Examples:

- NAS/production:
  - Google Cloud “Authorized redirect URI”:
    - `https://apiyt.mi-nas.me/api/auth/google/callback`
  - `.env`:
    - `GOOGLE_REDIRECT_URI=https://apiyt.mi-nas.me/api/auth/google/callback`
    - `FRONTEND_URL=https://ytcv.mi-nas.me`

- Local development:
  - Google Cloud “Authorized redirect URI”:
    - `http://localhost:5550/api/auth/google/callback`
  - `.env`:
    - `GOOGLE_REDIRECT_URI=http://localhost:5550/api/auth/google/callback`
    - `FRONTEND_URL=http://localhost:8080`

## Troubleshooting

- **401 responses**: verify cookie domain/path and CORS origins.
- **Google OAuth login fails**: verify `AUTH_MODE=google`, client ID/secret, and redirect URI.
- **OAuth console warnings about CSP / ERR_BLOCKED_BY_CLIENT**: these are browser/ad-blocker warnings from Google login pages and do not affect authentication. Disable blockers if you want a clean console.
- **No logs**: check `LOG_FILE` path and volume mounts.
- **DB errors**: ensure `DATABASE_URI` points to a writable volume.
- **Container baseline uses same-origin API calls**: ensure the frontend config inside the proxy uses `/api`, not a hardcoded external API host.
