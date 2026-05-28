#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: scripts/restore_postgres.sh backups/farmsource-YYYYMMDDTHHMMSSZ.dump" >&2
  exit 2
fi

backup_file="$1"
if [ ! -f "$backup_file" ]; then
  echo "Backup file not found: $backup_file" >&2
  exit 2
fi

compose_files=(-f docker-compose.yml -f docker-compose.production.yml)

cat "$backup_file" | docker compose "${compose_files[@]}" exec -T db pg_restore \
  -U "${POSTGRES_USER:-farmsource}" \
  -d "${POSTGRES_DB:-farmsource}" \
  --clean \
  --if-exists \
  --no-owner
