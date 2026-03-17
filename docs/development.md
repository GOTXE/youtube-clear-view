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

## Container Baseline (v0.2.0)

The v0.2.0 architecture baseline introduces repo-level infrastructure files in
`infra/`:

- `infra/docker/backend/Dockerfile`
- `infra/docker/log_viewer/Dockerfile`
- `infra/docker/proxy/Dockerfile`
- `infra/proxy/Caddyfile`
- `infra/compose/compose.v020.yaml`

This baseline is meant to move the app toward:

- same-origin frontend + API delivery through the proxy
- repo-level deployment topology
- an optional log viewer service
- a persistent SQLite volume managed by containers

It does not replace the local developer scripts yet.

Relevant refresh governance knobs in `backend/.env` / `.env.example`:
- `MANUAL_REFRESH_FULL_COOLDOWN_SECONDS`
- `MANUAL_REFRESH_CHANNEL_COOLDOWN_SECONDS`
- `ADMIN_USERNAMES`
- `SQLITE_METRICS_ENABLED`
- `SQLITE_METRICS_SLOW_WRITE_MS`
- `AUTH_TOKEN_ENCRYPTION_KEY`

LAN testing from another device:
- run `DEV_HOST=192.168.1.50 ./scripts/run_local.sh`
- `DEV_HOST` must be the LAN IP or hostname of the development PC
- the frontend will be reachable at `http://192.168.1.50:8080`
- the generated frontend config will point API calls to `http://192.168.1.50:5550`

Google OAuth local development must use:
- `GOOGLE_REDIRECT_URI=http://localhost:5550/api/auth/google/callback`
- `FRONTEND_URL=http://localhost:8080`

Google OAuth for web apps does not work reliably with raw private IP redirect URIs.
For OAuth from other devices, use one of these:
- keep OAuth local on `localhost`
- expose the dev app through an HTTPS hostname or tunnel
- test LAN browsing without OAuth and log in only from the development machine

For plain LAN browsing without Google OAuth:
- `FRONTEND_URL` may stay on `localhost`
- `CORS_ORIGINS` should still include the LAN frontend origin if frontend and API are split during development

## Google Account Switching

When `AUTH_MODE=google`, the app can switch between Google users already authenticated in the same browser.

- The backend keeps the active API session in the `ytcv_session` httpOnly cookie.
- The browser also keeps a signed list of known Google accounts via the Flask session cookie.
- The hamburger menu opens a switch-account modal that lists those known accounts.
- Selecting an existing account switches the backend session and reloads channels, videos, watched state, and settings for that user.
- Choosing a new account starts the normal Google OAuth flow and adds that account to the browser-known list after callback.

## Auth Storage Foundation

- API sessions are now stored as a hashed token in the database; the raw cookie value is never persisted for new sessions.
- Existing legacy session rows are migrated lazily on first successful use.
- Stored Google access token, refresh token, and OAuth scopes are encrypted at rest.
- `AUTH_TOKEN_ENCRYPTION_KEY` can be set explicitly; otherwise the app derives a stable encryption key from `FLASK_SECRET_KEY`.
- Google auth state is tracked in `google_auth_status` with values such as:
  - `not_linked`
  - `active`
  - `needs_reauth`
  - `revoked`
- On startup, SQLite migrations also normalize legacy Google users so older rows with persisted tokens move back to `active` automatically unless they were explicitly `revoked`.
- `POST /api/auth/google/unlink` revokes local Google linkage and clears stored OAuth credentials for the current user.

## MFA Enrollment Foundation

- Auth v2 now has a backend foundation for TOTP and recovery codes.
- New authenticated endpoints:
  - `GET /api/auth/mfa/status`
  - `POST /api/auth/totp/setup`
  - `POST /api/auth/totp/confirm`
  - `POST /api/auth/recovery-codes/regenerate`
  - `POST /api/auth/recovery-codes/consume`
- Current scope:
  - enroll TOTP
  - confirm TOTP with a real one-time code
  - generate and rotate recovery codes
  - consume recovery codes once
- This slice does not yet enforce MFA during sign-in. That will be wired into the login flow in a later auth v2 slice.
- The authenticated frontend now exposes a `Manage MFA` action in the hamburger menu.
- Current UI scope:
  - load MFA status for the current user
  - start TOTP setup
  - confirm setup with a real 6-digit code
  - render newly issued recovery codes
  - regenerate recovery codes after validating a current TOTP code
- MFA is now enforced for primary auth flows that still rely on username/Google session bootstrap:
  - local login
  - Google OAuth callback
  - Google account switching
- When a user has TOTP enabled, those primary flows stop at a pending MFA challenge.
- The frontend completes that challenge with either:
  - a current TOTP code
  - a recovery code
- Current non-goals:
  - enforcing an extra TOTP step after passkey sign-in
  - disabling TOTP from the UI
  - TV pairing integration

## Passkey Foundation

- Auth v2 now also has a backend WebAuthn/passkey foundation.
- New endpoints:
  - `GET /api/auth/passkeys`
  - `POST /api/auth/passkeys/register/options`
  - `POST /api/auth/passkeys/register/verify`
  - `DELETE /api/auth/passkeys/<id>`
  - `POST /api/auth/passkeys/authenticate/options`
  - `POST /api/auth/passkeys/authenticate/verify`
- Current scope:
  - persist passkey credentials per user
  - generate registration/authentication WebAuthn options
  - verify browser ceremonies and issue a backend session on successful assertion
- Frontend scope now included:
  - unauthenticated users can sign in with a passkey from the header menu when the browser supports WebAuthn
  - authenticated users can open a passkey management modal from the same menu
  - the modal can list registered passkeys, register a new passkey, and delete an existing one
- Current non-goals:
  - no enforced MFA step after passkey sign-in yet
  - no TV pairing integration yet
- Relevant config:
  - `PASSKEY_RP_NAME`
  - `PASSKEY_RP_ID`
  - `PASSKEY_ORIGIN`
  - `PASSKEY_ALLOWED_ORIGINS`

## Pairing Code Foundation

- Auth v2 now also has a pairing flow for TV and secondary devices.
- New endpoints:
  - `POST /api/auth/pairing/start`
  - `POST /api/auth/pairing/approve`
  - `POST /api/auth/pairing/claim`
- Current scope:
  - unauthenticated users can open `Sign in with device code` from the menu and start a short-lived pairing request
  - authenticated users can open `Approve device code` from the same menu and approve the code manually
  - the waiting device polls `claim` until the approval arrives and then receives a normal backend session cookie
- Current non-goals:
  - no QR flow yet
  - no pairing administration UI yet

## Device Type Persistence

- Device state is stored per `user_id + device_identifier` in `user_devices`.
- The frontend keeps only the latest device row id in local storage; the confirmed device type remains authoritative in the backend.
- The device modal now auto-opens only when the current user's device is not yet confirmed.
- The hamburger menu no longer exposes a separate `Device type` action.
- Manual device classification now lives inside the shared `Display setup` modal so hardware type and layout stay in one place.

## Frontend Mode System

- Devices can now also persist frontend display preferences:
  - `frontend_mode`: `phone`, `desktop_tablet`, or `tv`
  - `tv_scale`: `M`, `L`, `XL`, or `XXL`
  - optional TV setup hints:
    - `screen_size_inches`
    - `viewing_distance_m`
- The frontend resolves layout mode with this precedence:
  1. explicit local override saved from the display mode modal
  2. persisted device preferences from the backend
  3. mapped device type (`tv` -> `tv`, `mobile` -> `phone`, everything else -> `desktop_tablet`)
  4. viewport fallback
- The hamburger menu exposes a single `Display setup` action for authenticated users.
- That shared modal lets users adjust both:
  - the confirmed device type (`tv`, `tablet`, `mobile`, `desktop`)
  - the frontend layout mode and TV sizing hints
- Phone mode now includes a fixed bottom action bar and a subscriptions sheet so the main feed stays single-column while channels and filters remain reachable with one tap.
- TV mode now exposes a persistent quick-action rail for subscriptions, filters, refresh, and display setup so the most important actions are no longer buried behind the hamburger menu.
- The shared `Display setup` modal now also acts as the first TV calibration step:
  - TV screen size and viewing distance can be stored per device
  - the UI proposes a recommended TV scale
  - the modal shows a live TV preview before saving
  - saving a valid TV setup marks the TV scale as confirmed for that device

## Subscription Sidebar Search

- The subscriptions sidebar has its own local search field above the channel list.
- This filter is independent from the main video search and only narrows the visible channels in the sidebar.
- `Escape` clears the sidebar search.
- The overlaid broom action clears the sidebar search and keeps focus on the same field.

## Header Context Panel

- The header keeps the brand block on the left, a centered contextual summary panel, and the hamburger menu on the far right.
- The centered panel shows a global summary by default and switches to selected-channel context when a sidebar channel is active.
- Refresh progress is rendered in a detached header status bar below the main header row so it does not compete with the `Videos` title block.

## Refresh Governance

- Manual refresh is now governed by the backend instead of being treated as an unlimited client action.
- The backend enforces:
  - a stricter cooldown for full-library refreshes
  - a lighter cooldown for channel-scoped refreshes
  - one in-flight manual refresh per user at a time
- `GET /api/channels/refresh/stream` can now emit a terminal `blocked` event when:
  - a refresh is already running for that user
  - the cooldown window is still active
- The frontend interprets those blocked states and keeps the current UI stable instead of treating them as generic network failures.

## Admin Observability

- Admin-only runtime access is configured with `ADMIN_USERNAMES` in `backend/.env`.
- SQLite observability is process-local and intentionally lightweight for the current single-node deployment target.
- Admin users now get an `Admin observability` action in the app menu.
- The admin modal can:
  - inspect current SQLite write and lock metrics
  - inspect currently active manual refresh leases
  - toggle detailed recent-write capture on the current backend node
- Admin endpoints now expose:
  - SQLite write counters
  - slow write counters
  - lock error counters
  - recent write samples when detailed metrics are enabled
  - currently active manual refresh leases
- Detailed SQLite metrics can be enabled or disabled at runtime by an admin without changing the deployment topology.

## Channel Classification

- The app now uses a precision-first classifier set with only two active methods:
  - `youtube_topics`
  - `tfidf`
- `Hybrid` and `Ollama` are no longer part of the runtime classification path.
- The app taxonomy now includes direct YouTube-native categories that were missing
  from the original product taxonomy:
  - `Automotive`
  - `Animals`
- Bare subscription import no longer auto-classifies channels from weak snippet data alone.
- Classification happens after stronger evidence exists:
  - channel enrichment (`topic_ids`, keywords, country)
  - or recent local channel videos fetched during refresh
- Recent local videos are now the primary practical evidence source because many
  channels do not expose useful `topic_ids`, `keywords`, or `country`.
- Stored video evidence now includes:
  - `video_category_id`
  - `tags`
  - refreshed title/description/thumbnail/duration metadata on already known videos
- Manual reclassification first enriches unclassified channels with recent video
  evidence and only then runs full reclassification.
- Deterministic recent-video-category heuristics run before TF-IDF text
  similarity when the signal is clear enough.
- `TF-IDF` is intentionally stricter and may abstain instead of forcing a weak label.

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
- `infra/`: repo-level Docker, compose, and proxy baseline for v0.2.0
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
- Pull requests and reviewer-facing technical writeups in English.

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
4. Open a PR against `develop` unless the change is a release or hotfix for `main`.

## Branching Policy

- `develop`: main integration branch for ongoing work
- `main`: stable/release branch
- feature branches should branch from and merge back into `develop`
- release tags should be created from the release commit after merge into `main`
