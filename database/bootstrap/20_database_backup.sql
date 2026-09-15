USE office_asset_mgmt;

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS database_backup (
  backup_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  file_name VARCHAR(255) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  file_size BIGINT UNSIGNED NOT NULL DEFAULT 0,
  checksum_sha256 CHAR(64) NOT NULL DEFAULT '',
  backup_type VARCHAR(32) NOT NULL DEFAULT 'manual',
  requested_by BIGINT UNSIGNED NULL,
  requested_by_name VARCHAR(128) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL DEFAULT 'completed',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (backup_id),
  UNIQUE KEY uq_database_backup_file_name (file_name),
  KEY idx_database_backup_created (created_at),
  KEY idx_database_backup_type_created (backup_type, created_at),
  KEY idx_database_backup_requester (requested_by, created_at),
  CONSTRAINT fk_database_backup_requester
    FOREIGN KEY (requested_by)
    REFERENCES user_account (user_id)
    ON DELETE SET NULL
    ON UPDATE CASCADE,
  CONSTRAINT ck_database_backup_type
    CHECK (backup_type IN ('manual', 'scheduled')),
  CONSTRAINT ck_database_backup_status
    CHECK (status IN ('completed', 'expired', 'failed'))
) ENGINE = InnoDB;

INSERT INTO system_setting (setting_key, setting_value, setting_description)
VALUES
  ('backup_enabled', '0', '是否启用每日数据库自动备份：1 为启用，0 为停用'),
  ('backup_time', '02:00', '每日数据库自动备份时间，使用 HH:MM 格式'),
  ('backup_retention_days', '30', '自动清理完成备份前的保留天数，0 表示不自动清理')
ON DUPLICATE KEY UPDATE
  setting_description = VALUES(setting_description);
