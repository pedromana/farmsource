#!/usr/bin/env bash
set -euo pipefail

compose_files=(-f docker-compose.yml -f docker-compose.production.yml)
backup_dir="${BACKUP_DIR:-backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
filename="${backup_dir}/farmsource-${timestamp}.dump"

mkdir -p "$backup_dir"

docker compose "${compose_files[@]}" exec -T db pg_dump \
  -U "${POSTGRES_USER:-farmsource}" \
  -d "${POSTGRES_DB:-farmsource}" \
  -Fc \
  > "$filename"

echo "$filename"
