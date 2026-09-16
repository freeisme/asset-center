SET NAMES utf8mb4;

-- 公用人员：给非个人使用的设备提供一个可挂靠的虚拟使用人。
-- 该状态与 在职/停用/离职 并列，可挂靠办公终端、显示屏与非资产物资，
-- 但不允许绑定登录账号；办理离职时按“删除占位人员”处理（不进入离职人员档案）。

SET @has_employee_status_check = (
  SELECT COUNT(*)
  FROM information_schema.table_constraints
  WHERE constraint_schema = DATABASE()
    AND table_name = 'employee'
    AND constraint_name = 'ck_employee_status'
);
SET @drop_employee_status_check_sql = IF(
  @has_employee_status_check > 0,
  'ALTER TABLE employee DROP CHECK ck_employee_status',
  'SELECT 1'
);
PREPARE drop_employee_status_check_stmt FROM @drop_employee_status_check_sql;
EXECUTE drop_employee_status_check_stmt;
DEALLOCATE PREPARE drop_employee_status_check_stmt;

ALTER TABLE employee
  ADD CONSTRAINT ck_employee_status
  CHECK (employment_status IN ('active', 'inactive', 'left', 'shared'));
