SET NAMES utf8mb4;

-- Every inventory allocation must have its own usage row. The old unique
-- indexes caused a second issue of the same model to merge into the first row.
SET @has_non_asset_usage_unique_index = (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_non_asset_usage'
    AND index_name = 'uq_non_asset_usage_item_model'
);
SET @drop_non_asset_usage_unique_index_sql = IF(
  @has_non_asset_usage_unique_index > 0,
  'ALTER TABLE employee_non_asset_usage DROP INDEX uq_non_asset_usage_item_model',
  'SELECT 1'
);
PREPARE drop_non_asset_usage_unique_index_stmt FROM @drop_non_asset_usage_unique_index_sql;
EXECUTE drop_non_asset_usage_unique_index_stmt;
DEALLOCATE PREPARE drop_non_asset_usage_unique_index_stmt;

SET @has_non_asset_usage_index = (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_non_asset_usage'
    AND index_name = 'idx_non_asset_usage_item_model'
);
SET @add_non_asset_usage_index_sql = IF(
  @has_non_asset_usage_index = 0,
  'ALTER TABLE employee_non_asset_usage ADD KEY idx_non_asset_usage_item_model (employee_id, non_asset_type_id, brand, model, inventory_model_key)',
  'SELECT 1'
);
PREPARE add_non_asset_usage_index_stmt FROM @add_non_asset_usage_index_sql;
EXECUTE add_non_asset_usage_index_stmt;
DEALLOCATE PREPARE add_non_asset_usage_index_stmt;

SET @has_monitor_usage_unique_index = (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_monitor_usage'
    AND index_name = 'uq_employee_monitor_model'
);
SET @drop_monitor_usage_unique_index_sql = IF(
  @has_monitor_usage_unique_index > 0,
  'ALTER TABLE employee_monitor_usage DROP INDEX uq_employee_monitor_model',
  'SELECT 1'
);
PREPARE drop_monitor_usage_unique_index_stmt FROM @drop_monitor_usage_unique_index_sql;
EXECUTE drop_monitor_usage_unique_index_stmt;
DEALLOCATE PREPARE drop_monitor_usage_unique_index_stmt;

SET @has_monitor_usage_index = (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_monitor_usage'
    AND index_name = 'idx_employee_monitor_model'
);
SET @add_monitor_usage_index_sql = IF(
  @has_monitor_usage_index = 0,
  'ALTER TABLE employee_monitor_usage ADD KEY idx_employee_monitor_model (employee_id, display_name, model, inventory_model_key)',
  'SELECT 1'
);
PREPARE add_monitor_usage_index_stmt FROM @add_monitor_usage_index_sql;
EXECUTE add_monitor_usage_index_stmt;
DEALLOCATE PREPARE add_monitor_usage_index_stmt;
