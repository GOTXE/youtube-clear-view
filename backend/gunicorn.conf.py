"""Gunicorn configuration for the backend service."""

import os

host = os.getenv("FLASK_HOST", "0.0.0.0")
port = os.getenv("FLASK_PORT", "5550")

bind = f"{host}:{port}"
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
loglevel = os.getenv("LOG_LEVEL", "info").lower()
accesslog = "logs/access.log"
errorlog = "logs/error.log"
timeout = 120
graceful_timeout = 30
