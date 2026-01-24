# Complete Guide: YouTube Clear View

## Description

Web application for curating YouTube content, allowing users to watch only videos from subscribed channels without the recommendation algorithm. The application features:

- **Backend API** in Python3 + Flask (modular architecture) + SQLite (hosted on NAS)
- **Log Viewer** separate Flask microservice for log monitoring (hosted on NAS)
- **Frontend responsive** HTML/CSS/JavaScript vanilla (hosted on NAS)
- **Multi-user** with synchronization across devices
- **Automatic detection** of device type (TV 50"+, Tablet, Mobile, Desktop)
- **Integration** with YouTube Data API v3
- **Everything configurable** via `.env` file (no hardcoding)
- **Production-ready** with Gunicorn WSGI server
- **HTTPS only** for all internet-facing connections (via reverse proxy)
- **Comprehensive logging** with levels, colors, tracking numbers, and web viewer
- **Light/Dark theme** with user preference persistence
- **Infinite carousel** with dynamic video loading (pagination)
- **All code and comments in English**

---

## Architecture

**Separation Backend/Frontend/Log Viewer:**
- **Backend**: Microservice on NAS (Docker/systemd) - REST API on internal port 5550 (not exposed)
- **Log Viewer**: Separate microservice on internal port 5551 (not exposed)
- **Frontend**: Synology web folder (`/volume1/web/youtube-clear-view/`)
- **Reverse Proxy**: Nginx/Synology reverse proxy handles HTTPS termination

**Access URLs (via reverse proxy, HTTPS only):**
- Backend API: `https://apiyt.mi-nas.me/api`
- Log Viewer: `https://apiyt.mi-nas.me/logs` (or separate subdomain)
- Frontend Web: `https://ytcv.mi-nas.me/`

```
youtube-clear-view/
├── backend/                       # API Microservice on NAS
│   ├── app/                       # Flask application package (modular)
│   │   ├── __init__.py            # App factory (create_app)
│   │   ├── config.py              # Configuration from .env
│   │   ├── extensions.py          # Flask extensions (db, cors, etc.)
│   │   ├── models/                # SQLAlchemy models (split by domain)
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── channel.py
│   │   │   ├── video.py
│   │   │   ├── theme.py
│   │   │   └── device.py
│   │   ├── routes/                # API route blueprints
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── channels.py
│   │   │   ├── videos.py
│   │   │   ├── themes.py
│   │   │   └── devices.py
│   │   ├── services/              # Business logic services
│   │   │   ├── __init__.py
│   │   │   ├── youtube_api.py     # YouTube Data API v3 integration
│   │   │   └── video_cache.py     # Video caching service
│   │   ├── middleware/            # Custom middleware
│   │   │   ├── __init__.py
│   │   │   ├── error_handler.py   # Global error handling + friendly pages
│   │   │   └── auth_middleware.py # Authentication decorator
│   │   ├── logging/               # Logging system
│   │   │   ├── __init__.py
│   │   │   ├── logger.py          # Logger setup (levels, colors, files)
│   │   │   └── tracking.py        # Error tracking number generator
│   │   └── utils/                 # Utility functions
│   │       ├── __init__.py
│   │       └── helpers.py
│   ├── tests/                     # Test suite
│   │   ├── __init__.py
│   │   ├── conftest.py            # Pytest fixtures
│   │   ├── test_auth.py
│   │   ├── test_channels.py
│   │   ├── test_videos.py
│   │   ├── test_themes.py
│   │   ├── test_devices.py
│   │   └── test_youtube_api.py
│   ├── migrations/                # Database migrations (if needed)
│   ├── logs/                      # Log files directory
│   ├── requirements.txt           # Python dependencies
│   ├── gunicorn.conf.py           # Gunicorn configuration
│   ├── wsgi.py                    # WSGI entry point
│   ├── .env.example               # Configuration template
│   ├── .env                       # Real configuration (NOT committed)
│   ├── run_app.sh                 # Installer + launcher for Synology NAS
│   ├── Dockerfile                 # Docker image definition
│   ├── docker-compose.yml         # Docker deployment
│   └── seed_db.py                 # Test data seeding script
├── log_viewer/                    # Separate log viewer microservice
│   ├── app.py                     # Flask app for log viewing
│   ├── templates/
│   │   └── logs.html              # Log viewer web interface
│   ├── static/
│   │   └── style.css              # Minimal styling
│   ├── requirements.txt
│   ├── gunicorn.conf.py
│   ├── wsgi.py
│   └── run_log_viewer.sh          # Launcher script
├── frontend/                      # Deployed to /volume1/web/youtube-clear-view/
│   ├── index.html                 # Main page
│   ├── error/                     # Friendly error pages
│   │   ├── 404.html
│   │   ├── 500.html
│   │   └── maintenance.html
│   ├── config.js                  # Configuration (backend URL)
│   ├── css/
│   │   ├── main.css               # Base styles + theme system (light/dark)
│   │   ├── tv.css                 # Styles for TV 50"+
│   │   ├── tablet.css             # Styles for tablet
│   │   └── mobile.css             # Styles for mobile
│   ├── js/
│   │   ├── app.js                 # Main logic orchestrator
│   │   ├── api.js                 # REST API client
│   │   ├── auth.js                # Authentication management
│   │   ├── carousel.js            # Infinite carousel component
│   │   ├── device.js              # Device detection
│   │   ├── theme-switcher.js      # Light/Dark theme toggle
│   │   └── utils.js               # Utilities
│   └── assets/
│       └── icons/                 # Icons and resources
├── docs/                          # Technical documentation
│   ├── api-reference.md           # Complete API documentation
│   ├── architecture.md            # Architecture decisions
│   ├── deployment.md              # Deployment guide
│   └── development.md             # Development setup guide
├── tech_docs/                     # Local technical docs (NOT committed)
├── .gitignore
├── pytest.ini                     # Pytest configuration
└── README.md
```

---

## Design System Specifications

**IMPORTANT: Before implementing ANY code, the AI MUST read and follow these specs located in `tech_docs/uiux/`.**

These specs define mandatory standards. The hierarchy is: **universals > platform > contextual**.

### Code Discipline (applies to ALL steps, backend and frontend):
| File | Scope |
|------|-------|
| `tech_docs/estandar_codigo_limpio_ia.spec` | **CRITICAL**: Minimal code, fix root cause, no dead code, no wrappers for single use, no premature abstractions, YAGNI. Read BEFORE writing any code. |

### Universal UI Standards (always apply):
| File | Scope |
|------|-------|
| `tech_docs/uiux/estandar_colores_ia.spec` | Color tokens: --bg, --surface, --text, --primary, --error, etc. Use tokens ONLY, never raw hex. |
| `tech_docs/uiux/estandar_tipografia_ia.spec` | Typography roles: Display, H1-H3, Body, BodySmall, Caption. Weights, line-height, paragraph width. |
| `tech_docs/uiux/estandar_espaciado_ia.spec` | Spacing scale: use official scale, no arbitrary values. Consistent rhythm. |
| `tech_docs/uiux/estandar_componentes_basicos_ia.spec` | Component states: normal, hover, active, disabled, loading. 44px hitbox on touch. |

### Platform Standards (apply for web/mobile):
| File | Scope |
|------|-------|
| `tech_docs/uiux/estandar_web_uiux_ia.spec` | Web: responsive, WCAG AA, forms, tables, navigation, sanitize HTML, no internal info exposure. |
| `tech_docs/uiux/estandar_movil_uiux_ia.spec` | Mobile: 44px hitbox, natural gestures, bottom nav, 15-16dp min text, light/dark tokens. |
| `tech_docs/uiux/estandar_dashboards_uiux_ia.spec` | Dashboards: data over aesthetics, modular cards, filters, high contrast. (For log viewer) |

### Profile (security + integration rules):
| File | Scope |
|------|-------|
| `tech_docs/90.2_perfil_web_uiux_ia.spec` | Web profile: WCAG AA, sanitize HTML, no CSRF traces, no tokens in localStorage, no internal backend info. |
| `tech_docs/index_uiux_ia.spec` | Master index: hierarchy and loading order of specs. |

### How to use:
- **Before writing ANY code**: read `estandar_codigo_limpio` (minimal code, no residues, fix root cause)
- Before writing CSS: read `estandar_colores`, `estandar_tipografia`, `estandar_espaciado`
- Before writing HTML/components: read `estandar_componentes_basicos`, `estandar_web_uiux`
- Before writing mobile styles: read `estandar_movil_uiux`
- Before handling user data/security: read `90.2_perfil_web_uiux`
- For log viewer UI: read `estandar_dashboards_uiux`

---

## Step 1: Initial Project Setup

### Prompt for AI:

```
Create the initial structure for a project called "youtube-clear-view" with the following modular architecture:

- Directory backend/ with:
  - app/ package (NOT a single app.py):
    - __init__.py (app factory pattern with create_app function)
    - config.py (loads configuration from .env)
    - extensions.py (initializes Flask extensions: SQLAlchemy, CORS)
    - models/ directory with __init__.py (empty model files prepared)
    - routes/ directory with __init__.py
    - services/ directory with __init__.py
    - middleware/ directory with __init__.py
    - logging/ directory with __init__.py
    - utils/ directory with __init__.py
  - tests/ directory with __init__.py and conftest.py
  - logs/ directory (with .gitkeep)
  - wsgi.py (WSGI entry point: from app import create_app; app = create_app())
  - gunicorn.conf.py (Gunicorn config: workers, bind, log level)
  - requirements.txt (Flask, SQLAlchemy, python-dotenv, requests, flask-cors, gunicorn, colorlog, pytest)
  - .env.example (template with all variables)
  - run_app.sh (installer + launcher for Synology NAS at /volume1/Apps/youtube-clear-view/)

- Directory log_viewer/ with:
  - app.py (simple Flask app for viewing logs)
  - templates/logs.html
  - static/style.css
  - requirements.txt
  - wsgi.py
  - run_log_viewer.sh

- Directory frontend/ with:
  - index.html (basic responsive HTML5)
  - error/ directory with 404.html, 500.html, maintenance.html (friendly/fun error pages)
  - config.js and config.example.js
  - css/ directory: main.css, tv.css, tablet.css, mobile.css
  - js/ directory: app.js, api.js, auth.js, carousel.js, device.js, theme-switcher.js, utils.js
  - assets/icons/

- Directory docs/ with:
  - api-reference.md, architecture.md, deployment.md, development.md

- Root files:
  - tech_docs/ (local technical docs, NOT committed)
  - .gitignore (Python, .env, SQLite, __pycache__, logs/, node_modules, etc.)
  - pytest.ini (pytest configuration)
  - README.md (basic project description)

IMPORTANT:
- All code and comments must be in English
- The run_app.sh script must:
  1. Create /volume1/Apps/youtube-clear-view/ if not exists
  2. Create Python virtual environment (venv)
  3. Install dependencies from requirements.txt
  4. Initialize the database
  5. Launch the app with Gunicorn (production mode)
- Gunicorn config: bind to 0.0.0.0:5550, 2 workers, access log, error log
- The .env.example must include ALL variables (see configuration section below)

Create all these files with basic functional structure. Add descriptive English comments throughout.
```

### Testing:

```bash
# After creating the structure, verify:
python -c "from app import create_app; app = create_app(); print('App factory works')"
pytest tests/ -v  # Should pass (no tests yet, but no import errors)
```

### Git Commands:

```bash
cd /path/to/project
git add .
git commit -m "chore: initial project structure with modular architecture"
git push -u origin main
```

### Step 1 Status (2026-01-24)

Legend: [ ] not started, [~] partial, [x] done

- [x] backend/ scaffold created (app factory, config, extensions, packages, tests, logs/.gitkeep, wsgi, gunicorn.conf, requirements, .env.example, run_app.sh)
- [x] log_viewer/ scaffold created (app.py, templates, static, requirements, wsgi, run_log_viewer.sh)
- [x] frontend/ scaffold created (index, error pages, config files, css/js placeholders, assets/icons)
- [x] docs/ scaffold created (api-reference, architecture, deployment, development)
- [x] root files created (.gitignore, pytest.ini, README.md)
- [x] descriptive comments throughout (headers and key blocks annotated)
- [x] step tests run (app factory import OK; pytest passes)

Notes:
- Flask-SQLAlchemy added to backend/requirements.txt to match extensions usage.
- Added backend/tests/test_placeholder.py to avoid pytest no-tests failure.
- backend/Dockerfile, backend/docker-compose.yml, backend/seed_db.py were created ahead of their steps; confirm whether to keep or remove.

---

## Step 2: Database Models

### Prompt for AI:

```
Define SQLAlchemy models in backend/app/models/ split across domain files:

1. **backend/app/models/user.py - User**:
   - id (PK, autoincrement)
   - username (unique, not null)
   - display_name (display name)
   - theme_preference (string: 'light' or 'dark', default 'light')
   - session_token (string, nullable, indexed - for httpOnly cookie auth)
   - session_created_at (timestamp, nullable - when current session was created)
   - created_at (timestamp)
   - updated_at (timestamp)

2. **backend/app/models/channel.py - Channel**:
   - id (PK, autoincrement)
   - youtube_channel_id (unique, not null)
   - title (channel name)
   - thumbnail_url
   - description
   - created_at

3. **backend/app/models/channel.py - UserChannel** (many-to-many):
   - id (PK)
   - user_id (FK to User)
   - channel_id (FK to Channel)
   - subscribed_at

4. **backend/app/models/theme.py - Theme** (custom themes/categories):
   - id (PK)
   - user_id (FK to User)
   - name (theme name)
   - color (hex color code for UI)
   - created_at

5. **backend/app/models/theme.py - ThemeChannel** (channels in themes):
   - id (PK)
   - theme_id (FK to Theme)
   - channel_id (FK to Channel)

6. **backend/app/models/video.py - Video**:
   - id (PK)
   - youtube_video_id (unique)
   - channel_id (FK to Channel)
   - title
   - description
   - thumbnail_url
   - published_at
   - duration
   - fetched_at (when fetched from API)

7. **backend/app/models/video.py - WatchedVideo**:
   - id (PK)
   - user_id (FK to User)
   - video_id (FK to Video)
   - watched_at
   - device_id (FK to UserDevice, optional)

8. **backend/app/models/device.py - UserDevice**:
   - id (PK)
   - user_id (FK to User)
   - device_identifier (unique device hash)
   - device_type (enum: 'tv', 'tablet', 'mobile', 'desktop')
   - user_agent
   - last_used_at
   - created_at

9. **backend/app/models/__init__.py**:
   - Import all models
   - Export them for easy access

Implement with:
- Appropriate relationships (SQLAlchemy relationships)
- Indexes on frequently searched fields
- to_dict() methods for JSON serialization
- Appropriate cascade configurations
- English comments explaining each model and relationship

All code and comments in English.
```

### Testing:

```bash
cd backend
pytest tests/ -v
python -c "from app.models import User, Channel, Video, Theme, UserDevice; print('All models import correctly')"
```

### Git Commands:

```bash
git add backend/app/models/
git commit -m "feat: add database models for users, channels, videos and devices"
git push
```

### Step 2 Status (2026-01-24)

Legend: [ ] not started, [~] partial, [x] done

- [x] user, channel, theme, video, and device models implemented
- [x] relationships, indexes, and cascades defined
- [x] to_dict() methods added for all models
- [x] models exported in backend/app/models/__init__.py
- [x] step tests run (pytest passes; model imports OK)

---

## Step 3: Configuration, Extensions and Logging

### Prompt for AI:

```
Implement the configuration, extensions, and logging system:

1. **backend/app/config.py**:
   - Class Config that loads all variables from .env
   - Validation that critical variables exist
   - Reasonable defaults where applicable
   - Variables:
     - FLASK_SECRET_KEY (required)
     - YOUTUBE_API_KEY (required for production, optional for dev)
     - DATABASE_URI (default: sqlite:///youtube_clear_view.db)
     - FLASK_PORT (default: 5550)
     - FLASK_HOST (default: 0.0.0.0)
     - FLASK_DEBUG (default: False)
     - CORS_ORIGINS (comma-separated list of allowed origins)
     - LOG_LEVEL (default: INFO, options: DEBUG, INFO, WARNING, ERROR, CRITICAL)
     - LOG_FILE (default: logs/app.log)
     - LOG_MAX_SIZE (default: 10MB)
     - LOG_BACKUP_COUNT (default: 5)
     - LOG_VIEWER_USER (username for log viewer access)
     - LOG_VIEWER_PASSWORD (password for log viewer access)
     - LOG_VIEWER_PORT (default: 5551)
     - GUNICORN_WORKERS (default: 2)

2. **backend/app/extensions.py**:
   - Initialize SQLAlchemy (db)
   - Initialize Flask-CORS (cors)
   - Function to register all extensions with app

3. **backend/app/logging/logger.py**:
   - Setup colored console logging (using colorlog library):
     - DEBUG: cyan
     - INFO: green
     - WARNING: yellow
     - ERROR: red
     - CRITICAL: bold red
   - File logging (rotating file handler, max size from config)
   - Log format: [TIMESTAMP] [LEVEL] [TRACKING_ID] [MODULE] message
   - Function get_logger(name) to get a configured logger for any module

4. **backend/app/logging/tracking.py**:
   - Function generate_tracking_id() -> returns unique tracking number (e.g., "ERR-20240120-ABC123")
   - Used in error responses so users can report issues with a tracking number
   - Format: ERR-YYYYMMDD-XXXXXX (6 alphanumeric chars)

5. **backend/app/__init__.py** (App Factory):
   - create_app(config_class=None) function
   - Load configuration from Config
   - Initialize extensions (db, cors)
   - Setup logging system
   - Register all route blueprints
   - Register error handlers (friendly pages, tracking numbers)
   - Configure CORS properly for reverse proxy + httpOnly cookies:
     - Allow origins from CORS_ORIGINS in .env (MUST be explicit, no wildcards with credentials)
     - supports_credentials=True (required for cookies to be sent cross-origin)
     - Allow headers: Content-Type, X-Requested-With
     - Allow methods: GET, POST, PUT, DELETE, OPTIONS
     - Do NOT include Authorization in allowed headers (we use cookies, not headers)
   - Create database tables on first run
   - Health check endpoint: GET /api/health
   - Return app instance

6. **backend/app/middleware/error_handler.py**:
   - Global error handler for 400, 401, 403, 404, 500 errors
   - Each error response includes:
     - Friendly message (no technical details exposed to user)
     - Tracking number for error identification
     - Appropriate HTTP status code
   - Log full error details (stacktrace, request info) to log file
   - JSON response format: {"error": "message", "tracking_id": "ERR-...", "status": code}
   - try-catch wrapping for all route handlers

7. **backend/wsgi.py**:
   - Simple WSGI entry point for Gunicorn
   - from app import create_app; application = create_app()

8. **backend/gunicorn.conf.py**:
   - Bind: read from env or default 0.0.0.0:5550
   - Workers: read from env or default 2
   - Access log: logs/access.log
   - Error log: logs/error.log
   - Log level: from env
   - Timeout: 120
   - Graceful timeout: 30

IMPORTANT:
- Authentication uses httpOnly cookies (NOT localStorage, NOT Authorization headers)
- CORS must have supports_credentials=True and explicit origins (no wildcard '*')
- Errors must NEVER be shown to the end user in the web interface
- All errors must be caught, logged with tracking number, and return a clean JSON response
- The reverse proxy URL is https://apiyt.mi-nas.me (no port exposed to internet)
- CORS_ORIGINS should include the frontend URL: https://ytcv.mi-nas.me
- All code and comments in English
```

### Testing:

```bash
cd backend
pytest tests/ -v
python -c "
from app import create_app
app = create_app()
with app.test_client() as client:
    response = client.get('/api/health')
    print(response.json)
    assert response.status_code == 200
print('Health check passed')
"
```

### Git Commands:

```bash
git add backend/app/config.py backend/app/extensions.py backend/app/__init__.py
git add backend/app/logging/ backend/app/middleware/
git add backend/wsgi.py backend/gunicorn.conf.py
git commit -m "feat: implement configuration, logging system, and app factory"
git push
```

---

## Step 4: YouTube API Service

### Prompt for AI:

```
Implement backend/app/services/youtube_api.py with a YouTubeService class:

1. **__init__(api_key)**:
   - Initialize with YouTube API key
   - Configure the API client
   - Setup logger with module name

2. **get_channel_info(channel_id)**:
   - Fetch channel information: title, description, thumbnail
   - Return dict with data or None on error
   - Log errors with tracking number
   - Wrap in try-catch

3. **get_channel_videos(channel_id, max_results=50, page_token=None)**:
   - Fetch latest videos from a channel
   - Return dict with: {videos: [...], next_page_token: str|None}
   - Support pagination via page_token (for infinite carousel)
   - Each video: video_id, title, description, thumbnail, published_at, duration
   - Wrap in try-catch, log errors

4. **search_videos(query, channel_id=None, max_results=20)**:
   - Search videos by text
   - Optionally filter by channel
   - Return list of videos
   - Wrap in try-catch

5. **get_video_details(video_id)**:
   - Get complete details of a specific video
   - Include duration, statistics, etc.
   - Wrap in try-catch

Also implement **backend/app/services/video_cache.py**:
- Simple in-memory cache with TTL (configurable via .env)
- Cache YouTube API responses to reduce quota usage
- Methods: get(key), set(key, value, ttl), invalidate(key), clear()
- Thread-safe implementation

All methods must:
- Handle API rate limits gracefully
- Log errors appropriately with tracking numbers
- Return None or [] on error (never raise unhandled exceptions)
- Use the caching service to avoid redundant API calls
- Include English comments explaining logic

Add 'google-api-python-client' to requirements.txt.
```

### Testing:

```bash
cd backend
pytest tests/test_youtube_api.py -v
# Test with mock API responses (don't need real API key for tests)
```

### Git Commands:

```bash
git add backend/app/services/ backend/requirements.txt
git commit -m "feat: implement YouTube API service with caching"
git push
```

---

## Step 5: Routes - Authentication

### Prompt for AI:

```
Implement backend/app/routes/auth.py with Blueprint for authentication:

**Authentication method: httpOnly cookies (NOT localStorage)**
- On login, the backend sets an httpOnly + Secure + SameSite=Lax cookie containing the session token
- The browser sends the cookie automatically on every request (credentials: 'include')
- JavaScript NEVER has access to the token (XSS protection)
- On logout, the backend clears the cookie

**Endpoints:**

1. **POST /api/auth/login**:
   - Body: {username: string}
   - If user exists, set httpOnly cookie and return: {user_id, username, display_name, theme_preference}
   - If not exists, create automatically, then set cookie
   - Cookie settings: httpOnly=True, Secure=True, SameSite='Lax', max_age=30 days, path='/api'
   - Return 200 with user data (token is NOT in the response body)

2. **POST /api/auth/logout**:
   - Clear the auth cookie (set expired)
   - Return 200 with {message: "Logged out"}

3. **GET /api/auth/users**:
   - Return list of all users: [{id, username, display_name}]
   - For user selector in frontend (no auth required)

4. **GET /api/auth/current**:
   - Reads token from httpOnly cookie (NOT from Authorization header)
   - Return current user data
   - 401 if no cookie or invalid token (with tracking number, no details exposed)

5. **PUT /api/auth/profile**:
   - Body: {display_name: string, theme_preference: string}
   - Update user profile (including theme preference)
   - Requires authentication (cookie)

Implement:
- backend/app/middleware/auth_middleware.py: @require_auth decorator
  - Reads session token from request.cookies (NOT from headers)
  - Validates token against database
  - Sets g.current_user for route handlers
- Token generation (secure random hash stored in DB)
- All errors wrapped in try-catch with tracking numbers
- Appropriate logging at each step
- English comments throughout

IMPORTANT:
- Tokens are NEVER exposed in response bodies or JavaScript
- Errors returned to the user must be clean and friendly. Technical details go to logs only.
- The cookie must have Secure=True (HTTPS only) since all connections are via reverse proxy
```

### Testing:

```bash
cd backend
pytest tests/test_auth.py -v
```

### Git Commands:

```bash
git add backend/app/routes/auth.py backend/app/middleware/auth_middleware.py
git add backend/tests/test_auth.py
git commit -m "feat: implement user authentication endpoints"
git push
```

---

## Step 6: Routes - Channels

### Prompt for AI:

```
Implement backend/app/routes/channels.py with Blueprint for channel management:

**Endpoints:**

1. **GET /api/channels**:
   - Requires authentication
   - Return user's subscribed channels
   - Include YouTube channel information

2. **POST /api/channels/subscribe**:
   - Body: {youtube_channel_id: string}
   - Subscribe user to channel
   - If channel doesn't exist in DB, fetch from YouTube API and create it
   - Return 201 with channel data

3. **DELETE /api/channels/<channel_id>/unsubscribe**:
   - Unsubscribe user from channel
   - Don't delete channel from DB (other users may be subscribed)
   - Return 204

4. **POST /api/channels/refresh**:
   - Body: {channel_id: int} (optional, if not passed refresh all)
   - Fetch new videos from YouTube API
   - Update Video table
   - Return number of new videos found

5. **GET /api/channels/<channel_id>/videos**:
   - Return videos from specific channel
   - Query params: ?limit=20&offset=0&page_token=null
   - Support pagination for infinite carousel
   - Mark which ones are already watched by user

All require authentication. Use YouTubeService for YouTube data.
All errors wrapped in try-catch, logged with tracking numbers.
English comments throughout.
```

### Testing:

```bash
cd backend
pytest tests/test_channels.py -v
```

### Git Commands:

```bash
git add backend/app/routes/channels.py backend/tests/test_channels.py
git commit -m "feat: implement channel management endpoints"
git push
```

---

## Step 7: Routes - Videos

### Prompt for AI:

```
Implement backend/app/routes/videos.py with Blueprint for video management:

**Endpoints:**

1. **GET /api/videos/latest**:
   - Requires authentication
   - Return latest videos from all subscribed channels
   - Query params: ?limit=50&offset=0
   - Support pagination for infinite carousel loading
   - Ordered by published_at descending
   - Mark which are already watched
   - Return: {videos: [{video, channel, watched}], has_more: bool, next_offset: int}

2. **GET /api/videos/by-theme/<theme_id>**:
   - Return videos from channels associated with a theme
   - Same pagination format as /latest
   - Return: {videos: [...], has_more: bool, next_offset: int}

3. **POST /api/videos/<video_id>/watch**:
   - Body: {device_id: int} (optional)
   - Mark video as watched
   - Return 204

4. **DELETE /api/videos/<video_id>/unwatch**:
   - Unmark video as watched
   - Return 204

5. **GET /api/videos/search**:
   - Query params: ?q=text&channel_id=1&theme_id=2&limit=20&offset=0
   - Search videos in local database
   - Optional filters by channel or theme
   - Return paginated results with has_more flag

Implement efficient pagination and indexes for fast searches.
All responses must include pagination metadata for infinite scroll.
All errors wrapped in try-catch, logged with tracking numbers.
English comments throughout.
```

### Testing:

```bash
cd backend
pytest tests/test_videos.py -v
```

### Git Commands:

```bash
git add backend/app/routes/videos.py backend/tests/test_videos.py
git commit -m "feat: implement video management and search endpoints"
git push
```

---

## Step 8: Routes - Themes

### Prompt for AI:

```
Implement backend/app/routes/themes.py with Blueprint for theme management:

**Endpoints:**

1. **GET /api/themes**:
   - Requires authentication
   - Return user's themes with associated channels
   - Format: [{id, name, color, channels: [{id, title, thumbnail}]}]

2. **POST /api/themes**:
   - Body: {name: string, color: string}
   - Create new theme for user
   - Return 201 with created theme

3. **PUT /api/themes/<theme_id>**:
   - Body: {name: string, color: string}
   - Update theme
   - Return updated theme

4. **DELETE /api/themes/<theme_id>**:
   - Delete theme (don't delete channels)
   - Return 204

5. **POST /api/themes/<theme_id>/channels**:
   - Body: {channel_ids: [int, int, ...]}
   - Associate channels to theme
   - Return 200

6. **DELETE /api/themes/<theme_id>/channels/<channel_id>**:
   - Disassociate channel from theme
   - Return 204

Validate that user can only modify their own themes.
All errors wrapped in try-catch, logged with tracking numbers.
English comments throughout.
```

### Testing:

```bash
cd backend
pytest tests/test_themes.py -v
```

### Git Commands:

```bash
git add backend/app/routes/themes.py backend/tests/test_themes.py
git commit -m "feat: implement theme management endpoints"
git push
```

---

## Step 9: Routes - Devices

### Prompt for AI:

```
Implement backend/app/routes/devices.py with Blueprint for device management:

**Endpoints:**

1. **POST /api/devices/register**:
   - Body: {device_identifier: string, user_agent: string}
   - Register new device for user
   - If already exists, update last_used_at
   - Return: {id, device_type: null} (null = pending configuration)

2. **GET /api/devices**:
   - Requires authentication
   - Return user's devices
   - Format: [{id, device_identifier, device_type, last_used_at}]

3. **PUT /api/devices/<device_id>/type**:
   - Body: {device_type: 'tv' | 'tablet' | 'mobile' | 'desktop'}
   - User confirms/changes device type
   - Return updated device

4. **DELETE /api/devices/<device_id>**:
   - Delete device
   - Return 204

5. **POST /api/devices/detect**:
   - Body: {user_agent: string, screen_width: int, screen_height: int}
   - Suggest device type based on characteristics
   - Return: {suggested_type: string, confidence: float}
   - Detection algorithm:
     - screen_width >= 1920 && diagonal >= 40" equivalent → 'tv' (high confidence)
     - screen_width >= 768 && screen_width < 1920 → 'tablet'
     - screen_width < 768 → 'mobile'
     - Otherwise → 'desktop'

All errors wrapped in try-catch, logged with tracking numbers.
English comments throughout.
```

### Testing:

```bash
cd backend
pytest tests/test_devices.py -v
```

### Git Commands:

```bash
git add backend/app/routes/devices.py backend/tests/test_devices.py
git commit -m "feat: implement device management and detection endpoints"
git push
```

---

## Step 10: Log Viewer Microservice

### Design System Specs to read first:
- `tech_docs/uiux/estandar_dashboards_uiux_ia.spec` (data-centric layout, modular cards, filters)
- `tech_docs/uiux/estandar_colores_ia.spec` (color tokens for log levels)
- `tech_docs/uiux/estandar_tipografia_ia.spec` (legible typography, monospace for log entries)
- `tech_docs/uiux/estandar_componentes_basicos_ia.spec` (buttons, inputs, states)

### Prompt for AI:

```
Implement the log_viewer/ separate Flask microservice for viewing application logs:

1. **log_viewer/app.py**:
   - Simple Flask application
   - HTTP Basic Authentication (user:password from main app's .env: LOG_VIEWER_USER, LOG_VIEWER_PASSWORD)
   - Routes:
     - GET / → redirect to /logs
     - GET /logs → render log viewer page
     - GET /logs/api/entries → JSON API for log entries (with filtering)
       - Query params: ?level=ERROR&search=text&limit=100&offset=0&tracking_id=ERR-xxx
     - GET /logs/api/stats → JSON with log statistics (counts by level, recent errors)
   - Read log files from configured path (LOG_FILE from .env)
   - Parse log entries into structured data

2. **log_viewer/templates/logs.html**:
   - Clean, minimal white interface
   - Adaptive text size (readable on mobile and large screens)
   - Features:
     - Filter by log level (checkboxes: DEBUG, INFO, WARNING, ERROR, CRITICAL)
     - Search by text or tracking number
     - Auto-refresh toggle (every 5 seconds)
     - Color-coded log entries matching console colors
     - Pagination
     - Click on tracking ID to filter related entries
   - Responsive design (works on all screen sizes)

3. **log_viewer/static/style.css**:
   - Minimal, clean design on white background
   - Responsive font sizing (clamp() for adaptive text)
   - Color coding for log levels
   - Mobile-friendly layout

4. **log_viewer/requirements.txt**:
   - Flask
   - python-dotenv

5. **log_viewer/wsgi.py**:
   - WSGI entry point for Gunicorn

6. **log_viewer/run_log_viewer.sh**:
   - Similar to run_app.sh but for log viewer
   - Runs on port 5551

IMPORTANT:
- This is a SEPARATE service, not part of the main API
- Authentication is required (HTTP Basic Auth)
- Read-only access to logs (no modification)
- Must handle large log files efficiently (tail-like behavior, pagination)
- All code and comments in English
- The web interface must be very light: white background, adaptive text size
```

### Testing:

```bash
cd log_viewer
python -c "from app import create_app; print('Log viewer app works')"
```

### Git Commands:

```bash
git add log_viewer/
git commit -m "feat: implement separate log viewer microservice"
git push
```

---

## Step 11: Frontend - Configuration

### Prompt for AI:

```
Create frontend/config.js and frontend/config.example.js:

**Requirements:**

This file is the ONLY place where the backend URL is configured.
The API goes through a reverse proxy (HTTPS, no port exposed).

```javascript
// Application configuration
// All API connections use HTTPS via reverse proxy
const APP_CONFIG = {
  // Backend API URL (via reverse proxy, HTTPS only)
  API_BASE_URL: 'https://apiyt.mi-nas.me/api',

  // API version
  API_VERSION: 'v1',

  // Request timeout (ms)
  REQUEST_TIMEOUT: 30000,

  // YouTube configuration
  YOUTUBE_BASE_URL: 'https://www.youtube.com',

  // Pagination configuration (for infinite carousel)
  DEFAULT_PAGE_SIZE: 20,
  VIDEOS_PER_LOAD: 20,  // Videos loaded per infinite scroll trigger
  INITIAL_LOAD_COUNT: 50,  // Initial video load count

  // UI configuration
  NOTIFICATION_DURATION: 3000,

  // Theme configuration
  DEFAULT_THEME: 'light',  // 'light' or 'dark'

  // Device type constants
  DEVICE_TYPES: {
    TV: 'tv',
    TABLET: 'tablet',
    MOBILE: 'mobile',
    DESKTOP: 'desktop'
  },

  // Breakpoints for responsive detection (px)
  BREAKPOINTS: {
    MOBILE_MAX: 767,
    TABLET_MIN: 768,
    TABLET_MAX: 1919,
    TV_MIN: 1920
  }
};

// Export configuration
window.APP_CONFIG = APP_CONFIG;
```

Create config.example.js with placeholder values for committing to repo.
The real config.js should be in .gitignore.

All comments in English.
```

### Git Commands:

```bash
git add frontend/config.example.js
git commit -m "feat: add frontend configuration for API connection"
git push
```

---

## Step 12: Frontend - HTML Base

### Design System Specs to read first:
- `tech_docs/uiux/estandar_web_uiux_ia.spec` (responsive, WCAG AA, navigation, forms)
- `tech_docs/uiux/estandar_componentes_basicos_ia.spec` (component catalog, states, hitbox)
- `tech_docs/uiux/estandar_tipografia_ia.spec` (semantic heading hierarchy)
- `tech_docs/90.2_perfil_web_uiux_ia.spec` (accessibility, no internal info exposure)

### Prompt for AI:

```
Create frontend/index.html with semantic, responsive HTML5 structure:

**Requirements:**

1. **Head**:
   - Meta tags: viewport, charset UTF-8, description, theme-color
   - Title: "YouTube Clear View"
   - Links to all CSS (main.css always, then tv/tablet/mobile via media queries)
   - Preconnect to YouTube API

2. **Body structure**:
   - Header:
     - Logo/title "YouTube Clear View"
     - Theme toggle button (light/dark switch)
     - User selector (dropdown)
     - Current user displayed
     - Device type indicator

   - Section filters:
     - Search bar (text input with button)
     - Selectable filters (checkboxes): "Unwatched", "Last week", etc.
     - Theme selector (dropdown with user's themes)

   - Section main carousel:
     - Title: "Latest Videos"
     - Infinite carousel container (horizontal scroll with dynamic loading)

   - Section theme carousels:
     - Dynamic based on user's themes
     - Each with theme title and its color
     - Each is an infinite carousel

   - Footer:
     - Settings (button)
     - Credit line: "GOTXE + ❤️ + IA 🤖"
     - GitHub icon linking to the project repository (https://github.com/gotxe/youtube-clear-view)
     - About

3. **Accessibility**:
   - Appropriate ARIA labels
   - Keyboard navigation
   - Correct semantics
   - High contrast support

4. **No hardcoded content**:
   - Everything populated dynamically from JavaScript

**Scripts at end of body (in this order):**
1. config.js (FIRST - backend configuration)
2. utils.js
3. api.js
4. auth.js
5. device.js
6. theme-switcher.js
7. carousel.js
8. app.js

Also create the friendly error pages:
- frontend/error/404.html - Fun "lost in space" or similar themed 404 page
- frontend/error/500.html - Fun "oops, something broke" page
- frontend/error/maintenance.html - "We'll be back soon" page

Error pages should be:
- Self-contained (inline CSS, no external dependencies)
- Friendly and slightly humorous (not scary technical errors)
- Include a "Go Home" button
- Responsive and work on all devices
- Light background, clean design

All text content and comments in English.
```

### Git Commands:

```bash
git add frontend/index.html frontend/error/
git commit -m "feat: create responsive HTML structure with friendly error pages"
git push
```

---

## Step 13: Frontend - CSS with Light/Dark Theme System

### Design System Specs to read first (CRITICAL for this step):
- `tech_docs/uiux/estandar_colores_ia.spec` (ALL color tokens: --bg, --surface, --text, --primary, --error, etc. Use tokens ONLY)
- `tech_docs/uiux/estandar_tipografia_ia.spec` (roles: Display, H1-H3, Body, BodySmall, Caption. Weights and line-height)
- `tech_docs/uiux/estandar_espaciado_ia.spec` (spacing scale, no arbitrary values)
- `tech_docs/uiux/estandar_componentes_basicos_ia.spec` (states: normal, hover, active, disabled, loading)
- `tech_docs/uiux/estandar_web_uiux_ia.spec` (responsive, hover/focus/active consistent)
- `tech_docs/uiux/estandar_movil_uiux_ia.spec` (44px hitbox, 15-16dp min text, gestures)

### Prompt for AI:

```
Implement CSS files with responsive system and light/dark theme support:

**frontend/css/main.css**:
- CSS custom properties for theming:
  - :root (light theme - DEFAULT):
    - --bg-primary: #ffffff
    - --bg-secondary: #f8f9fa
    - --bg-card: #ffffff
    - --text-primary: #1a1a2e
    - --text-secondary: #4a4a6a
    - --accent-primary: #3b82f6
    - --accent-secondary: #10b981
    - --border: #e2e8f0
    - --shadow: rgba(0,0,0,0.1)
  - [data-theme="dark"]:
    - --bg-primary: #1a1a2e
    - --bg-secondary: #16213e
    - --bg-card: #1e2a3a
    - --text-primary: #f5f5f5
    - --text-secondary: #a0a0b0
    - --accent-primary: #60a5fa
    - --accent-secondary: #34d399
    - --border: #2d3748
    - --shadow: rgba(0,0,0,0.3)
- Basic CSS reset
- Base styles for body, header, sections using CSS variables
- Grid/flexbox system
- Button, input, video card styles
- Smooth hover and transition animations
- Typography: sans-serif, readable, using clamp() for adaptive sizing
- Theme toggle button styles (sun/moon icon)
- Notification/toast styles
- Modal styles
- Loading spinner
- Carousel base styles

**frontend/css/tv.css** (media query min-width: 1920px):
- Large font sizes (minimum 24px text, 48px titles) using clamp()
- Video thumbnails: 400px x 225px minimum
- Generous spacing between elements (40px+)
- Very visible focus states for remote control navigation
- Carousels with 4-5 visible items
- Design for 2.5m+ viewing distance

**frontend/css/tablet.css** (media query 768px - 1919px):
- Moderate sizes
- Thumbnails: 300px x 169px
- Carousels with 3 visible items
- Touch-friendly: buttons minimum 44px x 44px

**frontend/css/mobile.css** (media query max-width: 767px):
- Vertical layout
- Carousels with 1-2 visible items
- Optimized mobile navigation
- Thumbnails: 100% width, responsive
- Hamburger menu if needed

IMPORTANT:
- All sizes should use clamp() or relative units for smooth scaling
- Text must be readable on ALL screen sizes (mobile to 60" TV)
- The theme system uses data-theme attribute on <html> element
- Light theme is the DEFAULT
- Smooth transition between themes (0.3s transition on colors)
- All comments in English
```

### Git Commands:

```bash
git add frontend/css/
git commit -m "feat: implement responsive CSS with light/dark theme system"
git push
```

---

## Step 14: Frontend - JavaScript API Client

### Design System Specs to read first:
- `tech_docs/90.2_perfil_web_uiux_ia.spec` (security: sanitize HTML, no tokens in localStorage, no internal info exposure)
- `tech_docs/uiux/estandar_web_uiux_ia.spec` (no dynamic HTML without sanitization)

### Prompt for AI:

```
Implement frontend/js/api.js with client for backend communication:

**Class APIClient**:

Properties:
- baseURL (from APP_CONFIG.API_BASE_URL)
- timeout (from APP_CONFIG.REQUEST_TIMEOUT)
- (NO token property - authentication is handled by httpOnly cookies automatically)

Generic methods:
- async request(endpoint, method, body, headers)
  - Include timeout (AbortController)
  - Include credentials: 'include' in ALL fetch requests (sends httpOnly cookies automatically)
  - Do NOT manually set Authorization headers (cookies handle auth)
  - Handle network and CORS errors gracefully
  - Parse JSON responses
  - On error: return clean error object (never expose internals)
  - Handle 401 responses (redirect to login/user selector)
  - Log errors to console in development
- async get(endpoint, params)
- async post(endpoint, body)
- async put(endpoint, body)
- async delete(endpoint)
- (NO setToken/getToken/clearToken methods - cookies are managed by the browser)

Specific methods for each endpoint:
- **Auth**: login(username), logout(), getUsers(), getCurrentUser(), updateProfile(data)
- **Channels**: getChannels(), subscribe(youtubeChannelId), unsubscribe(channelId), refreshChannels(channelId?), getChannelVideos(channelId, limit, offset)
- **Videos**: getLatestVideos(limit, offset), getVideosByTheme(themeId, limit, offset), markAsWatched(videoId, deviceId?), markAsUnwatched(videoId), searchVideos(query, filters)
- **Themes**: getThemes(), createTheme(name, color), updateTheme(themeId, name, color), deleteTheme(themeId), addChannelsToTheme(themeId, channelIds), removeChannelFromTheme(themeId, channelId)
- **Devices**: registerDevice(deviceIdentifier, userAgent), getDevices(), setDeviceType(deviceId, deviceType), deleteDevice(deviceId), detectDevice(userAgent, screenWidth, screenHeight)

Error handling:
- Catch network errors
- Parse error responses from backend
- Handle tracking IDs from backend errors
- Retry logic for rate limiting (exponential backoff)
- Never expose raw errors to UI

All comments in English.
```

### Git Commands:

```bash
git add frontend/js/api.js
git commit -m "feat: implement API client for backend communication"
git push
```

---

## Step 15: Frontend - Authentication

### Design System Specs to read first:
- `tech_docs/90.2_perfil_web_uiux_ia.spec` (NO tokens in localStorage, sanitize HTML)
- `tech_docs/uiux/estandar_componentes_basicos_ia.spec` (modals, inputs with validation, button states)
- `tech_docs/uiux/estandar_colores_ia.spec` (state tokens for success/error feedback)

### Prompt for AI:

```
Implement frontend/js/auth.js for authentication management:

**IMPORTANT: No tokens in JavaScript. Authentication is via httpOnly cookies managed by the browser.**
The frontend NEVER stores, reads, or manipulates auth tokens. It simply calls API
endpoints and the browser handles cookies automatically.

**Features:**

1. **Initialization**:
   - Call /api/auth/current (browser sends cookie automatically)
   - If 200: user is authenticated, load user data (including theme_preference)
   - If 401: no valid session, show user selector
   - No localStorage involved for auth state

2. **User selector**:
   - Fetch user list from backend
   - Display visual list with names
   - "New user" button to create
   - On select: call login(username) → backend sets httpOnly cookie
   - Apply user's theme preference immediately

3. **Create user**:
   - Modal/prompt to enter username
   - Basic validation (not empty, alphanumeric)
   - Create user via API (login endpoint creates if not exists)
   - Cookie is set automatically by backend response

4. **Functions**:
   - async initAuth() → checks session via /api/auth/current
   - getCurrentUser() → returns cached user object or null
   - isAuthenticated() → boolean (based on cached state, not token check)
   - async logout() → calls /api/auth/logout (backend clears cookie), reloads page
   - async switchUser() → logout then show selector

5. **UI**:
   - Show current user in header
   - Button to switch user
   - Update UI when user changes

6. **Session handling**:
   - On 401 from any API call → clear cached user, show user selector
   - No manual token refresh needed (cookie has max_age set by backend)

Integrate with APIClient. Emit custom events when auth state changes.
All comments in English.
NEVER use localStorage or sessionStorage for authentication tokens.
```

### Git Commands:

```bash
git add frontend/js/auth.js
git commit -m "feat: implement user authentication and session management"
git push
```

---

## Step 16: Frontend - Device Detection

### Prompt for AI:

```
Implement frontend/js/device.js for device detection and management:

**Features:**

1. **Automatic detection**:
   - Generate unique device_identifier (fingerprint based on: user agent, screen resolution, timezone, language)
   - Gather data: user_agent, screen.width, screen.height
   - Call /api/devices/detect for suggestion
   - Register device: /api/devices/register

2. **First time on device**:
   - If device_type is null (new device)
   - Show modal/dialog: "We detected you're using a [suggested_type]. Is this correct?"
   - Options: Confirm / Change manually (radio buttons: TV, Tablet, Mobile, Desktop)
   - Save preference: /api/devices/:id/type

3. **Apply styles**:
   - Add class to <body>: device-tv, device-tablet, device-mobile, device-desktop
   - CSS responsive will apply appropriate styles
   - Save device_id in localStorage for future sessions

4. **Functions**:
   - async detectDevice()
   - async registerDevice()
   - async confirmDeviceType(type)
   - getDeviceId() → returns device_id from localStorage
   - getCurrentDeviceType() → returns current type

5. **Persistence**:
   - Save device_id in localStorage
   - On app start, check if device is already registered
   - Update last_used_at on each visit

Execute automatically after page load and authentication.
All comments in English.
```

### Git Commands:

```bash
git add frontend/js/device.js
git commit -m "feat: implement automatic device detection and type selection"
git push
```

---

## Step 17: Frontend - Theme Switcher

### Prompt for AI:

```
Implement frontend/js/theme-switcher.js for light/dark theme management:

**Features:**

1. **Initialization**:
   - Check user's theme_preference from auth data
   - If no user logged in, check localStorage for saved preference
   - If nothing saved, default to 'light'
   - Apply theme immediately on page load (prevent flash)

2. **Theme toggle**:
   - Toggle between 'light' and 'dark'
   - Set data-theme attribute on <html> element
   - Update toggle button icon (sun ↔ moon)
   - Save preference to localStorage
   - If authenticated, also save to backend (/api/auth/profile)
   - Smooth transition (CSS handles the animation)

3. **Functions**:
   - initTheme() - called on page load
   - toggleTheme() - switch between light/dark
   - setTheme(themeName) - set specific theme
   - getCurrentTheme() → returns 'light' or 'dark'

4. **Prevent flash of wrong theme**:
   - Add inline script in <head> of index.html that reads localStorage
     and applies data-theme before CSS loads
   - This prevents flash of light theme when user prefers dark (or vice versa)

All comments in English.
```

### Git Commands:

```bash
git add frontend/js/theme-switcher.js
git commit -m "feat: implement light/dark theme switcher with persistence"
git push
```

---

## Step 18: Frontend - Infinite Carousel Component

### Design System Specs to read first:
- `tech_docs/uiux/estandar_componentes_basicos_ia.spec` (card component, states, 44px hitbox on touch)
- `tech_docs/uiux/estandar_espaciado_ia.spec` (spacing scale for gaps between items)
- `tech_docs/uiux/estandar_movil_uiux_ia.spec` (touch gestures: swipe, scroll, tap)
- `tech_docs/uiux/estandar_web_uiux_ia.spec` (hover/focus/active states, accessibility)
- `tech_docs/uiux/estandar_colores_ia.spec` (tokens for watched/unwatched states, loading indicators)

### Prompt for AI:

```
Implement frontend/js/carousel.js with a reusable INFINITE carousel component:

**Class Carousel:**

Constructor:
- containerId: DOM container element ID
- fetchFunction: async function(offset, limit) that returns {videos: [], has_more: bool}
- options: {gap: 20, showControls: true, theme: null}

Methods:
- async init(): initial load of videos and render
- render(): creates the carousel HTML
- renderVideoCard(video): creates individual video card
  - Thumbnail as background image (lazy loaded)
  - Video title (truncated)
  - Channel name
  - Video duration badge
  - "Watched" indicator if watched === true
  - Click opens video in new YouTube tab
  - Click also marks as watched (if not already)
- scrollLeft(): scroll carousel left
- scrollRight(): scroll carousel right
- async loadMore(): triggered when approaching end of scroll
  - Fetches next page of videos from API
  - Appends new video cards to carousel track
  - Updates internal offset/page tracking
  - Shows loading indicator while fetching
- destroy(): cleanup event listeners and observers

**HTML structure:**
```html
<div class="carousel" data-theme-color="optional-color">
  <button class="carousel-control left" aria-label="Scroll left">◀</button>
  <div class="carousel-track">
    <!-- Video cards dynamically inserted -->
    <!-- Loading indicator at the end -->
  </div>
  <button class="carousel-control right" aria-label="Scroll right">▶</button>
</div>
```

**Infinite scroll behavior:**
- Use IntersectionObserver on a sentinel element at the end of the track
- When sentinel becomes visible, trigger loadMore()
- Show loading spinner while loading
- When has_more is false, remove sentinel (no more to load)
- Debounce to prevent multiple simultaneous loads

**Interactivity:**
- Navigation with left/right buttons
- Smooth horizontal scroll
- Touch/drag scroll on mobile devices
- Keyboard: left/right arrows when focused
- On video click:
  1. Open in new tab: `https://youtube.com/watch?v=${video.youtube_video_id}`
  2. Call API: markAsWatched(video.id, deviceId)
  3. Update UI: add "watched" class with fade animation

**Responsive:**
- TV: 4-5 visible videos
- Tablet: 3 visible videos
- Mobile: 1-2 visible videos
- Adjust automatically based on body class

**Lazy loading images:**
- Use loading="lazy" on thumbnail images
- IntersectionObserver for additional optimization
- Placeholder/skeleton while loading

Export class for use in app.js.
All comments in English.
```

### Git Commands:

```bash
git add frontend/js/carousel.js
git commit -m "feat: implement infinite carousel component with lazy loading"
git push
```

---

## Step 19: Frontend - Utilities

### Design System Specs to read first:
- `tech_docs/90.2_perfil_web_uiux_ia.spec` (sanitize HTML mandatory, no internal info exposure)
- `tech_docs/uiux/estandar_componentes_basicos_ia.spec` (modal, alert component patterns)
- `tech_docs/uiux/estandar_colores_ia.spec` (state tokens for notifications: --success, --warning, --error, --info)

### Prompt for AI:

```
Implement frontend/js/utils.js with utility functions:

**Functions:**

1. **formatDuration(seconds)**:
   - Convert seconds to HH:MM:SS or MM:SS format
   - Example: 125 → "2:05"

2. **formatDate(dateString)**:
   - Format ISO date to readable text
   - Example: "2024-01-20" → "Jan 20, 2024"
   - Use English locale

3. **timeAgo(dateString)**:
   - Relative time format
   - Example: "2 hours ago", "3 days ago"

4. **truncateText(text, maxLength)**:
   - Truncate text and add "..." if exceeds maxLength

5. **debounce(func, delay)**:
   - Implement debounce for searches
   - Return debounced function

6. **getYouTubeVideoUrl(videoId)**:
   - Return full URL: `https://www.youtube.com/watch?v=${videoId}`

7. **getYouTubeThumbnail(videoId, quality)**:
   - quality: 'default', 'medium', 'high', 'maxres'
   - Return thumbnail URL

8. **generateDeviceFingerprint()**:
   - Generate unique device hash
   - Uses: navigator.userAgent, screen.width, screen.height, timezone, language
   - Return string hash

9. **showNotification(message, type)**:
   - type: 'success', 'error', 'info', 'warning'
   - Show temporary toast notification (configurable duration)
   - Create DOM element, insert, and remove after timeout
   - Respects current theme (light/dark)

10. **showModal(title, content, buttons)**:
    - Show customizable modal
    - buttons: [{text, onClick, primary}]
    - Return Promise that resolves with clicked button
    - Respects current theme

11. **loadingSpinner(show, containerId?)**:
    - Show/hide loading spinner
    - If containerId, show in that container
    - Otherwise, full-screen overlay
    - Skeleton loading for cards

12. **sanitizeHTML(str)**:
    - Basic XSS protection for any dynamic content
    - Escape HTML entities

All comments in English.
```

### Git Commands:

```bash
git add frontend/js/utils.js
git commit -m "feat: implement utility functions for UI and data formatting"
git push
```

---

## Step 20: Frontend - Main Application

### Design System Specs to read first:
- `tech_docs/uiux/estandar_web_uiux_ia.spec` (responsive, navigation, overall structure)
- `tech_docs/uiux/estandar_componentes_basicos_ia.spec` (all component interactions)
- `tech_docs/90.2_perfil_web_uiux_ia.spec` (security: sanitize all dynamic content)
- `tech_docs/index_uiux_ia.spec` (hierarchy: universals > platform > contextual)

### Prompt for AI:

```
Implement frontend/js/app.js as the main application orchestrator:

**Initialization:**

1. **DOMContentLoaded**:
   - Verify APP_CONFIG is available
   - Initialize APIClient with APP_CONFIG.API_BASE_URL
   - Initialize theme (theme-switcher.js - prevent flash)
   - Execute initAuth()
   - Execute initDevice()
   - Once authenticated and device configured: loadApp()

2. **initAuth()**:
   - Check authentication (auth.js)
   - If not authenticated: show user selector
   - Wait for user to authenticate
   - Setup event listeners for user change

3. **initDevice()**:
   - Detect and register device (device.js)
   - If first time: show device type confirmation modal
   - Apply CSS classes based on device type

4. **loadApp()**:
   - Load user's channels
   - Load user's themes
   - Load recent videos (initial batch)
   - Render main infinite carousel with latest videos
   - Render infinite carousels per theme
   - Setup event listeners for filters and search

**Rendering:**

1. **renderMainCarousel()**:
   - Create Carousel instance with fetch function that calls getLatestVideos
   - The carousel handles its own infinite loading
   - Insert in corresponding section

2. **renderThemeCarousels(themes)**:
   - For each user theme
   - Create Carousel instance with fetch function for that theme
   - Apply theme color to title
   - Each carousel handles its own infinite loading

3. **setupFilters()**:
   - Event listeners on filter checkboxes
   - On change: reload carousels with filters
   - Filters: "Unwatched only", "Last week", "Last month"

4. **setupSearch()**:
   - Event listener on search input (with debounce 300ms)
   - Call searchVideos() API
   - Render results replacing normal carousels
   - "Clear search" button to return to normal view

5. **setupRefresh()**:
   - Button to refresh videos from YouTube API
   - Call /api/channels/refresh
   - Rebuild carousels with new videos
   - Show notification with count of new videos found

**Global state:**
- currentUser
- currentDevice
- channels
- themes
- filters (object with active filter state)
- carousels (array of Carousel instances for cleanup)

**Event listeners:**
- User change → reload everything
- Theme toggle → CSS handles it
- Filters → reload carousels
- Search → replace view
- Window resize → carousels adjust automatically

**Debug (development only):**
- window.appDebug = {getState, reloadVideos, clearCache, getCarousels}

Integrate all previous modules. This is the main file coordinating the entire app.
All comments in English.
```

### Git Commands:

```bash
git add frontend/js/app.js
git commit -m "feat: implement main application orchestration and UI rendering"
git push
```

---

## Step 21: Testing and Debugging

### Prompt for AI:

```
Implement comprehensive testing and debugging tools:

1. **backend/tests/conftest.py**:
   - Pytest fixtures for:
     - Test Flask app (with test config, in-memory SQLite)
     - Test client
     - Sample user, channel, video, theme data
     - Authenticated client (with valid token)
     - Mock YouTube API responses

2. **backend/tests/test_auth.py**:
   - Test login (new user creation, existing user login)
   - Test get users list
   - Test get current user (valid/invalid token)
   - Test update profile
   - Test authentication decorator

3. **backend/tests/test_channels.py**:
   - Test get channels (empty, with subscriptions)
   - Test subscribe (new channel, existing channel)
   - Test unsubscribe
   - Test refresh channels (mock YouTube API)
   - Test get channel videos with pagination

4. **backend/tests/test_videos.py**:
   - Test get latest videos with pagination
   - Test get videos by theme
   - Test mark as watched/unwatched
   - Test search videos with filters
   - Test pagination metadata (has_more, next_offset)

5. **backend/tests/test_themes.py**:
   - Test CRUD operations for themes
   - Test add/remove channels from themes
   - Test user isolation (can't modify other user's themes)

6. **backend/tests/test_devices.py**:
   - Test device registration
   - Test device detection algorithm
   - Test set device type
   - Test device deletion

7. **backend/seed_db.py**:
   - Create sample users (user1, user2)
   - Create sample channels (use real YouTube channel IDs)
   - Create sample themes
   - Associate channels to users and themes
   - Mark some videos as watched
   - Command: python seed_db.py

8. **backend/pytest.ini** (root):
   - Configure pytest settings
   - Test discovery paths
   - Markers for slow tests

All tests must:
- Be independent (no test depends on another)
- Clean up after themselves
- Use mocks for external services (YouTube API)
- Test both success and error cases
- Verify error tracking IDs are generated

All comments in English.
```

### Testing:

```bash
cd backend
pytest tests/ -v --tb=short
# All tests must pass before continuing to next step
```

### Git Commands:

```bash
git add backend/tests/ backend/seed_db.py pytest.ini
git commit -m "feat: add comprehensive test suite and data seeding script"
git push
```

---

## Step 22: Deployment Configuration

### Prompt for AI:

```
Prepare the application for deployment on Synology NAS:

## BACKEND (Microservice on NAS)

1. **backend/run_app.sh** (Installer + Launcher):
   ```bash
   #!/bin/bash
   # YouTube Clear View - Backend Installer and Launcher
   # Installs to /volume1/Apps/youtube-clear-view/backend/

   APP_NAME="youtube-clear-view"
   APP_DIR="/volume1/Apps/${APP_NAME}/backend"
   VENV_DIR="${APP_DIR}/venv"

   # Create app directory if not exists
   mkdir -p "${APP_DIR}"
   mkdir -p "${APP_DIR}/logs"

   # Copy files if running from source
   if [ "$(pwd)" != "${APP_DIR}" ]; then
     cp -r ./* "${APP_DIR}/"
   fi

   cd "${APP_DIR}"

   # Create virtual environment if not exists
   if [ ! -d "${VENV_DIR}" ]; then
     echo "Creating virtual environment..."
     python3 -m venv "${VENV_DIR}"
   fi

   # Activate venv
   source "${VENV_DIR}/bin/activate"

   # Install/update dependencies
   echo "Installing dependencies..."
   pip install --upgrade pip
   pip install -r requirements.txt

   # Initialize database (create tables)
   python -c "from app import create_app; app = create_app();
   with app.app_context(): from app.extensions import db; db.create_all();
   print('Database initialized')"

   # Launch with Gunicorn (production)
   echo "Starting YouTube Clear View backend..."
   exec gunicorn --config gunicorn.conf.py wsgi:application
   ```

2. **backend/Dockerfile**:
   - Python 3.11 slim base
   - Install dependencies
   - Copy application code
   - Expose port 5550
   - CMD: gunicorn with config
   - Health check

3. **backend/docker-compose.yml**:
   - Backend service (Python Flask + Gunicorn)
   - Log viewer service (separate container)
   - Persistent volume for SQLite DB
   - Persistent volume for logs (shared between services)
   - Port 5550:5550 (backend, internal only)
   - Port 5551:5551 (log viewer, internal only)
   - Environment variables from .env
   - Restart policy: unless-stopped
   - Health check endpoint

4. **Reverse Proxy Configuration** (backend/nginx-reverse-proxy.conf):
   - HTTPS termination
   - Proxy to backend on port 5550
   - Proxy to log viewer on port 5551
   - Force HTTPS (redirect HTTP → HTTPS)
   - Security headers
   - Example for Synology reverse proxy setup

## LOG VIEWER

5. **log_viewer/run_log_viewer.sh**:
   - Similar to run_app.sh but for log viewer
   - Installs to /volume1/Apps/youtube-clear-view/log_viewer/
   - Runs on port 5551

## FRONTEND

6. **frontend/deploy-to-synology.sh**:
   - Script to copy frontend to Synology via rsync
   - Configurable variables
   - Exclude unnecessary files
   - Set correct permissions

## IMPORTANT NOTES:
- NO ports are exposed directly to internet
- All traffic goes through reverse proxy with HTTPS
- The API URL is https://apiyt.mi-nas.me (proxied to localhost:5550)
- The frontend URL is https://ytcv.mi-nas.me (served from /volume1/web/)
- HTTP is NOT accepted (force redirect to HTTPS)
- All code and comments in English
```

### Git Commands:

```bash
git add backend/run_app.sh backend/Dockerfile backend/docker-compose.yml
git add backend/nginx-reverse-proxy.conf
git add log_viewer/run_log_viewer.sh
git add frontend/deploy-to-synology.sh
git commit -m "chore: add deployment configuration for Synology NAS"
git push
```

---

## Step 23: Technical Documentation

### Prompt for AI:

```
Create comprehensive technical documentation:

1. **docs/api-reference.md**:
   - Complete list of all API endpoints
   - Request/response examples for each
   - Authentication requirements
   - Error response format (with tracking IDs)
   - Pagination format
   - Rate limiting info

2. **docs/architecture.md**:
   - System architecture diagram (text-based)
   - Component descriptions
   - Data flow diagrams
   - Technology stack justification
   - Security architecture (HTTPS, reverse proxy, no exposed ports)
   - Logging architecture

3. **docs/deployment.md**:
   - Prerequisites
   - Step-by-step deployment guide for Synology NAS
   - Docker deployment option
   - Systemd deployment option
   - Reverse proxy setup (Nginx/Synology)
   - HTTPS certificate setup (Let's Encrypt)
   - Frontend deployment
   - Verification checklist
   - Troubleshooting guide

4. **docs/development.md**:
   - Local development setup
   - Project structure explanation
   - How to run tests
   - How to add new endpoints
   - Code style and conventions
   - Commit message format (Conventional Commits)
   - Git workflow

5. **README.md** (updated):
   - Project description
   - Features list
   - Quick start guide
   - Links to detailed docs
   - License (MIT)

All documentation in English.
```

### Git Commands:

```bash
git add docs/ README.md
git commit -m "docs: add comprehensive technical documentation"
git push
```

---

## Environment Variables (.env)

```bash
# ===========================================
# YouTube Clear View - Configuration
# ===========================================

# Flask Configuration
FLASK_SECRET_KEY=your-super-secret-key-here
FLASK_PORT=5550
FLASK_HOST=0.0.0.0
FLASK_DEBUG=False

# Database
DATABASE_URI=sqlite:///youtube_clear_view.db

# YouTube API
YOUTUBE_API_KEY=your-google-cloud-console-api-key

# CORS - IMPORTANT: Frontend is served via reverse proxy
# All connections are HTTPS
CORS_ORIGINS=https://ytcv.mi-nas.me,https://apiyt.mi-nas.me

# Gunicorn
GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=120

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
LOG_MAX_SIZE=10485760
LOG_BACKUP_COUNT=5

# Log Viewer (separate service)
LOG_VIEWER_USER=admin
LOG_VIEWER_PASSWORD=your-secure-log-password
LOG_VIEWER_PORT=5551

# Cache
CACHE_TTL=3600
```

**Important notes:**
- `CORS_ORIGINS`: Only HTTPS URLs (no HTTP accepted from internet)
- `LOG_LEVEL`: Controls verbosity (DEBUG shows everything, CRITICAL shows only critical)
- `LOG_VIEWER_USER/PASSWORD`: Credentials for accessing the log viewer web interface
- Separate multiple CORS origins with commas
- NO trailing slash in URLs
- All internet-facing connections use HTTPS via reverse proxy

---

## Implementation Checklist

**Backend:**
- [x] Step 1: Initial project structure (modular)
- [x] Step 2: Database models (split by domain)
- [ ] Step 3: Configuration, extensions, logging system
- [ ] Step 4: YouTube API service with caching
- [ ] Step 5: Routes - Authentication
- [ ] Step 6: Routes - Channels
- [ ] Step 7: Routes - Videos (with pagination for infinite scroll)
- [ ] Step 8: Routes - Themes
- [ ] Step 9: Routes - Devices

**Log Viewer:**
- [ ] Step 10: Separate log viewer microservice

**Frontend:**
- [ ] Step 11: Configuration (HTTPS URLs)
- [ ] Step 12: HTML base + friendly error pages
- [ ] Step 13: CSS responsive (light/dark theme, adaptive text)
- [ ] Step 14: API Client
- [ ] Step 15: Authentication
- [ ] Step 16: Device detection
- [ ] Step 17: Theme switcher (light/dark)
- [ ] Step 18: Infinite carousel component
- [ ] Step 19: Utilities
- [ ] Step 20: Main application

**Testing & Deployment:**
- [ ] Step 21: Comprehensive test suite
- [ ] Step 22: Deployment configuration (Gunicorn, Docker, reverse proxy)
- [ ] Step 23: Technical documentation

**Post-deployment:**
- [ ] Configure .env with real data
- [ ] Setup reverse proxy (HTTPS with Let's Encrypt)
- [ ] Deploy backend (Docker or run_app.sh)
- [ ] Deploy log viewer
- [ ] Deploy frontend to /volume1/web/youtube-clear-view/
- [ ] Verify HTTPS working correctly
- [ ] Verify CORS configured correctly
- [ ] Obtain YouTube API key
- [ ] Create first user
- [ ] Subscribe to test channels
- [ ] Run full test suite

---

## Key Implementation Requirements

### Code Standards
- **Language**: All code, comments, variables, functions, and documentation in English
- **Comments**: Comprehensive English comments explaining logic throughout all code
- **Testing**: Run tests after implementing each step. Do not proceed if tests fail.
- **Error handling**: All routes wrapped in try-catch. Errors logged with tracking numbers. Clean responses to users.

### Security
- HTTPS only for internet-facing connections
- No ports exposed directly (reverse proxy handles routing)
- HTTP Basic Auth for log viewer
- httpOnly + Secure cookies for API auth (no tokens in JavaScript/localStorage)
- Input validation and sanitization (sanitizeHTML for all dynamic content)
- Rate limiting on public endpoints
- No sensitive information in error responses
- CORS with explicit origins and credentials support
- SameSite=Lax cookies to prevent CSRF

### Performance
- Lazy loading of images
- Infinite scroll with pagination (no loading all videos at once)
- In-memory caching for YouTube API responses
- Database indexes on frequently queried fields
- Efficient pagination with offset/limit
- Image compression and responsive thumbnails

### UI/UX
- Light theme default, dark theme option
- Adaptive text sizing (clamp() for mobile to TV)
- Friendly error pages (not scary technical messages)
- Smooth animations and transitions
- Infinite carousel (loads more as you scroll)
- Toast notifications for actions
- Loading skeletons while fetching

---

## Git Commit Format (Conventional Commits)

```
<type>: <description in English>

Types:
- feat: new feature
- fix: bug fix
- docs: documentation changes
- style: formatting, missing semicolons, etc.
- refactor: code refactoring
- test: adding tests
- chore: maintenance tasks
- perf: performance improvements
```

---

**Project ready to begin!**

Follow the steps in order, run tests after each step, and make descriptive commits following Conventional Commits.
