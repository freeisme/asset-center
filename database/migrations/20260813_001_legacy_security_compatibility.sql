-- Compatibility for v1.2.x installations which predate the full security
-- hardening bootstrap script. All statements are intentionally idempotent.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS auth_bootstrap_guard (
  guard_id TINYINT UNSIGNED NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (guard_id),
  CONSTRAINT ck_auth_bootstrap_guard_id CHECK (guard_id = 1)
) ENGINE=InnoDB;

SET @add_auth_session_ip_address := IF(
  (SELECT COUNT(*)
   FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'auth_session'
     AND column_name = 'ip_address') = 0
  AND
  (SELECT COUNT(*)
   FROM information_schema.tables
   WHERE table_schema = DATABASE()
     AND table_name = 'auth_session') = 1,
  'ALTER TABLE auth_session ADD COLUMN ip_address VARCHAR(64) NULL AFTER revoked_at',
  'SELECT 1'
);
PREPARE add_auth_session_ip_address_stmt FROM @add_auth_session_ip_address;
EXECUTE add_auth_session_ip_address_stmt;
DEALLOCATE PREPARE add_auth_session_ip_address_stmt;

SET @add_auth_session_user_agent := IF(
  (SELECT COUNT(*)
   FROM information_schema.columns
   WHERE table_schema = DATABASE()
     AND table_name = 'auth_session'
     AND column_name = 'user_agent') = 0
  AND
  (SELECT COUNT(*)
   FROM information_schema.tables
   WHERE table_schema = DATABASE()
     AND table_name = 'auth_session') = 1,
  'ALTER TABLE auth_session ADD COLUMN user_agent VARCHAR(500) NULL AFTER ip_address',
  'SELECT 1'
);
PREPARE add_auth_session_user_agent_stmt FROM @add_auth_session_user_agent;
EXECUTE add_auth_session_user_agent_stmt;
DEALLOCATE PREPARE add_auth_session_user_agent_stmt;
