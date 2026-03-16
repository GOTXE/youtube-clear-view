FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/log_viewer

COPY log_viewer/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY log_viewer/ ./

RUN mkdir -p /logs

EXPOSE 5551

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', 5551)); s.close()"

CMD ["gunicorn", "--bind", "0.0.0.0:5551", "wsgi:application"]
