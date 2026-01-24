"""Gunicorn configuration for the backend service."""

bind = "0.0.0.0:5550"
workers = 2
loglevel = "info"
accesslog = "-"
errorlog = "-"
