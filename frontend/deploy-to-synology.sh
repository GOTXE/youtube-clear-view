#!/bin/bash
# Build and deploy production frontend assets to Synology NAS via rsync.

set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="${SOURCE_DIR}/dist"
DEST_USER="${DEPLOY_USER:-}"
DEST_HOST="${DEPLOY_HOST:-}"
DEST_PORT="${DEPLOY_PORT:-}"
DEST_PATH="${DEPLOY_PATH:-/volume1/web/yt-clear-view}"

if [[ -z "${DEST_USER}" ]]; then
  read -r -p "Synology SSH user: " DEST_USER
fi

if [[ -z "${DEST_USER}" ]]; then
  echo "Deployment user is required." >&2
  exit 1
fi

if [[ -z "${DEST_HOST}" ]]; then
  read -r -p "Synology host: " DEST_HOST
fi

if [[ -z "${DEST_HOST}" ]]; then
  echo "Deployment host is required." >&2
  exit 1
fi

if [[ -z "${DEST_PORT}" ]]; then
  read -r -p "Synology SSH port [22]: " DEST_PORT
fi

DEST_PORT="${DEST_PORT:-22}"

cd "${SOURCE_DIR}"
npm run build

rsync -avz --delete -e "ssh -p ${DEST_PORT}" "${DIST_DIR}/" "${DEST_USER}@${DEST_HOST}:${DEST_PATH}/"

ssh -p "${DEST_PORT}" "${DEST_USER}@${DEST_HOST}" "chmod -R 755 '${DEST_PATH}'"

echo "Frontend dist deployed to ${DEST_HOST}:${DEST_PATH} via port ${DEST_PORT}"
