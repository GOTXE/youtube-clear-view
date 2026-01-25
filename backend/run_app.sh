#!/bin/bash
# YT Clear View - Backend Installer and Launcher
# Installs to /volume1/Apps/yt-clear-view/backend/

APP_NAME="yt-clear-view"
APP_DIR="/volume1/Apps/${APP_NAME}/backend"
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

# Initialize database (create tables).
python -c "from app import create_app; app = create_app();\nwith app.app_context():\n    from app.extensions import db; db.create_all();\nprint('Database initialized')"

# Launch with Gunicorn (production).
echo "Starting YT Clear View backend..."
exec gunicorn --config gunicorn.conf.py wsgi:application
