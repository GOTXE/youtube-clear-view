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

## Frontend Mobile Scroll + Cache Notes

- Phone mode (`<= 767px`) uses document-level scrolling (`html/body`) to avoid
  nested scroll traps in mobile emulation and touch devices.
- Avoid reintroducing internal vertical scroll containers for primary mobile
  app content unless strictly required.
- Every frontend change requires rebuilding proxy image:
  - `./scripts/dev_docker.sh up --build proxy`
- Keep `frontend/sw.js` `CACHE_VERSION` updated so service worker clients fetch
  the latest CSS/JS bundle.

## Container Baseline (v0.2.0)

The v0.2.0 architecture baseline introduces repo-level infrastructure files in
`infra/`:

- `infra/docker/backend/Dockerfile`
- `infra/docker/proxy/Dockerfile`
- `infra/proxy/Caddyfile`
- `infra/compose/compose.v020.yaml`

This baseline is meant to move the app toward:

- same-origin frontend + API delivery through the proxy
- repo-level deployment topology
- admin logs integrated into `gestor`
- a persistent SQLite volume managed by containers

It does not replace the local developer scripts yet.

Relevant refresh governance knobs in `backend/.env` / `.env.example`:
- `MANUAL_REFRESH_FULL_COOLDOWN_SECONDS`
- `MANUAL_REFRESH_CHANNEL_COOLDOWN_SECONDS`
- `VIDEO_REFRESH_MODE`
- `YT_RSS_COMPLETION_COST`
- `APP_TIMEZONE`
- `ADMIN_USERNAMES`
- `SQLITE_METRICS_ENABLED`
- `SQLITE_METRICS_SLOW_WRITE_MS`
- `AUTH_TOKEN_ENCRYPTION_KEY`

Notes:
- `APP_TIMEZONE` controls the default timezone for backend log timestamps during
  startup.
- After boot, the active log timezone is updated to the persisted global admin
  timezone so scheduler settings, gestor log view, and backend timestamps stay
  aligned.
- Manual refresh jobs left in `queued` or `running` after a crash/restart are
  recovered on startup and marked as failed.

## RSS-First Video Refresh

The video refresh pipeline now supports three backend modes:

- `hybrid`
  - RSS feed discovery first
  - targeted YouTube API completion only for newly discovered IDs
  - fallback to the legacy full API refresh when the feed fails
- `rss_preferred`
  - RSS feed discovery first
  - targeted API completion for newly discovered IDs
  - no full API fallback when the feed fails
- `api_only`
  - disables RSS discovery
  - preserves the legacy per-channel API refresh path

Per-subscription RSS health is tracked in `user_channels`:

- `last_feed_checked_at`
- `last_feed_success_at`
- `last_feed_error_at`
- `feed_error_count`
- `refresh_mode_override`

Per-video RSS migration state is tracked in `videos`:

- `discovered_via`
- `metadata_incomplete`
- `source_last_seen_at`
- `feed_published_at`
- `feed_updated_at`

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
- the intended product flow is: first account bootstrap via Google OAuth on a compatible browser, then recurring LAN logins via local username/password, passkey, or pairing
- keep `GET /api/auth/google/link` available in development if you need to attach Google tokens to an already-created local/test account
- for first-time Google bootstrap (`auth_status=needs_setup`), the UI flow is:
  - local `username + password` setup
  - device-type confirmation
  - a readiness modal explaining that channels, videos, and categories are being prepared
- while that onboarding UI is shown, the app may already start importing subscriptions and preparing the first library state in the background

## Google Account Switching

When `AUTH_MODE=google`, the app can switch between Google users already authenticated in the same browser.

- The backend keeps the active API session in the `ytcv_session` httpOnly cookie.
- The dedicated gestor surface keeps its own admin-only API session in `ytcv_admin_session`, scoped to `/api/admin`, so opening `/gestor` in another tab does not replace the normal user session on `/`.
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

## Authentication & Security

### MFA (TOTP + Recovery Codes)

- Users can enroll TOTP from the hamburger menu via `Manage MFA`.
- TOTP setup returns a provisioning URI and a QR code; the user confirms enrollment by submitting a valid 6-digit code.
- Recovery codes are generated on TOTP confirmation and can be regenerated at any time after validating a current TOTP code.
- Each recovery code can only be consumed once.
- MFA is enforced on primary auth flows: local login, Google OAuth callback, and Google account switching. When a user has TOTP enabled, those flows pause at a pending MFA challenge that requires either a current TOTP code or a valid recovery code.

### Fallback Login

- Returning users with TOTP enabled have a direct recurring login path that does not require repeating Google OAuth:
  - username or email + current TOTP code
  - username or email + recovery code
- This provides a recovery mechanism if the Google session expires or the user loses access to the Google account.

### Password Support

- Local accounts (`AUTH_MODE=local`) support username + password authentication.
- Passwords are hashed before storage; plaintext passwords are never persisted.

### Passkey (WebAuthn/FIDO2)

- Authenticated users can register one or more passkeys from the passkey management modal (accessible via the header menu).
- Unauthenticated users can sign in with a registered passkey when the browser supports WebAuthn.
- Passkey credentials are persisted per user in the backend.
- Registration and authentication follow the standard WebAuthn ceremony flow with server-generated challenges.
- Passkey configuration is controlled by `PASSKEY_RP_NAME`, `PASSKEY_RP_ID`, `PASSKEY_ORIGIN`, and `PASSKEY_ALLOWED_ORIGINS`.

### Device Pairing (TV / Cross-Device Auth)

- Unauthenticated devices (typically TVs) can request a short-lived pairing code via `POST /api/auth/pairing/start`.
- An authenticated user approves the code from the hamburger menu (`Approve device code`) via `POST /api/auth/pairing/approve`.
- The waiting device polls `POST /api/auth/pairing/claim` until approval arrives, then receives a normal backend session cookie.
- This allows TV and secondary devices to authenticate without entering credentials on a limited input device.

### Google OAuth Account Linking/Unlinking

- The preferred production flow is Google-first account bootstrap, followed by mandatory local username/password setup in the post-Google wizard.
- `GET /api/auth/google/link` is still useful for development, migration, and support cases where an existing account must receive Google tokens later.
- `POST /api/auth/google/unlink` revokes the local Google linkage and clears stored OAuth credentials.
- Google auth state is tracked per user with statuses: `not_linked`, `active`, `needs_reauth`, `revoked`.

### Token Encryption at Rest

- Google access tokens, refresh tokens, and OAuth scopes are encrypted at rest using Fernet symmetric encryption.
- The encryption key can be set explicitly via `AUTH_TOKEN_ENCRYPTION_KEY`.
- If not set, the app derives a stable Fernet key from `FLASK_SECRET_KEY`.
- This ensures sensitive OAuth credentials are not stored in plaintext in the SQLite database.

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
- Returning users now also have a direct recurring fallback login path without repeating Google OAuth:
  - username/email + current TOTP code
  - username/email + recovery code
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
- Each device can also persist a friendly `display_name` for account-level device management.
- New devices receive an automatic label derived from their confirmed type, and older rows are backfilled lazily on read/update.
- The frontend keeps only the latest device row id in local storage; the confirmed device type remains authoritative in the backend.
- The device modal now auto-opens only when the current user's device is not yet confirmed.
- The hamburger menu no longer exposes a separate `Device type` action.
- Manual device classification now lives inside the shared `Display setup` modal so hardware type and layout stay in one place.
- `My account > Devices` can now rename devices via a dedicated endpoint instead of showing raw `user_agent` strings as the primary label.

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
- The hamburger menu is now grouped into:
  - `Account`
  - `Viewing`
  - `System`
- That shared modal lets users adjust both:
  - the confirmed device type (`tv`, `tablet`, `mobile`, `desktop`)
  - the frontend layout mode and TV sizing hints
- Phone mode now includes a fixed bottom action bar and a subscriptions sheet so the main feed stays single-column while channels and filters remain reachable with one tap.
- Desktop/tablet mode now owns the floating filters surface explicitly:
  - it stays closed until the user opens or docks it
  - the dock state is stored locally per browser
  - the panel can still be undocked and moved freely
- TV mode now exposes a persistent quick-action rail for subscriptions, filters, refresh, and display setup so the most important actions are no longer buried behind the hamburger menu.
- The shared `Display setup` modal now also acts as the first TV calibration step:
  - TV screen size and viewing distance can be stored per device
  - the UI proposes a recommended TV scale
  - the modal shows a live TV preview before saving
  - saving a valid TV setup marks the TV scale as confirmed for that device

## Player Overlay & Playback Progress

### Embedded Player

- Desktop/tablet and TV modes keep video playback inside the app with an embedded player overlay.
- The player uses the YouTube IFrame Player API with `enablejsapi=1` to enable programmatic control from the host page.
- Phone mode intentionally keeps the external YouTube redirect behavior.

### Auto-Mark Watched at 75%

- The player monitors playback progress via the IFrame API.
- When the user reaches 75% of the video duration, the video is automatically marked as watched without any user interaction.
- This threshold is designed to match natural viewing behavior where the remaining content is typically end screens or credits.

### Confirm Dialog on Close

- If the user closes the player overlay before reaching the 75% threshold, a confirm dialog appears with two options:
  - **Mark watched**: marks the video as watched and closes the overlay.
  - **Continue later**: saves the current playback position and closes the overlay without marking as watched.
- This prevents accidental loss of watch state when partially viewing a video.

### Progress Auto-Save

- While a video is playing, the frontend periodically saves the current playback position to the backend (approximately every 30 seconds).
- This ensures that progress is not lost if the browser crashes, the tab is closed, or the device loses power.

### Resume Playback

- When opening a video that has saved progress, the player automatically resumes from the last saved position.
- The IFrame API `seekTo()` method is used to jump to the saved timestamp after the player loads.

### Graceful Degradation

- Some browser extensions (ad blockers, privacy tools) block the YouTube IFrame API from loading.
- When the IFrame API is unavailable, the player falls back gracefully: the embed still renders but programmatic features (auto-mark, progress tracking, resume) are disabled.
- Users can still manually mark videos as watched and open them on YouTube directly.

### "Continue Watching" Carousel

- The main feed includes a "Continue watching" carousel that shows videos with saved in-progress playback.
- This carousel is hidden when there are no in-progress videos, so it does not take up space unnecessarily.
- Clicking a video in the carousel opens the player overlay and resumes from the saved position.

## TV Mode

### Compact Layout

- TV mode uses a compact header and footer optimized for large screens viewed from a distance.
- The header minimizes navigation chrome to maximize content area.
- The footer is condensed to show only essential information.

### Video Card Enhancements

- Video cards in TV mode display the channel name directly on the card surface.
- Metric alignment and colors are tuned for readability at TV viewing distances.

### Keyboard Navigation

- TV mode supports full keyboard navigation for use with remote controls and wireless keyboards.
- Arrow keys navigate between video cards in the carousel.
- Enter/OK activates the selected card (opens the player overlay).
- Escape closes overlays and modals.

### Sidebar Toggle

- The subscriptions sidebar can be toggled open and closed to maximize the video browsing area.
- The sidebar state persists across sessions.
- When collapsed, the full viewport width is available for video carousels.

## Subscription Sidebar Search

- The subscriptions sidebar has its own local search field above the channel list.
- This filter is independent from the main video search and only narrows the visible channels in the sidebar.
- `Escape` clears the sidebar search.
- The overlaid broom action clears the sidebar search and keeps focus on the same field.

## Header Context Panel

- The header keeps the brand block on the left, a centered contextual summary panel, and the hamburger menu on the far right.
- The centered panel shows a global summary by default and switches to selected-channel context when a sidebar channel is active.
- Refresh progress is rendered in a detached header status bar below the main header row so it does not compete with the `Videos` title block.

## Embedded Player Overlay

- Desktop/tablet and TV modes now keep video playback inside the app with an embedded player overlay.
- Clicking a video card in `desktop_tablet` or `tv` opens a blurred overlay with:
  - the embedded player
  - video metadata
  - `Mark watched`
  - `Open on YouTube`
- `phone` mode intentionally keeps the external YouTube behavior.
- The overlay closes with:
  - the close button
  - `Esc`
  - backdrop click
- Marking watched from the overlay updates the existing watched-state flow without requiring a backend schema change.

## CSS Organization (Mode-First)

- `frontend/css/main.css` is shared tokens + components only.
- Mode-specific selectors must live in:
  - `frontend/css/mode-desktop-tablet.css`
  - `frontend/css/mode-tv.css`
  - `frontend/css/mode-phone.css`
- Guardrail: `main.css` must not contain selectors starting with `html[data-mode=...`.

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
  - inspect active sessions and registered devices
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

### Channel classification actions in the UI

The authenticated web UI now exposes a single `Classify channels` action inside the
**Channels** section of the hamburger menu. Clicking it opens a choice modal with
two modes:

- `Basic`
  - Starts the existing background classification flow for channels that are still
    missing a usable automatic category.
  - This is the routine “fill the gaps” action.

- `Full`
  - Runs a broader maintenance flow for the current user:
    1. enrich unclassified channels with recent video evidence
    2. force a fresh automatic classification attempt for every subscribed channel
  - This is intentionally more expensive and should be treated as a corrective
    action, not a normal daily workflow.

Why it was moved out of the main page:
- It is not a browsing action.
- It changes classification state and can take a while.
- It fits better with other maintenance operations such as importing channels and
  refreshing videos.

Technical behavior:
- Frontend trigger: `#classify-channels-button` in the menu
- Both modes now run as backend background tasks. Reopening the web UI while the
  task is still active reattaches the client to the existing status poll.
- Start endpoint: `POST /api/channels/classify`
- Status endpoint: `GET /api/channels/classify/status`
- Full mode uses the same backend task plus recent video evidence enrichment
  before the reclassification phase.
- When the scheduler is enabled, the backend also attempts a `Basic`
  classification automatically up to two times per day for each active user
  that still has unclassified channels, as long as no refresh job is already
  running for that user.
- After success, the client refreshes the channel list and category carousels so
  the new assignments are visible immediately.

## Environment Variables Reference

### Core

| Variable | Description | Default |
|---|---|---|
| `FLASK_SECRET_KEY` | Session encryption key | (required) |
| `YT_API_KEY` | YouTube Data API key | (required) |
| `GOOGLE_CLIENT_ID` | OAuth client ID | (required for Google auth) |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | (required for Google auth) |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL | (required for Google auth) |
| `FRONTEND_URL` | Frontend origin for CORS | (required) |
| `AUTH_MODE` | `local` or `google` | `local` |
| `DATABASE_URI` | SQLite connection string | `sqlite:///yt_clear_view.db` |

### Administration

| Variable | Description | Default |
|---|---|---|
| `ADMIN_USERNAMES` | Comma-separated list of admin usernames | (none) |

### SQLite Metrics

| Variable | Description | Default |
|---|---|---|
| `SQLITE_METRICS_ENABLED` | Enable SQLite write metrics collection | `false` |
| `SQLITE_METRICS_SLOW_WRITE_MS` | Threshold in milliseconds for slow write warnings | `100` |

### Token Encryption

| Variable | Description | Default |
|---|---|---|
| `AUTH_TOKEN_ENCRYPTION_KEY` | Explicit Fernet key for encrypting OAuth tokens at rest | Derived from `FLASK_SECRET_KEY` |

### Refresh Governance

| Variable | Description | Default |
|---|---|---|
| `MANUAL_REFRESH_FULL_COOLDOWN_SECONDS` | Cooldown between full-library manual refreshes | `7200` |
| `MANUAL_REFRESH_CHANNEL_COOLDOWN_SECONDS` | Cooldown between per-channel manual refreshes | `1800` |

### WebAuthn / Passkeys

| Variable | Description | Default |
|---|---|---|
| `PASSKEY_RP_NAME` | Relying party display name shown during WebAuthn ceremonies | (required for passkeys) |
| `PASSKEY_RP_ID` | Relying party identifier (typically the domain name) | (required for passkeys) |
| `PASSKEY_ORIGIN` | Primary origin for WebAuthn verification | (required for passkeys) |
| `PASSKEY_ALLOWED_ORIGINS` | Comma-separated list of additional allowed origins for WebAuthn | (optional) |

### Optional Integrations

| Variable | Description | Default |
|---|---|---|
| `SCHEDULER_ENABLED` | Enable automatic refresh scheduler | `false` |
| `OLLAMA_HOST` | Ollama server URL for LLM classification | (none) |
| `OLLAMA_MODEL` | Ollama model name | (none) |
| `CLASSIFICATION_METHOD` | Classification strategy: `auto`, `youtube_topics`, `tfidf`, `ollama`, `hybrid` | `auto` |

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

## Admin Logs UX

- Severity filters, live review mode, and tracking ID lookup are available in `gestor`.
- `/logs` redirects to `/gestor/#logs`.

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
