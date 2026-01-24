# Minimal Docker image for the log viewer service.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5551

CMD ["gunicorn", "--bind", "0.0.0.0:5551", "wsgi:application"]
