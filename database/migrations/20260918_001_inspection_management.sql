SET NAMES utf8mb4;

-- 巡检管理：机房、弱电间与机柜的巡检模板、巡检任务和逐项记录。
-- 本迁移只新增表、字典和权限，不改动历史业务数据；
-- 巡检任务开始时会把模板事项快照进任务明细，后续改模板不影响历史巡检表。

CREATE TABLE IF NOT EXISTS asset_site (
  site_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  site_code VARCHAR(64) NOT NULL,
  site_name VARCHAR(128) NOT NULL,
  site_type VARCHAR(32) NOT NULL DEFAULT 'server_room',
  org_unit_id BIGINT UNSIGNED NULL,
  location_desc VARCHAR(255) NOT NULL DEFAULT '',
  remarks VARCHAR(500) NOT NULL DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (site_id),
  UNIQUE KEY uq_asset_site_code (site_code),
  KEY idx_asset_site_type (site_type, is_active),
  CONSTRAINT fk_asset_site_org_unit
    FOREIGN KEY (org_unit_id) REFERENCES org_unit (org_unit_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_asset_site_type CHECK (site_type IN ('server_room', 'weak_room')),
  CONSTRAINT ck_asset_site_active CHECK (is_active IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS asset_rack (
  rack_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  rack_code VARCHAR(64) NOT NULL,
  rack_name VARCHAR(128) NOT NULL,
  site_id BIGINT UNSIGNED NOT NULL,
  height_u INT NOT NULL DEFAULT 42,
  desc_units TINYINT(1) NOT NULL DEFAULT 0,
  org_unit_id BIGINT UNSIGNED NULL,
  remarks VARCHAR(500) NOT NULL DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (rack_id),
  UNIQUE KEY uq_asset_rack_code (rack_code),
  KEY idx_asset_rack_site (site_id, is_active),
  CONSTRAINT fk_asset_rack_site
    FOREIGN KEY (site_id) REFERENCES asset_site (site_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_asset_rack_org_unit
    FOREIGN KEY (org_unit_id) REFERENCES org_unit (org_unit_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_asset_rack_height CHECK (height_u BETWEEN 1 AND 100),
  CONSTRAINT ck_asset_rack_desc_units CHECK (desc_units IN (0, 1)),
  CONSTRAINT ck_asset_rack_active CHECK (is_active IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inspection_template (
  template_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  template_code VARCHAR(64) NOT NULL,
  template_name VARCHAR(128) NOT NULL,
  site_type VARCHAR(32) NOT NULL DEFAULT 'both',
  description VARCHAR(500) NOT NULL DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_by BIGINT UNSIGNED NULL,
  updated_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (template_id),
  UNIQUE KEY uq_inspection_template_code (template_code),
  CONSTRAINT fk_inspection_template_created_by
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_inspection_template_updated_by
    FOREIGN KEY (updated_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_inspection_template_site_type
    CHECK (site_type IN ('server_room', 'weak_room', 'both')),
  CONSTRAINT ck_inspection_template_active CHECK (is_active IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inspection_template_item (
  item_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  template_id BIGINT UNSIGNED NOT NULL,
  seq_no INT NOT NULL DEFAULT 10,
  category VARCHAR(64) NOT NULL DEFAULT '通用',
  item_title VARCHAR(200) NOT NULL,
  check_method VARCHAR(255) NOT NULL DEFAULT '',
  value_type VARCHAR(16) NOT NULL DEFAULT 'ok_fail',
  unit VARCHAR(32) NOT NULL DEFAULT '',
  normal_range VARCHAR(128) NOT NULL DEFAULT '',
  is_required TINYINT(1) NOT NULL DEFAULT 1,
  options_json JSON NULL,
  remarks VARCHAR(500) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (item_id),
  KEY idx_inspection_template_item (template_id, seq_no),
  CONSTRAINT fk_inspection_template_item_template
    FOREIGN KEY (template_id) REFERENCES inspection_template (template_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT ck_inspection_template_item_value_type
    CHECK (value_type IN ('ok_fail', 'number', 'text', 'select')),
  CONSTRAINT ck_inspection_template_item_required CHECK (is_required IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inspection_task (
  task_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  task_no VARCHAR(64) NOT NULL,
  template_id BIGINT UNSIGNED NULL,
  template_name VARCHAR(128) NOT NULL DEFAULT '',
  scope_kind VARCHAR(16) NOT NULL,
  site_id BIGINT UNSIGNED NULL,
  site_name VARCHAR(128) NOT NULL DEFAULT '',
  rack_id BIGINT UNSIGNED NULL,
  rack_name VARCHAR(128) NOT NULL DEFAULT '',
  inspector_user_id BIGINT UNSIGNED NULL,
  inspector_name VARCHAR(128) NOT NULL DEFAULT '',
  status VARCHAR(16) NOT NULL DEFAULT 'running',
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  submitted_at DATETIME NULL,
  item_total INT NOT NULL DEFAULT 0,
  item_ok INT NOT NULL DEFAULT 0,
  item_fail INT NOT NULL DEFAULT 0,
  item_na INT NOT NULL DEFAULT 0,
  abnormal_summary VARCHAR(1000) NOT NULL DEFAULT '',
  remarks VARCHAR(500) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (task_id),
  UNIQUE KEY uq_inspection_task_no (task_no),
  KEY idx_inspection_task_status (status, started_at),
  KEY idx_inspection_task_scope (site_id, rack_id),
  CONSTRAINT fk_inspection_task_template
    FOREIGN KEY (template_id) REFERENCES inspection_template (template_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_inspection_task_site
    FOREIGN KEY (site_id) REFERENCES asset_site (site_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_inspection_task_rack
    FOREIGN KEY (rack_id) REFERENCES asset_rack (rack_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_inspection_task_inspector
    FOREIGN KEY (inspector_user_id) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_inspection_task_scope_kind CHECK (scope_kind IN ('site', 'rack')),
  CONSTRAINT ck_inspection_task_status
    CHECK (status IN ('running', 'submitted', 'void'))
) ENGINE=InnoDB;

-- 巡检对象二选一（机房/弱电间或机柜）由服务层校验：MySQL 不允许在被
-- ON DELETE SET NULL 外键引用的列上再建 CHECK 约束。

CREATE TABLE IF NOT EXISTS inspection_task_item (
  task_item_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  task_id BIGINT UNSIGNED NOT NULL,
  seq_no INT NOT NULL DEFAULT 10,
  category VARCHAR(64) NOT NULL DEFAULT '通用',
  item_title VARCHAR(200) NOT NULL,
  check_method VARCHAR(255) NOT NULL DEFAULT '',
  value_type VARCHAR(16) NOT NULL DEFAULT 'ok_fail',
  unit VARCHAR(32) NOT NULL DEFAULT '',
  normal_range VARCHAR(128) NOT NULL DEFAULT '',
  is_required TINYINT(1) NOT NULL DEFAULT 1,
  result VARCHAR(16) NOT NULL DEFAULT 'pending',
  value_text VARCHAR(255) NOT NULL DEFAULT '',
  notes VARCHAR(500) NOT NULL DEFAULT '',
  is_abnormal TINYINT(1) NOT NULL DEFAULT 0,
  checked_at DATETIME NULL,
  checked_by_user_id BIGINT UNSIGNED NULL,
  checked_by_name VARCHAR(128) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (task_item_id),
  KEY idx_inspection_task_item (task_id, seq_no),
  CONSTRAINT fk_inspection_task_item_task
    FOREIGN KEY (task_id) REFERENCES inspection_task (task_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_inspection_task_item_checked_by
    FOREIGN KEY (checked_by_user_id) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_inspection_task_item_value_type
    CHECK (value_type IN ('ok_fail', 'number', 'text', 'select')),
  CONSTRAINT ck_inspection_task_item_result
    CHECK (result IN ('pending', 'ok', 'fail', 'na')),
  CONSTRAINT ck_inspection_task_item_abnormal CHECK (is_abnormal IN (0, 1))
) ENGINE=InnoDB;

INSERT INTO inspection_template (template_code, template_name, site_type, description, is_active)
VALUES
  ('XJ-SERVER-ROOM', '机房巡检', 'server_room', '机房环境、供电、设备与安全隐患标准巡检表', 1),
  ('XJ-WEAK-ROOM', '弱电间巡检', 'weak_room', '弱电间环境、配线、网络设备与安全隐患标准巡检表', 1)
ON DUPLICATE KEY UPDATE
  template_name = VALUES(template_name),
  site_type = VALUES(site_type),
  description = VALUES(description);

SET @tpl_server_room = (
  SELECT template_id FROM inspection_template WHERE template_code = 'XJ-SERVER-ROOM'
);
SET @tpl_weak_room = (
  SELECT template_id FROM inspection_template WHERE template_code = 'XJ-WEAK-ROOM'
);

INSERT INTO inspection_template_item (
  template_id, seq_no, category, item_title, check_method, value_type, unit, normal_range, is_required
)
SELECT
  @tpl_server_room, seed.seq_no, seed.category, seed.item_title, seed.check_method,
  seed.value_type, seed.unit, seed.normal_range, seed.is_required
FROM (
  SELECT 10 AS seq_no, '环境' AS category, '机房温度' AS item_title, '查看温湿度计并记录' AS check_method,
         'number' AS value_type, '℃' AS unit, '18-27' AS normal_range, 1 AS is_required, 1 AS auto_ticket
  UNION ALL SELECT 20, '环境', '机房湿度', '查看温湿度计并记录', 'number', '%', '40-70', 1, 1
  UNION ALL SELECT 30, '环境', '机房清洁与无异味', '目视检查地面、墙面与设备表面', 'ok_fail', '', '', 1, 0
  UNION ALL SELECT 40, '供电', 'UPS 运行状态与告警灯', '查看 UPS 面板指示灯与告警', 'ok_fail', '', '', 1, 1
  UNION ALL SELECT 50, '供电', 'UPS 电池健康或剩余容量', '查看 UPS 管理界面或面板读数', 'number', '%', '>=70', 1, 1
  UNION ALL SELECT 60, '供电', '市电与配电柜无异常', '目视检查配电柜、空开与指示灯', 'ok_fail', '', '', 1, 1
  UNION ALL SELECT 70, '设备', '服务器与存储指示灯正常', '逐台查看电源、硬盘与告警指示灯', 'ok_fail', '', '', 1, 1
  UNION ALL SELECT 80, '设备', '网络设备指示灯与端口状态正常', '查看交换机、路由器面板指示', 'ok_fail', '', '', 1, 1
  UNION ALL SELECT 90, '设备', '风扇与散热运行正常', '听声音、看转速与出风温度', 'ok_fail', '', '', 1, 1
  UNION ALL SELECT 100, '线缆', '线缆走线整齐、无破损', '目视检查跳线与主干线缆', 'ok_fail', '', '', 1, 0
  UNION ALL SELECT 110, '线缆', '线缆与端口标签完整', '抽查标签是否缺失或模糊', 'ok_fail', '', '', 1, 0
  UNION ALL SELECT 120, '安全', '消防设施可用、无遮挡', '检查灭火器压力表与有效期', 'ok_fail', '', '', 1, 1
  UNION ALL SELECT 130, '安全', '门禁、监控与钥匙管理正常', '检查门禁记录与摄像头画面', 'ok_fail', '', '', 1, 0
  UNION ALL SELECT 140, '安全', '无漏水、无渗水痕迹', '检查天花板、地面与管线', 'ok_fail', '', '', 1, 1
  UNION ALL SELECT 150, '安全', '防尘、防鼠措施有效', '检查封堵、防鼠板与积尘', 'ok_fail', '', '', 1, 0
  UNION ALL SELECT 160, '隐患', '本次巡检发现的问题与处理建议', '记录问题、影响范围与建议处理方式', 'text', '', '', 0, 1
) AS seed
WHERE @tpl_server_room IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM inspection_template_item existing
    WHERE existing.template_id = @tpl_server_room
  );

INSERT INTO inspection_template_item (
  template_id, seq_no, category, item_title, check_method, value_type, unit, normal_range, is_required
)
SELECT
  @tpl_weak_room, seed.seq_no, seed.category, seed.item_title, seed.check_method,
  seed.value_type, seed.unit, seed.normal_range, seed.is_required
FROM (
  SELECT 10 AS seq_no, '环境' AS category, '弱电间温度' AS item_title, '查看温湿度计并记录' AS check_method,
         'number' AS value_type, '℃' AS unit, '18-30' AS normal_range, 1 AS is_required, 1 AS auto_ticket
  UNION ALL SELECT 20, '环境', '弱电间湿度', '查看温湿度计并记录', 'number', '%', '40-75', 1, 1
  UNION ALL SELECT 30, '环境', '无渗漏、无积水', '检查地面、桥架与管线', 'ok_fail', '', '', 1, 1
  UNION ALL SELECT 40, '环境', '清洁与无杂物堆放', '目视检查房间与机柜周边', 'ok_fail', '', '', 1, 0
  UNION ALL SELECT 50, '机柜', '机柜与门锁完好', '检查柜门、锁具与固定情况', 'ok_fail', '', '', 1, 0
  UNION ALL SELECT 60, '机柜', '配线架与理线架整齐', '检查跳线走向与理线情况', 'ok_fail', '', '', 1, 0
  UNION ALL SELECT 70, '设备', '交换机与网络设备指示灯正常', '查看电源、链路与告警指示灯', 'ok_fail', '', '', 1, 1
  UNION ALL SELECT 80, '设备', '设备散热风扇运行正常', '听声音、摸出风温度', 'ok_fail', '', '', 1, 1
  UNION ALL SELECT 90, '供电', '电源模块与配电状态正常', '检查空开、电源适配器与排插', 'ok_fail', '', '', 1, 1
  UNION ALL SELECT 100, '供电', '接地与防雷措施完好', '检查接地线连接与防雷器状态', 'ok_fail', '', '', 1, 0
  UNION ALL SELECT 110, '线缆', '线缆标签完整可读', '抽查主干与端口标签', 'ok_fail', '', '', 1, 0
  UNION ALL SELECT 120, '安全', '消防设施可用、无遮挡', '检查灭火器与烟感状态', 'ok_fail', '', '', 1, 1
  UNION ALL SELECT 130, '安全', '门禁与钥匙管理正常', '检查门禁记录与钥匙台账', 'ok_fail', '', '', 1, 0
  UNION ALL SELECT 140, '隐患', '本次巡检发现的问题与处理建议', '记录问题、影响范围与建议处理方式', 'text', '', '', 0, 1
) AS seed
WHERE @tpl_weak_room IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM inspection_template_item existing
    WHERE existing.template_id = @tpl_weak_room
  );

INSERT INTO auth_module (module_code, module_name, category, sort_order, is_active)
VALUES ('inspection_management', '巡检管理', 'inventory', 58, 1)
ON DUPLICATE KEY UPDATE
  module_name = VALUES(module_name),
  category = VALUES(category),
  sort_order = VALUES(sort_order),
  is_active = 1;

INSERT IGNORE INTO auth_permission (module_code, action_code)
VALUES
  ('inspection_management', 'view'),
  ('inspection_management', 'create'),
  ('inspection_management', 'update'),
  ('inspection_management', 'delete'),
  ('inspection_management', 'export');

INSERT INTO auth_role_permission (
  role_id, permission_id, can_view, can_create, can_update,
  can_delete, can_approve, can_export, data_scope
)
SELECT
  role.role_id,
  permission.permission_id,
  1, 1, 1, 0, 0, 1, 'all'
FROM auth_role role
JOIN auth_permission permission
  ON permission.module_code = 'inspection_management'
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
  can_export = 1,
  data_scope = 'all';
