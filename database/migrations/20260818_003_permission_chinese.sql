SET NAMES utf8mb4;

UPDATE auth_module
SET module_name = CASE module_code
  WHEN 'dashboard' THEN '工作台'
  WHEN 'it_assets' THEN 'IT 资产'
  WHEN 'employees' THEN '员工'
  WHEN 'organizations' THEN '组织与资产关系'
  WHEN 'inventory_catalog' THEN '物资目录'
  WHEN 'inventory_operations' THEN '分配、归还、入库与领用'
  WHEN 'tickets' THEN '工单'
  WHEN 'sync' THEN '同步暂存'
  WHEN 'quality' THEN '数据质量审计'
  WHEN 'audit_logs' THEN '操作日志'
  WHEN 'backups' THEN '数据库备份'
  WHEN 'system_settings' THEN '系统设置'
  WHEN 'user_management' THEN '用户管理'
  WHEN 'role_management' THEN '角色与权限'
  WHEN 'system_updates' THEN '系统更新'
  WHEN 'changes' THEN '变更管理'
  WHEN 'problems' THEN '问题管理'
  WHEN 'knowledge' THEN '知识库'
  WHEN 'forms' THEN '服务表单'
  WHEN 'sla' THEN 'SLA 管理'
  WHEN 'approvals' THEN '审批流程'
  WHEN 'notifications' THEN '消息通知'
  ELSE module_name
END
WHERE is_active = 1;

UPDATE auth_role
SET role_name = CASE role_code
  WHEN 'admin' THEN '管理员'
  WHEN 'operator' THEN '服务台操作员'
  WHEN 'viewer' THEN '只读用户'
  WHEN 'user' THEN '普通用户'
  ELSE role_name
END
WHERE is_active = 1;
