#!/bin/bash
# Local development runner for backend + frontend + log viewer.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"

# Load logging utilities
source "${SCRIPT_DIR}/lib/logging.sh"

cd "${ROOT_DIR}"

# Initialize run log
init_run_log "run_local" "${ROOT_DIR}/logs/app_run"
cleanup_old_logs "${ROOT_DIR}/logs/app_run" 30

# Check for .env file
if [ ! -f "backend/.env" ]; then
    cp "backend/.env.example" "backend/.env"
    log_warn "Created backend/.env from example"
    log_error "Update FLASK_SECRET_KEY and CORS_ORIGINS=http://localhost:8080"
    log_error "Set YT_API_KEY or FLASK_DEBUG=true for local use."
    finalize_run_log 1
    exit 1
fi

log_info "Loading environment from backend/.env"
set -a
source "backend/.env"
set +a

PROD_MODE="${PROD:-false}"
MODE_LABEL="dev"
if [[ "${PROD_MODE}" == "true" || "${PROD_MODE}" == "TRUE" || "${PROD_MODE}" == "1" ]]; then
    MODE_LABEL="prod"
fi

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

# Install backend dependencies
log_pip_install "${VENV_PY}" "backend/requirements.txt"

FLASK_RUN_HOST="${FLASK_HOST:-0.0.0.0}"
FLASK_RUN_PORT="${FLASK_PORT:-5550}"

API_BASE_URL_VALUE="${API_BASE_URL:-}"
if [[ -z "${API_BASE_URL_VALUE}" ]]; then
    if [[ "${MODE_LABEL}" == "prod" ]]; then
        API_BASE_URL_VALUE="https://apiyt.mi-nas.me"
    else
        API_BASE_URL_VALUE="http://localhost:${FLASK_RUN_PORT}"
    fi
fi

# Configure frontend
CONFIG_TEMPLATE="${ROOT_DIR}/frontend/config.example.js"
CONFIG_TARGET="${ROOT_DIR}/frontend/config.js"
if [[ -f "${CONFIG_TEMPLATE}" ]]; then
    cp "${CONFIG_TEMPLATE}" "${CONFIG_TARGET}"
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

# Start backend
log_info "Starting Flask backend..."
"${VENV_PY}" -m flask --app backend/app run --host "${FLASK_RUN_HOST}" --port "${FLASK_RUN_PORT}" &
BACKEND_PID=$!
log_success "Backend started (PID: ${BACKEND_PID})"

# Setup log viewer venv
log_venv_create "${ROOT_DIR}/log_viewer/.venv"

LOG_VENV_PY="${ROOT_DIR}/log_viewer/.venv/bin/python"
log_cmd "Ensuring pip for log_viewer" "${LOG_VENV_PY}" -m ensurepip --upgrade || true

# Install log viewer dependencies
log_pip_install "${LOG_VENV_PY}" "log_viewer/requirements.txt"

LOG_VIEWER_USER="${LOG_VIEWER_USER:-admin}"
LOG_VIEWER_PASSWORD="${LOG_VIEWER_PASSWORD:-admin}"
export LOG_FILE="${LOG_FILE_PATH}"
export LOG_VIEWER_USER
export LOG_VIEWER_PASSWORD

# Start log viewer
log_info "Starting log viewer..."
"${LOG_VENV_PY}" log_viewer/app.py &
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
log_info "Mode: ${MODE_LABEL}"
log_info "Backend: http://${FLASK_RUN_HOST}:${FLASK_RUN_PORT}"
log_info "Log viewer: http://localhost:5551/logs"
log_info "Frontend API_BASE_URL: ${API_BASE_URL_VALUE}"
log_info "Starting frontend on http://localhost:8080"
log_info "=============================================="
log_info "Run log: ${RUN_LOG_FILE}"

cd frontend
python3 -m http.server 8080
