SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS service_form (
  form_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  form_code VARCHAR(64) NOT NULL,
  form_name VARCHAR(128) NOT NULL,
  record_type VARCHAR(32) NOT NULL,
  description VARCHAR(500) NOT NULL DEFAULT '',
  version_no INT UNSIGNED NOT NULL DEFAULT 1,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (form_id),
  UNIQUE KEY uq_service_form_code (form_code),
  KEY idx_service_form_type (record_type, is_active),
  CONSTRAINT fk_service_form_creator
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_service_form_type CHECK (record_type IN ('ticket', 'change', 'problem')),
  CONSTRAINT ck_service_form_active CHECK (is_active IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS service_form_field (
  field_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  form_id BIGINT UNSIGNED NOT NULL,
  field_key VARCHAR(64) NOT NULL,
  field_label VARCHAR(128) NOT NULL,
  field_type VARCHAR(32) NOT NULL,
  placeholder VARCHAR(255) NOT NULL DEFAULT '',
  default_value JSON NULL,
  options_json JSON NULL,
  is_required TINYINT(1) NOT NULL DEFAULT 0,
  is_readonly TINYINT(1) NOT NULL DEFAULT 0,
  sort_order INT NOT NULL DEFAULT 100,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (field_id),
  UNIQUE KEY uq_service_form_field_key (form_id, field_key),
  KEY idx_service_form_field_order (form_id, is_active, sort_order),
  CONSTRAINT fk_service_form_field_form
    FOREIGN KEY (form_id) REFERENCES service_form (form_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT ck_service_form_field_type CHECK (
    field_type IN ('text', 'textarea', 'number', 'date', 'datetime', 'select', 'multiselect', 'checkbox', 'employee', 'asset', 'organization')
  ),
  CONSTRAINT ck_service_form_field_flags CHECK (is_required IN (0, 1) AND is_readonly IN (0, 1) AND is_active IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS service_ticket_extension (
  ticket_id BIGINT UNSIGNED NOT NULL,
  form_id BIGINT UNSIGNED NULL,
  custom_fields JSON NOT NULL,
  sla_policy_id BIGINT UNSIGNED NULL,
  sla_started_at DATETIME NULL,
  first_response_at DATETIME NULL,
  response_due_at DATETIME NULL,
  resolution_due_at DATETIME NULL,
  approval_status VARCHAR(32) NOT NULL DEFAULT 'not_required',
  PRIMARY KEY (ticket_id),
  KEY idx_service_ticket_sla (resolution_due_at, approval_status),
  CONSTRAINT fk_service_ticket_extension_ticket
    FOREIGN KEY (ticket_id) REFERENCES itil_ticket (ticket_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_service_ticket_extension_form
    FOREIGN KEY (form_id) REFERENCES service_form (form_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_service_ticket_extension_approval CHECK (
    approval_status IN ('not_required', 'pending', 'approved', 'rejected')
  )
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS itil_change (
  change_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  change_number VARCHAR(32) NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT NOT NULL,
  change_type VARCHAR(16) NOT NULL DEFAULT 'normal',
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  impact VARCHAR(16) NOT NULL DEFAULT 'medium',
  risk VARCHAR(16) NOT NULL DEFAULT 'medium',
  planned_start_at DATETIME NULL,
  planned_end_at DATETIME NULL,
  assigned_to_user_id BIGINT UNSIGNED NULL,
  requester_employee_id BIGINT UNSIGNED NULL,
  org_unit_id BIGINT UNSIGNED NULL,
  related_ticket_id BIGINT UNSIGNED NULL,
  form_id BIGINT UNSIGNED NULL,
  custom_fields JSON NOT NULL,
  created_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (change_id),
  UNIQUE KEY uq_itil_change_number (change_number),
  KEY idx_itil_change_queue (status, impact, created_at),
  KEY idx_itil_change_assignee (assigned_to_user_id, status),
  CONSTRAINT fk_itil_change_assignee
    FOREIGN KEY (assigned_to_user_id) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_itil_change_requester
    FOREIGN KEY (requester_employee_id) REFERENCES employee (employee_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_itil_change_org
    FOREIGN KEY (org_unit_id) REFERENCES org_unit (org_unit_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_itil_change_ticket
    FOREIGN KEY (related_ticket_id) REFERENCES itil_ticket (ticket_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_itil_change_form
    FOREIGN KEY (form_id) REFERENCES service_form (form_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_itil_change_creator
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_itil_change_type CHECK (change_type IN ('standard', 'normal', 'emergency')),
  CONSTRAINT ck_itil_change_status CHECK (
    status IN ('draft', 'submitted', 'assessing', 'approved', 'rejected', 'scheduled', 'implementing', 'verified', 'closed', 'cancelled')
  ),
  CONSTRAINT ck_itil_change_impact CHECK (impact IN ('low', 'medium', 'high')),
  CONSTRAINT ck_itil_change_risk CHECK (risk IN ('low', 'medium', 'high'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS itil_problem (
  problem_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  problem_number VARCHAR(32) NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'new',
  impact VARCHAR(16) NOT NULL DEFAULT 'medium',
  root_cause TEXT NULL,
  workaround TEXT NULL,
  resolution TEXT NULL,
  assigned_to_user_id BIGINT UNSIGNED NULL,
  org_unit_id BIGINT UNSIGNED NULL,
  related_ticket_id BIGINT UNSIGNED NULL,
  form_id BIGINT UNSIGNED NULL,
  custom_fields JSON NOT NULL,
  created_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (problem_id),
  UNIQUE KEY uq_itil_problem_number (problem_number),
  KEY idx_itil_problem_queue (status, impact, created_at),
  KEY idx_itil_problem_assignee (assigned_to_user_id, status),
  CONSTRAINT fk_itil_problem_assignee
    FOREIGN KEY (assigned_to_user_id) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_itil_problem_org
    FOREIGN KEY (org_unit_id) REFERENCES org_unit (org_unit_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_itil_problem_ticket
    FOREIGN KEY (related_ticket_id) REFERENCES itil_ticket (ticket_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_itil_problem_form
    FOREIGN KEY (form_id) REFERENCES service_form (form_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_itil_problem_creator
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_itil_problem_status CHECK (
    status IN ('new', 'investigating', 'known_error', 'resolved', 'closed', 'cancelled')
  ),
  CONSTRAINT ck_itil_problem_impact CHECK (impact IN ('low', 'medium', 'high'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS knowledge_article (
  article_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  article_number VARCHAR(32) NULL,
  title VARCHAR(255) NOT NULL,
  summary VARCHAR(500) NOT NULL DEFAULT '',
  body MEDIUMTEXT NOT NULL,
  category VARCHAR(128) NOT NULL DEFAULT '通用',
  status VARCHAR(16) NOT NULL DEFAULT 'draft',
  visibility VARCHAR(16) NOT NULL DEFAULT 'all',
  owner_user_id BIGINT UNSIGNED NULL,
  created_by BIGINT UNSIGNED NULL,
  updated_by BIGINT UNSIGNED NULL,
  published_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (article_id),
  UNIQUE KEY uq_knowledge_article_number (article_number),
  KEY idx_knowledge_article_search (status, category, updated_at),
  CONSTRAINT fk_knowledge_article_owner
    FOREIGN KEY (owner_user_id) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_knowledge_article_creator
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_knowledge_article_updater
    FOREIGN KEY (updated_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_knowledge_article_status CHECK (status IN ('draft', 'review', 'published', 'archived')),
  CONSTRAINT ck_knowledge_article_visibility CHECK (visibility IN ('all', 'operator', 'private'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sla_policy (
  sla_policy_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  policy_code VARCHAR(64) NOT NULL,
  policy_name VARCHAR(128) NOT NULL,
  priority VARCHAR(16) NOT NULL,
  response_minutes INT UNSIGNED NOT NULL DEFAULT 60,
  resolution_minutes INT UNSIGNED NOT NULL DEFAULT 1440,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (sla_policy_id),
  UNIQUE KEY uq_sla_policy_code (policy_code),
  KEY idx_sla_policy_priority (priority, is_active),
  CONSTRAINT fk_sla_policy_creator
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_sla_policy_priority CHECK (priority IN ('low', 'medium', 'high')),
  CONSTRAINT ck_sla_policy_active CHECK (is_active IN (0, 1)),
  CONSTRAINT ck_sla_policy_minutes CHECK (response_minutes > 0 AND resolution_minutes > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS service_workflow (
  workflow_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  workflow_code VARCHAR(64) NOT NULL,
  workflow_name VARCHAR(128) NOT NULL,
  record_type VARCHAR(32) NOT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (workflow_id),
  UNIQUE KEY uq_service_workflow_code (workflow_code),
  KEY idx_service_workflow_type (record_type, is_active),
  CONSTRAINT fk_service_workflow_creator
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_service_workflow_type CHECK (record_type IN ('ticket', 'change', 'problem')),
  CONSTRAINT ck_service_workflow_active CHECK (is_active IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS service_workflow_step (
  step_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  workflow_id BIGINT UNSIGNED NOT NULL,
  step_order INT UNSIGNED NOT NULL,
  step_name VARCHAR(128) NOT NULL,
  approver_user_id BIGINT UNSIGNED NULL,
  approver_role_code VARCHAR(64) NULL,
  is_required TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (step_id),
  UNIQUE KEY uq_service_workflow_step (workflow_id, step_order),
  CONSTRAINT fk_service_workflow_step_workflow
    FOREIGN KEY (workflow_id) REFERENCES service_workflow (workflow_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_service_workflow_step_user
    FOREIGN KEY (approver_user_id) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_service_workflow_step_flags CHECK (is_required IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS service_approval (
  approval_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  record_type VARCHAR(32) NOT NULL,
  record_id BIGINT UNSIGNED NOT NULL,
  workflow_id BIGINT UNSIGNED NOT NULL,
  current_step_order INT UNSIGNED NOT NULL DEFAULT 1,
  status VARCHAR(16) NOT NULL DEFAULT 'pending',
  requested_by BIGINT UNSIGNED NULL,
  completed_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (approval_id),
  UNIQUE KEY uq_service_approval_record (record_type, record_id, status),
  KEY idx_service_approval_queue (status, current_step_order, created_at),
  CONSTRAINT fk_service_approval_workflow
    FOREIGN KEY (workflow_id) REFERENCES service_workflow (workflow_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_service_approval_requester
    FOREIGN KEY (requested_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_service_approval_type CHECK (record_type IN ('ticket', 'change', 'problem')),
  CONSTRAINT ck_service_approval_status CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS service_approval_decision (
  decision_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  approval_id BIGINT UNSIGNED NOT NULL,
  step_order INT UNSIGNED NOT NULL,
  decision VARCHAR(16) NOT NULL,
  comment VARCHAR(1000) NOT NULL DEFAULT '',
  decided_by BIGINT UNSIGNED NULL,
  decided_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (decision_id),
  UNIQUE KEY uq_service_approval_decision (approval_id, step_order, decided_by),
  CONSTRAINT fk_service_approval_decision_approval
    FOREIGN KEY (approval_id) REFERENCES service_approval (approval_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_service_approval_decision_user
    FOREIGN KEY (decided_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_service_approval_decision_value CHECK (decision IN ('approved', 'rejected'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS service_notification (
  notification_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  recipient_user_id BIGINT UNSIGNED NOT NULL,
  record_type VARCHAR(32) NOT NULL,
  record_id BIGINT UNSIGNED NULL,
  notification_type VARCHAR(32) NOT NULL,
  title VARCHAR(255) NOT NULL,
  content VARCHAR(1000) NOT NULL,
  is_read TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  read_at DATETIME NULL,
  PRIMARY KEY (notification_id),
  KEY idx_service_notification_recipient (recipient_user_id, is_read, created_at),
  CONSTRAINT fk_service_notification_user
    FOREIGN KEY (recipient_user_id) REFERENCES user_account (user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT ck_service_notification_type CHECK (record_type IN ('ticket', 'change', 'problem', 'knowledge', 'approval', 'system')),
  CONSTRAINT ck_service_notification_read CHECK (is_read IN (0, 1))
) ENGINE=InnoDB;

INSERT INTO auth_module (module_code, module_name, category, sort_order)
VALUES
  ('tickets', '工单', 'itil', 70),
  ('changes', '变更管理', 'itil', 71),
  ('problems', '问题管理', 'itil', 72),
  ('knowledge', '知识库', 'itil', 73),
  ('forms', '服务表单', 'itil', 74),
  ('sla', 'SLA 管理', 'itil', 75),
  ('approvals', '审批流程', 'itil', 76),
  ('notifications', '消息通知', 'itil', 77)
ON DUPLICATE KEY UPDATE
  module_name = VALUES(module_name),
  category = VALUES(category),
  sort_order = VALUES(sort_order),
  is_active = 1;

INSERT IGNORE INTO auth_permission (module_code, action_code)
SELECT module_code, action_code
FROM auth_module
CROSS JOIN (
  SELECT 'view' AS action_code
  UNION ALL SELECT 'create'
  UNION ALL SELECT 'update'
  UNION ALL SELECT 'delete'
  UNION ALL SELECT 'approve'
  UNION ALL SELECT 'export'
) actions
WHERE module_code IN ('changes', 'problems', 'knowledge', 'forms', 'sla', 'approvals', 'notifications');

INSERT INTO auth_role_permission (
  role_id, permission_id, can_view, can_create, can_update,
  can_delete, can_approve, can_export, data_scope
)
SELECT
  role.role_id,
  permission.permission_id,
  CASE
    WHEN role.role_code = 'admin' THEN 1
    WHEN role.role_code = 'operator' AND permission.action_code IN ('view', 'create', 'update', 'approve', 'export') THEN 1
    WHEN role.role_code = 'viewer' AND permission.action_code IN ('view', 'export') THEN 1
    WHEN role.role_code = 'user' AND permission.module_code IN ('tickets', 'knowledge') AND permission.action_code IN ('view', 'create') THEN 1
    ELSE 0
  END,
  CASE
    WHEN role.role_code = 'admin' THEN 1
    WHEN role.role_code = 'operator' AND permission.action_code = 'create' THEN 1
    WHEN role.role_code = 'user' AND permission.module_code = 'tickets' AND permission.action_code = 'create' THEN 1
    ELSE 0
  END,
  CASE
    WHEN role.role_code = 'admin' THEN 1
    WHEN role.role_code = 'operator' AND permission.action_code = 'update' THEN 1
    ELSE 0
  END,
  CASE WHEN role.role_code = 'admin' AND permission.action_code = 'delete' THEN 1 ELSE 0 END,
  CASE
    WHEN role.role_code = 'admin' THEN 1
    WHEN role.role_code = 'operator' AND permission.action_code = 'approve' THEN 1
    ELSE 0
  END,
  CASE
    WHEN role.role_code IN ('admin', 'operator', 'viewer') AND permission.action_code = 'export' THEN 1
    ELSE 0
  END,
  CASE
    WHEN role.role_code = 'admin' THEN 'all'
    WHEN role.role_code = 'user' AND permission.module_code = 'tickets' THEN 'submitted'
    ELSE 'all'
  END
FROM auth_role role
CROSS JOIN auth_permission permission
WHERE permission.module_code IN ('changes', 'problems', 'knowledge', 'forms', 'sla', 'approvals', 'notifications')
ON DUPLICATE KEY UPDATE
  can_view = VALUES(can_view),
  can_create = VALUES(can_create),
  can_update = VALUES(can_update),
  can_delete = VALUES(can_delete),
  can_approve = VALUES(can_approve),
  can_export = VALUES(can_export),
  data_scope = VALUES(data_scope);

INSERT INTO service_form (form_code, form_name, record_type, description, created_by)
VALUES
  ('incident_default', '故障事件表单', 'ticket', '用于记录服务中断、设备故障和异常事件。', NULL),
  ('request_default', '服务请求表单', 'ticket', '用于记录标准化 IT 服务申请。', NULL),
  ('change_default', '标准变更表单', 'change', '用于记录计划内的 IT 变更。', NULL),
  ('problem_default', '问题分析表单', 'problem', '用于记录重复事件和根因分析。', NULL)
ON DUPLICATE KEY UPDATE
  form_name = VALUES(form_name),
  description = VALUES(description),
  is_active = 1;

INSERT INTO service_form_field (
  form_id, field_key, field_label, field_type, placeholder, is_required, sort_order
)
SELECT form_id, 'business_impact', '业务影响说明', 'textarea', '请说明影响范围和业务损失。', 0, 20
FROM service_form
WHERE form_code IN ('incident_default', 'request_default', 'change_default', 'problem_default')
  AND NOT EXISTS (
    SELECT 1
    FROM service_form_field field_row
    WHERE field_row.form_id = service_form.form_id
      AND field_row.field_key = 'business_impact'
  );

INSERT INTO service_form_field (
  form_id, field_key, field_label, field_type, placeholder, is_required, sort_order
)
SELECT form_id, 'expected_time', '期望完成时间', 'datetime', '', 0, 30
FROM service_form
WHERE form_code IN ('request_default', 'change_default')
  AND NOT EXISTS (
    SELECT 1
    FROM service_form_field field_row
    WHERE field_row.form_id = service_form.form_id
      AND field_row.field_key = 'expected_time'
  );

INSERT INTO sla_policy (
  policy_code, policy_name, priority, response_minutes, resolution_minutes, created_by
)
VALUES
  ('high_default', '高优先级 SLA', 'high', 30, 240, NULL),
  ('medium_default', '中优先级 SLA', 'medium', 120, 1440, NULL),
  ('low_default', '低优先级 SLA', 'low', 480, 4320, NULL)
ON DUPLICATE KEY UPDATE
  policy_name = VALUES(policy_name),
  response_minutes = VALUES(response_minutes),
  resolution_minutes = VALUES(resolution_minutes),
  is_active = 1;

INSERT INTO service_workflow (workflow_code, workflow_name, record_type, created_by)
VALUES
  ('change_default', '变更两级审批', 'change', NULL)
ON DUPLICATE KEY UPDATE
  workflow_name = VALUES(workflow_name),
  is_active = 1;

INSERT INTO service_workflow_step (workflow_id, step_order, step_name, approver_role_code)
SELECT workflow_id, 1, '服务台审核', 'operator'
FROM service_workflow workflow
WHERE workflow.workflow_code = 'change_default'
  AND NOT EXISTS (
    SELECT 1 FROM service_workflow_step step
    WHERE step.workflow_id = workflow.workflow_id AND step.step_order = 1
  );

INSERT INTO service_workflow_step (workflow_id, step_order, step_name, approver_role_code)
SELECT workflow_id, 2, '管理员审批', 'admin'
FROM service_workflow workflow
WHERE workflow.workflow_code = 'change_default'
  AND NOT EXISTS (
    SELECT 1 FROM service_workflow_step step
    WHERE step.workflow_id = workflow.workflow_id AND step.step_order = 2
  );
