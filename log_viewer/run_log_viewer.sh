#!/bin/bash
# YouTube Clear View - Log Viewer Installer and Launcher
# Installs to /volume1/Apps/youtube-clear-view/log_viewer/

APP_NAME="youtube-clear-view"
APP_DIR="/volume1/Apps/${APP_NAME}/log_viewer"
VENV_DIR="${APP_DIR}/venv"

# Create app directory if not exists.
mkdir -p "${APP_DIR}"
mkdir -p "${APP_DIR}/logs"

# Copy files if running from source.
if [ "$(pwd)" != "${APP_DIR}" ]; then
  cp -r ./* "${APP_DIR}/"
fi

cd "${APP_DIR}"

# Create virtual environment if not exists.
if [ ! -d "${VENV_DIR}" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "${VENV_DIR}"
fi

# Activate venv.
source "${VENV_DIR}/bin/activate"

# Install/update dependencies.
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Launch with Gunicorn (production).
echo "Starting YouTube Clear View log viewer..."
exec gunicorn --bind 0.0.0.0:5551 wsgi:application
