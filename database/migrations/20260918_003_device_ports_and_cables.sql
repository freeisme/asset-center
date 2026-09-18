SET NAMES utf8mb4;

-- 设备面板与网络拓扑（阶段 1/2）：型号库、端口模板、实例端口、线缆与拓扑坐标。
-- 本迁移只新增表，不改动历史业务数据，也不改变既有接口；
-- 端口与线缆的冲突规则（同端口只能有一条活动链路、不能自己连自己）由服务层校验。

CREATE TABLE IF NOT EXISTS device_type_catalog (
  catalog_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  slug VARCHAR(100) NOT NULL,
  manufacturer VARCHAR(100) NOT NULL DEFAULT '',
  model VARCHAR(128) NOT NULL,
  part_number VARCHAR(100) NOT NULL DEFAULT '',
  u_height DECIMAL(4,1) NOT NULL DEFAULT 1.0,
  category VARCHAR(32) NOT NULL DEFAULT 'other',
  is_full_depth TINYINT(1) NOT NULL DEFAULT 1,
  front_image TINYINT(1) NOT NULL DEFAULT 0,
  rear_image TINYINT(1) NOT NULL DEFAULT 0,
  image_front_path VARCHAR(255) NOT NULL DEFAULT '',
  image_rear_path VARCHAR(255) NOT NULL DEFAULT '',
  source VARCHAR(32) NOT NULL DEFAULT 'manual',
  source_ref VARCHAR(255) NOT NULL DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (catalog_id),
  UNIQUE KEY uq_device_type_slug (slug),
  KEY idx_device_type_manufacturer (manufacturer, model),
  KEY idx_device_type_category (category, is_active),
  CONSTRAINT ck_device_type_u_height CHECK (u_height >= 0.5 AND u_height <= 50),
  CONSTRAINT ck_device_type_category CHECK (
    category IN (
      'server', 'network', 'patch-panel', 'power', 'storage',
      'kvm', 'av-media', 'cooling', 'shelf', 'blank', 'cable-management', 'other'
    )
  ),
  CONSTRAINT ck_device_type_full_depth CHECK (is_full_depth IN (0, 1)),
  CONSTRAINT ck_device_type_images CHECK (front_image IN (0, 1) AND rear_image IN (0, 1)),
  CONSTRAINT ck_device_type_active CHECK (is_active IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS device_type_port_template (
  template_port_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  catalog_id BIGINT UNSIGNED NOT NULL,
  face VARCHAR(8) NOT NULL DEFAULT 'front',
  port_name VARCHAR(64) NOT NULL,
  port_type VARCHAR(64) NOT NULL DEFAULT '',
  port_kind VARCHAR(16) NOT NULL DEFAULT 'network',
  row_index INT NOT NULL DEFAULT 1,
  position_index INT NOT NULL DEFAULT 1,
  notes VARCHAR(255) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (template_port_id),
  UNIQUE KEY uq_device_type_port (catalog_id, face, port_name),
  KEY idx_device_type_port_order (catalog_id, face, row_index, position_index),
  CONSTRAINT fk_device_type_port_catalog
    FOREIGN KEY (catalog_id) REFERENCES device_type_catalog (catalog_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT ck_device_type_port_face CHECK (face IN ('front', 'rear')),
  CONSTRAINT ck_device_type_port_kind
    CHECK (port_kind IN ('network', 'fiber', 'power', 'console', 'other'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS rack_device_port (
  port_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  placement_id BIGINT UNSIGNED NOT NULL,
  face VARCHAR(8) NOT NULL DEFAULT 'front',
  port_name VARCHAR(64) NOT NULL,
  port_type VARCHAR(64) NOT NULL DEFAULT '',
  port_kind VARCHAR(16) NOT NULL DEFAULT 'network',
  row_index INT NOT NULL DEFAULT 1,
  position_index INT NOT NULL DEFAULT 1,
  direction VARCHAR(8) NOT NULL DEFAULT 'bidi',
  speed VARCHAR(32) NOT NULL DEFAULT '',
  status VARCHAR(16) NOT NULL DEFAULT 'unknown',
  notes VARCHAR(255) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (port_id),
  UNIQUE KEY uq_rack_port_name (placement_id, face, port_name),
  KEY idx_rack_port_placement (placement_id, row_index, position_index),
  KEY idx_rack_port_status (status),
  CONSTRAINT fk_rack_port_placement
    FOREIGN KEY (placement_id) REFERENCES rack_device_placement (placement_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT ck_rack_port_face CHECK (face IN ('front', 'rear')),
  CONSTRAINT ck_rack_port_kind
    CHECK (port_kind IN ('network', 'fiber', 'power', 'console', 'other')),
  CONSTRAINT ck_rack_port_direction CHECK (direction IN ('in', 'out', 'bidi')),
  CONSTRAINT ck_rack_port_status CHECK (status IN ('up', 'down', 'disabled', 'unknown'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS rack_cable_run (
  cable_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  a_port_id BIGINT UNSIGNED NOT NULL,
  b_port_id BIGINT UNSIGNED NOT NULL,
  medium VARCHAR(16) NOT NULL DEFAULT 'cat6',
  length_m DECIMAL(6,1) NULL,
  label VARCHAR(128) NOT NULL DEFAULT '',
  status VARCHAR(16) NOT NULL DEFAULT 'connected',
  notes VARCHAR(500) NOT NULL DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  a_active_key BIGINT UNSIGNED
    GENERATED ALWAYS AS (IF(is_active = 1, a_port_id, NULL)) VIRTUAL,
  b_active_key BIGINT UNSIGNED
    GENERATED ALWAYS AS (IF(is_active = 1, b_port_id, NULL)) VIRTUAL,
  created_by BIGINT UNSIGNED NULL,
  updated_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (cable_id),
  UNIQUE KEY uq_cable_port_a (a_active_key),
  UNIQUE KEY uq_cable_port_b (b_active_key),
  KEY idx_cable_status (status, is_active),
  CONSTRAINT fk_cable_port_a
    FOREIGN KEY (a_port_id) REFERENCES rack_device_port (port_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_cable_port_b
    FOREIGN KEY (b_port_id) REFERENCES rack_device_port (port_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_cable_created_by
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_cable_updated_by
    FOREIGN KEY (updated_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_cable_medium CHECK (
    medium IN ('cat5e', 'cat6', 'fiber-om3', 'fiber-os2', 'dac', 'power', 'console', 'other')
  ),
  CONSTRAINT ck_cable_status
    CHECK (status IN ('connected', 'planned', 'disconnected', 'fault')),
  CONSTRAINT ck_cable_active CHECK (is_active IN (0, 1)),
  CONSTRAINT ck_cable_length CHECK (length_m IS NULL OR length_m > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS topology_node_position (
  position_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  node_kind VARCHAR(16) NOT NULL DEFAULT 'placement',
  node_id BIGINT UNSIGNED NOT NULL,
  x INT NOT NULL DEFAULT 0,
  y INT NOT NULL DEFAULT 0,
  updated_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (position_id),
  UNIQUE KEY uq_topology_node (node_kind, node_id),
  CONSTRAINT fk_topology_position_placement
    FOREIGN KEY (node_id) REFERENCES rack_device_placement (placement_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_topology_position_updated_by
    FOREIGN KEY (updated_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_topology_node_kind CHECK (node_kind IN ('placement'))
) ENGINE=InnoDB;
