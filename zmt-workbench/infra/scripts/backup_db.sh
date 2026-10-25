#!/usr/bin/env bash
# PostgreSQL 每日备份：容器内 pg_dump → gzip，保留 14 天，并做完整性校验。
# 由 /etc/cron.d/zmt-backup 每日 03:45 调用，也可手动执行。
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/zmt-workbench/backups/db}"
KEEP_DAYS="${KEEP_DAYS:-14}"
CONTAINER="${CONTAINER:-zmt-postgres}"
DB_USER="${DB_USER:-zmt}"
DB_NAME="${DB_NAME:-zmt}"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${BACKUP_DIR}/zmt-${STAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

# 先写临时文件，校验通过再改名，避免半截备份被当成可用备份
docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges \
  | gzip -6 > "${OUT}.tmp"
gzip -t "${OUT}.tmp"
mv "${OUT}.tmp" "$OUT"

echo "[$(date '+%F %T')] backup ok: ${OUT} ($(du -h "$OUT" | cut -f1))"

find "$BACKUP_DIR" -name 'zmt-*.sql.gz' -type f -mtime +"${KEEP_DAYS}" -delete
echo "[$(date '+%F %T')] retained: $(find "$BACKUP_DIR" -name 'zmt-*.sql.gz' -type f | wc -l) file(s)"
