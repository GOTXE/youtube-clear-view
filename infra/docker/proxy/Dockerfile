FROM debian:bookworm-slim AS frontend-build

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --include=dev

COPY frontend/ ./

RUN cat > config.js <<'EOF'
const APP_CONFIG = {
  API_BASE_URL: '',
  API_VERSION: 'v1',
  REQUEST_TIMEOUT: 30000,
  YT_BASE_URL: 'https://www.youtube.com',
  DEFAULT_PAGE_SIZE: 20,
  VIDEOS_PER_LOAD: 8,
  INITIAL_LOAD_COUNT: 8,
  NOTIFICATION_DURATION: 3000,
  DEFAULT_THEME: 'light',
  DEVICE_TYPES: {
    TV: 'tv',
    TABLET: 'tablet',
    MOBILE: 'mobile',
    DESKTOP: 'desktop'
  },
  BREAKPOINTS: {
    MOBILE_MAX: 767,
    TABLET_MIN: 768,
    TABLET_MAX: 1919,
    TV_MIN: 1920
  }
};

window.APP_CONFIG = APP_CONFIG;
EOF

RUN bash ./build-dist.sh

FROM caddy:2.8-alpine

COPY infra/proxy/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-build /app/frontend/dist /srv

EXPOSE 8080
