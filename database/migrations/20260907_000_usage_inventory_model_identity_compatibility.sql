SET NAMES utf8mb4;

-- MySQL 8.4 rejects a STORED generated column based on a column that is
-- referenced by an ON DELETE SET NULL foreign key. Create the indexed key
-- as VIRTUAL first; the following 20260907_001 migration then remains
-- checksum-compatible and only sees the already-created objects.
SET @has_non_asset_usage_model_key = (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_non_asset_usage'
    AND column_name = 'inventory_model_key'
);
SET @add_non_asset_usage_model_key_sql = IF(
  @has_non_asset_usage_model_key = 0,
  'ALTER TABLE employee_non_asset_usage ADD COLUMN inventory_model_key BIGINT UNSIGNED GENERATED ALWAYS AS (COALESCE(inventory_model_id, 0)) VIRTUAL AFTER inventory_model_id',
  'SELECT 1'
);
PREPARE add_non_asset_usage_model_key_stmt FROM @add_non_asset_usage_model_key_sql;
EXECUTE add_non_asset_usage_model_key_stmt;
DEALLOCATE PREPARE add_non_asset_usage_model_key_stmt;

SET @has_monitor_usage_model_key = (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_monitor_usage'
    AND column_name = 'inventory_model_key'
);
SET @add_monitor_usage_model_key_sql = IF(
  @has_monitor_usage_model_key = 0,
  'ALTER TABLE employee_monitor_usage ADD COLUMN inventory_model_key BIGINT UNSIGNED GENERATED ALWAYS AS (COALESCE(inventory_model_id, 0)) VIRTUAL AFTER inventory_model_id',
  'SELECT 1'
);
PREPARE add_monitor_usage_model_key_stmt FROM @add_monitor_usage_model_key_sql;
EXECUTE add_monitor_usage_model_key_stmt;
DEALLOCATE PREPARE add_monitor_usage_model_key_stmt;

SET @has_non_asset_usage_model_key_index = (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_non_asset_usage'
    AND index_name = 'uq_non_asset_usage_item_model'
);
SET @add_non_asset_usage_model_key_index_sql = IF(
  @has_non_asset_usage_model_key_index = 0,
  'ALTER TABLE employee_non_asset_usage ADD UNIQUE KEY uq_non_asset_usage_item_model (employee_id, non_asset_type_id, brand, model, inventory_model_key)',
  'SELECT 1'
);
PREPARE add_non_asset_usage_model_key_index_stmt FROM @add_non_asset_usage_model_key_index_sql;
EXECUTE add_non_asset_usage_model_key_index_stmt;
DEALLOCATE PREPARE add_non_asset_usage_model_key_index_stmt;

SET @has_monitor_usage_model_key_index = (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_monitor_usage'
    AND index_name = 'uq_employee_monitor_model'
);
SET @add_monitor_usage_model_key_index_sql = IF(
  @has_monitor_usage_model_key_index = 0,
  'ALTER TABLE employee_monitor_usage ADD UNIQUE KEY uq_employee_monitor_model (employee_id, display_name, model, inventory_model_key)',
  'SELECT 1'
);
PREPARE add_monitor_usage_model_key_index_stmt FROM @add_monitor_usage_model_key_index_sql;
EXECUTE add_monitor_usage_model_key_index_stmt;
DEALLOCATE PREPARE add_monitor_usage_model_key_index_stmt;

SET @has_non_asset_usage_legacy_key = (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_non_asset_usage'
    AND index_name = 'uq_non_asset_usage_item'
);
SET @drop_non_asset_usage_legacy_key_sql = IF(
  @has_non_asset_usage_legacy_key > 0,
  'ALTER TABLE employee_non_asset_usage DROP INDEX uq_non_asset_usage_item',
  'SELECT 1'
);
PREPARE drop_non_asset_usage_legacy_key_stmt FROM @drop_non_asset_usage_legacy_key_sql;
EXECUTE drop_non_asset_usage_legacy_key_stmt;
DEALLOCATE PREPARE drop_non_asset_usage_legacy_key_stmt;

SET @has_monitor_usage_legacy_key = (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_monitor_usage'
    AND index_name = 'uq_employee_monitor'
);
SET @drop_monitor_usage_legacy_key_sql = IF(
  @has_monitor_usage_legacy_key > 0,
  'ALTER TABLE employee_monitor_usage DROP INDEX uq_employee_monitor',
  'SELECT 1'
);
PREPARE drop_monitor_usage_legacy_key_stmt FROM @drop_monitor_usage_legacy_key_sql;
EXECUTE drop_monitor_usage_legacy_key_stmt;
DEALLOCATE PREPARE drop_monitor_usage_legacy_key_stmt;
