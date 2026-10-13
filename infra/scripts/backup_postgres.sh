#!/usr/bin/env bash
# Daily PostgreSQL backup with 14-day rotation.
# crontab -e (user domicile):  15 3 * * * /opt/domicilesecure/app/infra/scripts/backup_postgres.sh
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/domicilesecure/backups}"
DB_NAME="${DB_NAME:-domicilesecure}"
KEEP_DAYS="${KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
file="$BACKUP_DIR/${DB_NAME}_$(date +%Y%m%d_%H%M%S).dump"

pg_dump --format=custom --no-owner "$DB_NAME" > "$file"
chmod 600 "$file"
find "$BACKUP_DIR" -name "${DB_NAME}_*.dump" -mtime +"$KEEP_DAYS" -delete

echo "Backup written to $file"
# Restore: pg_restore --clean --no-owner -d domicilesecure <file>
