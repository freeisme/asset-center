#!/usr/bin/env bash
set -euo pipefail
umask 077

MYSQLDUMP_BIN="${MYSQLDUMP_BIN:-mysqldump}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-office_asset_app}"
DB_NAME="${DB_NAME:-office_asset_mgmt}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/office-asset-mgmt}"

if [[ -z "${MYSQL_PWD:-}" ]]; then
  read -r -s -p "MySQL password for ${DB_USER}: " MYSQL_PWD
  echo
  export MYSQL_PWD
fi

mkdir -p "${BACKUP_DIR}"
backup_file="${BACKUP_DIR}/${DB_NAME}_$(date +%Y%m%d_%H%M%S)_${RANDOM}.sql"
temporary_file="$(mktemp "${BACKUP_DIR}/.${DB_NAME}.XXXXXX.tmp")"
cleanup() {
  rm -f -- "${temporary_file}"
}
trap cleanup EXIT

"${MYSQLDUMP_BIN}" \
  --host="${DB_HOST}" \
  --port="${DB_PORT}" \
  --user="${DB_USER}" \
  --single-transaction \
  --skip-lock-tables \
  --no-tablespaces \
  --routines \
  --events \
  --triggers \
  --hex-blob \
  --default-character-set=utf8mb4 \
  "${DB_NAME}" > "${temporary_file}"

if [[ ! -s "${temporary_file}" ]]; then
  echo "Backup output is empty; refusing to publish a partial file." >&2
  exit 1
fi

chmod 600 "${temporary_file}"
mv -- "${temporary_file}" "${backup_file}"
trap - EXIT
echo "Backup written to ${backup_file}"
