#!/usr/bin/env bash
set -euo pipefail

: "${MYSQL_DATABASE:?MYSQL_DATABASE must be set}"
: "${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD must be set}"

SEED_DIR="${SEED_DIR:-/seed/bootstrap}"
MYSQL_BIN="${MYSQL_BIN:-mysql}"

mysql_args=(
  --protocol=socket
  --user=root
  "--database=${MYSQL_DATABASE}"
  --default-character-set=utf8mb4
)

# Keep the root password out of the client process arguments. The official
# MySQL image already provides MYSQL_ROOT_PASSWORD only during initialization.
export MYSQL_PWD="${MYSQL_ROOT_PASSWORD}"

if [[ ! "${MYSQL_DATABASE}" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "MYSQL_DATABASE must contain only letters, numbers, and underscores." >&2
  exit 1
fi

sql_files=(
  01_schema.sql
  02_seed_reference_data.sql
  03_views.sql
  04_routines.sql
  10_audit_log.sql
  12_it_inventory.sql
  13_hardening_migration.sql
  14_computer_configuration.sql
  15_inventory_computer_batches.sql
  16_inventory_purchase_log.sql
  17_data_lineage_and_consistency.sql
  18_backfill_computer_inbound_dates.sql
  19_auth_and_settings.sql
  20_database_backup.sql
  21_security_hardening.sql
  22_update_repository_setting.sql
)

for sql_file in "${sql_files[@]}"; do
  if [[ ! -f "${SEED_DIR}/${sql_file}" ]]; then
    echo "Missing database seed file: ${SEED_DIR}/${sql_file}" >&2
    exit 1
  fi
  echo "Applying ${sql_file}"
  sed -E '/^[[:space:]]*USE[[:space:]]+[^;]+;[[:space:]]*$/Id' \
    "${SEED_DIR}/${sql_file}" | "${MYSQL_BIN}" "${mysql_args[@]}"
done

echo "Recording legacy migration baseline"
"${MYSQL_BIN}" "${mysql_args[@]}" -e "
  CREATE TABLE IF NOT EXISTS schema_migration (
    version VARCHAR(128) NOT NULL,
    checksum_sha256 CHAR(64) NOT NULL,
    description VARCHAR(255) NOT NULL DEFAULT '',
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_by VARCHAR(128) NOT NULL DEFAULT '',
    PRIMARY KEY (version)
  ) ENGINE=InnoDB;
  INSERT INTO schema_migration (version, checksum_sha256, description, applied_by)
  VALUES (
    'legacy-20260813',
    SHA2('legacy-20260813', 256),
    'Historical schema baseline recorded by Docker initialization',
    'docker-init'
  )
  ON DUPLICATE KEY UPDATE version = VALUES(version);
"

echo "Database initialization completed: ${MYSQL_DATABASE}"
