-- Security and referential-integrity migration.
-- Run against the selected application database after database/20_database_backup.sql.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS auth_bootstrap_guard (
  guard_id TINYINT UNSIGNED NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (guard_id),
  CONSTRAINT ck_auth_bootstrap_guard_id CHECK (guard_id = 1)
) ENGINE = InnoDB;

-- Existing installations created before session provenance was added need the
-- columns below before the application starts writing client metadata.
SET @add_auth_session_ip_address := IF(
  (SELECT COUNT(*)
   FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'auth_session'
     AND column_name = 'ip_address') = 0,
  'ALTER TABLE auth_session ADD COLUMN ip_address VARCHAR(64) NULL AFTER revoked_at',
  'SELECT 1'
);
PREPARE add_auth_session_ip_address_stmt FROM @add_auth_session_ip_address;
EXECUTE add_auth_session_ip_address_stmt;
DEALLOCATE PREPARE add_auth_session_ip_address_stmt;

SET @add_auth_session_user_agent := IF(
  (SELECT COUNT(*)
   FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'auth_session'
     AND column_name = 'user_agent') = 0,
  'ALTER TABLE auth_session ADD COLUMN user_agent VARCHAR(500) NULL AFTER ip_address',
  'SELECT 1'
);
PREPARE add_auth_session_user_agent_stmt FROM @add_auth_session_user_agent;
EXECUTE add_auth_session_user_agent_stmt;
DEALLOCATE PREPARE add_auth_session_user_agent_stmt;

-- Keep legacy type codes compatible while updating visible terminology.
UPDATE non_asset_type
SET type_name = '办公终端'
WHERE LOWER(TRIM(type_code)) IN ('computer', 'pc')
  AND TRIM(type_name) <> '办公终端'
  AND NOT EXISTS (
    SELECT 1
    FROM (
      SELECT non_asset_type_id, type_name
      FROM non_asset_type
    ) AS existing_type
    WHERE existing_type.type_name = '办公终端'
      AND existing_type.non_asset_type_id <> non_asset_type.non_asset_type_id
  );

UPDATE inventory_movement_log
SET type_name = '办公终端',
    source_label = CASE WHEN source_label = '电脑入库' THEN '办公终端入库' ELSE source_label END,
    target_label = CASE WHEN target_label = '电脑入库' THEN '办公终端入库' ELSE target_label END
WHERE TRIM(type_name) IN ('电脑', '办公终端', '办公设备终端')
   OR source_label = '电脑入库'
   OR target_label = '电脑入库';

UPDATE inventory_purchase_log
SET type_name = '办公终端',
    source_label = CASE WHEN source_label = '电脑入库' THEN '办公终端入库' ELSE source_label END
WHERE TRIM(type_name) IN ('电脑', '办公终端', '办公设备终端')
   OR source_label = '电脑入库';

-- Existing installations may contain references created before catalog foreign
-- keys were introduced. Null only missing targets; valid soft-deleted rows stay.
UPDATE computer_asset computer_row
LEFT JOIN it_inventory_model model_row
  ON model_row.model_id = computer_row.inventory_model_id
SET computer_row.inventory_model_id = NULL,
    computer_row.inventory_stock_adjusted = 0
WHERE computer_row.inventory_model_id IS NOT NULL
  AND model_row.model_id IS NULL;

UPDATE employee_monitor_usage usage_row
LEFT JOIN it_inventory_brand brand_row
  ON brand_row.brand_id = usage_row.inventory_brand_id
LEFT JOIN it_inventory_model model_row
  ON model_row.model_id = usage_row.inventory_model_id
SET usage_row.inventory_brand_id = CASE WHEN brand_row.brand_id IS NULL THEN NULL ELSE usage_row.inventory_brand_id END,
    usage_row.inventory_model_id = CASE WHEN model_row.model_id IS NULL THEN NULL ELSE usage_row.inventory_model_id END
WHERE (usage_row.inventory_brand_id IS NOT NULL AND brand_row.brand_id IS NULL)
   OR (usage_row.inventory_model_id IS NOT NULL AND model_row.model_id IS NULL);

UPDATE employee_non_asset_usage usage_row
LEFT JOIN it_inventory_brand brand_row
  ON brand_row.brand_id = usage_row.inventory_brand_id
LEFT JOIN it_inventory_model model_row
  ON model_row.model_id = usage_row.inventory_model_id
SET usage_row.inventory_brand_id = CASE WHEN brand_row.brand_id IS NULL THEN NULL ELSE usage_row.inventory_brand_id END,
    usage_row.inventory_model_id = CASE WHEN model_row.model_id IS NULL THEN NULL ELSE usage_row.inventory_model_id END
WHERE (usage_row.inventory_brand_id IS NOT NULL AND brand_row.brand_id IS NULL)
   OR (usage_row.inventory_model_id IS NOT NULL AND model_row.model_id IS NULL);

SET @add_computer_inventory_model_index := IF(
  (SELECT COUNT(*)
   FROM information_schema.statistics
   WHERE table_schema = DATABASE()
     AND table_name = 'computer_asset'
     AND index_name = 'idx_computer_inventory_model') = 0,
  'ALTER TABLE computer_asset ADD KEY idx_computer_inventory_model (inventory_model_id)',
  'SELECT 1'
);
PREPARE add_computer_inventory_model_index_stmt FROM @add_computer_inventory_model_index;
EXECUTE add_computer_inventory_model_index_stmt;
DEALLOCATE PREPARE add_computer_inventory_model_index_stmt;

SET @add_computer_inventory_model_fk := IF(
  (SELECT COUNT(*)
   FROM information_schema.table_constraints
   WHERE constraint_schema = DATABASE()
     AND table_name = 'computer_asset'
     AND constraint_name = 'fk_computer_inventory_model') = 0,
  'ALTER TABLE computer_asset ADD CONSTRAINT fk_computer_inventory_model FOREIGN KEY (inventory_model_id) REFERENCES it_inventory_model (model_id) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE add_computer_inventory_model_fk_stmt FROM @add_computer_inventory_model_fk;
EXECUTE add_computer_inventory_model_fk_stmt;
DEALLOCATE PREPARE add_computer_inventory_model_fk_stmt;
