#!/bin/bash
# Local development runner for backend + frontend + log viewer.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${ROOT_DIR}"

if [ ! -f "backend/.env" ]; then
  cp "backend/.env.example" "backend/.env"
  echo "Created backend/.env. Update FLASK_SECRET_KEY and CORS_ORIGINS=http://localhost:8080."
  echo "Set YT_API_KEY or FLASK_DEBUG=true for local use."
  exit 1
fi

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

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

VENV_PY="${ROOT_DIR}/.venv/bin/python"
"${VENV_PY}" -m ensurepip --upgrade >/dev/null 2>&1 || true
"${VENV_PY}" -m pip install -r backend/requirements.txt

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
fi

"${VENV_PY}" -m flask --app backend/app run --host "${FLASK_RUN_HOST}" --port "${FLASK_RUN_PORT}" &
BACKEND_PID=$!

if [ ! -d "log_viewer/.venv" ]; then
  python3 -m venv log_viewer/.venv
fi

LOG_VENV_PY="${ROOT_DIR}/log_viewer/.venv/bin/python"
"${LOG_VENV_PY}" -m ensurepip --upgrade >/dev/null 2>&1 || true
"${LOG_VENV_PY}" -m pip install -r log_viewer/requirements.txt

LOG_VIEWER_USER="${LOG_VIEWER_USER:-admin}"
LOG_VIEWER_PASSWORD="${LOG_VIEWER_PASSWORD:-admin}"
export LOG_FILE="${LOG_FILE_PATH}"
export LOG_VIEWER_USER
export LOG_VIEWER_PASSWORD

"${LOG_VENV_PY}" log_viewer/app.py &
LOG_VIEWER_PID=$!

cleanup() {
  kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  kill "${LOG_VIEWER_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Mode: ${MODE_LABEL}"
echo "Backend running on http://${FLASK_RUN_HOST}:${FLASK_RUN_PORT}"

echo "Log viewer running on http://localhost:5551/logs"

echo "Frontend config API_BASE_URL=${API_BASE_URL_VALUE}"
echo "Starting frontend on http://localhost:8080"
cd frontend
python3 -m http.server 8080
