SET NAMES utf8mb4;

ALTER TABLE auth_role
  MODIFY COLUMN role_code VARCHAR(64)
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci
  NOT NULL;
