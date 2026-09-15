SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS inventory_movement_note_correction (
  correction_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  movement_log_id BIGINT UNSIGNED NOT NULL,
  corrected_note VARCHAR(500) NOT NULL,
  correction_reason VARCHAR(500) NOT NULL,
  created_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (correction_id),
  KEY idx_inventory_movement_note_correction_log (movement_log_id, created_at, correction_id),
  CONSTRAINT fk_inventory_movement_note_correction_log
    FOREIGN KEY (movement_log_id) REFERENCES inventory_movement_log (movement_log_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_inventory_movement_note_correction_user
    FOREIGN KEY (created_by) REFERENCES user_account (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

SET @add_quality_resolution_result := IF(
  (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'data_quality_issue'
      AND column_name = 'resolution_result'
  ) = 0,
  'ALTER TABLE data_quality_issue ADD COLUMN resolution_result TEXT NULL AFTER details',
  'SELECT 1'
);
PREPARE add_quality_resolution_result_stmt FROM @add_quality_resolution_result;
EXECUTE add_quality_resolution_result_stmt;
DEALLOCATE PREPARE add_quality_resolution_result_stmt;
