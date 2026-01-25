#!/bin/bash
# Local development runner for backend + frontend.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${ROOT_DIR}"

if [ ! -f "backend/.env" ]; then
  cp "backend/.env.example" "backend/.env"
  echo "Created backend/.env. Update FLASK_SECRET_KEY and CORS_ORIGINS=http://localhost:8080."
  echo "Set YOUTUBE_API_KEY or FLASK_DEBUG=true for local use."
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r backend/requirements.txt

python -m flask --app backend/app run --port 5550 &
BACKEND_PID=$!

cleanup() {
  kill "${BACKEND_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Backend running on http://localhost:5550"

echo "Starting frontend on http://localhost:8080"
cd frontend
python3 -m http.server 8080
