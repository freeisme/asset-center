USE office_asset_mgmt;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP VIEW IF EXISTS v_employee_office_device_summary;
DROP VIEW IF EXISTS v_employee_office_devices;
DROP VIEW IF EXISTS v_employee_org_tree;
DROP VIEW IF EXISTS v_org_unit_tree;
DROP VIEW IF EXISTS v_computer_asset_detail;

DROP TABLE IF EXISTS employee_monitor_usage;
DROP TABLE IF EXISTS employee_non_asset_usage;
DROP TABLE IF EXISTS computer_assignment_history;
DROP TABLE IF EXISTS left_employee_archive;
DROP TABLE IF EXISTS inventory_transfer_log;
DROP TABLE IF EXISTS inventory_purchase_log;
DROP TABLE IF EXISTS inventory_movement_log;
DROP TABLE IF EXISTS inventory_warehouse_stock;
DROP TABLE IF EXISTS inventory_warehouse;
DROP TABLE IF EXISTS it_inventory_model;
DROP TABLE IF EXISTS it_inventory_brand;
DROP TABLE IF EXISTS non_asset_type;
DROP TABLE IF EXISTS computer_assignment;
DROP TABLE IF EXISTS computer_asset;
DROP TABLE IF EXISTS employee;
DROP TABLE IF EXISTS org_unit;
DROP TABLE IF EXISTS app_state_revision;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE org_unit (
  org_unit_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  org_code VARCHAR(64) NOT NULL,
  org_name VARCHAR(128) NOT NULL,
  parent_org_unit_id BIGINT UNSIGNED NULL,
  sort_order INT NOT NULL DEFAULT 1000,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (org_unit_id),
  UNIQUE KEY uq_org_unit_parent_code (parent_org_unit_id, org_code),
  KEY idx_org_unit_parent (parent_org_unit_id),
  CONSTRAINT fk_org_unit_parent
    FOREIGN KEY (parent_org_unit_id)
    REFERENCES org_unit (org_unit_id)
    ON DELETE SET NULL
    ON UPDATE CASCADE,
  CONSTRAINT ck_org_unit_sort_order CHECK (sort_order >= 0),
  CONSTRAINT ck_org_unit_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;

CREATE TABLE app_state_revision (
  revision_id TINYINT UNSIGNED NOT NULL,
  revision BIGINT UNSIGNED NOT NULL DEFAULT 1,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (revision_id),
  CONSTRAINT ck_app_state_revision_id CHECK (revision_id = 1)
) ENGINE = InnoDB;

INSERT INTO app_state_revision (revision_id, revision) VALUES (1, 1);

CREATE TABLE employee (
  employee_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  employee_no VARCHAR(64) NOT NULL,
  employee_name VARCHAR(128) NOT NULL,
  org_unit_id BIGINT UNSIGNED NULL,
  department VARCHAR(128) NULL,
  position_name VARCHAR(128) NULL,
  email VARCHAR(255) NULL,
  mobile VARCHAR(32) NULL,
  employment_status VARCHAR(32) NOT NULL DEFAULT 'active',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (employee_id),
  UNIQUE KEY uq_employee_no (employee_no),
  KEY idx_employee_org_unit (org_unit_id),
  KEY idx_employee_name (employee_name),
  CONSTRAINT fk_employee_org_unit
    FOREIGN KEY (org_unit_id)
    REFERENCES org_unit (org_unit_id)
    ON DELETE SET NULL
    ON UPDATE CASCADE,
  CONSTRAINT ck_employee_status
    CHECK (employment_status IN ('active', 'inactive', 'left')),
  CONSTRAINT ck_employee_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;

CREATE TABLE left_employee_archive (
  archive_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source_employee_ref VARCHAR(128) NULL,
  employee_no VARCHAR(64) NOT NULL,
  employee_name VARCHAR(128) NOT NULL,
  org_unit_id BIGINT UNSIGNED NULL,
  org_path VARCHAR(500) NULL,
  department VARCHAR(128) NULL,
  position_name VARCHAR(128) NULL,
  email VARCHAR(255) NULL,
  mobile VARCHAR(32) NULL,
  leave_date DATE NULL,
  leave_info VARCHAR(500) NULL,
  leave_remark VARCHAR(500) NULL,
  device_snapshot JSON NOT NULL,
  archived_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (archive_id),
  KEY idx_left_employee_source (source_employee_ref),
  KEY idx_left_employee_no (employee_no),
  KEY idx_left_employee_org (org_unit_id),
  KEY idx_left_employee_leave_date (leave_date)
) ENGINE = InnoDB;

CREATE TABLE computer_asset (
  computer_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  device_name VARCHAR(128) NOT NULL,
  org_unit_id BIGINT UNSIGNED NULL,
  device_type VARCHAR(64) NOT NULL,
  brand VARCHAR(64) NULL,
  model VARCHAR(128) NULL,
  inventory_model_id BIGINT UNSIGNED NULL,
  inventory_stock_adjusted TINYINT(1) NOT NULL DEFAULT 0,
  cpu VARCHAR(128) NULL,
  memory VARCHAR(64) NULL,
  storage VARCHAR(128) NULL,
  gpu VARCHAR(128) NULL,
  fixed_asset_code VARCHAR(128) NULL,
  purchase_date DATE NULL,
  registered_date DATE NULL,
  sn_st VARCHAR(128) NULL,
  wifi_mac CHAR(17) NULL,
  ethernet_mac CHAR(17) NULL,
  location VARCHAR(255) NULL,
  department VARCHAR(128) NULL,
  position_name VARCHAR(128) NULL,
  it_asset_status VARCHAR(32) NOT NULL DEFAULT 'in_use',
  remarks VARCHAR(500) NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (computer_id),
  UNIQUE KEY uq_computer_device_name (device_name),
  UNIQUE KEY uq_computer_fixed_asset_code (fixed_asset_code),
  UNIQUE KEY uq_computer_sn_st (sn_st),
  KEY idx_computer_org_unit (org_unit_id),
  KEY idx_computer_status (it_asset_status),
  KEY idx_computer_department (department),
  CONSTRAINT fk_computer_org_unit
    FOREIGN KEY (org_unit_id)
    REFERENCES org_unit (org_unit_id)
    ON DELETE SET NULL
    ON UPDATE CASCADE,
  CONSTRAINT ck_computer_status
    CHECK (it_asset_status IN ('in_use', 'idle', 'repair', 'retired', 'lost')),
  CONSTRAINT ck_computer_dates
    CHECK (registered_date IS NULL OR purchase_date IS NULL OR registered_date >= purchase_date),
  CONSTRAINT ck_computer_wifi_mac
    CHECK (
      wifi_mac IS NULL OR
      wifi_mac REGEXP '^[0-9A-Fa-f]{2}(-[0-9A-Fa-f]{2}){5}$'
    ),
  CONSTRAINT ck_computer_ethernet_mac
    CHECK (
      ethernet_mac IS NULL OR
      ethernet_mac REGEXP '^[0-9A-Fa-f]{2}(-[0-9A-Fa-f]{2}){5}$'
    ),
  CONSTRAINT ck_computer_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;

CREATE TABLE computer_assignment (
  assignment_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  computer_id BIGINT UNSIGNED NOT NULL,
  employee_id BIGINT UNSIGNED NOT NULL,
  assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  returned_at DATETIME NULL,
  assignment_status VARCHAR(32) NOT NULL DEFAULT 'active',
  notes VARCHAR(500) NULL,
  active_computer_id BIGINT UNSIGNED
    GENERATED ALWAYS AS (
      CASE WHEN returned_at IS NULL THEN computer_id ELSE NULL END
    ) STORED,
  PRIMARY KEY (assignment_id),
  UNIQUE KEY uq_computer_active_assignment (active_computer_id),
  KEY idx_assignment_employee_active (employee_id, returned_at),
  KEY idx_assignment_computer_history (computer_id, assigned_at),
  CONSTRAINT fk_assignment_computer
    FOREIGN KEY (computer_id)
    REFERENCES computer_asset (computer_id)
    ON DELETE RESTRICT
    ON UPDATE RESTRICT,
  CONSTRAINT fk_assignment_employee
    FOREIGN KEY (employee_id)
    REFERENCES employee (employee_id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE,
  CONSTRAINT ck_assignment_status
    CHECK (assignment_status IN ('active', 'returned', 'cancelled')),
  CONSTRAINT ck_assignment_dates
    CHECK (returned_at IS NULL OR returned_at >= assigned_at),
  CONSTRAINT ck_assignment_status_date
    CHECK (
      (assignment_status = 'active' AND returned_at IS NULL)
      OR (assignment_status IN ('returned', 'cancelled') AND returned_at IS NOT NULL)
    )
) ENGINE = InnoDB;

CREATE TABLE non_asset_type (
  non_asset_type_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  type_code VARCHAR(64) NOT NULL,
  type_name VARCHAR(128) NOT NULL,
  unit_name VARCHAR(32) NOT NULL DEFAULT '件',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (non_asset_type_id),
  UNIQUE KEY uq_non_asset_type_code (type_code),
  UNIQUE KEY uq_non_asset_type_name (type_name),
  CONSTRAINT ck_non_asset_type_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;

CREATE TABLE it_inventory_brand (
  brand_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  non_asset_type_id BIGINT UNSIGNED NOT NULL,
  brand_name VARCHAR(128) NOT NULL,
  sort_order INT NOT NULL DEFAULT 1000,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
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
  CONSTRAINT ck_it_inventory_brand_sort_order CHECK (sort_order >= 0),
  CONSTRAINT ck_it_inventory_brand_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;

CREATE TABLE it_inventory_model (
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
  is_active TINYINT(1) NOT NULL DEFAULT 1,
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
  CONSTRAINT ck_it_inventory_model_sort_order CHECK (sort_order >= 0),
  CONSTRAINT ck_it_inventory_model_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;

CREATE TABLE inventory_warehouse (
  warehouse_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  warehouse_code VARCHAR(64) NOT NULL,
  warehouse_name VARCHAR(128) NOT NULL,
  org_unit_id BIGINT UNSIGNED NOT NULL,
  manager_employee_id BIGINT UNSIGNED NULL,
  contact_phone VARCHAR(64) NOT NULL DEFAULT '',
  address VARCHAR(255) NOT NULL DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  remarks VARCHAR(500) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (warehouse_id),
  UNIQUE KEY uq_inventory_warehouse_code (warehouse_code),
  KEY idx_inventory_warehouse_org (org_unit_id, is_active, warehouse_name),
  KEY idx_inventory_warehouse_manager (manager_employee_id),
  CONSTRAINT fk_inventory_warehouse_org
    FOREIGN KEY (org_unit_id) REFERENCES org_unit (org_unit_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_warehouse_manager
    FOREIGN KEY (manager_employee_id) REFERENCES employee (employee_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_inventory_warehouse_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;

CREATE TABLE inventory_warehouse_stock (
  warehouse_id BIGINT UNSIGNED NOT NULL,
  model_id BIGINT UNSIGNED NOT NULL,
  quantity INT UNSIGNED NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (warehouse_id, model_id),
  KEY idx_inventory_warehouse_stock_model (model_id, warehouse_id),
  CONSTRAINT fk_inventory_warehouse_stock_warehouse
    FOREIGN KEY (warehouse_id) REFERENCES inventory_warehouse (warehouse_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_warehouse_stock_model
    FOREIGN KEY (model_id) REFERENCES it_inventory_model (model_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT ck_inventory_warehouse_stock_quantity CHECK (quantity >= 0)
) ENGINE = InnoDB;

CREATE TABLE inventory_transfer_log (
  transfer_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source_warehouse_id BIGINT UNSIGNED NOT NULL,
  target_warehouse_id BIGINT UNSIGNED NOT NULL,
  model_id BIGINT UNSIGNED NOT NULL,
  quantity INT UNSIGNED NOT NULL,
  note VARCHAR(500) NOT NULL DEFAULT '',
  created_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (transfer_id),
  KEY idx_inventory_transfer_source (source_warehouse_id, created_at),
  KEY idx_inventory_transfer_target (target_warehouse_id, created_at),
  KEY idx_inventory_transfer_model (model_id, created_at),
  CONSTRAINT fk_inventory_transfer_source
    FOREIGN KEY (source_warehouse_id) REFERENCES inventory_warehouse (warehouse_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_inventory_transfer_target
    FOREIGN KEY (target_warehouse_id) REFERENCES inventory_warehouse (warehouse_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_inventory_transfer_model
    FOREIGN KEY (model_id) REFERENCES it_inventory_model (model_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT ck_inventory_transfer_quantity CHECK (quantity > 0),
  CONSTRAINT ck_inventory_transfer_warehouses CHECK (source_warehouse_id <> target_warehouse_id)
) ENGINE = InnoDB;

CREATE TABLE inventory_movement_log (
  movement_log_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  movement_direction VARCHAR(16) NOT NULL,
  type_name VARCHAR(128) NOT NULL DEFAULT '',
  brand_name VARCHAR(128) NOT NULL DEFAULT '',
  model_name VARCHAR(128) NOT NULL DEFAULT '',
  quantity INT UNSIGNED NOT NULL,
  source_label VARCHAR(255) NOT NULL DEFAULT '',
  source_warehouse_id BIGINT UNSIGNED NULL,
  target_label VARCHAR(255) NOT NULL DEFAULT '',
  target_warehouse_id BIGINT UNSIGNED NULL,
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
  KEY idx_inventory_movement_source_warehouse (source_warehouse_id, occurred_at),
  KEY idx_inventory_movement_target_warehouse (target_warehouse_id, occurred_at),
  CONSTRAINT fk_inventory_movement_source_warehouse
    FOREIGN KEY (source_warehouse_id) REFERENCES inventory_warehouse (warehouse_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_movement_target_warehouse
    FOREIGN KEY (target_warehouse_id) REFERENCES inventory_warehouse (warehouse_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT ck_inventory_movement_direction CHECK (movement_direction IN ('increase', 'decrease')),
  CONSTRAINT ck_inventory_movement_quantity CHECK (quantity > 0)
) ENGINE = InnoDB;

CREATE TABLE inventory_purchase_log (
  purchase_log_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  type_name VARCHAR(128) NOT NULL DEFAULT '',
  brand_name VARCHAR(128) NOT NULL DEFAULT '',
  model_name VARCHAR(128) NOT NULL DEFAULT '',
  non_asset_type_id BIGINT UNSIGNED NULL,
  brand_id BIGINT UNSIGNED NULL,
  model_id BIGINT UNSIGNED NULL,
  warehouse_id BIGINT UNSIGNED NULL,
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
  KEY idx_inventory_purchase_warehouse (warehouse_id, inbound_date),
  CONSTRAINT fk_inventory_purchase_warehouse
    FOREIGN KEY (warehouse_id) REFERENCES inventory_warehouse (warehouse_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT ck_inventory_purchase_quantity CHECK (quantity > 0),
  CONSTRAINT ck_inventory_purchase_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;

CREATE TABLE computer_assignment_history (
  history_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  computer_id BIGINT UNSIGNED NOT NULL,
  device_name VARCHAR(128) NOT NULL DEFAULT '',
  employee_id BIGINT UNSIGNED NOT NULL,
  employee_no VARCHAR(64) NOT NULL DEFAULT '',
  employee_name VARCHAR(128) NOT NULL DEFAULT '',
  assigned_at DATETIME NOT NULL,
  returned_at DATETIME NULL,
  assignment_status VARCHAR(32) NOT NULL DEFAULT 'active',
  notes VARCHAR(500) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (history_id),
  UNIQUE KEY uq_assignment_history_snapshot (computer_id, employee_id, assigned_at),
  KEY idx_assignment_history_computer (computer_id, assigned_at),
  KEY idx_assignment_history_employee (employee_id, assigned_at),
  CONSTRAINT ck_assignment_history_status CHECK (assignment_status IN ('active', 'returned', 'cancelled'))
) ENGINE = InnoDB;

CREATE TABLE employee_non_asset_usage (
  non_asset_usage_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  employee_id BIGINT UNSIGNED NOT NULL,
  non_asset_type_id BIGINT UNSIGNED NOT NULL,
  inventory_brand_id BIGINT UNSIGNED NULL,
  inventory_model_id BIGINT UNSIGNED NULL,
  brand VARCHAR(128) NOT NULL DEFAULT '',
  model VARCHAR(128) NOT NULL DEFAULT '',
  quantity INT UNSIGNED NOT NULL,
  stock_adjusted TINYINT(1) NOT NULL DEFAULT 0,
  inventory_model_key BIGINT UNSIGNED
    GENERATED ALWAYS AS (COALESCE(inventory_model_id, 0)) VIRTUAL,
  last_counted_date DATE NULL,
  notes VARCHAR(500) NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (non_asset_usage_id),
  KEY idx_non_asset_usage_item_model (
    employee_id, non_asset_type_id, brand, model, inventory_model_key
  ),
  KEY idx_non_asset_usage_employee (employee_id),
  KEY idx_non_asset_usage_type (non_asset_type_id),
  CONSTRAINT fk_non_asset_usage_employee
    FOREIGN KEY (employee_id)
    REFERENCES employee (employee_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_non_asset_usage_type
    FOREIGN KEY (non_asset_type_id)
    REFERENCES non_asset_type (non_asset_type_id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE,
  CONSTRAINT ck_non_asset_usage_quantity CHECK (quantity > 0),
  CONSTRAINT ck_non_asset_usage_stock_adjusted CHECK (stock_adjusted IN (0, 1)),
  CONSTRAINT ck_non_asset_usage_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;

CREATE TABLE employee_monitor_usage (
  monitor_usage_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  employee_id BIGINT UNSIGNED NOT NULL,
  non_asset_type_id BIGINT UNSIGNED NULL,
  inventory_brand_id BIGINT UNSIGNED NULL,
  inventory_model_id BIGINT UNSIGNED NULL,
  display_name VARCHAR(128) NOT NULL,
  model VARCHAR(128) NOT NULL DEFAULT '',
  quantity INT UNSIGNED NOT NULL DEFAULT 1,
  stock_adjusted TINYINT(1) NOT NULL DEFAULT 0,
  inventory_model_key BIGINT UNSIGNED
    GENERATED ALWAYS AS (COALESCE(inventory_model_id, 0)) VIRTUAL,
  last_counted_date DATE NULL,
  notes VARCHAR(500) NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (monitor_usage_id),
  KEY idx_employee_monitor_model (
    employee_id, display_name, model, inventory_model_key
  ),
  KEY idx_monitor_usage_type (non_asset_type_id),
  KEY idx_monitor_employee (employee_id),
  CONSTRAINT fk_monitor_usage_employee
    FOREIGN KEY (employee_id)
    REFERENCES employee (employee_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_monitor_usage_type
    FOREIGN KEY (non_asset_type_id)
    REFERENCES non_asset_type (non_asset_type_id)
    ON DELETE SET NULL
    ON UPDATE CASCADE,
  CONSTRAINT ck_monitor_usage_quantity CHECK (quantity > 0),
  CONSTRAINT ck_monitor_usage_stock_adjusted CHECK (stock_adjusted IN (0, 1)),
  CONSTRAINT ck_monitor_usage_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;
