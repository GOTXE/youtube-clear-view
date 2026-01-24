# Minimal Docker image for the backend service.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5550

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import sys, urllib.request; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:5550/api/health').status == 200 else sys.exit(1)"

CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:application"]
