USE office_asset_mgmt;

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS user_org_scope (
  scope_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  org_unit_id BIGINT UNSIGNED NOT NULL,
  include_descendants TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (scope_id),
  UNIQUE KEY uq_user_org_scope (user_id, org_unit_id),
  KEY idx_user_org_scope_org (org_unit_id),
  CONSTRAINT fk_user_org_scope_user
    FOREIGN KEY (user_id) REFERENCES user_account (user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_user_org_scope_org
    FOREIGN KEY (org_unit_id) REFERENCES org_unit (org_unit_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT ck_user_org_scope_descendants CHECK (include_descendants IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS asset_relation (
  relation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source_entity_type VARCHAR(32) NOT NULL,
  source_entity_id BIGINT UNSIGNED NOT NULL,
  relation_type VARCHAR(32) NOT NULL,
  target_entity_type VARCHAR(32) NOT NULL,
  target_entity_id BIGINT UNSIGNED NOT NULL,
  notes VARCHAR(500) NOT NULL DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (relation_id),
  UNIQUE KEY uq_asset_relation (
    source_entity_type, source_entity_id, relation_type, target_entity_type, target_entity_id
  ),
  KEY idx_asset_relation_source (source_entity_type, source_entity_id, is_active),
  KEY idx_asset_relation_target (target_entity_type, target_entity_id, is_active),
  CONSTRAINT fk_asset_relation_creator
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_asset_relation_active CHECK (is_active IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS api_idempotency_key (
  idempotency_key VARCHAR(128) NOT NULL,
  operation_code VARCHAR(128) NOT NULL,
  request_hash CHAR(64) NOT NULL,
  response_json JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NOT NULL,
  PRIMARY KEY (idempotency_key, operation_code),
  KEY idx_api_idempotency_expiry (expires_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inventory_allocation_history (
  allocation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  allocation_type VARCHAR(32) NOT NULL,
  employee_id BIGINT UNSIGNED NOT NULL,
  non_asset_type_id BIGINT UNSIGNED NULL,
  inventory_model_id BIGINT UNSIGNED NULL,
  usage_record_id BIGINT UNSIGNED NULL,
  quantity INT UNSIGNED NOT NULL DEFAULT 1,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  issued_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  returned_at DATETIME NULL,
  notes VARCHAR(500) NOT NULL DEFAULT '',
  issued_by BIGINT UNSIGNED NULL,
  returned_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (allocation_id),
  KEY idx_inventory_allocation_employee (employee_id, status, issued_at),
  KEY idx_inventory_allocation_model (inventory_model_id, status),
  CONSTRAINT fk_inventory_allocation_employee
    FOREIGN KEY (employee_id) REFERENCES employee (employee_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_allocation_type
    FOREIGN KEY (non_asset_type_id) REFERENCES non_asset_type (non_asset_type_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_allocation_model
    FOREIGN KEY (inventory_model_id) REFERENCES it_inventory_model (model_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_allocation_issued_by
    FOREIGN KEY (issued_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_allocation_returned_by
    FOREIGN KEY (returned_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_inventory_allocation_type CHECK (allocation_type IN ('monitor', 'non_asset')),
  CONSTRAINT ck_inventory_allocation_status CHECK (status IN ('active', 'returned', 'cancelled')),
  CONSTRAINT ck_inventory_allocation_quantity CHECK (quantity > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS asset_status_history (
  status_history_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  computer_id BIGINT UNSIGNED NOT NULL,
  previous_status VARCHAR(32) NOT NULL DEFAULT '',
  next_status VARCHAR(32) NOT NULL,
  reason VARCHAR(500) NOT NULL DEFAULT '',
  changed_by BIGINT UNSIGNED NULL,
  changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (status_history_id),
  KEY idx_asset_status_history_computer (computer_id, changed_at),
  CONSTRAINT fk_asset_status_history_computer
    FOREIGN KEY (computer_id) REFERENCES computer_asset (computer_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_asset_status_history_user
    FOREIGN KEY (changed_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_asset_status_history_next CHECK (
    next_status IN ('in_use', 'idle', 'repair', 'retired', 'lost')
  )
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sync_source (
  source_code VARCHAR(64) NOT NULL,
  source_name VARCHAR(128) NOT NULL,
  priority_rank INT NOT NULL DEFAULT 100,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (source_code),
  CONSTRAINT ck_sync_source_priority CHECK (priority_rank >= 0),
  CONSTRAINT ck_sync_source_active CHECK (is_active IN (0, 1))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sync_run (
  sync_run_id CHAR(36) NOT NULL,
  source_code VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'staged',
  source_reference VARCHAR(255) NOT NULL DEFAULT '',
  payload_hash CHAR(64) NOT NULL DEFAULT '',
  records_total INT UNSIGNED NOT NULL DEFAULT 0,
  records_valid INT UNSIGNED NOT NULL DEFAULT 0,
  records_invalid INT UNSIGNED NOT NULL DEFAULT 0,
  records_applied INT UNSIGNED NOT NULL DEFAULT 0,
  error_summary VARCHAR(1000) NOT NULL DEFAULT '',
  requested_by BIGINT UNSIGNED NULL,
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  PRIMARY KEY (sync_run_id),
  KEY idx_sync_run_source_status (source_code, status, started_at),
  CONSTRAINT fk_sync_run_source
    FOREIGN KEY (source_code) REFERENCES sync_source (source_code)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_sync_run_user
    FOREIGN KEY (requested_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_sync_run_status CHECK (status IN ('staged', 'validated', 'applied', 'failed', 'cancelled'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sync_staging_record (
  staging_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sync_run_id CHAR(36) NOT NULL,
  entity_type VARCHAR(32) NOT NULL,
  external_id VARCHAR(128) NOT NULL,
  requested_action VARCHAR(16) NOT NULL DEFAULT 'upsert',
  payload JSON NOT NULL,
  validation_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  validation_errors JSON NULL,
  target_entity_id BIGINT UNSIGNED NULL,
  applied_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (staging_id),
  UNIQUE KEY uq_sync_staging_record (sync_run_id, entity_type, external_id),
  KEY idx_sync_staging_status (sync_run_id, validation_status),
  CONSTRAINT fk_sync_staging_run
    FOREIGN KEY (sync_run_id) REFERENCES sync_run (sync_run_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT ck_sync_staging_action CHECK (requested_action IN ('upsert', 'disable')),
  CONSTRAINT ck_sync_staging_status CHECK (validation_status IN ('pending', 'valid', 'invalid', 'applied'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sync_entity_mapping (
  mapping_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source_code VARCHAR(64) NOT NULL,
  entity_type VARCHAR(32) NOT NULL,
  external_id VARCHAR(128) NOT NULL,
  target_entity_id BIGINT UNSIGNED NOT NULL,
  last_synced_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (mapping_id),
  UNIQUE KEY uq_sync_entity_mapping (source_code, entity_type, external_id),
  KEY idx_sync_entity_mapping_target (entity_type, target_entity_id),
  CONSTRAINT fk_sync_entity_mapping_source
    FOREIGN KEY (source_code) REFERENCES sync_source (source_code)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS data_quality_issue (
  issue_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  fingerprint CHAR(64) NOT NULL,
  rule_code VARCHAR(64) NOT NULL,
  severity VARCHAR(16) NOT NULL DEFAULT 'medium',
  entity_type VARCHAR(32) NOT NULL,
  entity_id BIGINT UNSIGNED NULL,
  title VARCHAR(255) NOT NULL,
  details JSON NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'open',
  first_detected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_detected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at DATETIME NULL,
  resolved_by BIGINT UNSIGNED NULL,
  PRIMARY KEY (issue_id),
  UNIQUE KEY uq_data_quality_fingerprint (fingerprint),
  KEY idx_data_quality_status (status, severity, last_detected_at),
  CONSTRAINT fk_data_quality_resolved_by
    FOREIGN KEY (resolved_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_data_quality_severity CHECK (severity IN ('low', 'medium', 'high')),
  CONSTRAINT ck_data_quality_status CHECK (status IN ('open', 'resolved', 'ignored'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS job_execution (
  execution_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_name VARCHAR(64) NOT NULL,
  run_key VARCHAR(128) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'running',
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  details JSON NULL,
  error_message VARCHAR(1000) NOT NULL DEFAULT '',
  PRIMARY KEY (execution_id),
  UNIQUE KEY uq_job_execution_run_key (job_name, run_key),
  KEY idx_job_execution_status (job_name, status, started_at),
  CONSTRAINT ck_job_execution_status CHECK (status IN ('running', 'completed', 'failed', 'skipped'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS itil_ticket (
  ticket_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ticket_number VARCHAR(32) NULL,
  ticket_type VARCHAR(16) NOT NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'new',
  impact VARCHAR(16) NOT NULL DEFAULT 'medium',
  urgency VARCHAR(16) NOT NULL DEFAULT 'medium',
  priority VARCHAR(16) NOT NULL DEFAULT 'medium',
  source VARCHAR(32) NOT NULL DEFAULT 'portal',
  requester_employee_id BIGINT UNSIGNED NULL,
  org_unit_id BIGINT UNSIGNED NULL,
  assigned_to_user_id BIGINT UNSIGNED NULL,
  related_computer_id BIGINT UNSIGNED NULL,
  resolution TEXT NULL,
  resolved_at DATETIME NULL,
  closed_at DATETIME NULL,
  created_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (ticket_id),
  UNIQUE KEY uq_itil_ticket_number (ticket_number),
  KEY idx_itil_ticket_queue (status, priority, created_at),
  KEY idx_itil_ticket_requester (requester_employee_id, status),
  KEY idx_itil_ticket_org (org_unit_id, status),
  KEY idx_itil_ticket_assignee (assigned_to_user_id, status),
  KEY idx_itil_ticket_computer (related_computer_id, status),
  CONSTRAINT fk_itil_ticket_requester
    FOREIGN KEY (requester_employee_id) REFERENCES employee (employee_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_itil_ticket_org
    FOREIGN KEY (org_unit_id) REFERENCES org_unit (org_unit_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_itil_ticket_assignee
    FOREIGN KEY (assigned_to_user_id) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_itil_ticket_computer
    FOREIGN KEY (related_computer_id) REFERENCES computer_asset (computer_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_itil_ticket_creator
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_itil_ticket_type CHECK (ticket_type IN ('incident', 'request')),
  CONSTRAINT ck_itil_ticket_status CHECK (
    status IN ('new', 'assigned', 'in_progress', 'pending', 'resolved', 'closed', 'cancelled')
  ),
  CONSTRAINT ck_itil_ticket_impact CHECK (impact IN ('low', 'medium', 'high')),
  CONSTRAINT ck_itil_ticket_urgency CHECK (urgency IN ('low', 'medium', 'high')),
  CONSTRAINT ck_itil_ticket_priority CHECK (priority IN ('low', 'medium', 'high')),
  CONSTRAINT ck_itil_ticket_source CHECK (source IN ('portal', 'phone', 'email', 'monitoring', 'import'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS itil_ticket_history (
  history_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ticket_id BIGINT UNSIGNED NOT NULL,
  entry_type VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  old_values JSON NULL,
  new_values JSON NULL,
  is_public TINYINT(1) NOT NULL DEFAULT 1,
  created_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (history_id),
  KEY idx_itil_ticket_history_ticket (ticket_id, created_at),
  CONSTRAINT fk_itil_ticket_history_ticket
    FOREIGN KEY (ticket_id) REFERENCES itil_ticket (ticket_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_itil_ticket_history_creator
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_itil_ticket_history_type CHECK (
    entry_type IN ('created', 'note', 'assignment', 'status_change', 'resolution', 'system')
  ),
  CONSTRAINT ck_itil_ticket_history_public CHECK (is_public IN (0, 1))
) ENGINE=InnoDB;

INSERT INTO sync_source (source_code, source_name, priority_rank, is_active)
VALUES
  ('manual', 'Manual maintenance', 10, 1),
  ('excel', 'Excel import', 50, 1),
  ('hr', 'HR directory', 20, 1)
ON DUPLICATE KEY UPDATE
  source_name = VALUES(source_name),
  priority_rank = VALUES(priority_rank),
  is_active = VALUES(is_active);
