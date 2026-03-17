"""Gunicorn configuration for the backend service."""

import os

host = os.getenv("FLASK_HOST", "0.0.0.0")
port = os.getenv("FLASK_PORT", "5550")
log_file = os.getenv("LOG_FILE", "logs/app.log")
log_dir = os.path.dirname(log_file) or "logs"
os.makedirs(log_dir, exist_ok=True)

bind = f"{host}:{port}"
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
loglevel = os.getenv("LOG_LEVEL", "info").lower()
accesslog = os.path.join(log_dir, "access.log")
errorlog = os.path.join(log_dir, "error.log")
timeout = 120
graceful_timeout = 30
