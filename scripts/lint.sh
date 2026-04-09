#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ran_any=false
frontend_eslint_config=false

if compgen -G "${repo_root}/frontend/eslint.config.*" >/dev/null; then
  frontend_eslint_config=true
elif compgen -G "${repo_root}/frontend/.eslintrc*" >/dev/null; then
  frontend_eslint_config=true
fi

if [[ -x "${repo_root}/.venv/bin/ruff" ]]; then
  "${repo_root}/.venv/bin/ruff" check "${repo_root}/backend"
  ran_any=true
elif command -v ruff >/dev/null 2>&1; then
  ruff check "${repo_root}/backend"
  ran_any=true
fi

if [[ "${frontend_eslint_config}" == true ]] && [[ -x "${repo_root}/frontend/node_modules/.bin/eslint" ]]; then
  "${repo_root}/frontend/node_modules/.bin/eslint" "${repo_root}/frontend/js" "${repo_root}/frontend/tests"
  ran_any=true
elif [[ "${frontend_eslint_config}" == true ]] && command -v eslint >/dev/null 2>&1; then
  eslint "${repo_root}/frontend/js" "${repo_root}/frontend/tests"
  ran_any=true
fi

if [[ "${ran_any}" == false ]]; then
  echo "No lint tooling configured yet; skipping lint."
fi
