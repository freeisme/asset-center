import { api } from "./client";

export interface AuditLog {
  id: string;
  actionType: string;
  entityType: string;
  entityId: string;
  entityName: string;
  employeeId: string;
  employeeName: string;
  deviceName: string;
  oldValue: unknown;
  newValue: unknown;
  summary: string;
  actor: string;
  source: string;
  createdAt: string;
  category?: string;
  changeLabel?: string;
}

export interface AuditQuery {
  startDate?: string;
  endDate?: string;
  employee?: string;
  actionType?: string;
  category?: string;
  entityType?: string;
  keyword?: string;
  limit?: number;
}

/** 与旧前端 auditActionLabels / auditActionExtraLabels 保持一致。 */
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  employee_added: "新增人员",
  employee_removed: "删除人员",
  employee_archived: "离职归档",
  employee_offboarded: "办理离职",
  employee_status_changed: "人员状态变更",
  computer_status_changed: "办公终端状态变更",
  computer_assignment_changed: "办公终端分配变更",
  computer_added: "新增办公终端",
  computer_removed: "删除办公终端",
  monitor_added: "增加显示屏",
  monitor_removed: "减少显示屏",
  non_asset_added: "增加非资产设备",
  non_asset_removed: "减少非资产设备",
  non_asset_quantity_changed: "非资产数量变更",
  inventory_group_added: "库存组新增",
  inventory_group_changed: "库存组变更",
  inventory_group_removed: "库存组删除",
  inventory_stock_changed: "库存数量变更",
  employee_info_changed: "人员信息变更",
  computer_info_changed: "办公终端信息变更",
  monitor_changed: "人员显示屏信息变更",
  non_asset_changed: "人员非资产物资信息变更",
  inventory_type_changed: "物资类型变更",
  inventory_brand_changed: "物资品牌变更",
  inventory_model_changed: "物资型号变更",
  database_backup_created: "手动创建数据库备份",
  database_backup_scheduled: "定时创建数据库备份",
  database_backup_schedule_changed: "数据库自动备份设置变更",
  database_backup_downloaded: "下载数据库备份",
};

export const AUDIT_CATEGORY_LABELS: Record<string, string> = {
  inventory: "物资变动",
  employee: "人员变动",
  computer: "办公终端信息变动",
  organization: "组织架构变动",
  other: "其他变动",
};

export const AUDIT_ENTITY_TYPE_LABELS: Record<string, string> = {
  it_inventory: "IT物资",
  inventory_type: "IT物资类型",
  inventory_brand: "IT物资品牌",
  inventory_model: "IT物资型号",
  employee: "使用人员",
  computer: "办公终端",
  monitor: "显示屏",
  non_asset: "非资产物资",
  org_unit: "组织架构",
};

export const AUDIT_CATEGORY_OPTIONS = ["inventory", "employee", "computer", "organization"];
export const AUDIT_ENTITY_TYPE_OPTIONS = [
  "it_inventory",
  "employee",
  "computer",
  "monitor",
  "non_asset",
  "org_unit",
];

const STATUS_LABELS: Record<string, string> = {
  in_use: "在用",
  idle: "闲置",
  repair: "维修",
  retired: "报废",
  lost: "丢失",
  active: "在职",
  inactive: "停用",
  left: "离职",
  shared: "公用",
};

const VALUE_FIELD_LABELS: Record<string, string> = {
  status: "状态",
  department: "部门",
  employeeNo: "人员编号",
  employeeName: "使用人",
  quantity: "数量",
  typeName: "类型",
  typeId: "类型编号",
  brand: "品牌",
  brandId: "品牌编号",
  model: "型号",
  modelId: "型号编号",
  name: "名称",
  deviceName: "设备名",
  orgId: "组织",
  deviceType: "设备类型",
  fixedAssetCode: "固资编码",
  purchaseDate: "购置日期",
  registeredDate: "注册日期",
  snSt: "SN/ST",
  wifiMac: "Wifi MAC",
  ethernetMac: "网口 MAC",
  location: "位置",
  remarks: "备注",
  email: "邮箱",
  mobile: "手机",
  position: "岗位",
};

export function auditActionLabel(actionType: string): string {
  return AUDIT_ACTION_LABELS[actionType] || actionType || "其他操作";
}

export function auditCategoryForLog(log: AuditLog): string {
  if (log.category) return log.category;
  if (["inventory_type", "inventory_brand", "inventory_model"].includes(log.entityType)) {
    return "inventory";
  }
  if (["employee", "monitor", "non_asset"].includes(log.entityType)) return "employee";
  if (log.entityType === "computer") return "computer";
  if (log.entityType === "org_unit") return "organization";
  return "other";
}

export function auditCategoryLabel(log: AuditLog): string {
  const category = auditCategoryForLog(log);
  return AUDIT_CATEGORY_LABELS[category] || category || "其他变动";
}

export function auditEntityTypeLabel(entityType: string): string {
  return AUDIT_ENTITY_TYPE_LABELS[entityType] || entityType || "其他对象";
}

export function auditChangeLabel(log: AuditLog): string {
  const oldValue = log.oldValue as { quantity?: unknown } | null;
  const newValue = log.newValue as { quantity?: unknown } | null;
  const oldQuantity = Number(oldValue?.quantity ?? 0);
  const newQuantity = Number(newValue?.quantity ?? 0);
  if (log.actionType === "inventory_stock_changed") {
    if (newQuantity > oldQuantity) return "物资库存增加";
    if (newQuantity < oldQuantity) return "物资库存减少";
  }
  if (log.actionType === "non_asset_quantity_changed") {
    if (newQuantity > oldQuantity) return "人员物资增加";
    if (newQuantity < oldQuantity) return "人员物资减少";
  }
  return log.changeLabel || auditActionLabel(log.actionType);
}

export function auditTagType(actionType: string): "danger" | "warning" | "success" {
  if (actionType.includes("removed") || actionType.includes("status_changed")) return "danger";
  if (actionType.includes("assignment") || actionType.includes("changed")) return "warning";
  return "success";
}

export function auditValueText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "无";
  if (typeof value !== "object") return String(value);
  const parts: string[] = [];
  Object.entries(value as Record<string, unknown>).forEach(([key, item]) => {
    if (key === "assignment" && item && typeof item === "object") {
      const assignment = item as { employeeName?: string; employeeNo?: string };
      parts.push(`使用人：${assignment.employeeName || "未分配"}`);
      if (assignment.employeeNo) parts.push(`编号：${assignment.employeeNo}`);
      return;
    }
    const label = VALUE_FIELD_LABELS[key] || key;
    const displayValue =
      key === "status" && typeof item === "string" ? STATUS_LABELS[item] || item : item;
    if (displayValue !== null && displayValue !== undefined && displayValue !== "") {
      parts.push(`${label}：${String(displayValue)}`);
    }
  });
  return parts.join("；") || "无";
}

export function buildAuditQuery(query: AuditQuery): string {
  const params = new URLSearchParams();
  if (query.startDate) params.set("startDate", query.startDate);
  if (query.endDate) params.set("endDate", query.endDate);
  if (query.employee) params.set("employee", query.employee.trim());
  if (query.actionType) params.set("actionType", query.actionType);
  if (query.category) params.set("category", query.category);
  if (query.entityType) params.set("entityType", query.entityType);
  if (query.keyword) params.set("keyword", query.keyword.trim());
  params.set("limit", String(query.limit ?? 5000));
  return params.toString();
}

export async function fetchAuditLogs(
  query: AuditQuery,
): Promise<{ logs: AuditLog[]; total: number; limit: number }> {
  const payload = await api<{ logs: AuditLog[]; total: number; limit: number }>(
    `/api/audit-logs?${buildAuditQuery(query)}`,
  );
  return {
    logs: Array.isArray(payload.logs) ? payload.logs : [],
    total: Number(payload.total ?? 0),
    limit: Number(payload.limit ?? 0),
  };
}

export function auditLogsToCsv(logs: AuditLog[]): string {
  const header = [
    "时间",
    "操作类别",
    "具体变动",
    "对象类型",
    "变更对象",
    "关联人员",
    "人员编号",
    "变更前",
    "变更后",
    "变更说明",
    "操作人",
    "来源",
  ];
  const rows = logs.map((log) => [
    log.createdAt,
    auditCategoryLabel(log),
    auditChangeLabel(log),
    auditEntityTypeLabel(log.entityType),
    log.entityName || log.deviceName || "",
    log.employeeName || "",
    log.employeeId || "",
    auditValueText(log.oldValue),
    auditValueText(log.newValue),
    log.summary || "",
    log.actor || "",
    log.source || "",
  ]);
  const escape = (value: string) => `"${String(value ?? "").replace(/"/g, '""')}"`;
  return [header, ...rows].map((row) => row.map(escape).join(",")).join("\r\n");
}
