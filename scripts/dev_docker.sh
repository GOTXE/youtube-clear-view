#!/bin/bash
# Development helper for the local Docker Compose stack.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/infra/compose/compose.v020.yaml"
DB_PATH="/data/youtube_clear_view.db"
DEFAULT_SERVICES=(backend proxy log_viewer)
BACKEND_HEALTH_TIMEOUT_SECONDS=90

usage() {
    cat <<'EOF'
Usage:
  ./scripts/dev_docker.sh up [--build] [--no-cache] [--reset-db] [--backup-db] [service...]
  ./scripts/dev_docker.sh build [--no-cache] [service...]
  ./scripts/dev_docker.sh down
  ./scripts/dev_docker.sh db-reset [--backup]
  ./scripts/dev_docker.sh db-ls

Commands:
  up         Start the dev stack. Defaults to: backend proxy log_viewer
  build      Build one or more services. Defaults to: backend proxy log_viewer
  down       Stop the compose stack
  db-reset   Remove the SQLite database from the Docker volume
  db-ls      List database files inside /data

Options:
  --build    Build before starting services
  --no-cache Build without Docker cache
  --reset-db Remove the current SQLite database before starting
  --backup-db
             Backup youtube_clear_view.db to youtube_clear_view.db.bak before reset
  --backup   Alias for --backup-db when used with db-reset
EOF
}

compose() {
    docker compose -f "${COMPOSE_FILE}" "$@"
}

resolve_services() {
    if [[ "$#" -eq 0 ]]; then
        printf '%s\n' "${DEFAULT_SERVICES[@]}"
        return
    fi
    printf '%s\n' "$@"
}

service_in_list() {
    local needle="$1"
    shift

    local service
    for service in "$@"; do
        if [[ "${service}" == "${needle}" ]]; then
            return 0
        fi
    done
    return 1
}

wait_for_backend_healthy() {
    local timeout_seconds="${1:-${BACKEND_HEALTH_TIMEOUT_SECONDS}}"
    local elapsed=0
    local container_id=""
    local health_status=""

    while [[ "${elapsed}" -lt "${timeout_seconds}" ]]; do
        container_id="$(compose ps -q backend 2>/dev/null || true)"
        if [[ -n "${container_id}" ]]; then
            health_status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}" 2>/dev/null || true)"
            if [[ "${health_status}" == "healthy" ]]; then
                return 0
            fi
            if [[ "${health_status}" == "exited" || "${health_status}" == "dead" ]]; then
                echo "Backend container stopped before becoming healthy." >&2
                compose logs --tail=200 backend || true
                return 1
            fi
        fi

        sleep 2
        elapsed=$((elapsed + 2))
    done

    echo "Timed out waiting for backend to become healthy." >&2
    compose logs --tail=200 backend || true
    return 1
}

db_reset() {
    local backup="${1:-false}"

    compose down

    if [[ "${backup}" == "true" ]]; then
        compose run --rm backend sh -lc "
            if [ -f '${DB_PATH}' ]; then
                mv '${DB_PATH}' '${DB_PATH}.bak'
            fi
            rm -f '${DB_PATH}-shm' '${DB_PATH}-wal'
            ls -l /data
        "
        return
    fi

    compose run --rm backend sh -lc "
        rm -f '${DB_PATH}' '${DB_PATH}-shm' '${DB_PATH}-wal'
        ls -l /data
    "
}

main() {
    if [[ "$#" -eq 0 ]]; then
        usage
        exit 1
    fi

    local command="$1"
    shift

    case "${command}" in
        up)
            local do_build="false"
            local no_cache="false"
            local reset_db="false"
            local backup_db="false"
            local services=()

            while [[ "$#" -gt 0 ]]; do
                case "$1" in
                    --build)
                        do_build="true"
                        ;;
                    --no-cache)
                        no_cache="true"
                        ;;
                    --reset-db)
                        reset_db="true"
                        ;;
                    --backup-db)
                        backup_db="true"
                        ;;
                    -h|--help)
                        usage
                        exit 0
                        ;;
                    *)
                        services+=("$1")
                        ;;
                esac
                shift
            done

            mapfile -t services < <(resolve_services "${services[@]}")

            if [[ "${do_build}" == "true" ]]; then
                if [[ "${no_cache}" == "true" ]]; then
                    compose build --no-cache "${services[@]}"
                else
                    compose build "${services[@]}"
                fi
            fi

            if [[ "${reset_db}" == "true" ]]; then
                db_reset "${backup_db}"
            fi

            if service_in_list proxy "${services[@]}"; then
                compose up -d backend
                wait_for_backend_healthy

                local remaining_services=()
                local service
                for service in "${services[@]}"; do
                    if [[ "${service}" != "backend" ]]; then
                        remaining_services+=("${service}")
                    fi
                done

                if [[ "${#remaining_services[@]}" -gt 0 ]]; then
                    compose up -d "${remaining_services[@]}"
                fi
            else
                compose up -d "${services[@]}"
            fi
            ;;

        build)
            local no_cache="false"
            local services=()

            while [[ "$#" -gt 0 ]]; do
                case "$1" in
                    --no-cache)
                        no_cache="true"
                        ;;
                    -h|--help)
                        usage
                        exit 0
                        ;;
                    *)
                        services+=("$1")
                        ;;
                esac
                shift
            done

            mapfile -t services < <(resolve_services "${services[@]}")
            if [[ "${no_cache}" == "true" ]]; then
                compose build --no-cache "${services[@]}"
            else
                compose build "${services[@]}"
            fi
            ;;

        down)
            compose down
            ;;

        db-reset)
            local backup_db="false"
            while [[ "$#" -gt 0 ]]; do
                case "$1" in
                    --backup|--backup-db)
                        backup_db="true"
                        ;;
                    -h|--help)
                        usage
                        exit 0
                        ;;
                    *)
                        echo "Unknown option for db-reset: $1" >&2
                        usage
                        exit 1
                        ;;
                esac
                shift
            done

            db_reset "${backup_db}"
            ;;

        db-ls)
            compose run --rm backend sh -lc "ls -l /data"
            ;;

        -h|--help|help)
            usage
            ;;

        *)
            echo "Unknown command: ${command}" >&2
            usage
            exit 1
            ;;
    esac
}

main "$@"
