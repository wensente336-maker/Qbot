#!/usr/bin/env bash
# PostgreSQL 每日备份：容器内 pg_dump → gzip，保留 14 天，并做完整性校验。
# 失败会通过飞书群机器人告警；配好 /etc/zmt/storage.env 的 OFFSITE_CMD 后自动推异地。
# 由 /etc/cron.d/zmt-backup 每日 03:45 调用，也可手动执行。
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/zmt-workbench/backups/db}"
KEEP_DAYS="${KEEP_DAYS:-14}"
CONTAINER="${CONTAINER:-zmt-postgres}"
DB_USER="${DB_USER:-zmt}"
DB_NAME="${DB_NAME:-zmt}"
STORAGE_ENV="${STORAGE_ENV:-/etc/zmt/storage.env}"
ALERT_SCRIPT="/opt/zmt-workbench/infra/scripts/zmt_alert.py"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${BACKUP_DIR}/zmt-${STAMP}.sql.gz"

notify() {
  python3 "$ALERT_SCRIPT" "$*" >/dev/null 2>&1 || true
}

on_error() {
  local code=$?
  echo "[$(date '+%F %T')] backup failed (exit=$code)" >&2
  notify "数据库备份失败：host=$(hostname) exit=$code"
}
trap on_error ERR

mkdir -p "$BACKUP_DIR"

# 先写临时文件，校验通过再改名，避免半截备份被当成可用备份
docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges \
  | gzip -6 > "${OUT}.tmp"
gzip -t "${OUT}.tmp"
mv "${OUT}.tmp" "$OUT"

SIZE="$(du -h "$OUT" | cut -f1)"
echo "[$(date '+%F %T')] backup ok: ${OUT} (${SIZE})"

# 异地副本（预留）：在 /etc/zmt/storage.env 里配置 OFFSITE_CMD，$1 为备份文件路径
if [ -f "$STORAGE_ENV" ]; then
  # shellcheck disable=SC1090
  . "$STORAGE_ENV"
fi
if [ -n "${OFFSITE_CMD:-}" ]; then
  if bash -c "$OFFSITE_CMD" zmt-backup "$OUT"; then
    echo "[$(date '+%F %T')] offsite ok"
  else
    echo "[$(date '+%F %T')] offsite failed: ${OUT}" >&2
    notify "数据库异地备份失败：${OUT}（本地副本已保留）"
  fi
else
  echo "[$(date '+%F %T')] offsite skipped: OFFSITE_CMD 未配置（/etc/zmt/storage.env）"
fi

find "$BACKUP_DIR" -name 'zmt-*.sql.gz' -type f -mtime +"${KEEP_DAYS}" -delete
echo "[$(date '+%F %T')] retained: $(find "$BACKUP_DIR" -name 'zmt-*.sql.gz' -type f | wc -l) file(s)"
