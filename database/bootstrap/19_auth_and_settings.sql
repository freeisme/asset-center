USE office_asset_mgmt;

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS user_account (
  user_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL,
  display_name VARCHAR(128) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  user_role VARCHAR(32) NOT NULL DEFAULT 'operator',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  failed_attempts INT UNSIGNED NOT NULL DEFAULT 0,
  locked_until DATETIME NULL,
  last_login_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  UNIQUE KEY uq_user_account_username (username),
  KEY idx_user_account_active (is_active, username),
  CONSTRAINT ck_user_account_role CHECK (user_role IN ('admin', 'operator', 'viewer')),
  CONSTRAINT ck_user_account_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS auth_session (
  session_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_token_hash CHAR(64) NOT NULL,
  csrf_token_hash CHAR(64) NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  expires_at DATETIME NOT NULL,
  last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revoked_at DATETIME NULL,
  ip_address VARCHAR(64) NOT NULL DEFAULT '',
  user_agent VARCHAR(500) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (session_id),
  UNIQUE KEY uq_auth_session_token (session_token_hash),
  KEY idx_auth_session_user (user_id, revoked_at, expires_at),
  CONSTRAINT fk_auth_session_user
    FOREIGN KEY (user_id)
    REFERENCES user_account (user_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS system_setting (
  setting_key VARCHAR(128) NOT NULL,
  setting_value VARCHAR(1000) NOT NULL DEFAULT '',
  setting_description VARCHAR(255) NOT NULL DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  updated_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (setting_key),
  KEY idx_system_setting_active (is_active, setting_key),
  CONSTRAINT fk_system_setting_user
    FOREIGN KEY (updated_by)
    REFERENCES user_account (user_id)
    ON DELETE SET NULL
    ON UPDATE CASCADE,
  CONSTRAINT ck_system_setting_active CHECK (is_active IN (0, 1))
) ENGINE = InnoDB;

INSERT INTO system_setting (setting_key, setting_value, setting_description)
VALUES
  ('app_name', '办公资产管理系统', '登录页和系统顶部显示的系统名称'),
  ('login_notice', '', '登录页提示语'),
  ('session_hours', '8', '登录会话有效时长，单位为小时')
ON DUPLICATE KEY UPDATE
  setting_description = VALUES(setting_description);

DELETE FROM auth_session
WHERE revoked_at IS NOT NULL
   OR expires_at <= NOW();
