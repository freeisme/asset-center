export interface NavItem {
  page: string;
  path: string;
  title: string;
  group: string;
  /** 决定菜单可见性的权限资源（任一 action=view 可见即显示） */
  modules: string[];
}

const SERVICE_MODULES = [
  "tickets",
  "changes",
  "problems",
  "knowledge",
  "forms",
  "sla",
  "approvals",
  "notifications",
];

export const NAV_ITEMS: NavItem[] = [
  { page: "dashboard", path: "/dashboard", title: "资产总览", group: "资产台账", modules: ["dashboard"] },
  { page: "computers", path: "/computers", title: "办公终端", group: "资产台账", modules: ["it_assets"] },
  { page: "rackLayout", path: "/rack-layout", title: "机柜视图", group: "资产台账", modules: ["rack_layout"] },
  { page: "employees", path: "/employees", title: "使用人员", group: "资产台账", modules: ["employees"] },
  { page: "leftEmployees", path: "/left-employees", title: "离职人员", group: "资产台账", modules: ["employees"] },
  {
    page: "inventory",
    path: "/inventory",
    title: "IT物资",
    group: "资源与审计",
    modules: ["inventory_catalog", "warehouse_management"],
  },
  {
    page: "flowControl",
    path: "/flow-control",
    title: "物资流转记录",
    group: "资源与审计",
    modules: ["inventory_operations"],
  },
  {
    page: "scrapRecords",
    path: "/scrap-records",
    title: "报废记录",
    group: "资源与审计",
    modules: ["scrap_management"],
  },
  {
    page: "inspection",
    path: "/inspection",
    title: "机房巡检",
    group: "资源与审计",
    modules: ["inspection_management"],
  },
  { page: "dictionary", path: "/dictionary", title: "基础字典", group: "资源与审计", modules: ["organizations"] },
  { page: "audit", path: "/audit", title: "操作日志", group: "资源与审计", modules: ["audit_logs"] },
  { page: "tickets", path: "/tickets", title: "工单", group: "系统", modules: ["tickets"] },
  {
    page: "serviceManagement",
    path: "/service-management",
    title: "服务管理",
    group: "服务管理",
    modules: SERVICE_MODULES,
  },
  { page: "governance", path: "/governance", title: "同步与质量", group: "服务管理", modules: ["sync"] },
  { page: "settings", path: "/settings", title: "设置", group: "服务管理", modules: ["system_settings"] },
];

export const NAV_GROUPS = ["资产台账", "资源与审计", "系统", "服务管理"];

export const PAGE_BY_PATH: Record<string, string> = Object.fromEntries(
  NAV_ITEMS.map((item) => [item.path, item.page]),
);

export const PATH_BY_PAGE: Record<string, string> = Object.fromEntries(
  NAV_ITEMS.map((item) => [item.page, item.path]),
);

export const NAV_BY_PAGE: Record<string, NavItem> = Object.fromEntries(
  NAV_ITEMS.map((item) => [item.page, item]),
);
