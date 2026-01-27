#!/bin/bash
# YT Clear View - Backend Installer and Launcher
# Installs to /volume1/Apps/yt-clear-view/backend/

set -euo pipefail

APP_NAME="yt-clear-view"
APP_DIR="/volume1/Apps/${APP_NAME}/backend"
VENV_DIR="${APP_DIR}/venv"
RUN_LOG_DIR="${APP_DIR}/logs/app_run"

# =============================================================================
# Inline logging functions (self-contained for NAS deployment)
# =============================================================================
LOG_RED='\033[0;31m'
LOG_GREEN='\033[0;32m'
LOG_YELLOW='\033[1;33m'
LOG_BLUE='\033[0;34m'
LOG_NC='\033[0m'
RUN_LOG_FILE=""

init_run_log() {
    local script_name="$1"
    local log_dir="$2"
    local timestamp
    timestamp=$(date '+%Y%m%d_%H%M%S')
    mkdir -p "${log_dir}"
    RUN_LOG_FILE="${log_dir}/${script_name}_${timestamp}.log"
    {
        echo "=============================================="
        echo "YT Clear View - ${script_name} Run Log"
        echo "=============================================="
        echo "Start time: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "User: $(whoami)"
        echo "Hostname: $(hostname)"
        echo "Working dir: $(pwd)"
        echo "=============================================="
        echo ""
    } >> "${RUN_LOG_FILE}"
    log_info "Run log initialized: ${RUN_LOG_FILE}"
}

log_info() {
    local msg="$1"
    local ts; ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${LOG_BLUE}[INFO]${LOG_NC} ${msg}"
    [[ -n "${RUN_LOG_FILE}" ]] && echo "[${ts}] [INFO] ${msg}" >> "${RUN_LOG_FILE}"
}

log_success() {
    local msg="$1"
    local ts; ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${LOG_GREEN}[OK]${LOG_NC} ${msg}"
    [[ -n "${RUN_LOG_FILE}" ]] && echo "[${ts}] [OK] ${msg}" >> "${RUN_LOG_FILE}"
}

log_warn() {
    local msg="$1"
    local ts; ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${LOG_YELLOW}[WARN]${LOG_NC} ${msg}"
    [[ -n "${RUN_LOG_FILE}" ]] && echo "[${ts}] [WARN] ${msg}" >> "${RUN_LOG_FILE}"
}

log_error() {
    local msg="$1"
    local ts; ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${LOG_RED}[ERROR]${LOG_NC} ${msg}" >&2
    [[ -n "${RUN_LOG_FILE}" ]] && echo "[${ts}] [ERROR] ${msg}" >> "${RUN_LOG_FILE}"
}

log_cmd() {
    local desc="$1"; shift
    local ts; ts=$(date '+%Y-%m-%d %H:%M:%S')
    log_info "${desc}..."
    if [[ -n "${RUN_LOG_FILE}" ]]; then
        echo "[${ts}] [CMD] $*" >> "${RUN_LOG_FILE}"
        if "$@" >> "${RUN_LOG_FILE}" 2>&1; then
            log_success "${desc} completed"
            return 0
        else
            local exit_code=$?
            log_error "${desc} failed (exit code: ${exit_code})"
            return ${exit_code}
        fi
    else
        "$@"
    fi
}

log_environment() {
    log_info "Logging environment info..."
    {
        echo ""
        echo "--- System ---"
        echo "OS: $(uname -s) $(uname -r)"
        echo "Architecture: $(uname -m)"
        echo "Python: $(python3 --version 2>/dev/null || echo 'not found')"
        echo ""
        echo "--- Configuration (non-sensitive) ---"
        echo "FLASK_HOST: ${FLASK_HOST:-not set}"
        echo "FLASK_PORT: ${FLASK_PORT:-not set}"
        echo "PROD: ${PROD:-not set}"
        echo "LOG_LEVEL: ${LOG_LEVEL:-not set}"
        echo "OLLAMA_API_URL: ${OLLAMA_API_URL:-not set}"
        echo "OLLAMA_MODEL: ${OLLAMA_MODEL:-not set}"
        echo ""
    } >> "${RUN_LOG_FILE}"
}

finalize_run_log() {
    local exit_code="${1:-0}"
    if [[ -n "${RUN_LOG_FILE}" ]]; then
        {
            echo ""
            echo "=============================================="
            echo "End time: $(date '+%Y-%m-%d %H:%M:%S')"
            echo "Exit code: ${exit_code}"
            echo "=============================================="
        } >> "${RUN_LOG_FILE}"
    fi
    if [[ "${exit_code}" -eq 0 ]]; then
        log_success "Script completed successfully"
    else
        log_error "Script exited with code: ${exit_code}"
    fi
}

cleanup_old_logs() {
    local log_dir="$1"
    local days="${2:-30}"
    [[ -d "${log_dir}" ]] && find "${log_dir}" -name "*.log" -type f -mtime "+${days}" -delete 2>/dev/null || true
}

# =============================================================================
# Main script
# =============================================================================

# Create app directory if not exists
mkdir -p "${APP_DIR}"
mkdir -p "${APP_DIR}/logs"

# Initialize run log
init_run_log "backend" "${RUN_LOG_DIR}"
cleanup_old_logs "${RUN_LOG_DIR}" 30

# Copy files if running from source
if [ "$(pwd)" != "${APP_DIR}" ]; then
    log_info "Copying files to ${APP_DIR}..."
    cp -r ./* "${APP_DIR}/"
    log_success "Files copied"
fi

cd "${APP_DIR}"

# Load environment if .env exists
if [ -f ".env" ]; then
    log_info "Loading environment from .env"
    set -a
    source ".env"
    set +a
fi

# Log environment info
log_environment

# Create virtual environment if not exists
if [ ! -d "${VENV_DIR}" ]; then
    log_info "Creating virtual environment..."
    if python3 -m venv "${VENV_DIR}" >> "${RUN_LOG_FILE}" 2>&1; then
        log_success "Virtual environment created"
    else
        log_error "Failed to create virtual environment"
        finalize_run_log 1
        exit 1
    fi
else
    log_info "Virtual environment exists: ${VENV_DIR}"
fi

# Activate venv
source "${VENV_DIR}/bin/activate"

# Install/update dependencies
log_info "Installing dependencies..."
{
    echo ""
    echo "--- pip install output ---"
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "--- end pip install ---"
    echo ""
} >> "${RUN_LOG_FILE}" 2>&1
log_success "Dependencies installed"

# Initialize database (create tables)
log_info "Initializing database..."
if python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.extensions import db
    db.create_all()
print('Database initialized')
" >> "${RUN_LOG_FILE}" 2>&1; then
    log_success "Database initialized"
else
    log_error "Database initialization failed"
    finalize_run_log 1
    exit 1
fi

log_info "=============================================="
log_info "Starting YT Clear View backend with Gunicorn..."
log_info "Run log: ${RUN_LOG_FILE}"
log_info "=============================================="

# Launch with Gunicorn (production)
exec gunicorn --config gunicorn.conf.py wsgi:application
