#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ran_any=false

if [[ -x "${repo_root}/.venv/bin/mypy" ]]; then
  "${repo_root}/.venv/bin/mypy" "${repo_root}/backend/app"
  ran_any=true
elif command -v mypy >/dev/null 2>&1; then
  mypy "${repo_root}/backend/app"
  ran_any=true
fi

if [[ -x "${repo_root}/frontend/node_modules/.bin/tsc" ]] && [[ -f "${repo_root}/frontend/tsconfig.json" ]]; then
  "${repo_root}/frontend/node_modules/.bin/tsc" --noEmit -p "${repo_root}/frontend/tsconfig.json"
  ran_any=true
elif command -v tsc >/dev/null 2>&1 && [[ -f "${repo_root}/frontend/tsconfig.json" ]]; then
  tsc --noEmit -p "${repo_root}/frontend/tsconfig.json"
  ran_any=true
fi

if [[ "${ran_any}" == false ]]; then
  echo "No typecheck tooling configured yet; skipping typecheck."
fi
