# ====================== BUILD STAGE ======================
# Instala dependencias Python (puede necesitar compiladores para algunas wheels).
# Este stage no llega a producción.
FROM python:3.11-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ====================== RUNTIME STAGE ======================
# Solo contiene el intérprete, site-packages copiados y el código de la app.
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend

# Copiar únicamente lo instalado en el builder (sin compiladores ni caché)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# Código de la aplicación (sin tests ni archivos de desarrollo, ver .dockerignore)
COPY backend/ ./

RUN mkdir -p /data /logs

# TODO: usuario no-root — requiere un entrypoint que haga chown /data /logs
# al arrancar antes de ceder el proceso a gunicorn (los volúmenes Docker se
# montan como root y sobrescriben el chown hecho en build time).

EXPOSE 5550

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import sys, urllib.request; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:5550/api/health').status == 200 else sys.exit(1)"

CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:application"]
