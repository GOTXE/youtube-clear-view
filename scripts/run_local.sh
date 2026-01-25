#!/bin/bash
# Local development runner for backend + frontend + log viewer.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${ROOT_DIR}"

if [ ! -f "backend/.env" ]; then
  cp "backend/.env.example" "backend/.env"
  echo "Created backend/.env. Update FLASK_SECRET_KEY and CORS_ORIGINS=http://localhost:8080."
  echo "Set YOUTUBE_API_KEY or FLASK_DEBUG=true for local use."
  exit 1
fi

set -a
source "backend/.env"
set +a

LOG_FILE_PATH="${LOG_FILE:-logs/app.log}"
if [[ "${LOG_FILE_PATH}" != /* ]]; then
  LOG_FILE_PATH="${ROOT_DIR}/${LOG_FILE_PATH}"
fi

mkdir -p "$(dirname "${LOG_FILE_PATH}")"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r backend/requirements.txt

python -m flask --app backend/app run --port 5550 &
BACKEND_PID=$!

deactivate

if [ ! -d "log_viewer/.venv" ]; then
  python3 -m venv log_viewer/.venv
fi

source log_viewer/.venv/bin/activate
pip install -r log_viewer/requirements.txt

LOG_VIEWER_USER="${LOG_VIEWER_USER:-admin}"
LOG_VIEWER_PASSWORD="${LOG_VIEWER_PASSWORD:-admin}"
export LOG_FILE="${LOG_FILE_PATH}"
export LOG_VIEWER_USER
export LOG_VIEWER_PASSWORD

python log_viewer/app.py &
LOG_VIEWER_PID=$!

deactivate

cleanup() {
  kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  kill "${LOG_VIEWER_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Backend running on http://localhost:5550"

echo "Log viewer running on http://localhost:5551/logs"

echo "Starting frontend on http://localhost:8080"
cd frontend
python3 -m http.server 8080
