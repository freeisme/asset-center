-- Keep workflow approver role comparisons compatible with legacy account role columns.
ALTER TABLE service_workflow_step
  MODIFY COLUMN approver_role_code VARCHAR(64)
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci
  NULL;
