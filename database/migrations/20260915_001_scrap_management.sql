SET NAMES utf8mb4;

-- 报废管理：发放中的 IT 物资可直接报废（不回收、不回补库存），
-- 电脑资产报废后软归档并保留报废记录快照。
-- 本迁移只新增表、列和权限，不修改历史业务数据。

CREATE TABLE IF NOT EXISTS scrap_reason (
  reason_code VARCHAR(64) NOT NULL,
  reason_name VARCHAR(128) NOT NULL,
  applies_to VARCHAR(16) NOT NULL DEFAULT 'both',
  sort_order INT NOT NULL DEFAULT 1000,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (reason_code),
  CONSTRAINT ck_scrap_reason_applies_to
    CHECK (applies_to IN ('inventory', 'asset', 'both')),
  CONSTRAINT ck_scrap_reason_active CHECK (is_active IN (0, 1))
) ENGINE=InnoDB;

INSERT INTO scrap_reason (reason_code, reason_name, applies_to, sort_order, is_active)
VALUES
  ('damaged_unrepairable', '损坏无法修复', 'both', 10, 1),
  ('worn_out', '老化到寿命期限', 'both', 20, 1),
  ('abnormal_damage', '人为损坏或异常损坏', 'both', 30, 1),
  ('lost_offsite', '外借丢失或无法找回', 'inventory', 40, 1),
  ('obsoleted', '技术淘汰无法继续使用', 'both', 50, 1),
  ('other', '其他原因', 'both', 900, 1)
ON DUPLICATE KEY UPDATE
  reason_name = VALUES(reason_name),
  applies_to = VALUES(applies_to),
  sort_order = VALUES(sort_order);

CREATE TABLE IF NOT EXISTS inventory_scrap_record (
  scrap_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  allocation_type VARCHAR(32) NOT NULL,
  usage_record_id BIGINT UNSIGNED NULL,
  allocation_id BIGINT UNSIGNED NULL,
  employee_id BIGINT UNSIGNED NULL,
  employee_no VARCHAR(64) NOT NULL DEFAULT '',
  employee_name VARCHAR(128) NOT NULL DEFAULT '',
  org_unit_id BIGINT UNSIGNED NULL,
  non_asset_type_id BIGINT UNSIGNED NULL,
  type_name VARCHAR(128) NOT NULL DEFAULT '',
  brand_id BIGINT UNSIGNED NULL,
  brand_name VARCHAR(128) NOT NULL DEFAULT '',
  inventory_model_id BIGINT UNSIGNED NULL,
  model_name VARCHAR(128) NOT NULL DEFAULT '',
  warehouse_id BIGINT UNSIGNED NULL,
  warehouse_name VARCHAR(128) NOT NULL DEFAULT '',
  quantity INT UNSIGNED NOT NULL,
  stock_adjusted TINYINT(1) NOT NULL DEFAULT 0,
  scrap_reason_code VARCHAR(64) NOT NULL DEFAULT '',
  scrap_reason VARCHAR(255) NOT NULL DEFAULT '',
  scrap_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  operated_by BIGINT UNSIGNED NULL,
  operated_by_name VARCHAR(128) NOT NULL DEFAULT '',
  notes VARCHAR(500) NOT NULL DEFAULT '',
  attachment_ref VARCHAR(500) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (scrap_id),
  KEY idx_inventory_scrap_time (scrap_at, scrap_id),
  KEY idx_inventory_scrap_employee (employee_id, scrap_at),
  KEY idx_inventory_scrap_model (inventory_model_id, scrap_at),
  KEY idx_inventory_scrap_usage (allocation_type, usage_record_id),
  CONSTRAINT fk_inventory_scrap_employee
    FOREIGN KEY (employee_id) REFERENCES employee (employee_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_scrap_type
    FOREIGN KEY (non_asset_type_id) REFERENCES non_asset_type (non_asset_type_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_scrap_brand
    FOREIGN KEY (brand_id) REFERENCES it_inventory_brand (brand_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_scrap_model
    FOREIGN KEY (inventory_model_id) REFERENCES it_inventory_model (model_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_scrap_warehouse
    FOREIGN KEY (warehouse_id) REFERENCES inventory_warehouse (warehouse_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_scrap_allocation
    FOREIGN KEY (allocation_id) REFERENCES inventory_allocation_history (allocation_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_scrap_operator
    FOREIGN KEY (operated_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_inventory_scrap_type
    CHECK (allocation_type IN ('monitor', 'non_asset')),
  CONSTRAINT ck_inventory_scrap_quantity CHECK (quantity > 0),
  CONSTRAINT ck_inventory_scrap_stock_adjusted CHECK (stock_adjusted IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS asset_scrap_record (
  scrap_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  computer_id BIGINT UNSIGNED NULL,
  device_name VARCHAR(128) NOT NULL DEFAULT '',
  org_unit_id BIGINT UNSIGNED NULL,
  device_type VARCHAR(64) NOT NULL DEFAULT '',
  brand VARCHAR(64) NOT NULL DEFAULT '',
  model VARCHAR(128) NOT NULL DEFAULT '',
  cpu VARCHAR(128) NOT NULL DEFAULT '',
  memory VARCHAR(64) NOT NULL DEFAULT '',
  storage VARCHAR(128) NOT NULL DEFAULT '',
  gpu VARCHAR(128) NOT NULL DEFAULT '',
  fixed_asset_code VARCHAR(128) NOT NULL DEFAULT '',
  sn_st VARCHAR(128) NOT NULL DEFAULT '',
  purchase_date DATE NULL,
  registered_date DATE NULL,
  previous_status VARCHAR(32) NOT NULL DEFAULT '',
  employee_id BIGINT UNSIGNED NULL,
  employee_no VARCHAR(64) NOT NULL DEFAULT '',
  employee_name VARCHAR(128) NOT NULL DEFAULT '',
  scrap_reason_code VARCHAR(64) NOT NULL DEFAULT '',
  scrap_reason VARCHAR(255) NOT NULL DEFAULT '',
  scrap_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  operated_by BIGINT UNSIGNED NULL,
  operated_by_name VARCHAR(128) NOT NULL DEFAULT '',
  notes VARCHAR(500) NOT NULL DEFAULT '',
  attachment_ref VARCHAR(500) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (scrap_id),
  KEY idx_asset_scrap_time (scrap_at, scrap_id),
  KEY idx_asset_scrap_computer (computer_id, scrap_at),
  KEY idx_asset_scrap_employee (employee_id, scrap_at),
  CONSTRAINT fk_asset_scrap_computer
    FOREIGN KEY (computer_id) REFERENCES computer_asset (computer_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_asset_scrap_org
    FOREIGN KEY (org_unit_id) REFERENCES org_unit (org_unit_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_asset_scrap_employee
    FOREIGN KEY (employee_id) REFERENCES employee (employee_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_asset_scrap_operator
    FOREIGN KEY (operated_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 电脑资产报废后软归档：保留资产主记录用于追溯，但从台账中隐藏。
SET @has_computer_archived = (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'computer_asset'
    AND column_name = 'is_archived'
);
SET @computer_archived_sql = IF(
  @has_computer_archived = 0,
  'ALTER TABLE computer_asset ADD COLUMN is_archived TINYINT(1) NOT NULL DEFAULT 0 AFTER is_active, ADD COLUMN archived_at DATETIME NULL AFTER is_archived, ADD COLUMN archived_by BIGINT UNSIGNED NULL AFTER archived_at, ADD KEY idx_computer_archived (is_archived, it_asset_status)',
  'SELECT 1'
);
PREPARE computer_archived_stmt FROM @computer_archived_sql;
EXECUTE computer_archived_stmt;
DEALLOCATE PREPARE computer_archived_stmt;

SET @has_computer_archived_fk = (
  SELECT COUNT(*)
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'computer_asset'
    AND constraint_name = 'fk_computer_archived_by'
);
SET @computer_archived_fk_sql = IF(
  @has_computer_archived_fk = 0,
  'ALTER TABLE computer_asset ADD CONSTRAINT fk_computer_archived_by FOREIGN KEY (archived_by) REFERENCES user_account (user_id) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE computer_archived_fk_stmt FROM @computer_archived_fk_sql;
EXECUTE computer_archived_fk_stmt;
DEALLOCATE PREPARE computer_archived_fk_stmt;

-- 报废的领用记录需要独立状态，不能伪装成“已归还”。
SET @has_allocation_status_check = (
  SELECT COUNT(*)
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'inventory_allocation_history'
    AND constraint_name = 'ck_inventory_allocation_status'
);
SET @drop_allocation_status_check_sql = IF(
  @has_allocation_status_check > 0,
  'ALTER TABLE inventory_allocation_history DROP CHECK ck_inventory_allocation_status',
  'SELECT 1'
);
PREPARE drop_allocation_status_check_stmt FROM @drop_allocation_status_check_sql;
EXECUTE drop_allocation_status_check_stmt;
DEALLOCATE PREPARE drop_allocation_status_check_stmt;

ALTER TABLE inventory_allocation_history
  ADD CONSTRAINT ck_inventory_allocation_status
  CHECK (status IN ('active', 'returned', 'cancelled', 'scrapped'));

INSERT INTO auth_module (module_code, module_name, category, sort_order, is_active)
VALUES ('scrap_management', '报废管理', 'inventory', 56, 1)
ON DUPLICATE KEY UPDATE
  module_name = VALUES(module_name),
  category = VALUES(category),
  sort_order = VALUES(sort_order),
  is_active = 1;

INSERT IGNORE INTO auth_permission (module_code, action_code)
VALUES
  ('scrap_management', 'view'),
  ('scrap_management', 'create'),
  ('scrap_management', 'update'),
  ('scrap_management', 'delete'),
  ('scrap_management', 'approve'),
  ('scrap_management', 'export');

INSERT INTO auth_role_permission (
  role_id, permission_id, can_view, can_create, can_update,
  can_delete, can_approve, can_export, data_scope
)
SELECT
  role.role_id,
  permission.permission_id,
  1, 1, 0, 0, 0, 1, 'all'
FROM auth_role role
JOIN auth_permission permission
  ON permission.module_code = 'scrap_management'
WHERE role.is_active = 1
  AND (
    role.is_super_admin = 1
    OR role.role_code = 'admin'
    OR role.role_category = 'admin'
  )
ON DUPLICATE KEY UPDATE
  can_view = 1,
  can_create = 1,
  can_export = 1,
  data_scope = 'all';
