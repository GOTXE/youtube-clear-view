# Deployment

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
cd /volume1/Apps/youtube-clear-view/backend
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

## Log Viewer Deployment

### Run Script

```bash
cd /volume1/Apps/youtube-clear-view/log_viewer
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

## Frontend Deployment

Deploy to Web Station path:

```bash
cd frontend
./deploy-to-synology.sh
```

By default, it syncs to `/volume1/web/youtube-clear-view/`.

## HTTPS Certificates

- Use Let's Encrypt in Synology Control Panel.
- Assign certificates to the reverse proxy hostnames.

## Verification Checklist

- `/api/health` returns `{"status": "ok"}`
- `/logs` prompts for Basic Auth
- Frontend loads without console errors
- Login sets `ytcv_session` cookie
- New videos appear after refresh

## Troubleshooting

- **401 responses**: verify cookie domain/path and CORS origins.
- **No logs**: check `LOG_FILE` path and volume mounts.
- **DB errors**: ensure `DATABASE_URI` points to a writable volume.
