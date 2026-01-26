#!/bin/bash
# Production runner for backend + log viewer (use a real web server for frontend).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ ! -f "backend/.env" ]; then
  echo "Missing backend/.env. Copy backend/.env.example and fill it first."
  exit 1
fi

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

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

VENV_PY="${ROOT_DIR}/.venv/bin/python"
"${VENV_PY}" -m ensurepip --upgrade >/dev/null 2>&1 || true
"${VENV_PY}" -m pip install -r backend/requirements.txt
"${VENV_PY}" -m pip install -r log_viewer/requirements.txt

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
  fi
fi

export LOG_FILE="${LOG_FILE_PATH}"
export LOG_VIEWER_USER="${LOG_VIEWER_USER:-admin}"
export LOG_VIEWER_PASSWORD="${LOG_VIEWER_PASSWORD:-admin}"

BACKEND_HOST="${FLASK_HOST:-0.0.0.0}"
BACKEND_PORT="${FLASK_PORT:-5550}"

(
  cd backend
  exec "${ROOT_DIR}/.venv/bin/gunicorn" --config gunicorn.conf.py wsgi:application --bind "${BACKEND_HOST}:${BACKEND_PORT}"
) &
BACKEND_PID=$!

(
  cd log_viewer
  exec "${ROOT_DIR}/.venv/bin/gunicorn" --bind 0.0.0.0:5551 wsgi:application
) &
LOG_VIEWER_PID=$!

cleanup() {
  kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  kill "${LOG_VIEWER_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Production mode: ${PROD_MODE}"
echo "Backend running on http://${BACKEND_HOST}:${BACKEND_PORT}"
echo "Log viewer running on http://localhost:5551/logs"
echo "Serve frontend with a real web server (nginx) and point it to frontend/."

wait
