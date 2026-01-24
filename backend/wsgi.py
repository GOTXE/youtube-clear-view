"""WSGI entry point for Gunicorn."""

from app import create_app

# Expose the WSGI application callable.
application = create_app()
