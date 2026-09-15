#!/usr/bin/env bash
set -euo pipefail
umask 077

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
COMPOSE_FILE="${COMPOSE_FILE:-${APP_DIR}/compose.yaml}"
ENV_FILE="${ENV_FILE:-${APP_DIR}/.env}"
BACKUP_DIR="${BACKUP_DIR:-${HOME:-/tmp}/backups/office-asset-mgmt}"
DB_NAME="${DB_NAME:-office_asset_mgmt}"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Compose file not found: ${COMPOSE_FILE}" >&2
  exit 1
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Runtime environment file not found: ${ENV_FILE}" >&2
  exit 1
fi
if [[ ! "${DB_NAME}" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "DB_NAME must contain only letters, numbers, and underscores." >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"
backup_file="${BACKUP_DIR}/${DB_NAME}_$(date +%Y%m%d_%H%M%S)_${RANDOM}.sql.gz"
checksum_file="${backup_file}.sha256"
sql_temporary_file="$(mktemp "${BACKUP_DIR}/.${DB_NAME}.XXXXXX.sql.tmp")"
archive_temporary_file="$(mktemp "${BACKUP_DIR}/.${DB_NAME}.XXXXXX.sql.gz.tmp")"
checksum_temporary_file="$(mktemp "${BACKUP_DIR}/.${DB_NAME}.XXXXXX.sha256.tmp")"
cleanup() {
  rm -f -- "${sql_temporary_file}" "${archive_temporary_file}" "${checksum_temporary_file}"
}
trap cleanup EXIT

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" exec -T db sh -c \
  'MYSQL_PWD="$MYSQL_PASSWORD" exec mysqldump --single-transaction --skip-lock-tables --no-tablespaces --routines --events --triggers --hex-blob -u"$MYSQL_USER" "$MYSQL_DATABASE"' \
  > "${sql_temporary_file}"

if [[ ! -s "${sql_temporary_file}" ]]; then
  echo "Backup output is empty; refusing to publish a partial file." >&2
  exit 1
fi

gzip --stdout -- "${sql_temporary_file}" > "${archive_temporary_file}"
if [[ ! -s "${archive_temporary_file}" ]]; then
  echo "Compressed backup output is empty; refusing to publish a partial file." >&2
  exit 1
fi

sha256sum "${archive_temporary_file}" > "${checksum_temporary_file}"
chmod 600 "${archive_temporary_file}" "${checksum_temporary_file}"
mv -- "${archive_temporary_file}" "${backup_file}"
mv -- "${checksum_temporary_file}" "${checksum_file}"
trap - EXIT
rm -f -- "${sql_temporary_file}"
echo "Backup written to ${backup_file}"
echo "Checksum written to ${checksum_file}"
