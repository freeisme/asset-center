SET NAMES utf8mb4;

ALTER TABLE user_account
  ADD COLUMN employee_id BIGINT UNSIGNED NULL AFTER role_code,
  ADD UNIQUE KEY uq_user_account_employee (employee_id),
  ADD CONSTRAINT fk_user_account_employee
    FOREIGN KEY (employee_id) REFERENCES employee (employee_id)
    ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE service_form
  ADD COLUMN layout_json JSON NULL AFTER description,
  ADD COLUMN workflow_json JSON NULL AFTER layout_json,
  ADD COLUMN list_config_json JSON NULL AFTER workflow_json,
  ADD COLUMN settings_json JSON NULL AFTER list_config_json,
  ADD COLUMN published_at DATETIME NULL AFTER is_active;

ALTER TABLE service_form_field
  ADD COLUMN field_config JSON NULL AFTER options_json,
  DROP CHECK ck_service_form_field_type,
  ADD CONSTRAINT ck_service_form_field_type CHECK (
    field_type IN (
      'text', 'textarea', 'number', 'date', 'datetime', 'select',
      'multiselect', 'checkbox', 'employee', 'asset', 'organization', 'system'
    )
  );

CREATE TABLE IF NOT EXISTS service_form_permission (
  form_permission_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  form_id BIGINT UNSIGNED NOT NULL,
  subject_type VARCHAR(16) NOT NULL,
  subject_id BIGINT UNSIGNED NOT NULL,
  can_view TINYINT(1) NOT NULL DEFAULT 0,
  can_submit TINYINT(1) NOT NULL DEFAULT 0,
  can_update TINYINT(1) NOT NULL DEFAULT 0,
  can_delete TINYINT(1) NOT NULL DEFAULT 0,
  can_approve TINYINT(1) NOT NULL DEFAULT 0,
  can_export TINYINT(1) NOT NULL DEFAULT 0,
  data_scope VARCHAR(24) NOT NULL DEFAULT 'all',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (form_permission_id),
  UNIQUE KEY uq_service_form_permission (form_id, subject_type, subject_id),
  KEY idx_service_form_permission_subject (subject_type, subject_id),
  CONSTRAINT fk_service_form_permission_form
    FOREIGN KEY (form_id) REFERENCES service_form (form_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT ck_service_form_permission_subject CHECK (subject_type IN ('role', 'user')),
  CONSTRAINT ck_service_form_permission_scope CHECK (
    data_scope IN ('all', 'organization', 'own', 'submitted', 'assigned', 'none')
  ),
  CONSTRAINT ck_service_form_permission_flags CHECK (
    can_view IN (0, 1) AND can_submit IN (0, 1) AND can_update IN (0, 1)
    AND can_delete IN (0, 1) AND can_approve IN (0, 1) AND can_export IN (0, 1)
  )
) ENGINE=InnoDB;
