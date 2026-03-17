#!/usr/bin/env bash

set -euo pipefail

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="${FRONTEND_DIR}/dist"

rm -rf "${DIST_DIR}"
mkdir -p "${DIST_DIR}"
mkdir -p "${DIST_DIR}/css" "${DIST_DIR}/js" "${DIST_DIR}/i18n" "${DIST_DIR}/error" "${DIST_DIR}/assets"

cp "${FRONTEND_DIR}/index.html" "${DIST_DIR}/index.html"

if [[ -f "${FRONTEND_DIR}/config.js" ]]; then
  cp "${FRONTEND_DIR}/config.js" "${DIST_DIR}/config.js"
else
  cp "${FRONTEND_DIR}/config.example.js" "${DIST_DIR}/config.js"
fi

TERSER="${FRONTEND_DIR}/node_modules/.bin/terser"
MINIFY_CSS="${FRONTEND_DIR}/scripts/minify-css.mjs"

# Minify JS
if [[ -x "${TERSER}" ]]; then
  for f in "${FRONTEND_DIR}/js/"*.js; do
    name="$(basename "$f")"
    "${TERSER}" "$f" -o "${DIST_DIR}/js/${name}" --compress drop_console=true --mangle
  done
  "${TERSER}" "${DIST_DIR}/config.js" -o "${DIST_DIR}/config.js" --compress --mangle
  printf 'JS minified\n'
else
  cp -R "${FRONTEND_DIR}/js/." "${DIST_DIR}/js/"
  printf 'JS copied (terser not available)\n'
fi

# Minify CSS
if command -v node &>/dev/null && [[ -f "${MINIFY_CSS}" ]]; then
  node "${MINIFY_CSS}" "${FRONTEND_DIR}/css" "${DIST_DIR}/css"
else
  cp -R "${FRONTEND_DIR}/css/." "${DIST_DIR}/css/"
  printf 'CSS copied (node not available)\n'
fi

# Copy remaining assets
cp -R "${FRONTEND_DIR}/i18n/." "${DIST_DIR}/i18n/"
cp -R "${FRONTEND_DIR}/error/." "${DIST_DIR}/error/"
cp -R "${FRONTEND_DIR}/assets/." "${DIST_DIR}/assets/"
cp "${FRONTEND_DIR}/manifest.json" "${DIST_DIR}/manifest.json"
cp "${FRONTEND_DIR}/favicon.svg" "${DIST_DIR}/favicon.svg"

# Minificar sw.js si terser está disponible
if [[ -x "${TERSER}" ]]; then
  "${TERSER}" "${FRONTEND_DIR}/sw.js" -o "${DIST_DIR}/sw.js" --compress --mangle
else
  cp "${FRONTEND_DIR}/sw.js" "${DIST_DIR}/sw.js"
fi

printf 'Frontend build ready in %s\n' "${DIST_DIR}"
