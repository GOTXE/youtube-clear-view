# Container Install Modes

This document defines the target installation contract for YTCV containers
using Docker Compose:

- `prod` mode by default (GHCR images)
- `dev` mode when explicitly requested (local source build)

Status: implemented baseline (compose + workflow). Keep this file as the
contract for future refinements.

## 1. Goals

- Keep installation easy for normal users (no local build required).
- Keep contribution flow practical for developers (clone + build + edit + PR).
- Keep Google OAuth mandatory for YouTube token bootstrap in all modes.
- Keep runtime configuration externalized via Docker Compose env vars or `.env`.

## 2. Authentication Model (Fixed)

`AUTH_MODE=google` is mandatory in both `prod` and `dev`.

Google OAuth is used to bootstrap YouTube access tokens into the database.
After bootstrap, users can continue with local app authentication/session flows.

## 3. OAuth Redirect Decision Gate

During setup, users must choose one of these two OAuth callback strategies:

1. `localhost` callback (single-device)
- `GOOGLE_REDIRECT_URI=http://localhost:5550/api/auth/google/callback`
- Valid for Google OAuth.
- Only works when browser and Docker host are the same machine.

2. External callback URL (multi-device/LAN/public hostname)
- `GOOGLE_REDIRECT_URI=https://<your-host>/api/auth/google/callback`
- Must be HTTPS for Google web OAuth in this scenario.
- Intended for TV/phone/tablet access through a stable host URL.

Important:
- Raw LAN IP callback URLs over HTTP are not a reliable Google OAuth path.
- If callback is not `localhost`, treat HTTPS as required.

## 4. Compose Strategy

### 4.1 Production mode (default)

- Uses prebuilt images from GHCR.
- No source build required.
- Default behavior when no dev override is provided.

Target pattern:

```yaml
services:
  backend:
    image: ghcr.io/<owner>/ytcv-backend:${YTCV_TAG:-latest}
    env_file:
      - ./backend/.env
  proxy:
    image: ghcr.io/<owner>/ytcv-proxy:${YTCV_TAG:-latest}
```

### 4.2 Development mode (explicit)

- Requires cloning the repository.
- Uses compose override for local `build` and developer mounts/options.
- Intended for editing code and opening PRs.
- Compose is the source of truth; repository helper scripts can wrap it for convenience.

Target command:

```bash
docker compose -f infra/compose/compose.yaml -f infra/compose/compose.dev.yaml up --build
```

Without `compose.dev.yaml`, behavior is `prod` by default.

## 5. Image Tag Policy (GHCR)

Publish both immutable and moving tags:

- Immutable release tags: `vX.Y.Z`
- Moving channel tag: `latest`

Recommended usage:

- Normal users: pin `YTCV_TAG=vX.Y.Z` for reproducibility.
- Fast collaboration/dev smoke tests: use `latest`.

## 6. Configuration Contract

Users may configure variables in either location:

- `backend/.env` (recommended for secrets)
- inline `environment:` section in compose

Required keys:

- `AUTH_MODE=google`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- `YT_API_KEY`
- `FRONTEND_URL`
- `CORS_ORIGINS`
- `FLASK_SECRET_KEY`

## 7. User Flows

### 7.1 Normal user (prod)

1. Create `backend/.env` from `backend/.env.prod.example`.
2. Set Google/API variables.
3. Choose callback mode (`localhost` or external HTTPS).
4. Start with prod compose.

### 7.2 Contributor (dev)

1. Clone repository.
2. Create `backend/.env` from `backend/.env.prod.example`.
3. Set Google/API variables (usually localhost callback).
4. Start with dev override compose and local build (direct compose command or repository helper script).
5. Edit, test, submit PR.

## 8. Implementation Checklist

1. Add base compose file using GHCR images (`prod` default).
2. Add `compose.dev.yaml` override for local build/dev behavior.
3. Add release workflow that publishes backend/proxy images to GHCR with
   `latest` and `vX.Y.Z` tags.
4. Add startup validation docs/checks for OAuth callback strategy.
5. Update README and deployment docs with final commands once compose files are
   in place.
