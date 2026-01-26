#!/bin/bash
# Deploy frontend assets to Synology NAS via rsync.

set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST_USER="${DEPLOY_USER:-admin}"
DEST_HOST="${DEPLOY_HOST:-nas.local}"
DEST_PATH="${DEPLOY_PATH:-/volume1/web/yt-clear-view}"

RSYNC_EXCLUDES=(
  --exclude ".git"
  --exclude "node_modules"
  --exclude "*.map"
  --exclude ".DS_Store"
)

rsync -avz --delete "${RSYNC_EXCLUDES[@]}" "${SOURCE_DIR}/" "${DEST_USER}@${DEST_HOST}:${DEST_PATH}/"

ssh "${DEST_USER}@${DEST_HOST}" "chmod -R 755 '${DEST_PATH}'"

echo "Frontend deployed to ${DEST_HOST}:${DEST_PATH}"
