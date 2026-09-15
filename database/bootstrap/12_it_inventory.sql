USE office_asset_mgmt;

SET NAMES utf8mb4;

INSERT INTO non_asset_type (type_code, type_name, unit_name)
VALUES ('monitor', '显示屏', '件')
ON DUPLICATE KEY UPDATE
  type_name = VALUES(type_name),
  unit_name = VALUES(unit_name),
  is_active = 1,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO non_asset_type (type_code, type_name, unit_name)
VALUES ('computer', '电脑', '台')
ON DUPLICATE KEY UPDATE
  type_name = VALUES(type_name),
  unit_name = VALUES(unit_name),
  is_active = 1,
  updated_at = CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS it_inventory_brand (
  brand_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  non_asset_type_id BIGINT UNSIGNED NOT NULL,
  brand_name VARCHAR(128) NOT NULL,
  sort_order INT NOT NULL DEFAULT 1000,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (brand_id),
  UNIQUE KEY uq_it_inventory_brand (non_asset_type_id, brand_name),
  KEY idx_it_inventory_brand_type (non_asset_type_id, sort_order, brand_id),
  CONSTRAINT fk_it_inventory_brand_type
    FOREIGN KEY (non_asset_type_id)
    REFERENCES non_asset_type (non_asset_type_id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE,
  CONSTRAINT ck_it_inventory_brand_sort_order CHECK (sort_order >= 0)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS it_inventory_model (
  model_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  non_asset_type_id BIGINT UNSIGNED NOT NULL,
  brand_id BIGINT UNSIGNED NOT NULL,
  model_name VARCHAR(128) NOT NULL,
  batch_key VARCHAR(64) NOT NULL DEFAULT '',
  quantity INT UNSIGNED NOT NULL DEFAULT 0,
  inbound_date DATE NULL,
  cpu VARCHAR(128) NULL,
  memory VARCHAR(64) NULL,
  storage VARCHAR(128) NULL,
  gpu VARCHAR(128) NULL,
  sort_order INT NOT NULL DEFAULT 1000,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (model_id),
  UNIQUE KEY uq_it_inventory_model (brand_id, model_name, batch_key),
  KEY idx_it_inventory_model_type (non_asset_type_id, sort_order, model_id),
  KEY idx_it_inventory_model_brand (brand_id, sort_order, model_id),
  CONSTRAINT fk_it_inventory_model_type
    FOREIGN KEY (non_asset_type_id)
    REFERENCES non_asset_type (non_asset_type_id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE,
  CONSTRAINT fk_it_inventory_model_brand
    FOREIGN KEY (brand_id)
    REFERENCES it_inventory_brand (brand_id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE,
  CONSTRAINT ck_it_inventory_model_quantity CHECK (quantity >= 0),
  CONSTRAINT ck_it_inventory_model_sort_order CHECK (sort_order >= 0)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS inventory_movement_log (
  movement_log_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  movement_direction VARCHAR(16) NOT NULL,
  type_name VARCHAR(128) NOT NULL DEFAULT '',
  brand_name VARCHAR(128) NOT NULL DEFAULT '',
  model_name VARCHAR(128) NOT NULL DEFAULT '',
  quantity INT UNSIGNED NOT NULL,
  source_label VARCHAR(255) NOT NULL DEFAULT '',
  target_label VARCHAR(255) NOT NULL DEFAULT '',
  note VARCHAR(500) NOT NULL DEFAULT '',
  related_employee_no VARCHAR(64) NOT NULL DEFAULT '',
  related_employee_name VARCHAR(128) NOT NULL DEFAULT '',
  trigger_action VARCHAR(64) NOT NULL DEFAULT 'manual',
  occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (movement_log_id),
  KEY idx_inventory_movement_occurred_at (occurred_at, movement_log_id),
  KEY idx_inventory_movement_direction (movement_direction, occurred_at),
  KEY idx_inventory_movement_employee (related_employee_no, occurred_at),
  CONSTRAINT ck_inventory_movement_direction CHECK (movement_direction IN ('increase', 'decrease')),
  CONSTRAINT ck_inventory_movement_quantity CHECK (quantity > 0)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS inventory_purchase_log (
  purchase_log_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  type_name VARCHAR(128) NOT NULL DEFAULT '',
  brand_name VARCHAR(128) NOT NULL DEFAULT '',
  model_name VARCHAR(128) NOT NULL DEFAULT '',
  non_asset_type_id BIGINT UNSIGNED NULL,
  brand_id BIGINT UNSIGNED NULL,
  model_id BIGINT UNSIGNED NULL,
  quantity INT UNSIGNED NOT NULL,
  inbound_date DATE NULL,
  cpu VARCHAR(128) NULL,
  memory VARCHAR(64) NULL,
  storage VARCHAR(128) NULL,
  gpu VARCHAR(128) NULL,
  source_label VARCHAR(255) NOT NULL DEFAULT '',
  note VARCHAR(500) NOT NULL DEFAULT '',
  source_movement_log_id BIGINT UNSIGNED NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (purchase_log_id),
  UNIQUE KEY uq_inventory_purchase_source (source_movement_log_id),
  KEY idx_inventory_purchase_date (inbound_date, purchase_log_id),
  KEY idx_inventory_purchase_type (type_name, inbound_date),
  CONSTRAINT ck_inventory_purchase_quantity CHECK (quantity > 0),
  CONSTRAINT ck_inventory_purchase_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;

SET @monitor_type_column_exists := (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_monitor_usage'
    AND column_name = 'non_asset_type_id'
);
SET @monitor_type_sql := IF(
  @monitor_type_column_exists = 0,
  'ALTER TABLE employee_monitor_usage ADD COLUMN non_asset_type_id BIGINT UNSIGNED NULL AFTER employee_id',
  'SELECT 1'
);
PREPARE monitor_type_statement FROM @monitor_type_sql;
EXECUTE monitor_type_statement;
DEALLOCATE PREPARE monitor_type_statement;

SET @monitor_type_index_exists := (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_monitor_usage'
    AND index_name = 'idx_monitor_usage_type'
);
SET @monitor_type_index_sql := IF(
  @monitor_type_index_exists = 0,
  'ALTER TABLE employee_monitor_usage ADD KEY idx_monitor_usage_type (non_asset_type_id)',
  'SELECT 1'
);
PREPARE monitor_type_index_statement FROM @monitor_type_index_sql;
EXECUTE monitor_type_index_statement;
DEALLOCATE PREPARE monitor_type_index_statement;

SET @monitor_type_fk_exists := (
  SELECT COUNT(*)
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'employee_monitor_usage'
    AND constraint_name = 'fk_monitor_usage_type'
);
SET @monitor_type_fk_sql := IF(
  @monitor_type_fk_exists = 0,
  'ALTER TABLE employee_monitor_usage ADD CONSTRAINT fk_monitor_usage_type FOREIGN KEY (non_asset_type_id) REFERENCES non_asset_type (non_asset_type_id) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE monitor_type_fk_statement FROM @monitor_type_fk_sql;
EXECUTE monitor_type_fk_statement;
DEALLOCATE PREPARE monitor_type_fk_statement;

SET @monitor_stock_column_exists := (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_monitor_usage'
    AND column_name = 'stock_adjusted'
);
SET @monitor_stock_sql := IF(
  @monitor_stock_column_exists = 0,
  'ALTER TABLE employee_monitor_usage ADD COLUMN stock_adjusted TINYINT(1) NOT NULL DEFAULT 0 AFTER quantity',
  'SELECT 1'
);
PREPARE monitor_stock_statement FROM @monitor_stock_sql;
EXECUTE monitor_stock_statement;
DEALLOCATE PREPARE monitor_stock_statement;

SET @non_asset_stock_column_exists := (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'employee_non_asset_usage'
    AND column_name = 'stock_adjusted'
);
SET @non_asset_stock_sql := IF(
  @non_asset_stock_column_exists = 0,
  'ALTER TABLE employee_non_asset_usage ADD COLUMN stock_adjusted TINYINT(1) NOT NULL DEFAULT 0 AFTER quantity',
  'SELECT 1'
);
PREPARE non_asset_stock_statement FROM @non_asset_stock_sql;
EXECUTE non_asset_stock_statement;
DEALLOCATE PREPARE non_asset_stock_statement;
