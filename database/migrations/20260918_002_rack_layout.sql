SET NAMES utf8mb4;

-- 机柜视图（独立模块）：把台账里的设备放到机柜的具体 U 位，
-- 支持前面板 / 后面板 / 整机深度三种安装面，位置冲突由服务层校验。
-- 本迁移只新增表与权限，不改动历史业务数据。

CREATE TABLE IF NOT EXISTS rack_device_placement (
  placement_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  rack_id BIGINT UNSIGNED NOT NULL,
  source_kind VARCHAR(16) NOT NULL DEFAULT 'custom',
  computer_id BIGINT UNSIGNED NULL,
  inventory_model_id BIGINT UNSIGNED NULL,
  display_name VARCHAR(128) NOT NULL,
  brand_model VARCHAR(160) NOT NULL DEFAULT '',
  category VARCHAR(32) NOT NULL DEFAULT 'other',
  position_u INT NOT NULL,
  u_height INT NOT NULL DEFAULT 1,
  face VARCHAR(8) NOT NULL DEFAULT 'front',
  status_snapshot VARCHAR(32) NOT NULL DEFAULT '',
  asset_code VARCHAR(128) NOT NULL DEFAULT '',
  serial_number VARCHAR(128) NOT NULL DEFAULT '',
  owner_label VARCHAR(128) NOT NULL DEFAULT '',
  notes VARCHAR(500) NOT NULL DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_by BIGINT UNSIGNED NULL,
  updated_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (placement_id),
  UNIQUE KEY uq_rack_placement_computer (computer_id),
  KEY idx_rack_placement_rack (rack_id, is_active, position_u),
  KEY idx_rack_placement_computer (computer_id, is_active),
  CONSTRAINT fk_rack_placement_rack
    FOREIGN KEY (rack_id) REFERENCES asset_rack (rack_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_rack_placement_computer
    FOREIGN KEY (computer_id) REFERENCES computer_asset (computer_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_rack_placement_inventory_model
    FOREIGN KEY (inventory_model_id) REFERENCES it_inventory_model (model_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_rack_placement_created_by
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_rack_placement_updated_by
    FOREIGN KEY (updated_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_rack_placement_source_kind
    CHECK (source_kind IN ('computer', 'custom')),
  CONSTRAINT ck_rack_placement_category CHECK (
    category IN (
      'server', 'network', 'patch-panel', 'power', 'storage',
      'kvm', 'av-media', 'cooling', 'shelf', 'blank', 'cable-management', 'other'
    )
  ),
  CONSTRAINT ck_rack_placement_face CHECK (face IN ('front', 'rear', 'both')),
  CONSTRAINT ck_rack_placement_position CHECK (position_u >= 1),
  CONSTRAINT ck_rack_placement_height CHECK (u_height BETWEEN 1 AND 50),
  CONSTRAINT ck_rack_placement_active CHECK (is_active IN (0, 1))
) ENGINE=InnoDB;

INSERT INTO auth_module (module_code, module_name, category, sort_order, is_active)
VALUES ('rack_layout', '机柜视图', 'asset', 25, 1)
ON DUPLICATE KEY UPDATE
  module_name = VALUES(module_name),
  category = VALUES(category),
  sort_order = VALUES(sort_order),
  is_active = 1;

INSERT IGNORE INTO auth_permission (module_code, action_code)
VALUES
  ('rack_layout', 'view'),
  ('rack_layout', 'create'),
  ('rack_layout', 'update'),
  ('rack_layout', 'delete'),
  ('rack_layout', 'export');

INSERT INTO auth_role_permission (
  role_id, permission_id, can_view, can_create, can_update,
  can_delete, can_approve, can_export, data_scope
)
SELECT
  role.role_id,
  permission.permission_id,
  1, 1, 1, 1, 0, 1, 'all'
FROM auth_role role
JOIN auth_permission permission
  ON permission.module_code = 'rack_layout'
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
  can_export = 1,
  data_scope = 'all';
