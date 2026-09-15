SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS inventory_warehouse (
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
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inventory_warehouse_stock (
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
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inventory_transfer_log (
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
  CONSTRAINT fk_inventory_transfer_creator
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_inventory_transfer_quantity CHECK (quantity > 0),
  CONSTRAINT ck_inventory_transfer_warehouses CHECK (source_warehouse_id <> target_warehouse_id)
) ENGINE=InnoDB;

SET @has_allocation_warehouse = (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'inventory_allocation_history'
    AND column_name = 'warehouse_id'
);
SET @allocation_warehouse_sql = IF(
  @has_allocation_warehouse = 0,
  'ALTER TABLE inventory_allocation_history ADD COLUMN warehouse_id BIGINT UNSIGNED NULL AFTER inventory_model_id',
  'SELECT 1'
);
PREPARE allocation_warehouse_stmt FROM @allocation_warehouse_sql;
EXECUTE allocation_warehouse_stmt;
DEALLOCATE PREPARE allocation_warehouse_stmt;

SET @has_movement_source_warehouse = (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'inventory_movement_log'
    AND column_name = 'source_warehouse_id'
);
SET @movement_source_warehouse_sql = IF(
  @has_movement_source_warehouse = 0,
  'ALTER TABLE inventory_movement_log ADD COLUMN source_warehouse_id BIGINT UNSIGNED NULL AFTER source_label',
  'SELECT 1'
);
PREPARE movement_source_warehouse_stmt FROM @movement_source_warehouse_sql;
EXECUTE movement_source_warehouse_stmt;
DEALLOCATE PREPARE movement_source_warehouse_stmt;

SET @has_movement_target_warehouse = (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'inventory_movement_log'
    AND column_name = 'target_warehouse_id'
);
SET @movement_target_warehouse_sql = IF(
  @has_movement_target_warehouse = 0,
  'ALTER TABLE inventory_movement_log ADD COLUMN target_warehouse_id BIGINT UNSIGNED NULL AFTER target_label',
  'SELECT 1'
);
PREPARE movement_target_warehouse_stmt FROM @movement_target_warehouse_sql;
EXECUTE movement_target_warehouse_stmt;
DEALLOCATE PREPARE movement_target_warehouse_stmt;

SET @has_purchase_warehouse = (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'inventory_purchase_log'
    AND column_name = 'warehouse_id'
);
SET @purchase_warehouse_sql = IF(
  @has_purchase_warehouse = 0,
  'ALTER TABLE inventory_purchase_log ADD COLUMN warehouse_id BIGINT UNSIGNED NULL AFTER model_id',
  'SELECT 1'
);
PREPARE purchase_warehouse_stmt FROM @purchase_warehouse_sql;
EXECUTE purchase_warehouse_stmt;
DEALLOCATE PREPARE purchase_warehouse_stmt;

SET @has_allocation_warehouse_fk = (
  SELECT COUNT(*)
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'inventory_allocation_history'
    AND constraint_name = 'fk_inventory_allocation_warehouse'
);
SET @allocation_warehouse_fk_sql = IF(
  @has_allocation_warehouse_fk = 0,
  'ALTER TABLE inventory_allocation_history ADD KEY idx_inventory_allocation_warehouse (warehouse_id, status), ADD CONSTRAINT fk_inventory_allocation_warehouse FOREIGN KEY (warehouse_id) REFERENCES inventory_warehouse (warehouse_id) ON DELETE RESTRICT ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE allocation_warehouse_fk_stmt FROM @allocation_warehouse_fk_sql;
EXECUTE allocation_warehouse_fk_stmt;
DEALLOCATE PREPARE allocation_warehouse_fk_stmt;

SET @has_movement_source_warehouse_fk = (
  SELECT COUNT(*)
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'inventory_movement_log'
    AND constraint_name = 'fk_inventory_movement_source_warehouse'
);
SET @movement_source_warehouse_fk_sql = IF(
  @has_movement_source_warehouse_fk = 0,
  'ALTER TABLE inventory_movement_log ADD KEY idx_inventory_movement_source_warehouse (source_warehouse_id, occurred_at), ADD CONSTRAINT fk_inventory_movement_source_warehouse FOREIGN KEY (source_warehouse_id) REFERENCES inventory_warehouse (warehouse_id) ON DELETE RESTRICT ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE movement_source_warehouse_fk_stmt FROM @movement_source_warehouse_fk_sql;
EXECUTE movement_source_warehouse_fk_stmt;
DEALLOCATE PREPARE movement_source_warehouse_fk_stmt;

SET @has_movement_target_warehouse_fk = (
  SELECT COUNT(*)
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'inventory_movement_log'
    AND constraint_name = 'fk_inventory_movement_target_warehouse'
);
SET @movement_target_warehouse_fk_sql = IF(
  @has_movement_target_warehouse_fk = 0,
  'ALTER TABLE inventory_movement_log ADD KEY idx_inventory_movement_target_warehouse (target_warehouse_id, occurred_at), ADD CONSTRAINT fk_inventory_movement_target_warehouse FOREIGN KEY (target_warehouse_id) REFERENCES inventory_warehouse (warehouse_id) ON DELETE RESTRICT ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE movement_target_warehouse_fk_stmt FROM @movement_target_warehouse_fk_sql;
EXECUTE movement_target_warehouse_fk_stmt;
DEALLOCATE PREPARE movement_target_warehouse_fk_stmt;

SET @has_purchase_warehouse_fk = (
  SELECT COUNT(*)
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'inventory_purchase_log'
    AND constraint_name = 'fk_inventory_purchase_warehouse'
);
SET @purchase_warehouse_fk_sql = IF(
  @has_purchase_warehouse_fk = 0,
  'ALTER TABLE inventory_purchase_log ADD KEY idx_inventory_purchase_warehouse (warehouse_id, inbound_date), ADD CONSTRAINT fk_inventory_purchase_warehouse FOREIGN KEY (warehouse_id) REFERENCES inventory_warehouse (warehouse_id) ON DELETE RESTRICT ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE purchase_warehouse_fk_stmt FROM @purchase_warehouse_fk_sql;
EXECUTE purchase_warehouse_fk_stmt;
DEALLOCATE PREPARE purchase_warehouse_fk_stmt;

SET @has_transfer_creator_fk = (
  SELECT COUNT(*)
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'inventory_transfer_log'
    AND constraint_name = 'fk_inventory_transfer_creator'
);
SET @transfer_creator_fk_sql = IF(
  @has_transfer_creator_fk = 0,
  'ALTER TABLE inventory_transfer_log ADD CONSTRAINT fk_inventory_transfer_creator FOREIGN KEY (created_by) REFERENCES user_account (user_id) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE transfer_creator_fk_stmt FROM @transfer_creator_fk_sql;
EXECUTE transfer_creator_fk_stmt;
DEALLOCATE PREPARE transfer_creator_fk_stmt;

SET @root_org_id = NULL;
SELECT org_unit_id
INTO @root_org_id
FROM org_unit
WHERE is_active = 1
  AND parent_org_unit_id IS NULL
ORDER BY sort_order, org_unit_id
LIMIT 1;

INSERT INTO org_unit (org_code, org_name, parent_org_unit_id, sort_order, is_active)
SELECT 'ROOT', '根组织', NULL, 0, 1
FROM DUAL
WHERE @root_org_id IS NULL;

SELECT org_unit_id
INTO @root_org_id
FROM org_unit
WHERE is_active = 1
  AND parent_org_unit_id IS NULL
ORDER BY sort_order, org_unit_id
LIMIT 1;

INSERT INTO inventory_warehouse (
  warehouse_code, warehouse_name, org_unit_id, is_active, remarks
)
VALUES ('WH-001', '仓库1', @root_org_id, 1, '系统迁移创建的默认仓库')
ON DUPLICATE KEY UPDATE
  warehouse_name = VALUES(warehouse_name),
  org_unit_id = VALUES(org_unit_id),
  is_active = 1;

SELECT warehouse_id
INTO @default_warehouse_id
FROM inventory_warehouse
WHERE warehouse_code = 'WH-001'
LIMIT 1;

INSERT INTO inventory_warehouse_stock (warehouse_id, model_id, quantity)
SELECT @default_warehouse_id, model_id, quantity
FROM it_inventory_model
WHERE is_active = 1
ON DUPLICATE KEY UPDATE
  warehouse_id = VALUES(warehouse_id);

INSERT INTO auth_module (module_code, module_name, category, sort_order, is_active)
VALUES ('warehouse_management', '仓库管理', 'inventory', 55, 1)
ON DUPLICATE KEY UPDATE
  module_name = VALUES(module_name),
  category = VALUES(category),
  sort_order = VALUES(sort_order),
  is_active = 1;

INSERT IGNORE INTO auth_permission (module_code, action_code)
VALUES
  ('warehouse_management', 'view'),
  ('warehouse_management', 'create'),
  ('warehouse_management', 'update'),
  ('warehouse_management', 'delete'),
  ('warehouse_management', 'approve'),
  ('warehouse_management', 'export');

INSERT INTO auth_role_permission (
  role_id, permission_id, can_view, can_create, can_update,
  can_delete, can_approve, can_export, data_scope
)
SELECT
  role.role_id,
  permission.permission_id,
  1, 1, 1, 1, 1, 1, 'all'
FROM auth_role role
JOIN auth_permission permission
  ON permission.module_code = 'warehouse_management'
WHERE role.is_active = 1
  AND (
    role.is_super_admin = 1
    OR role.role_code = 'admin'
    OR role.role_category = 'admin'
  )
ON DUPLICATE KEY UPDATE
  can_view = 1,
  can_create = 1,
  can_update = 1,
  can_delete = 1,
  can_approve = 1,
  can_export = 1,
  data_scope = 'all';
