#!/bin/bash
# =============================================================================
# Logging utilities for run scripts
# Source this file: source "$(dirname "${BASH_SOURCE[0]}")/lib/logging.sh"
# =============================================================================

# Colors for terminal output
readonly LOG_RED='\033[0;31m'
readonly LOG_GREEN='\033[0;32m'
readonly LOG_YELLOW='\033[1;33m'
readonly LOG_BLUE='\033[0;34m'
readonly LOG_NC='\033[0m' # No Color

# Global log file path (set by init_run_log)
RUN_LOG_FILE=""

# Initialize run log
# Usage: init_run_log "script_name" "/path/to/logs/app_run"
init_run_log() {
    local script_name="$1"
    local log_dir="$2"
    local timestamp
    timestamp=$(date '+%Y%m%d_%H%M%S')

    mkdir -p "${log_dir}"
    RUN_LOG_FILE="${log_dir}/${script_name}_${timestamp}.log"

    # Write header
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

# Log message to both terminal and file
# Usage: log_info "message"
log_info() {
    local msg="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${LOG_BLUE}[INFO]${LOG_NC} ${msg}"
    [[ -n "${RUN_LOG_FILE}" ]] && echo "[${timestamp}] [INFO] ${msg}" >> "${RUN_LOG_FILE}"
}

log_success() {
    local msg="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${LOG_GREEN}[OK]${LOG_NC} ${msg}"
    [[ -n "${RUN_LOG_FILE}" ]] && echo "[${timestamp}] [OK] ${msg}" >> "${RUN_LOG_FILE}"
}

log_warn() {
    local msg="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${LOG_YELLOW}[WARN]${LOG_NC} ${msg}"
    [[ -n "${RUN_LOG_FILE}" ]] && echo "[${timestamp}] [WARN] ${msg}" >> "${RUN_LOG_FILE}"
}

log_error() {
    local msg="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${LOG_RED}[ERROR]${LOG_NC} ${msg}" >&2
    [[ -n "${RUN_LOG_FILE}" ]] && echo "[${timestamp}] [ERROR] ${msg}" >> "${RUN_LOG_FILE}"
}

# Log command output (captures both stdout and stderr)
# Usage: log_cmd "description" command arg1 arg2 ...
log_cmd() {
    local desc="$1"
    shift
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    log_info "${desc}..."

    if [[ -n "${RUN_LOG_FILE}" ]]; then
        echo "[${timestamp}] [CMD] $*" >> "${RUN_LOG_FILE}"
        if "$@" >> "${RUN_LOG_FILE}" 2>&1; then
            log_success "${desc} completed"
            return 0
        else
            local exit_code=$?
            log_error "${desc} failed (exit code: ${exit_code})"
            return ${exit_code}
        fi
    else
        if "$@"; then
            log_success "${desc} completed"
            return 0
        else
            local exit_code=$?
            log_error "${desc} failed (exit code: ${exit_code})"
            return ${exit_code}
        fi
    fi
}

# Log environment info (without secrets)
log_environment() {
    log_info "Environment info:"
    {
        echo ""
        echo "--- System ---"
        echo "OS: $(uname -s) $(uname -r)"
        echo "Architecture: $(uname -m)"
        echo "Python: $(python3 --version 2>/dev/null || echo 'not found')"
        echo "Pip: $(python3 -m pip --version 2>/dev/null || echo 'not found')"
        echo ""
        echo "--- Configuration (non-sensitive) ---"
        echo "FLASK_HOST: ${FLASK_HOST:-not set}"
        echo "FLASK_PORT: ${FLASK_PORT:-not set}"
        echo "FLASK_DEBUG: ${FLASK_DEBUG:-not set}"
        echo "PROD: ${PROD:-not set}"
        echo "LOG_LEVEL: ${LOG_LEVEL:-not set}"
        echo "LOG_FILE: ${LOG_FILE:-not set}"
        echo "OLLAMA_API_URL: ${OLLAMA_API_URL:-not set}"
        echo "OLLAMA_MODEL: ${OLLAMA_MODEL:-not set}"
        echo ""
    } >> "${RUN_LOG_FILE}"
}

# Log pip install with full output
# Usage: log_pip_install "/path/to/venv/bin/python" "requirements.txt"
log_pip_install() {
    local venv_python="$1"
    local requirements="$2"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    log_info "Installing dependencies from ${requirements}..."

    if [[ -n "${RUN_LOG_FILE}" ]]; then
        echo "" >> "${RUN_LOG_FILE}"
        echo "[${timestamp}] [PIP] Installing from ${requirements}" >> "${RUN_LOG_FILE}"
        echo "--- pip install output ---" >> "${RUN_LOG_FILE}"

        if "${venv_python}" -m pip install -r "${requirements}" >> "${RUN_LOG_FILE}" 2>&1; then
            echo "--- end pip install ---" >> "${RUN_LOG_FILE}"
            echo "" >> "${RUN_LOG_FILE}"
            log_success "Dependencies installed"
            return 0
        else
            local exit_code=$?
            echo "--- pip install FAILED ---" >> "${RUN_LOG_FILE}"
            echo "" >> "${RUN_LOG_FILE}"
            log_error "Dependency installation failed (exit code: ${exit_code})"
            log_error "Check log file for details: ${RUN_LOG_FILE}"
            return ${exit_code}
        fi
    else
        "${venv_python}" -m pip install -r "${requirements}"
    fi
}

# Log venv creation
# Usage: log_venv_create "/path/to/venv"
log_venv_create() {
    local venv_path="$1"

    if [ -d "${venv_path}" ]; then
        log_info "Virtual environment exists: ${venv_path}"
        return 0
    fi

    log_info "Creating virtual environment: ${venv_path}"

    if [[ -n "${RUN_LOG_FILE}" ]]; then
        if python3 -m venv "${venv_path}" >> "${RUN_LOG_FILE}" 2>&1; then
            log_success "Virtual environment created"
            return 0
        else
            local exit_code=$?
            log_error "Failed to create virtual environment"
            return ${exit_code}
        fi
    else
        python3 -m venv "${venv_path}"
    fi
}

# Finalize log
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

# Cleanup old logs (keep last N days)
# Usage: cleanup_old_logs "/path/to/logs/app_run" 30
cleanup_old_logs() {
    local log_dir="$1"
    local days="${2:-30}"

    if [[ -d "${log_dir}" ]]; then
        find "${log_dir}" -name "*.log" -type f -mtime "+${days}" -delete 2>/dev/null || true
    fi
}
