#!/bin/bash
# Production runner for backend + log viewer (use a real web server for frontend).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"

# Load logging utilities
source "${SCRIPT_DIR}/lib/logging.sh"

cd "${ROOT_DIR}"

# Initialize run log
init_run_log "run_prod" "${ROOT_DIR}/logs/app_run"
cleanup_old_logs "${ROOT_DIR}/logs/app_run" 30

# Check for .env file
if [ ! -f "backend/.env" ]; then
    log_error "Missing backend/.env. Copy backend/.env.example and fill it first."
    finalize_run_log 1
    exit 1
fi

log_info "Loading environment from backend/.env"
set -a
source "backend/.env"
set +a

PROD_MODE="${PROD:-true}"
export PROD="${PROD_MODE}"

LOG_FILE_PATH="${LOG_FILE:-logs/app.log}"
if [[ "${LOG_FILE_PATH}" != /* ]]; then
    LOG_FILE_PATH="${ROOT_DIR}/${LOG_FILE_PATH}"
fi
mkdir -p "$(dirname "${LOG_FILE_PATH}")"

# Log environment info
log_environment

# Create/check venv
log_venv_create "${ROOT_DIR}/.venv"

VENV_PY="${ROOT_DIR}/.venv/bin/python"
log_cmd "Ensuring pip is up to date" "${VENV_PY}" -m ensurepip --upgrade || true

# Install dependencies
log_pip_install "${VENV_PY}" "backend/requirements.txt"
log_pip_install "${VENV_PY}" "log_viewer/requirements.txt"

# Configure frontend if needed
CONFIG_TEMPLATE="${ROOT_DIR}/frontend/config.example.js"
CONFIG_TARGET="${ROOT_DIR}/frontend/config.js"
if [[ -f "${CONFIG_TEMPLATE}" && ! -f "${CONFIG_TARGET}" ]]; then
    cp "${CONFIG_TEMPLATE}" "${CONFIG_TARGET}"
    API_BASE_URL_VALUE="${API_BASE_URL:-}"
    if [[ -n "${API_BASE_URL_VALUE}" ]]; then
        API_BASE_URL_VALUE="${API_BASE_URL_VALUE}" CONFIG_TARGET="${CONFIG_TARGET}" python3 - <<'PY'
from pathlib import Path
import os

config_path = Path(os.environ["CONFIG_TARGET"])
api_base_url = os.environ["API_BASE_URL_VALUE"]
text = config_path.read_text(encoding="utf-8")
lines = []
for line in text.splitlines():
    if "API_BASE_URL:" in line:
        indent = line.split("API_BASE_URL")[0]
        line = f"{indent}API_BASE_URL: '{api_base_url}',"
    lines.append(line)
config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
        log_success "Frontend config updated with API_BASE_URL=${API_BASE_URL_VALUE}"
    fi
fi

export LOG_FILE="${LOG_FILE_PATH}"
export LOG_VIEWER_USER="${LOG_VIEWER_USER:-admin}"
export LOG_VIEWER_PASSWORD="${LOG_VIEWER_PASSWORD:-admin}"

BACKEND_HOST="${FLASK_HOST:-0.0.0.0}"
BACKEND_PORT="${FLASK_PORT:-5550}"

# Start backend with gunicorn
log_info "Starting backend with Gunicorn..."
(
    cd backend
    exec "${ROOT_DIR}/.venv/bin/gunicorn" --config gunicorn.conf.py wsgi:application --bind "${BACKEND_HOST}:${BACKEND_PORT}"
) &
BACKEND_PID=$!
log_success "Backend started (PID: ${BACKEND_PID})"

# Start log viewer with gunicorn
log_info "Starting log viewer with Gunicorn..."
(
    cd log_viewer
    exec "${ROOT_DIR}/.venv/bin/gunicorn" --bind 0.0.0.0:5551 wsgi:application
) &
LOG_VIEWER_PID=$!
log_success "Log viewer started (PID: ${LOG_VIEWER_PID})"

cleanup() {
    log_info "Shutting down services..."
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
    kill "${LOG_VIEWER_PID}" >/dev/null 2>&1 || true
    finalize_run_log 0
}
trap cleanup EXIT

log_info "=============================================="
log_info "Production mode: ${PROD_MODE}"
log_info "Backend: http://${BACKEND_HOST}:${BACKEND_PORT}"
log_info "Log viewer: http://localhost:5551/logs"
log_info "Serve frontend with nginx pointing to frontend/"
log_info "=============================================="
log_info "Run log: ${RUN_LOG_FILE}"

wait
