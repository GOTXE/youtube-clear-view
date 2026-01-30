# Installation & Setup (Non-Technical Guide)

This page is for people who want to *use* **YT Clear View (YTCV)** (and optionally help with development),
without digging into internal architecture details.

If you prefer technical references:
- Architecture: [architecture.md](architecture.md)
- API reference: [api-reference.md](api-reference.md)

---

## 1) What you need (applies to every platform)

### A) A place to run the server

YTCV runs on a server (PC or NAS). Your TV/phone/PC connect to it through a web browser.
It is specifically designed for a “server in the house” setup where you mainly watch from a TV browser over LAN.

You need one of these:
- A Synology NAS (recommended for always-on home servers)
- A Linux machine (mini PC, NUC, home server)
- Docker support (optional, if you prefer containers)

### B) Google OAuth (required)

YTCV uses Google OAuth to:
- identify each user
- read that user's subscribed channels via the official YouTube API

You will need:
- a Google account
- a Google Cloud project
- YouTube Data API v3 enabled
- OAuth Client ID + Secret

Important: OAuth works best with a stable HTTPS URL (a normal website URL). TVs are especially picky.

Reference:
- Deployment details: [deployment.md](deployment.md)

Official Google references (English):
- Google Cloud Console: [console.cloud.google.com](https://console.cloud.google.com/)
- YouTube Data API v3: [YouTube Data API Overview](https://developers.google.com/youtube/v3)
- Enable an API in a project: [Enable APIs](https://cloud.google.com/apis/docs/getting-started#enabling_apis)
- OAuth consent screen: [Configure OAuth consent](https://developers.google.com/workspace/guides/configure-oauth-consent)
- Create OAuth credentials: [Create credentials](https://developers.google.com/workspace/guides/create-credentials)

---

## 2) Choose a platform

### Option A: Synology NAS (recommended for home use)

Why this is easiest:
- built-in reverse proxy + HTTPS certificates
- always-on
- easy backups of a single folder

Suggested folder layout (simple):
- Put everything under: `/volume1/ytcv/`
  - `/volume1/ytcv/data/` (database + cached thumbnails)
  - `/volume1/ytcv/logs/` (log files)
  - `/volume1/ytcv/backend/` (backend service)
  - `/volume1/ytcv/frontend/` (static web files)
  - `/volume1/ytcv/log_viewer/` (log viewer service)

What you will configure:
- Synology Reverse Proxy:
  - one public HTTPS hostname for the UI (recommended)
  - routes for `/api` (backend) and optionally `/logs` (log viewer)
- `.env` values (OAuth and URLs)

Where it usually fails:
- Google OAuth redirect URL does not match your real HTTPS URL exactly
- cookies not sticking because HTTPS detection / proxy headers are wrong
- file permissions for the DB/logs folder

Next step:
- Follow [deployment.md](deployment.md) (Synology section)

### Option B: Linux server (simple home server)

Why:
- flexible and fast
- can be a small always-on device

Typical setup:
- run backend + log viewer as background services
- use a reverse proxy (nginx/caddy) for HTTPS
- store DB/logs in a persistent folder you own

Where it usually fails:
- missing HTTPS (OAuth issues)
- wrong CORS / FRONTEND_URL configuration
- ports already in use

Next step:
- Follow [deployment.md](deployment.md) (Linux notes)

### Option C: Docker / container deployment

Why:
- repeatable installs
- easy upgrades and rollbacks

You will still need:
- persistent volumes for DB, thumbnails, and logs
- a reverse proxy for HTTPS if you want OAuth to work reliably across devices

Next step:
- Follow [deployment.md](deployment.md) (Docker section)

---

## 3) Using the app (after deployment)

1. Open the website on your device (TV browser, phone, PC).
2. Click “Sign in with Google”.
3. The app imports your subscriptions and starts building your timeline.
4. Use filters and categories to browse what you actually follow.

Tip:
- The first import may take time (large subscription lists). The UI should show progress.
  If you do not see progress updates, please wait a bit and avoid refreshing the page.

---

## 4) Developer setup (if you want to contribute)

If you want to run it on your computer for development and testing:
- Use [development.md](development.md) for the full instructions.

Common flow:
- start the backend + frontend locally
- run tests before opening PRs
- keep secrets out of git (`backend/.env` is not committed)

---

## 5) Troubleshooting (quick checklist)

If login fails:
- verify your public URL is HTTPS and reachable from the device
- verify the OAuth redirect URI matches *exactly* (no extra slashes, correct host, correct scheme)
- check backend logs for a tracking ID and open the log viewer if available

If the app loads but shows no content:
- confirm you are signed in
- confirm subscriptions import completed
- trigger a refresh and wait for it to finish

If you see database errors:
- confirm the DB path is writable
- on NAS, prefer a single backend instance and avoid multiple workers with SQLite
