#!/usr/bin/env bash

set -euo pipefail

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="${FRONTEND_DIR}/dist"

rm -rf "${DIST_DIR}"
mkdir -p "${DIST_DIR}"
mkdir -p "${DIST_DIR}/css" "${DIST_DIR}/js" "${DIST_DIR}/i18n" "${DIST_DIR}/error"

cp "${FRONTEND_DIR}/index.html" "${DIST_DIR}/index.html"

if [[ -f "${FRONTEND_DIR}/config.js" ]]; then
  cp "${FRONTEND_DIR}/config.js" "${DIST_DIR}/config.js"
else
  cp "${FRONTEND_DIR}/config.example.js" "${DIST_DIR}/config.js"
fi

cp -R "${FRONTEND_DIR}/css/." "${DIST_DIR}/css/"
cp -R "${FRONTEND_DIR}/js/." "${DIST_DIR}/js/"
cp -R "${FRONTEND_DIR}/i18n/." "${DIST_DIR}/i18n/"
cp -R "${FRONTEND_DIR}/error/." "${DIST_DIR}/error/"

printf 'Frontend build ready in %s\n' "${DIST_DIR}"
