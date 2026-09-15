SET NAMES utf8mb4;

SET @has_role_category = (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'auth_role'
    AND column_name = 'role_category'
);
SET @role_category_sql = IF(
  @has_role_category = 0,
  'ALTER TABLE auth_role ADD COLUMN role_category VARCHAR(32) NOT NULL DEFAULT ''custom'' AFTER role_name',
  'SELECT 1'
);
PREPARE role_category_stmt FROM @role_category_sql;
EXECUTE role_category_stmt;
DEALLOCATE PREPARE role_category_stmt;

UPDATE auth_role
SET role_category = CASE
  WHEN is_super_admin = 1 OR role_code = 'admin' THEN 'admin'
  WHEN role_code IN ('user', 'viewer') THEN 'ordinary'
  ELSE 'custom'
END
WHERE role_category IS NULL OR role_category = '' OR role_category = 'custom';
