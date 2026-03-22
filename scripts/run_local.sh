#!/bin/bash
# Local development runner for backend + frontend.

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
FRONTEND_PORT="${FRONTEND_PORT:-8080}"
FRONTEND_BIND_HOST="${FRONTEND_BIND_HOST:-0.0.0.0}"
DEV_HOST="${DEV_HOST:-localhost}"
FRONTEND_PUBLIC_URL="http://${DEV_HOST}:${FRONTEND_PORT}"

API_BASE_URL_VALUE="${API_BASE_URL:-}"
if [[ -z "${API_BASE_URL_VALUE}" ]]; then
    if [[ "${MODE_LABEL}" == "prod" ]]; then
        API_BASE_URL_VALUE="https://apiyt.mi-nas.me"
    else
        API_BASE_URL_VALUE="http://${DEV_HOST}:${FLASK_RUN_PORT}"
    fi
fi

if [[ "${MODE_LABEL}" != "prod" ]]; then
    if [[ ",${CORS_ORIGINS:-}," != *",${FRONTEND_PUBLIC_URL},"* ]]; then
        log_warn "CORS_ORIGINS does not include ${FRONTEND_PUBLIC_URL}"
    fi

    if [[ "${AUTH_MODE:-local}" == "google" ]]; then
        if [[ "${FRONTEND_URL:-}" != "${FRONTEND_PUBLIC_URL}" ]]; then
            log_warn "FRONTEND_URL is ${FRONTEND_URL:-<empty>} and may not match LAN browsing at ${FRONTEND_PUBLIC_URL}"
        fi
        if [[ "${DEV_HOST}" != "localhost" && "${DEV_HOST}" != "127.0.0.1" ]]; then
            log_warn "Google OAuth web apps usually reject raw private IP redirect URIs; use localhost or an HTTPS hostname/tunnel for OAuth testing"
        fi
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

export LOG_FILE="${LOG_FILE_PATH}"

cleanup() {
    log_info "Shutting down services..."
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
    finalize_run_log 0
}
trap cleanup EXIT

log_info "=============================================="
log_info "Mode: ${MODE_LABEL}"
log_info "Backend: http://${FLASK_RUN_HOST}:${FLASK_RUN_PORT}"
log_info "Backend (LAN): http://${DEV_HOST}:${FLASK_RUN_PORT}"
log_info "Frontend API_BASE_URL: ${API_BASE_URL_VALUE}"
log_info "Frontend: ${FRONTEND_PUBLIC_URL}"
log_info "Frontend bind: http://${FRONTEND_BIND_HOST}:${FRONTEND_PORT}"
log_info "=============================================="
log_info "Run log: ${RUN_LOG_FILE}"

cd frontend
python3 -m http.server "${FRONTEND_PORT}" --bind "${FRONTEND_BIND_HOST}"
