#!/bin/bash
# Genera las imágenes Docker de producción (backend + proxy) para YTCV.
#
# Usar al final de un ciclo de desarrollo, antes de desplegar en el NAS o
# en cualquier entorno de producción. Las imágenes resultantes son multi-stage
# y no contienen dependencias de desarrollo (tests, compiladores, etc.).
#
# La versión se toma del tag Git más reciente (git describe --tags).
# Si no hay tags, usa el hash corto del commit.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/infra/compose/compose.yaml"

VERSION="$(git -C "${ROOT_DIR}" describe --tags --always --dirty 2>/dev/null || echo "dev")"

usage() {
    cat <<'EOF'
Genera las imágenes Docker de producción para YTCV (backend + proxy).

Uso:
  ./scripts/build_prod.sh [opciones]

Opciones:
  --no-cache          Construir sin caché de Docker
  --backup-db         Hacer backup de la BD antes de construir (recomendado)
  --push REGISTRY     Publicar imágenes en un registry (ej: registry.local:5000)
  --version VERSION   Forzar etiqueta de versión (por defecto: git describe --tags)
  -h, --help          Mostrar esta ayuda

Ejemplos:
  ./scripts/build_prod.sh --backup-db
  ./scripts/build_prod.sh --no-cache --backup-db
  ./scripts/build_prod.sh --version v0.3.0 --backup-db
  ./scripts/build_prod.sh --push registry.local:5000 --version v0.3.0
EOF
}

NO_CACHE=""
PUSH_REGISTRY=""
BACKUP_DB="false"
DB_PATH="/data/youtube_clear_view.db"

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --no-cache)   NO_CACHE="--no-cache" ;;
        --backup-db)  BACKUP_DB="true" ;;
        --push)       PUSH_REGISTRY="${2:?--push requiere un argumento}"; shift ;;
        --version)    VERSION="${2:?--version requiere un valor}"; shift ;;
        -h|--help)    usage; exit 0 ;;
        *)            echo "Opción desconocida: $1" >&2; usage; exit 1 ;;
    esac
    shift
done

BACKEND_IMAGE="ytcv-backend:${VERSION}"
PROXY_IMAGE="ytcv-proxy:${VERSION}"

echo "==> Construyendo imágenes de producción"
echo "    Versión : ${VERSION}"
echo "    Backend : ${BACKEND_IMAGE}"
echo "    Proxy   : ${PROXY_IMAGE}"
[[ -n "${NO_CACHE}" ]]      && echo "    Caché   : desactivada"
[[ "${BACKUP_DB}" == "true" ]] && echo "    Backup  : BD incluida"
echo ""

cd "${ROOT_DIR}"

# --- Backup de la BD (opcional) ---
if [[ "${BACKUP_DB}" == "true" ]]; then
    echo "--- Backup de la base de datos..."
    if docker compose -f "${COMPOSE_FILE}" run --rm --no-deps backend \
        sh -c "[ -f '${DB_PATH}' ] && cp '${DB_PATH}' '${DB_PATH}.bak' && echo '  Backup OK: ${DB_PATH}.bak' || echo '  No hay BD en ${DB_PATH}, se omite el backup'"; then
        :
    else
        echo "  AVISO: no se pudo hacer el backup (¿el volumen aún no existe?). Continuando..."
    fi
    echo ""
fi

echo "--- [1/2] Backend..."
# shellcheck disable=SC2086
docker build ${NO_CACHE} \
    -f infra/docker/backend/Dockerfile \
    -t "${BACKEND_IMAGE}" \
    .

echo ""
echo "--- [2/2] Proxy..."
# shellcheck disable=SC2086
docker build ${NO_CACHE} \
    -f infra/docker/proxy/Dockerfile \
    -t "${PROXY_IMAGE}" \
    .

echo ""
echo "==> Tamaño de las imágenes generadas:"
docker images --format "  {{.Repository}}:{{.Tag}}  {{.Size}}" \
    | grep -E "ytcv-(backend|proxy):${VERSION//./\\.}" || true

if [[ -n "${PUSH_REGISTRY}" ]]; then
    BACKEND_REMOTE="${PUSH_REGISTRY}/ytcv-backend:${VERSION}"
    PROXY_REMOTE="${PUSH_REGISTRY}/ytcv-proxy:${VERSION}"

    echo ""
    echo "==> Publicando en ${PUSH_REGISTRY}..."
    docker tag "${BACKEND_IMAGE}" "${BACKEND_REMOTE}"
    docker tag "${PROXY_IMAGE}"   "${PROXY_REMOTE}"
    docker push "${BACKEND_REMOTE}"
    docker push "${PROXY_REMOTE}"
    echo "  OK: ${BACKEND_REMOTE}"
    echo "  OK: ${PROXY_REMOTE}"
fi

echo ""
echo "==> Listo."
echo "    Para arrancar el stack:"
echo "    docker compose -f infra/compose/compose.yaml up -d"
