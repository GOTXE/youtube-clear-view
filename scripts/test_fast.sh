#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${ROOT_DIR}"
pytest -q backend/tests -m "not slow"
"${ROOT_DIR}/scripts/test_frontend.sh"
