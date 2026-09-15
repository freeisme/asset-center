USE office_asset_mgmt;

SET NAMES utf8mb4;

-- Keep the human-readable snapshot fields, but also retain the selected
-- inventory catalog IDs so renaming a catalog item cannot break lineage.
SET @add_computer_inventory_model_id := IF(
  (SELECT COUNT(*)
   FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'computer_asset'
     AND column_name = 'inventory_model_id') = 0,
  'ALTER TABLE computer_asset ADD COLUMN inventory_model_id BIGINT UNSIGNED NULL AFTER model',
  'SELECT 1'
);
PREPARE add_computer_inventory_model_id_stmt FROM @add_computer_inventory_model_id;
EXECUTE add_computer_inventory_model_id_stmt;
DEALLOCATE PREPARE add_computer_inventory_model_id_stmt;

SET @add_computer_inventory_stock_adjusted := IF(
  (SELECT COUNT(*)
   FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'computer_asset'
     AND column_name = 'inventory_stock_adjusted') = 0,
  'ALTER TABLE computer_asset ADD COLUMN inventory_stock_adjusted TINYINT(1) NOT NULL DEFAULT 0 AFTER inventory_model_id',
  'SELECT 1'
);
PREPARE add_computer_inventory_stock_adjusted_stmt FROM @add_computer_inventory_stock_adjusted;
EXECUTE add_computer_inventory_stock_adjusted_stmt;
DEALLOCATE PREPARE add_computer_inventory_stock_adjusted_stmt;

SET @add_monitor_inventory_brand_id := IF(
  (SELECT COUNT(*)
   FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'employee_monitor_usage'
     AND column_name = 'inventory_brand_id') = 0,
  'ALTER TABLE employee_monitor_usage ADD COLUMN inventory_brand_id BIGINT UNSIGNED NULL AFTER non_asset_type_id',
  'SELECT 1'
);
PREPARE add_monitor_inventory_brand_id_stmt FROM @add_monitor_inventory_brand_id;
EXECUTE add_monitor_inventory_brand_id_stmt;
DEALLOCATE PREPARE add_monitor_inventory_brand_id_stmt;

SET @add_monitor_inventory_model_id := IF(
  (SELECT COUNT(*)
   FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'employee_monitor_usage'
     AND column_name = 'inventory_model_id') = 0,
  'ALTER TABLE employee_monitor_usage ADD COLUMN inventory_model_id BIGINT UNSIGNED NULL AFTER inventory_brand_id',
  'SELECT 1'
);
PREPARE add_monitor_inventory_model_id_stmt FROM @add_monitor_inventory_model_id;
EXECUTE add_monitor_inventory_model_id_stmt;
DEALLOCATE PREPARE add_monitor_inventory_model_id_stmt;

SET @add_non_asset_inventory_brand_id := IF(
  (SELECT COUNT(*)
   FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'employee_non_asset_usage'
     AND column_name = 'inventory_brand_id') = 0,
  'ALTER TABLE employee_non_asset_usage ADD COLUMN inventory_brand_id BIGINT UNSIGNED NULL AFTER non_asset_type_id',
  'SELECT 1'
);
PREPARE add_non_asset_inventory_brand_id_stmt FROM @add_non_asset_inventory_brand_id;
EXECUTE add_non_asset_inventory_brand_id_stmt;
DEALLOCATE PREPARE add_non_asset_inventory_brand_id_stmt;

SET @add_non_asset_inventory_model_id := IF(
  (SELECT COUNT(*)
   FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'employee_non_asset_usage'
     AND column_name = 'inventory_model_id') = 0,
  'ALTER TABLE employee_non_asset_usage ADD COLUMN inventory_model_id BIGINT UNSIGNED NULL AFTER inventory_brand_id',
  'SELECT 1'
);
PREPARE add_non_asset_inventory_model_id_stmt FROM @add_non_asset_inventory_model_id;
EXECUTE add_non_asset_inventory_model_id_stmt;
DEALLOCATE PREPARE add_non_asset_inventory_model_id_stmt;

SET @add_purchase_type_id := IF(
  (SELECT COUNT(*)
   FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'inventory_purchase_log'
     AND column_name = 'non_asset_type_id') = 0,
  'ALTER TABLE inventory_purchase_log ADD COLUMN non_asset_type_id BIGINT UNSIGNED NULL AFTER model_name',
  'SELECT 1'
);
PREPARE add_purchase_type_id_stmt FROM @add_purchase_type_id;
EXECUTE add_purchase_type_id_stmt;
DEALLOCATE PREPARE add_purchase_type_id_stmt;

SET @add_purchase_brand_id := IF(
  (SELECT COUNT(*)
   FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'inventory_purchase_log'
     AND column_name = 'brand_id') = 0,
  'ALTER TABLE inventory_purchase_log ADD COLUMN brand_id BIGINT UNSIGNED NULL AFTER non_asset_type_id',
  'SELECT 1'
);
PREPARE add_purchase_brand_id_stmt FROM @add_purchase_brand_id;
EXECUTE add_purchase_brand_id_stmt;
DEALLOCATE PREPARE add_purchase_brand_id_stmt;

SET @add_purchase_model_id := IF(
  (SELECT COUNT(*)
   FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'inventory_purchase_log'
     AND column_name = 'model_id') = 0,
  'ALTER TABLE inventory_purchase_log ADD COLUMN model_id BIGINT UNSIGNED NULL AFTER brand_id',
  'SELECT 1'
);
PREPARE add_purchase_model_id_stmt FROM @add_purchase_model_id;
EXECUTE add_purchase_model_id_stmt;
DEALLOCATE PREPARE add_purchase_model_id_stmt;

-- Backfill unambiguous catalog links from the existing text snapshots.
UPDATE employee_monitor_usage usage_row
JOIN it_inventory_brand brand
  ON brand.brand_name = usage_row.display_name
JOIN it_inventory_model model
  ON model.brand_id = brand.brand_id
 AND model.model_name = usage_row.model
 AND model.non_asset_type_id = usage_row.non_asset_type_id
SET usage_row.inventory_brand_id = brand.brand_id,
    usage_row.inventory_model_id = model.model_id
WHERE usage_row.inventory_model_id IS NULL;

UPDATE employee_non_asset_usage usage_row
JOIN it_inventory_brand brand
  ON brand.brand_name = usage_row.brand
JOIN it_inventory_model model
  ON model.brand_id = brand.brand_id
 AND model.model_name = usage_row.model
 AND model.non_asset_type_id = usage_row.non_asset_type_id
SET usage_row.inventory_brand_id = brand.brand_id,
    usage_row.inventory_model_id = model.model_id
WHERE usage_row.inventory_model_id IS NULL;

UPDATE inventory_purchase_log purchase_row
JOIN non_asset_type type_row
  ON type_row.type_name = purchase_row.type_name
JOIN it_inventory_brand brand
  ON brand.non_asset_type_id = type_row.non_asset_type_id
 AND brand.brand_name = purchase_row.brand_name
JOIN it_inventory_model model
  ON model.brand_id = brand.brand_id
 AND model.model_name = purchase_row.model_name
SET purchase_row.non_asset_type_id = type_row.non_asset_type_id,
    purchase_row.brand_id = brand.brand_id,
    purchase_row.model_id = model.model_id
WHERE purchase_row.model_id IS NULL;

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

SET @add_monitor_inventory_model_index := IF(
  (SELECT COUNT(*)
   FROM information_schema.statistics
   WHERE table_schema = DATABASE()
     AND table_name = 'employee_monitor_usage'
     AND index_name = 'idx_monitor_inventory_model') = 0,
  'ALTER TABLE employee_monitor_usage ADD KEY idx_monitor_inventory_model (inventory_model_id)',
  'SELECT 1'
);
PREPARE add_monitor_inventory_model_index_stmt FROM @add_monitor_inventory_model_index;
EXECUTE add_monitor_inventory_model_index_stmt;
DEALLOCATE PREPARE add_monitor_inventory_model_index_stmt;

SET @add_non_asset_inventory_model_index := IF(
  (SELECT COUNT(*)
   FROM information_schema.statistics
   WHERE table_schema = DATABASE()
     AND table_name = 'employee_non_asset_usage'
     AND index_name = 'idx_non_asset_inventory_model') = 0,
  'ALTER TABLE employee_non_asset_usage ADD KEY idx_non_asset_inventory_model (inventory_model_id)',
  'SELECT 1'
);
PREPARE add_non_asset_inventory_model_index_stmt FROM @add_non_asset_inventory_model_index;
EXECUTE add_non_asset_inventory_model_index_stmt;
DEALLOCATE PREPARE add_non_asset_inventory_model_index_stmt;

SET @add_purchase_model_index := IF(
  (SELECT COUNT(*)
   FROM information_schema.statistics
   WHERE table_schema = DATABASE()
     AND table_name = 'inventory_purchase_log'
     AND index_name = 'idx_inventory_purchase_model') = 0,
  'ALTER TABLE inventory_purchase_log ADD KEY idx_inventory_purchase_model (model_id, inbound_date)',
  'SELECT 1'
);
PREPARE add_purchase_model_index_stmt FROM @add_purchase_model_index;
EXECUTE add_purchase_model_index_stmt;
DEALLOCATE PREPARE add_purchase_model_index_stmt;

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

SET @add_monitor_inventory_brand_fk := IF(
  (SELECT COUNT(*)
   FROM information_schema.table_constraints
   WHERE constraint_schema = DATABASE()
     AND table_name = 'employee_monitor_usage'
     AND constraint_name = 'fk_monitor_inventory_brand') = 0,
  'ALTER TABLE employee_monitor_usage ADD CONSTRAINT fk_monitor_inventory_brand FOREIGN KEY (inventory_brand_id) REFERENCES it_inventory_brand (brand_id) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE add_monitor_inventory_brand_fk_stmt FROM @add_monitor_inventory_brand_fk;
EXECUTE add_monitor_inventory_brand_fk_stmt;
DEALLOCATE PREPARE add_monitor_inventory_brand_fk_stmt;

SET @add_monitor_inventory_model_fk := IF(
  (SELECT COUNT(*)
   FROM information_schema.table_constraints
   WHERE constraint_schema = DATABASE()
     AND table_name = 'employee_monitor_usage'
     AND constraint_name = 'fk_monitor_inventory_model') = 0,
  'ALTER TABLE employee_monitor_usage ADD CONSTRAINT fk_monitor_inventory_model FOREIGN KEY (inventory_model_id) REFERENCES it_inventory_model (model_id) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE add_monitor_inventory_model_fk_stmt FROM @add_monitor_inventory_model_fk;
EXECUTE add_monitor_inventory_model_fk_stmt;
DEALLOCATE PREPARE add_monitor_inventory_model_fk_stmt;

SET @add_non_asset_inventory_brand_fk := IF(
  (SELECT COUNT(*)
   FROM information_schema.table_constraints
   WHERE constraint_schema = DATABASE()
     AND table_name = 'employee_non_asset_usage'
     AND constraint_name = 'fk_non_asset_inventory_brand') = 0,
  'ALTER TABLE employee_non_asset_usage ADD CONSTRAINT fk_non_asset_inventory_brand FOREIGN KEY (inventory_brand_id) REFERENCES it_inventory_brand (brand_id) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE add_non_asset_inventory_brand_fk_stmt FROM @add_non_asset_inventory_brand_fk;
EXECUTE add_non_asset_inventory_brand_fk_stmt;
DEALLOCATE PREPARE add_non_asset_inventory_brand_fk_stmt;

SET @add_non_asset_inventory_model_fk := IF(
  (SELECT COUNT(*)
   FROM information_schema.table_constraints
   WHERE constraint_schema = DATABASE()
     AND table_name = 'employee_non_asset_usage'
     AND constraint_name = 'fk_non_asset_inventory_model') = 0,
  'ALTER TABLE employee_non_asset_usage ADD CONSTRAINT fk_non_asset_inventory_model FOREIGN KEY (inventory_model_id) REFERENCES it_inventory_model (model_id) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE add_non_asset_inventory_model_fk_stmt FROM @add_non_asset_inventory_model_fk;
EXECUTE add_non_asset_inventory_model_fk_stmt;
DEALLOCATE PREPARE add_non_asset_inventory_model_fk_stmt;

SET @add_purchase_type_fk := IF(
  (SELECT COUNT(*)
   FROM information_schema.table_constraints
   WHERE constraint_schema = DATABASE()
     AND table_name = 'inventory_purchase_log'
     AND constraint_name = 'fk_inventory_purchase_type') = 0,
  'ALTER TABLE inventory_purchase_log ADD CONSTRAINT fk_inventory_purchase_type FOREIGN KEY (non_asset_type_id) REFERENCES non_asset_type (non_asset_type_id) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE add_purchase_type_fk_stmt FROM @add_purchase_type_fk;
EXECUTE add_purchase_type_fk_stmt;
DEALLOCATE PREPARE add_purchase_type_fk_stmt;

SET @add_purchase_brand_fk := IF(
  (SELECT COUNT(*)
   FROM information_schema.table_constraints
   WHERE constraint_schema = DATABASE()
     AND table_name = 'inventory_purchase_log'
     AND constraint_name = 'fk_inventory_purchase_brand') = 0,
  'ALTER TABLE inventory_purchase_log ADD CONSTRAINT fk_inventory_purchase_brand FOREIGN KEY (brand_id) REFERENCES it_inventory_brand (brand_id) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE add_purchase_brand_fk_stmt FROM @add_purchase_brand_fk;
EXECUTE add_purchase_brand_fk_stmt;
DEALLOCATE PREPARE add_purchase_brand_fk_stmt;

SET @add_purchase_model_fk := IF(
  (SELECT COUNT(*)
   FROM information_schema.table_constraints
   WHERE constraint_schema = DATABASE()
     AND table_name = 'inventory_purchase_log'
     AND constraint_name = 'fk_inventory_purchase_model') = 0,
  'ALTER TABLE inventory_purchase_log ADD CONSTRAINT fk_inventory_purchase_model FOREIGN KEY (model_id) REFERENCES it_inventory_model (model_id) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE add_purchase_model_fk_stmt FROM @add_purchase_model_fk;
EXECUTE add_purchase_model_fk_stmt;
DEALLOCATE PREPARE add_purchase_model_fk_stmt;
