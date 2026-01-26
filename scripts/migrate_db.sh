#!/bin/bash
# Migrate existing SQLite data to new YT naming without losing data.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/backend/.env"

if [ -f "${ENV_FILE}" ]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

DATABASE_URI_VALUE="${DATABASE_URI:-}"

parse_sqlite_path() {
  local uri="$1"
  if [[ "${uri}" == sqlite:////* ]]; then
    echo "${uri#sqlite:////}"
    return
  fi
  if [[ "${uri}" == sqlite:///* ]]; then
    echo "${uri#sqlite:///}"
    return
  fi
  echo ""
}

resolve_path() {
  local path="$1"
  if [[ -z "${path}" ]]; then
    echo ""
    return
  fi
  if [[ "${path}" = /* ]]; then
    echo "${path}"
    return
  fi
  echo "${ROOT_DIR}/${path}"
}

OLD_DB_PATH="${1:-}"
NEW_DB_PATH="${2:-}"

if [[ -z "${OLD_DB_PATH}" || -z "${NEW_DB_PATH}" ]]; then
  parsed_path="$(parse_sqlite_path "${DATABASE_URI_VALUE}")"
  if [[ -z "${parsed_path}" ]]; then
    echo "Usage: $0 <old_db_path> <new_db_path>"
    echo "Or set DATABASE_URI=sqlite:///path.db in backend/.env and run without args."
    exit 1
  fi

  resolved="$(resolve_path "${parsed_path}")"
  if [[ "${resolved}" == *"youtube_clear_view.db"* ]]; then
    OLD_DB_PATH="${resolved}"
    NEW_DB_PATH="${resolved/youtube_clear_view.db/yt_clear_view.db}"
  elif [[ "${resolved}" == *"yt_clear_view.db"* ]]; then
    candidate="${resolved/yt_clear_view.db/youtube_clear_view.db}"
    if [[ -f "${candidate}" ]]; then
      OLD_DB_PATH="${candidate}"
      NEW_DB_PATH="${resolved}"
    else
      OLD_DB_PATH="${resolved}"
      NEW_DB_PATH="${resolved}"
    fi
  else
    OLD_DB_PATH="${resolved}"
    NEW_DB_PATH="${resolved}"
  fi
fi

if [[ -z "${OLD_DB_PATH}" || -z "${NEW_DB_PATH}" ]]; then
  echo "Missing database paths."
  exit 1
fi

if [[ ! -f "${OLD_DB_PATH}" ]]; then
  echo "Old DB not found: ${OLD_DB_PATH}"
  exit 1
fi

if [[ "${OLD_DB_PATH}" != "${NEW_DB_PATH}" ]]; then
  if [[ -f "${NEW_DB_PATH}" && "${FORCE:-}" != "1" ]]; then
    echo "New DB already exists: ${NEW_DB_PATH}"
    echo "Set FORCE=1 to overwrite."
    exit 1
  fi
  mkdir -p "$(dirname "${NEW_DB_PATH}")"
  cp "${OLD_DB_PATH}" "${NEW_DB_PATH}"
fi

PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

export DATABASE_URI="sqlite:///${NEW_DB_PATH}"

cd "${ROOT_DIR}/backend"
"${PYTHON_BIN}" - <<'PY'
from app import create_app
app = create_app()
print("Migration complete.")
PY

cd "${ROOT_DIR}"

if [[ "${OLD_DB_PATH}" != "${NEW_DB_PATH}" ]]; then
  echo "Copied DB to: ${NEW_DB_PATH}"
  echo "Update backend/.env DATABASE_URI to: sqlite:///${NEW_DB_PATH}"
else
  echo "DB migrated in-place: ${NEW_DB_PATH}"
fi
