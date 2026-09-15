USE office_asset_mgmt;

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS audit_log (
  audit_log_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  action_type VARCHAR(64) NOT NULL,
  entity_type VARCHAR(64) NOT NULL,
  entity_id VARCHAR(64) NULL,
  entity_name VARCHAR(255) NULL,
  employee_id VARCHAR(64) NULL,
  employee_name VARCHAR(128) NULL,
  device_name VARCHAR(128) NULL,
  old_value JSON NULL,
  new_value JSON NULL,
  summary VARCHAR(500) NOT NULL,
  actor VARCHAR(128) NOT NULL DEFAULT 'web',
  source VARCHAR(32) NOT NULL DEFAULT 'web',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (audit_log_id),
  KEY idx_audit_log_created_at (created_at, audit_log_id),
  KEY idx_audit_log_action (action_type, created_at),
  KEY idx_audit_log_entity (entity_type, entity_id),
  KEY idx_audit_log_employee (employee_id, created_at),
  KEY idx_audit_log_device (device_name, created_at)
) ENGINE = InnoDB;
