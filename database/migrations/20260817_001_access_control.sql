SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS auth_module (
  module_code VARCHAR(64) NOT NULL,
  module_name VARCHAR(128) NOT NULL,
  category VARCHAR(64) NOT NULL DEFAULT 'system',
  sort_order INT NOT NULL DEFAULT 1000,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (module_code),
  KEY idx_auth_module_active (is_active, sort_order)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS auth_role (
  role_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  role_code VARCHAR(64) NOT NULL,
  role_name VARCHAR(128) NOT NULL,
  is_system TINYINT(1) NOT NULL DEFAULT 0,
  is_super_admin TINYINT(1) NOT NULL DEFAULT 0,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (role_id),
  UNIQUE KEY uq_auth_role_code (role_code),
  KEY idx_auth_role_active (is_active, role_name),
  CONSTRAINT fk_auth_role_creator
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_auth_role_flags CHECK (is_system IN (0, 1) AND is_super_admin IN (0, 1) AND is_active IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS auth_permission (
  permission_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  module_code VARCHAR(64) NOT NULL,
  action_code VARCHAR(32) NOT NULL,
  PRIMARY KEY (permission_id),
  UNIQUE KEY uq_auth_permission (module_code, action_code),
  CONSTRAINT fk_auth_permission_module
    FOREIGN KEY (module_code) REFERENCES auth_module (module_code)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS auth_role_permission (
  role_id BIGINT UNSIGNED NOT NULL,
  permission_id BIGINT UNSIGNED NOT NULL,
  can_view TINYINT(1) NOT NULL DEFAULT 0,
  can_create TINYINT(1) NOT NULL DEFAULT 0,
  can_update TINYINT(1) NOT NULL DEFAULT 0,
  can_delete TINYINT(1) NOT NULL DEFAULT 0,
  can_approve TINYINT(1) NOT NULL DEFAULT 0,
  can_export TINYINT(1) NOT NULL DEFAULT 0,
  data_scope VARCHAR(32) NOT NULL DEFAULT 'none',
  PRIMARY KEY (role_id, permission_id),
  CONSTRAINT fk_auth_role_permission_role
    FOREIGN KEY (role_id) REFERENCES auth_role (role_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_auth_role_permission_permission
    FOREIGN KEY (permission_id) REFERENCES auth_permission (permission_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT ck_auth_role_permission_scope CHECK (data_scope IN ('all', 'organization', 'own', 'submitted', 'assigned', 'none'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS auth_user_permission (
  user_id BIGINT UNSIGNED NOT NULL,
  permission_id BIGINT UNSIGNED NOT NULL,
  can_view TINYINT(1) NOT NULL DEFAULT 0,
  can_create TINYINT(1) NOT NULL DEFAULT 0,
  can_update TINYINT(1) NOT NULL DEFAULT 0,
  can_delete TINYINT(1) NOT NULL DEFAULT 0,
  can_approve TINYINT(1) NOT NULL DEFAULT 0,
  can_export TINYINT(1) NOT NULL DEFAULT 0,
  data_scope VARCHAR(32) NOT NULL DEFAULT 'none',
  PRIMARY KEY (user_id, permission_id),
  CONSTRAINT fk_auth_user_permission_user
    FOREIGN KEY (user_id) REFERENCES user_account (user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_auth_user_permission_permission
    FOREIGN KEY (permission_id) REFERENCES auth_permission (permission_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT ck_auth_user_permission_scope CHECK (data_scope IN ('all', 'organization', 'own', 'submitted', 'assigned', 'none'))
) ENGINE=InnoDB;

SET @has_role_code = (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'user_account'
    AND column_name = 'role_code'
);
SET @role_code_sql = IF(
  @has_role_code = 0,
  'ALTER TABLE user_account ADD COLUMN role_code VARCHAR(64) NULL AFTER user_role',
  'SELECT 1'
);
PREPARE role_code_stmt FROM @role_code_sql;
EXECUTE role_code_stmt;
DEALLOCATE PREPARE role_code_stmt;

INSERT INTO auth_module (module_code, module_name, category, sort_order)
VALUES
  ('dashboard', 'Dashboard', 'asset', 10),
  ('it_assets', 'IT assets', 'asset', 20),
  ('employees', 'Employees', 'asset', 30),
  ('organizations', 'Organizations and asset relations', 'asset', 40),
  ('inventory_catalog', 'Inventory catalog', 'inventory', 50),
  ('inventory_operations', 'Allocation, return, receipt and issue', 'inventory', 60),
  ('tickets', 'ITIL service desk', 'itil', 70),
  ('sync', 'Synchronization staging', 'governance', 80),
  ('quality', 'Data quality audit', 'governance', 90),
  ('audit_logs', 'Operation logs', 'governance', 100),
  ('backups', 'Database backups', 'system', 110),
  ('system_settings', 'System settings', 'system', 120),
  ('user_management', 'User accounts', 'system', 130),
  ('role_management', 'Roles and permissions', 'system', 140),
  ('system_updates', 'System updates', 'system', 150)
ON DUPLICATE KEY UPDATE
  module_name = VALUES(module_name),
  category = VALUES(category),
  sort_order = VALUES(sort_order),
  is_active = 1;

INSERT IGNORE INTO auth_permission (module_code, action_code)
SELECT module_code, action_code
FROM (
  SELECT module_code
  FROM auth_module
  WHERE is_active = 1
) modules
CROSS JOIN (
  SELECT 'view' AS action_code
  UNION ALL SELECT 'create'
  UNION ALL SELECT 'update'
  UNION ALL SELECT 'delete'
  UNION ALL SELECT 'approve'
  UNION ALL SELECT 'export'
) actions;

INSERT INTO auth_role (role_code, role_name, is_system, is_super_admin)
VALUES
  ('admin', 'Administrator', 1, 1),
  ('operator', 'Operator', 1, 0),
  ('viewer', 'Read only', 1, 0),
  ('user', 'Ordinary user', 1, 0)
ON DUPLICATE KEY UPDATE
  role_name = VALUES(role_name),
  is_system = VALUES(is_system),
  is_super_admin = VALUES(is_super_admin),
  is_active = 1;

UPDATE user_account
SET role_code = CASE
  WHEN user_role IN ('admin', 'operator', 'viewer') THEN user_role
  ELSE 'user'
END
WHERE role_code IS NULL OR role_code = '';

INSERT IGNORE INTO auth_role_permission (
  role_id, permission_id, can_view, can_create, can_update,
  can_delete, can_approve, can_export, data_scope
)
SELECT
  role.role_id,
  permission.permission_id,
  CASE
    WHEN permission.action_code <> 'view' THEN 0
    WHEN role.role_code = 'admin' THEN 1
    WHEN role.role_code = 'operator'
      AND permission.module_code IN (
        'dashboard', 'it_assets', 'employees', 'organizations',
        'inventory_catalog', 'inventory_operations', 'tickets', 'sync', 'quality', 'audit_logs'
      ) THEN 1
    WHEN role.role_code = 'viewer'
      AND permission.module_code NOT IN ('user_management', 'role_management', 'system_updates') THEN 1
    WHEN role.role_code = 'user'
      AND permission.module_code IN ('dashboard', 'it_assets', 'tickets') THEN 1
    ELSE 0
  END,
  CASE
    WHEN permission.action_code <> 'create' THEN 0
    WHEN role.role_code = 'admin' THEN 1
    WHEN role.role_code = 'operator'
      AND permission.module_code IN (
        'it_assets', 'employees', 'organizations',
        'inventory_catalog', 'inventory_operations', 'tickets', 'sync'
      ) THEN 1
    WHEN role.role_code = 'user' AND permission.module_code = 'tickets' THEN 1
    ELSE 0
  END,
  CASE
    WHEN permission.action_code <> 'update' THEN 0
    WHEN role.role_code = 'admin' THEN 1
    WHEN role.role_code = 'operator'
      AND permission.module_code IN (
        'it_assets', 'employees', 'organizations',
        'inventory_catalog', 'inventory_operations', 'tickets', 'sync', 'quality'
      ) THEN 1
    ELSE 0
  END,
  IF(
    permission.action_code = 'delete'
    AND role.role_code = 'admin'
    AND permission.module_code IN ('it_assets', 'employees', 'organizations', 'inventory_catalog'),
    1,
    0
  ),
  IF(
    permission.action_code = 'approve'
    AND role.role_code = 'admin',
    1,
    IF(
      permission.action_code = 'approve'
      AND role.role_code = 'operator'
      AND permission.module_code IN ('inventory_operations', 'tickets', 'sync', 'quality'),
      1,
      0
    )
  ),
  IF(
    permission.action_code = 'export'
    AND role.role_code IN ('admin', 'operator', 'viewer')
    AND permission.module_code NOT IN ('user_management', 'role_management'),
    1,
    0
  ),
  CASE
    WHEN role.role_code = 'admin' THEN 'all'
    WHEN role.role_code = 'user' AND permission.module_code = 'tickets' THEN 'submitted'
    WHEN role.role_code = 'user' THEN 'own'
    ELSE 'all'
  END
FROM auth_role role
CROSS JOIN auth_permission permission;
