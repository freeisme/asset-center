USE office_asset_mgmt;

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS app_state_revision (
  revision_id TINYINT UNSIGNED NOT NULL,
  revision BIGINT UNSIGNED NOT NULL DEFAULT 1,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (revision_id),
  CONSTRAINT ck_app_state_revision_id CHECK (revision_id = 1)
) ENGINE = InnoDB;

INSERT INTO app_state_revision (revision_id, revision)
VALUES (1, 1)
ON DUPLICATE KEY UPDATE revision_id = revision_id;

CREATE TABLE IF NOT EXISTS computer_assignment_history (
  history_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  computer_id BIGINT UNSIGNED NOT NULL,
  device_name VARCHAR(128) NOT NULL DEFAULT '',
  employee_id BIGINT UNSIGNED NOT NULL,
  employee_no VARCHAR(64) NOT NULL DEFAULT '',
  employee_name VARCHAR(128) NOT NULL DEFAULT '',
  assigned_at DATETIME NOT NULL,
  returned_at DATETIME NULL,
  assignment_status VARCHAR(32) NOT NULL DEFAULT 'active',
  notes VARCHAR(500) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (history_id),
  UNIQUE KEY uq_assignment_history_snapshot (computer_id, employee_id, assigned_at),
  KEY idx_assignment_history_computer (computer_id, assigned_at),
  KEY idx_assignment_history_employee (employee_id, assigned_at),
  CONSTRAINT ck_assignment_history_status CHECK (assignment_status IN ('active', 'returned', 'cancelled'))
) ENGINE = InnoDB;

SET @add_employee_active := IF(
  (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'employee' AND column_name = 'is_active') = 0,
  'ALTER TABLE employee ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1 AFTER employment_status',
  'SELECT 1'
);
PREPARE add_employee_active_stmt FROM @add_employee_active;
EXECUTE add_employee_active_stmt;
DEALLOCATE PREPARE add_employee_active_stmt;

SET @add_computer_active := IF(
  (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'computer_asset' AND column_name = 'is_active') = 0,
  'ALTER TABLE computer_asset ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1 AFTER remarks',
  'SELECT 1'
);
PREPARE add_computer_active_stmt FROM @add_computer_active;
EXECUTE add_computer_active_stmt;
DEALLOCATE PREPARE add_computer_active_stmt;

SET @add_brand_active := IF(
  (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'it_inventory_brand' AND column_name = 'is_active') = 0,
  'ALTER TABLE it_inventory_brand ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1 AFTER sort_order',
  'SELECT 1'
);
PREPARE add_brand_active_stmt FROM @add_brand_active;
EXECUTE add_brand_active_stmt;
DEALLOCATE PREPARE add_brand_active_stmt;

SET @add_model_active := IF(
  (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'it_inventory_model' AND column_name = 'is_active') = 0,
  'ALTER TABLE it_inventory_model ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1 AFTER sort_order',
  'SELECT 1'
);
PREPARE add_model_active_stmt FROM @add_model_active;
EXECUTE add_model_active_stmt;
DEALLOCATE PREPARE add_model_active_stmt;

SET @add_non_asset_usage_active := IF(
  (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'employee_non_asset_usage' AND column_name = 'is_active') = 0,
  'ALTER TABLE employee_non_asset_usage ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1 AFTER notes',
  'SELECT 1'
);
PREPARE add_non_asset_usage_active_stmt FROM @add_non_asset_usage_active;
EXECUTE add_non_asset_usage_active_stmt;
DEALLOCATE PREPARE add_non_asset_usage_active_stmt;

SET @add_monitor_active := IF(
  (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'employee_monitor_usage' AND column_name = 'is_active') = 0,
  'ALTER TABLE employee_monitor_usage ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1 AFTER notes',
  'SELECT 1'
);
PREPARE add_monitor_active_stmt FROM @add_monitor_active;
EXECUTE add_monitor_active_stmt;
DEALLOCATE PREPARE add_monitor_active_stmt;

UPDATE employee SET is_active = CASE WHEN employment_status = 'left' THEN 0 ELSE 1 END;
UPDATE computer_asset SET is_active = 1 WHERE is_active IS NULL;
UPDATE it_inventory_brand SET is_active = 1 WHERE is_active IS NULL;
UPDATE it_inventory_model SET is_active = 1 WHERE is_active IS NULL;
UPDATE employee_non_asset_usage SET is_active = 1 WHERE is_active IS NULL;
UPDATE employee_monitor_usage SET is_active = 1 WHERE is_active IS NULL;

SET @drop_wifi_mac_check := IF(
  (SELECT COUNT(*) FROM information_schema.table_constraints
   WHERE constraint_schema = DATABASE()
     AND table_name = 'computer_asset'
     AND constraint_name = 'ck_computer_wifi_mac') > 0,
  'ALTER TABLE computer_asset DROP CHECK ck_computer_wifi_mac',
  'SELECT 1'
);
PREPARE drop_wifi_mac_check_stmt FROM @drop_wifi_mac_check;
EXECUTE drop_wifi_mac_check_stmt;
DEALLOCATE PREPARE drop_wifi_mac_check_stmt;

SET @drop_ethernet_mac_check := IF(
  (SELECT COUNT(*) FROM information_schema.table_constraints
   WHERE constraint_schema = DATABASE()
     AND table_name = 'computer_asset'
     AND constraint_name = 'ck_computer_ethernet_mac') > 0,
  'ALTER TABLE computer_asset DROP CHECK ck_computer_ethernet_mac',
  'SELECT 1'
);
PREPARE drop_ethernet_mac_check_stmt FROM @drop_ethernet_mac_check;
EXECUTE drop_ethernet_mac_check_stmt;
DEALLOCATE PREPARE drop_ethernet_mac_check_stmt;

-- Canonicalize legacy MAC values before applying the short-hyphen format.
UPDATE computer_asset
SET
  wifi_mac = CASE
    WHEN wifi_mac IS NULL OR TRIM(wifi_mac) = '' THEN NULL
    WHEN wifi_mac REGEXP '^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$'
      THEN UPPER(REPLACE(wifi_mac, ':', '-'))
    WHEN wifi_mac REGEXP '^[0-9A-Fa-f]{2}(-[0-9A-Fa-f]{2}){5}$'
      THEN UPPER(wifi_mac)
    ELSE wifi_mac
  END,
  ethernet_mac = CASE
    WHEN ethernet_mac IS NULL OR TRIM(ethernet_mac) = '' THEN NULL
    WHEN ethernet_mac REGEXP '^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$'
      THEN UPPER(REPLACE(ethernet_mac, ':', '-'))
    WHEN ethernet_mac REGEXP '^[0-9A-Fa-f]{2}(-[0-9A-Fa-f]{2}){5}$'
      THEN UPPER(ethernet_mac)
    ELSE ethernet_mac
  END;

ALTER TABLE computer_asset
  ADD CONSTRAINT ck_computer_wifi_mac
    CHECK (
      wifi_mac IS NULL OR
      wifi_mac REGEXP '^[0-9A-Fa-f]{2}(-[0-9A-Fa-f]{2}){5}$'
    ),
  ADD CONSTRAINT ck_computer_ethernet_mac
    CHECK (
      ethernet_mac IS NULL OR
      ethernet_mac REGEXP '^[0-9A-Fa-f]{2}(-[0-9A-Fa-f]{2}){5}$'
    );
