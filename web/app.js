const UI_STORAGE_KEY = "office-asset-center-ui-v1";
const API_STATE_URL = "/api/state";
const API_AUDIT_LOGS_URL = "/api/audit-logs";
const API_AUTH_SESSION_URL = "/api/auth/session";
const API_AUTH_LOGIN_URL = "/api/auth/login";
const API_AUTH_BOOTSTRAP_STATUS_URL = "/api/auth/bootstrap-status";
const API_AUTH_BOOTSTRAP_URL = "/api/auth/bootstrap";
const API_AUTH_LOGOUT_URL = "/api/auth/logout";
const API_AUTH_CHANGE_PASSWORD_URL = "/api/auth/change-password";
const API_AUTH_PERMISSIONS_URL = "/api/auth/permissions";
const API_USERS_URL = "/api/users";
const API_ACCESS_CONTROL_URL = "/api/access-control";
const API_ROLES_URL = "/api/roles";
const API_SETTINGS_URL = "/api/settings";
const API_BACKUPS_URL = "/api/backups";
const API_UPDATE_CHECK_URL = "/api/updates/check";
const API_UPDATE_APPLY_URL = "/api/updates/apply";
const API_RESOURCES_URL = "/api/resources";
const API_EMPLOYEES_URL = "/api/employees";
const API_TICKETS_URL = "/api/tickets";
const API_SERVICE_FORMS_URL = "/api/service/forms";
const API_SERVICE_FORM_PERMISSIONS_URL = "/permissions";
const API_CHANGES_URL = "/api/changes";
const API_PROBLEMS_URL = "/api/problems";
const API_KNOWLEDGE_URL = "/api/knowledge";
const API_SLA_POLICIES_URL = "/api/sla/policies";
const API_APPROVALS_URL = "/api/approvals";
const API_WORKFLOWS_URL = "/api/approval-workflows";
const API_NOTIFICATIONS_URL = "/api/notifications";
const API_SYNC_RUNS_URL = "/api/sync-runs";
const API_QUALITY_ISSUES_URL = "/api/data-quality/issues";
const API_SCRAP_RECORDS_URL = "/api/scrap-records";
const API_SCRAP_REASONS_URL = "/api/scrap-reasons";
const THEME_STORAGE_KEY = "office-asset-center-theme-v1";
const UPDATE_RELEASE_CHANNELS = {
  release: "发行版",
  beta: "Beta 版",
};
const DEFAULT_UPDATE_RELEASE_CHANNEL = "beta";
const GITHUB_UPDATE_REPOSITORY_URL = "https://github.com/freeisme/asset-center.git";
const UPDATE_SOURCES = {
  github: "GitHub 官方更新",
  custom: "自定义更新地址",
};

function applyTheme(theme) {
  const isDark = theme === "dark";
  document.documentElement.dataset.theme = isDark ? "dark" : "light";
  const metaThemeColor = document.querySelector('meta[name="theme-color"]');
  if (metaThemeColor) metaThemeColor.setAttribute("content", isDark ? "#000000" : "#ffffff");
  const toggle = document.querySelector('[data-action="toggle-theme"]');
  if (toggle) {
    toggle.textContent = isDark ? "☀" : "☾";
    toggle.title = isDark ? "切换日间模式" : "切换夜间模式";
    toggle.setAttribute("aria-label", toggle.title);
    toggle.setAttribute("aria-pressed", String(isDark));
  }
}

function initializeTheme() {
  const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  applyTheme(savedTheme === "dark" ? "dark" : "light");
}

function toggleTheme() {
  const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  applyTheme(nextTheme);
}

const pageMeta = {
  dashboard: {
    title: "资产总览",
    description: "掌握办公设备分布、使用状态和人员领用情况。",
  },
  computers: {
    title: "办公终端",
    description: "维护办公终端资产台账、归属人员和 IT 资产状态。",
  },
  employees: {
    title: "使用人员",
    description: "按组织架构树查看人员和名下办公设备。",
  },
  leftEmployees: {
    title: "离职人员",
    description: "保存离职人员资料、离职信息和离职时使用设备快照。",
  },
  inventory: {
    title: "IT物资",
    description: "管理办公终端、显示屏和其他 IT 物资库存、采购入库与分配状态。",
  },
  flowControl: {
    title: "物资流转记录",
    description: "自动汇总物资变动，识别业务类型和分类，并支持补充备注。",
  },
  scrapRecords: {
    title: "报废记录",
    description: "登记发放物资和办公终端的报废处理结果，报废不回收库存且保留审计追溯。",
  },
  dictionary: {
    title: "基础字典",
    description: "维护组织架构树和非资产设备类型。",
  },
  audit: {
    title: "操作日志",
    description: "记录设备状态变更和人员 IT 物资领用变化。",
  },
  tickets: {
    title: "工单",
    description: "统一受理故障、服务请求、变更和问题，记录处理过程并保留审批历史。",
  },
  serviceManagement: {
    title: "服务管理",
    description: "管理工单、变更、问题、知识库、SLA、审批和消息通知。",
  },
  formDesigner: {
    title: "表单设计",
    description: "配置业务字段、流程、列表和表单权限。",
  },
  governance: {
    title: "同步与质量",
    description: "外部数据先在暂存区校验，再由授权人员应用，并持续检查资产数据质量。",
  },
  settings: {
    title: "设置",
    description: "管理系统参数、账号和个人登录安全。",
  },
};

const statusLabels = {
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

const offboardActionLabels = {
  recover: "回收",
  transfer: "转交他人",
  exception: "异常待处理",
};

const roleLabels = {
  admin: "管理员",
  super_admin: "超级管理员",
  operator: "操作员",
  viewer: "只读用户",
  user: "普通用户",
};

const roleCategoryLabels = {
  admin: "管理员",
  ordinary: "普通用户",
  custom: "自定义角色",
};

const roleCategoryOptions = Object.entries(roleCategoryLabels).map(([value, label]) => ({ value, label }));

const permissionModuleLabels = {
  dashboard: "资产总览",
  it_assets: "办公终端",
  employees: "使用人员",
  organizations: "组织与资产关系",
  inventory_catalog: "IT物资",
  inventory_operations: "物资流转记录",
  warehouse_management: "仓库管理",
  scrap_management: "报废管理",
  inspection_management: "巡检管理",
  audit_logs: "操作日志",
  backups: "备份",
  role_management: "角色与权限",
  system_settings: "系统设置",
  system_updates: "系统更新",
  sync: "同步与质量",
  tickets: "工单",
  changes: "变更管理",
  problems: "问题管理",
  knowledge: "知识库",
  forms: "表单",
  sla: "SLA策略",
  approvals: "审批流程",
  notifications: "消息提醒",
  service_management: "服务管理",
};

function escapeRegExp(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizePermissionModuleName(rawName, code) {
  const text = String(rawName || "").trim();
  const moduleCode = String(code || "").trim();
  if (!text) return "";
  if (!moduleCode) return text;
  const cleaned = text
    .replace(new RegExp(`(?:[\\s·•｜|/\\-]+)?${escapeRegExp(moduleCode)}$`, "i"), "")
    .trim();
  return cleaned || text;
}

const deviceTypeLabels = {
  laptop: "笔记本",
  desktop: "台式机",
  workstation: "工作站",
  mini_pc: "迷你主机",
};

const deferredTextFilterNames = new Set([
  "employees",
  "employeeAssetSearch",
  "inventorySearch",
  "flowSearch",
  "flowEmployee",
  "flowSourceTarget",
  "scrapSearch",
  "auditSearch",
  "auditEmployee",
]);

let state = loadInitialState();
let remoteSyncQueue = Promise.resolve();
let pendingDeviceSave = null;
let pendingLeaveRecovery = null;
let pendingDeviceRecovery = null;
let filterSearchDrafts = {};
let authState = { authenticated: false, user: null, bootstrapRequired: false };
let ticketFormDraft = { forms: [], selectedCode: "" };
let serviceRecordFormDrafts = {
  change: { forms: [], selectedCode: "" },
  problem: { forms: [], selectedCode: "" },
};
let formDesignerState = {
  formId: "",
  form: null,
  selectedFieldKey: "",
  selectedWorkflowStepIndex: -1,
  activePanel: "form",
  permissions: [],
  loading: false,
  dirty: false,
};
let settingsState = {
  settings: {},
  users: [],
  backups: [],
  loaded: false,
  view: "system",
  updateStatus: null,
  updateChecking: false,
  updateApplying: false,
  updateSelectedSha: "",
  updateRepositoryUrl: "",
  updateSource: "github",
  updateCustomRepositoryUrl: "",
  updateReleaseChannel: DEFAULT_UPDATE_RELEASE_CHANNEL,
  accessControl: {
    modules: [],
    roles: [],
    users: [],
    targetType: "role",
    targetId: "",
    permissions: [],
    loading: false,
  },
};
let lastRenderedPage = "";
let inventoryWarehouseView = "";
let controlIdSequence = 0;
let asyncRequestSequence = 0;
const latestAsyncRequests = new Map();
let authBootPromise = null;
const DEFAULT_SCRAP_REASONS = [
  { code: "damaged_unrepairable", name: "损坏无法修复", appliesTo: "both" },
  { code: "worn_out", name: "老化到寿命期限", appliesTo: "both" },
  { code: "abnormal_damage", name: "人为损坏或异常损坏", appliesTo: "both" },
  { code: "lost_offsite", name: "外借丢失或无法找回", appliesTo: "inventory" },
  { code: "obsoleted", name: "技术淘汰无法继续使用", appliesTo: "both" },
  { code: "other", name: "其他原因", appliesTo: "both" },
];
let scrapState = {
  records: [],
  reasons: [],
  loaded: false,
  loading: false,
  filterKind: "",
  filterSearch: "",
};
let operationsState = {
  tickets: [],
  syncRuns: [],
  qualityIssues: [],
  ticketLoading: false,
  governanceLoading: false,
  service: {
    view: "tickets",
    loading: false,
    changes: [],
    problems: [],
    articles: [],
    forms: [],
    policies: [],
    approvals: [],
    workflows: [],
    workflowUsers: [],
    workflowRoles: [],
    notifications: [],
  },
};

function authRoleLabel(role) {
  return roleLabels[role] || role || "未知角色";
}

function unreadNotificationCount() {
  return (serviceState().notifications || []).filter((item) => !item.isRead).length;
}

function isAdminUser() {
  return Boolean(authState.user?.isSuperAdmin);
}

function canWriteState() {
  return [
    "it_assets",
    "employees",
    "organizations",
    "inventory_catalog",
    "inventory_operations",
  ].some((moduleCode) => hasPermission(moduleCode, "create") || hasPermission(moduleCode, "update"));
}

function hasPermission(moduleCode, action = "view") {
  if (authState.user?.isSuperAdmin) return true;
  const permission = (authState.permissions || []).find(
    (item) => item.moduleCode === moduleCode && item.actionCode === action,
  );
  return Boolean(permission?.[`can${action.charAt(0).toUpperCase()}${action.slice(1)}`]);
}

const serviceViewModules = {
  tickets: "tickets",
  changes: "changes",
  problems: "problems",
  knowledge: "knowledge",
  forms: "forms",
  policies: "sla",
  approvals: "approvals",
  notifications: "notifications",
};

function canViewServiceView(view) {
  return hasPermission(serviceViewModules[view] || "", "view");
}

function availableServiceViews() {
  return Object.keys(serviceViewModules).filter(canViewServiceView);
}

function normalizeServiceView() {
  const service = serviceState();
  if (!canViewServiceView(service.view)) {
    service.view = availableServiceViews()[0] || "tickets";
  }
  return service.view;
}

function canViewPage(page) {
  if (page === "serviceManagement") return availableServiceViews().length > 0;
  const modules = {
    dashboard: "dashboard",
    computers: "it_assets",
    employees: "employees",
    leftEmployees: "employees",
    inventory: "inventory_catalog",
    flowControl: "inventory_operations",
    scrapRecords: "scrap_management",
    inspection: "inspection_management",
    dictionary: "organizations",
    audit: "audit_logs",
    tickets: "tickets",
    formDesigner: "forms",
    governance: "sync",
    settings: "system_settings",
  };
  if (page === "inventory") {
    return hasPermission("inventory_catalog", "view") || hasPermission("warehouse_management", "view");
  }
  return hasPermission(modules[page] || "dashboard", "view");
}

function beginAsyncRequest(key) {
  const requestId = ++asyncRequestSequence;
  latestAsyncRequests.set(key, requestId);
  return requestId;
}

function isLatestAsyncRequest(key, requestId) {
  return latestAsyncRequests.get(key) === requestId;
}

function invalidateAsyncRequests() {
  latestAsyncRequests.clear();
}

function createId(prefix) {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return `${prefix}-${window.crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getSeedState() {
  const orgs = [
    { id: "1", code: "HQ", name: "总部", parentId: "", sortOrder: 10 },
  ];

  return {
    page: "dashboard",
    filters: {
      computers: "",
      computerStatus: "",
      employees: "",
      employeeAssetSearch: "",
      employeeStatus: "",
      employeeOrg: "",
      employeeDevice: "",
      leftEmployees: "",
      dictionary: "",
      inventorySearch: "",
      inventoryType: "",
      inventoryBrand: "",
      auditSearch: "",
      auditAction: "",
      auditCategory: "",
      auditEntityType: "",
      auditEmployee: "",
      auditStartDate: "",
      auditEndDate: "",
    },
    selectedComputerIds: [],
    selectedEmployeeIds: [],
    expandedOrgIds: orgs.map((org) => org.id),
    includeSharedInOrgCount: false,
    expandedInventoryTypeIds: [],
    expandedInventoryBrandIds: [],
    orgs,
    nonAssetTypes: [
      { id: "mouse", code: "mouse", name: "鼠标", unit: "件" },
      { id: "keyboard", code: "keyboard", name: "键盘", unit: "件" },
      { id: "docking_station", code: "docking_station", name: "拓展坞", unit: "件" },
      { id: "headset", code: "headset", name: "耳机", unit: "件" },
      { id: "usb_hub", code: "usb_hub", name: "USB集线器", unit: "件" },
      { id: "webcam", code: "webcam", name: "摄像头", unit: "件" },
      { id: "computer", code: "computer", name: "办公终端", unit: "台" },
    ],
    inventoryBrands: [],
    inventoryModels: [],
    warehouses: [],
    warehouseStocks: [],
    inventoryMovementLogs: [],
    inventoryPurchaseLogs: [],
    stateRevision: 0,
    employees: [],
    leftEmployees: [],
    computers: [],
    auditLogs: [],
    auditLogTotal: 0,
  };
}

function loadUiState() {
  try {
    const saved = window.localStorage.getItem(UI_STORAGE_KEY);
    if (saved) return JSON.parse(saved);
  } catch (error) {
    console.warn("Unable to load local UI state", error);
  }
  return {};
}

function extractUiState(value) {
  return {
    page: value.page,
    filters: value.filters,
    selectedComputerIds: value.selectedComputerIds,
    selectedEmployeeIds: value.selectedEmployeeIds,
    expandedOrgIds: value.expandedOrgIds,
    includeSharedInOrgCount: Boolean(value.includeSharedInOrgCount),
    expandedInventoryTypeIds: value.expandedInventoryTypeIds,
    expandedInventoryBrandIds: value.expandedInventoryBrandIds,
  };
}

function loadInitialState() {
  return normalizeState({
    ...getSeedState(),
    ...loadUiState(),
  });
}

function normalizeState(value) {
  const seed = getSeedState();
  const orgs = normalizeOrgs(Array.isArray(value.orgs) ? value.orgs : seed.orgs);
  const expandedOrgIds = Array.isArray(value.expandedOrgIds) ? value.expandedOrgIds : orgs.map((org) => org.id);
  let nonAssetTypes = Array.isArray(value.nonAssetTypes) ? value.nonAssetTypes : seed.nonAssetTypes;
  if (!nonAssetTypes.some((type) => isComputerInventoryType(type))) {
    nonAssetTypes = nonAssetTypes.concat([{ id: "computer", code: "computer", name: "办公终端", unit: "台" }]);
  }
  const inventoryBrands = Array.isArray(value.inventoryBrands)
    ? value.inventoryBrands.map((brand) => ({
        id: brand.id || createId("brand"),
        typeId: brand.typeId || "",
        name: brand.name || brand.brandName || "",
        sortOrder: Math.max(0, Number(brand.sortOrder ?? 1000)),
      }))
    : seed.inventoryBrands;
  const inventoryModels = Array.isArray(value.inventoryModels)
    ? value.inventoryModels.map((model) => {
        const type = nonAssetTypes.find((item) => item.id === (model.typeId || ""));
        const computerModel = isComputerInventoryType(type);
        return {
          id: model.id || createId("model"),
          typeId: model.typeId || "",
          brandId: model.brandId || "",
          name: model.name || model.modelName || "",
          batchKey: model.batchKey || "",
          quantity: Math.max(0, Number(model.quantity ?? 0)),
          inboundDate: computerModel ? model.inboundDate || "" : "",
          cpu: computerModel ? model.cpu || "" : "",
          memory: computerModel ? model.memory || "" : "",
          storage: computerModel ? model.storage || "" : "",
          gpu: computerModel ? model.gpu || "" : "",
          sortOrder: Math.max(0, Number(model.sortOrder ?? 1000)),
        };
      })
    : seed.inventoryModels;
  const warehouses = normalizeWarehouses(Array.isArray(value.warehouses) ? value.warehouses : seed.warehouses);
  const warehouseIds = new Set(warehouses.map((warehouse) => warehouse.id));
  const warehouseStocks = normalizeWarehouseStocks(
    Array.isArray(value.warehouseStocks) ? value.warehouseStocks : seed.warehouseStocks,
  ).filter((stock) => warehouseIds.has(stock.warehouseId));
  const inventoryTypeIds = new Set(nonAssetTypes.map((type) => type.id));
  const inventoryBrandIds = new Set(inventoryBrands.map((brand) => brand.id));
  const expandedInventoryTypeIds = Array.isArray(value.expandedInventoryTypeIds)
    ? value.expandedInventoryTypeIds.filter((id) => inventoryTypeIds.has(id))
    : nonAssetTypes.map((type) => type.id);
  const expandedInventoryBrandIds = Array.isArray(value.expandedInventoryBrandIds)
    ? value.expandedInventoryBrandIds.filter((id) => inventoryBrandIds.has(id))
    : [];
  const employeeIds = new Set((Array.isArray(value.employees) ? value.employees : seed.employees).map((employee) => employee.id));
  const computerIds = new Set((Array.isArray(value.computers) ? value.computers : seed.computers).map((computer) => computer.id));

  return {
    ...seed,
    ...value,
    filters: { ...seed.filters, ...(value.filters || {}) },
    selectedComputerIds: Array.isArray(value.selectedComputerIds)
      ? value.selectedComputerIds.filter((id) => computerIds.has(id))
      : [],
    stateRevision: Math.max(0, Number(value.stateRevision || 0)),
    selectedEmployeeIds: Array.isArray(value.selectedEmployeeIds)
      ? value.selectedEmployeeIds.filter((id) => employeeIds.has(id))
      : [],
    expandedOrgIds,
    expandedInventoryTypeIds,
    expandedInventoryBrandIds,
    orgs,
    nonAssetTypes,
    inventoryBrands,
    inventoryModels,
    warehouses,
    warehouseStocks,
    inventoryMovementLogs: Array.isArray(value.inventoryMovementLogs)
      ? value.inventoryMovementLogs.map((log) => ({
          id: String(log.id || createId("invlog")),
          direction: log.direction === "decrease" ? "decrease" : "increase",
          typeName: log.typeName || "",
          brandName: log.brandName || "",
          modelName: log.modelName || "",
          quantity: Math.max(1, Number(log.quantity || 1)),
          sourceWarehouseId: String(log.sourceWarehouseId || ""),
          targetWarehouseId: String(log.targetWarehouseId || ""),
           sourceLabel: log.sourceLabel || "",
           targetLabel: log.targetLabel || "",
           note: log.effectiveNote || log.note || "",
           originalNote: log.originalNote || log.note || "",
           effectiveNote: log.effectiveNote || log.note || "",
           noteCorrections: Array.isArray(log.noteCorrections) ? log.noteCorrections : [],
           relatedEmployeeNo: log.relatedEmployeeNo || "",
          relatedEmployeeName: log.relatedEmployeeName || "",
          triggerAction: log.triggerAction || "manual",
          occurredAt: log.occurredAt || "",
        }))
      : [],
    inventoryPurchaseLogs: Array.isArray(value.inventoryPurchaseLogs)
      ? value.inventoryPurchaseLogs.map((log) => ({
          id: String(log.id || createId("purchase")),
          typeName: log.typeName || "",
          brandName: log.brandName || "",
          modelName: log.modelName || "",
          typeId: String(log.typeId || ""),
          brandId: String(log.brandId || ""),
          modelId: String(log.modelId || ""),
          warehouseId: String(log.warehouseId || ""),
          quantity: Math.max(1, Number(log.quantity || 1)),
          inboundDate: log.inboundDate || "",
          cpu: log.cpu || "",
          memory: log.memory || "",
          storage: log.storage || "",
          gpu: log.gpu || "",
          sourceLabel: log.sourceLabel || "",
          note: log.note || "",
          sourceMovementLogId: log.sourceMovementLogId || "",
          createdAt: log.createdAt || "",
        }))
      : [],
    auditLogs: Array.isArray(value.auditLogs)
      ? value.auditLogs.map((log) => ({
          id: String(log.id || ""),
          actionType: log.actionType || "",
          entityType: log.entityType || "",
          category: log.category || "",
          categoryLabel: log.categoryLabel || "",
          changeLabel: log.changeLabel || "",
          entityId: log.entityId || "",
          entityName: log.entityName || "",
          employeeId: log.employeeId || "",
          employeeName: log.employeeName || "",
          deviceName: log.deviceName || "",
          oldValue: log.oldValue ?? null,
          newValue: log.newValue ?? null,
          summary: log.summary || "",
          actor: log.actor || "web",
          source: log.source || "web",
          createdAt: log.createdAt || "",
        }))
      : seed.auditLogs,
    auditLogTotal: Math.max(
      0,
      Number(value.auditLogTotal ?? (Array.isArray(value.auditLogs) ? value.auditLogs.length : seed.auditLogTotal)),
    ),
    employees: Array.isArray(value.employees)
      ? value.employees.map((employee) => {
          const monitors = Array.isArray(employee.monitors)
            ? employee.monitors.map((monitor) => ({
                id: monitor.id || createId("mon"),
                typeId: monitor.typeId || defaultMonitorTypeId(),
                brand: monitor.brand || monitor.displayName || "",
                model: monitor.model || "",
                inventoryBrandId: monitor.inventoryBrandId || "",
                inventoryModelId: monitor.inventoryModelId || "",
                stockAdjusted: Boolean(monitor.stockAdjusted),
              }))
            : [];
          const nonAssetItems = Array.isArray(employee.nonAssetItems)
            ? employee.nonAssetItems.map((item) => ({
                id: item.id || createId("na"),
                typeId: item.typeId || "mouse",
                brand: item.brand || "",
                model: item.model || "",
                quantity: Math.max(1, Number(item.quantity || 1)),
                inventoryBrandId: item.inventoryBrandId || "",
                inventoryModelId: item.inventoryModelId || "",
                stockAdjusted: Boolean(item.stockAdjusted),
              }))
            : Object.entries(employee.nonAssets || {}).reduce((items, [typeId, quantity]) => {
                const count = Math.max(0, Number(quantity || 0));
                if (count) {
                  items.push({
                    id: createId("na"),
                    typeId,
                    brand: "",
                    model: "",
                    quantity: count,
                    inventoryBrandId: "",
                    inventoryModelId: "",
                    stockAdjusted: false,
                  });
                }
                return items;
              }, []);
          const normalizedEmployee = {
            ...employee,
            monitors,
            nonAssetItems,
            nonAssets: {},
          };
          syncNonAssetAggregate(normalizedEmployee);
          return normalizedEmployee;
        })
      : seed.employees,
    leftEmployees: Array.isArray(value.leftEmployees)
      ? value.leftEmployees.map((item) => ({
          id: item.id || createId("left"),
          sourceEmployeeId: item.sourceEmployeeId || "",
          employeeNo: item.employeeNo || "",
          name: item.name || "",
          orgId: item.orgId || "",
          orgPath: item.orgPath || "",
          department: item.department || "",
          position: item.position || "",
          email: item.email || "",
          mobile: item.mobile || "",
          leaveDate: item.leaveDate || "",
          leaveInfo: item.leaveInfo || "",
          leaveRemark: item.leaveRemark || "",
          archivedAt: item.archivedAt || "",
          devices: Array.isArray(item.devices)
            ? item.devices.map((device) => ({
                category: device.category || "other",
                label: device.label || "",
                detail: device.detail || "",
                quantity: Math.max(1, Number(device.quantity || 1)),
                typeId: device.typeId || "",
                typeName: device.typeName || "",
                brandId: device.brandId || "",
                modelId: device.modelId || "",
                brand: device.brand || "",
                model: device.model || "",
                action: device.action || "",
                actionLabel: device.actionLabel || "",
                targetEmployeeId: device.targetEmployeeId || "",
                targetEmployeeNo: device.targetEmployeeNo || "",
                targetEmployeeName: device.targetEmployeeName || "",
                handlingNote: device.handlingNote || "",
              }))
            : [],
        }))
      : seed.leftEmployees,
    computers: Array.isArray(value.computers)
      ? value.computers.map((computer) => normalizeComputerRecord(computer, employeeIds))
      : seed.computers,
  };
}

function normalizeOrgs(orgs) {
  const hasParentField = orgs.some((org) => Object.prototype.hasOwnProperty.call(org, "parentId"));
  const hqOrg = orgs.find((org) => org.code === "HQ") || orgs[0];
  return orgs.map((org, index) => ({
    ...org,
    parentId: hasParentField ? String(org.parentId || "") : org.id === hqOrg?.id ? "" : hqOrg?.id || "",
    sortOrder: Number(org.sortOrder ?? (index + 1) * 10),
  }));
}

const orgCodeOverrides = {};

const chineseInitialFallbacks = {
  产: "C", 人: "R", 事: "S", 行: "X", 政: "Z", 研: "Y", 发: "F", 光: "G", 敏: "M", 树: "S",
  脂: "Z", 部: "B", 工: "G", 程: "C", 技: "J", 术: "S", 供: "G", 应: "Y", 链: "L", 管: "G", 理: "L",
  计: "J", 划: "H", 控: "K", 制: "Z", 营: "Y", 销: "X", 心: "X", 苏: "S", 州: "Z", 南: "N", 通: "T",
  科: "K", 德: "D", 产: "C", 品: "P", 财: "C", 务: "W", 仓: "C", 储: "C", 物: "W", 公: "G", 共: "G",
  其: "Q", 他: "T", 成: "C", 包: "B", 装: "Z", 质: "Z", 设: "S", 备: "B", 研: "Y", 采: "C", 购: "G",
  基: "J", 础: "C", 材: "C", 料: "L", 型: "X", 及: "J", 高: "G", 性: "X", 能: "N", 课: "K", 创: "C",
  新: "X", 医: "Y", 用: "Y", 实: "S", 验: "Y", 室: "S", 艺: "Y", 测: "C", 试: "S", 颜: "Y", 色: "S",
  海: "H", 外: "W", 国: "G", 内: "N", 大: "D", 客: "K", 户: "H", 媒: "M", 体: "T", 运: "Y", 项: "X",
  目: "M", 稽: "J", 核: "H", 审: "S", 持: "C", 续: "X", 善: "S", 与: "Y", 组: "Z", 一: "Y", 二: "E",
  班: "B",
};

function chineseInitial(char) {
  return chineseInitialFallbacks[char] || "";
}

function orgCodeBase(name) {
  const text = String(name || "").trim();
  if (!text) return "ORG";
  if (orgCodeOverrides[text]) return orgCodeOverrides[text];
  const ascii = text
    .replace(/[^A-Za-z0-9]+/g, "")
    .toUpperCase();
  if (ascii) return ascii.slice(0, 8);
  const initials = [...text].map(chineseInitial).join("");
  return (initials || "ORG").slice(0, 8);
}

function orgCodeFor(org, parentId = org?.parentId || "", excludeId = org?.id || "") {
  const base = orgCodeBase(org?.name);
  const siblingCodes = new Set(
    state.orgs
      .filter((item) => item.id !== excludeId && (item.parentId || "") === (parentId || ""))
      .map((item) => String(item.code || "").toUpperCase()),
  );
  if (!siblingCodes.has(base)) return base;
  let index = 2;
  while (siblingCodes.has(`${base}${index}`)) index += 1;
  return `${base}${index}`;
}

function employeeNumberPrefix(orgId) {
  const path = [];
  let current = getOrg(orgId);
  const visited = new Set();
  while (current && !visited.has(current.id)) {
    visited.add(current.id);
    path.unshift(current.code || orgCodeBase(current.name));
    current = current.parentId ? getOrg(current.parentId) : null;
  }
  const codes = path.filter(Boolean);
  if (codes.length > 1) codes.shift();
  return codes.join("-") || "ORG";
}

function employeeNumberFor(orgId, employeeId = "", status = "active") {
  if (status === "shared") {
    const org = getOrg(orgId);
    const orgCode = String(org?.code || orgCodeBase(org?.name)).toUpperCase() || "ORG";
    const sharedPrefix = `SHARED-${orgCode}-`;
    const usedShared = new Set(
      state.employees
        .filter((employee) => employee.id !== employeeId)
        .map((employee) => String(employee.employeeNo || ""))
        .filter((value) => value.startsWith(sharedPrefix))
        .map((value) => value.slice(sharedPrefix.length))
        .filter((value) => /^\d+$/.test(value))
        .map((value) => Number(value)),
    );
    let sharedSequence = 1;
    while (usedShared.has(sharedSequence)) sharedSequence += 1;
    return `${sharedPrefix}${String(sharedSequence).padStart(2, "0")}`;
  }
  const prefix = employeeNumberPrefix(orgId);
  const departmentEmployees = state.employees.filter(
    (employee) => employee.orgId === orgId && employee.id !== employeeId,
  );
  const used = new Set(
    departmentEmployees
      .map((employee) => String(employee.employeeNo || "").match(/-(\d+)$/)?.[1])
      .filter(Boolean)
      .map((value) => Number(value)),
  );
  let sequence = 1;
  while (used.has(sequence)) sequence += 1;
  return `${prefix}-${String(sequence).padStart(3, "0")}`;
}

function cookieValue(name) {
  return document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${name}=`))
    ?.slice(name.length + 1) || "";
}

function requestJson(url, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfToken = cookieValue("oa_csrf");
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  }
  return fetch(url, {
    ...options,
    method,
    headers,
    credentials: "same-origin",
  }).then(async (response) => {
    const text = await response.text();
    let payload = {};
    try {
      payload = text ? JSON.parse(text) : {};
    } catch (error) {
      const parseError = new Error(`服务器返回了无效响应（${response.status}）`);
      parseError.status = response.status;
      throw parseError;
    }
    if (!response.ok) {
      const error = new Error(payload.error || `Request failed with status ${response.status}`);
      error.status = response.status;
      error.code = payload.code || "";
      if (
        response.status === 401 &&
        authState.authenticated &&
        !url.includes("/api/auth/session") &&
        !url.includes("/api/auth/logout")
      ) {
        authState = { authenticated: false, user: null, bootstrapRequired: false };
        settingsState = {
          settings: {},
          users: [],
          backups: [],
          loaded: false,
          view: "system",
          updateStatus: null,
          updateChecking: false,
          updateApplying: false,
          updateSelectedSha: "",
          updateRepositoryUrl: "",
          updateSource: "github",
          updateCustomRepositoryUrl: "",
          updateReleaseChannel: DEFAULT_UPDATE_RELEASE_CHANNEL,
          accessControl: {
            modules: [],
            roles: [],
            users: [],
            targetType: "role",
            targetId: "",
            permissions: [],
            loading: false,
          },
        };
        invalidateAsyncRequests();
        authBootPromise = null;
        startAuth();
      }
      throw error;
    }
    return payload;
  });
}

function newIdempotencyKey(operation) {
  const suffix =
    window.crypto && typeof window.crypto.randomUUID === "function"
      ? window.crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${operation}-${suffix}`;
}

function saveResource(resourceType, resourceId, payload) {
  const suffix = resourceId ? `/${encodeURIComponent(resourceId)}` : "";
  return requestJson(`${API_RESOURCES_URL}/${encodeURIComponent(resourceType)}${suffix}`, {
    method: resourceId ? "PUT" : "POST",
    body: JSON.stringify(payload),
  });
}

function runCommand(url, payload, operation) {
  return requestJson(url, {
    method: "POST",
    headers: { "Idempotency-Key": newIdempotencyKey(operation) },
    body: JSON.stringify(payload),
  });
}

async function reloadDomainState() {
  await hydrateStateFromServer({ toast: false });
}

async function activeAllocations() {
  const payload = await requestJson("/api/inventory/allocations?status=active");
  return Array.isArray(payload.allocations) ? payload.allocations : [];
}

function scrapReasonsFor(kind) {
  const reasons = (scrapState.reasons || []).filter(
    (reason) => !kind || reason.appliesTo === kind || reason.appliesTo === "both",
  );
  if (reasons.length) return reasons;
  return DEFAULT_SCRAP_REASONS.filter(
    (reason) => !kind || reason.appliesTo === kind || reason.appliesTo === "both",
  );
}

async function loadScrapReasons() {
  if (scrapState.reasons.length) return scrapState.reasons;
  try {
    const payload = await requestJson(API_SCRAP_REASONS_URL);
    scrapState.reasons = Array.isArray(payload.reasons) ? payload.reasons : [];
  } catch (error) {
    console.error("Unable to load scrap reasons", error);
    scrapState.reasons = DEFAULT_SCRAP_REASONS.slice();
  }
  return scrapState.reasons;
}

async function loadScrapRecords(options = {}) {
  const requestId = beginAsyncRequest("scrap-records");
  scrapState.loading = true;
  try {
    const payload = await requestJson(`${API_SCRAP_RECORDS_URL}?limit=1000`);
    if (!isLatestAsyncRequest("scrap-records", requestId)) return;
    scrapState.records = Array.isArray(payload.records) ? payload.records : [];
    scrapState.loaded = true;
    if (options.toast) showToast(`已加载 ${scrapState.records.length} 条报废记录`);
  } finally {
    scrapState.loading = false;
  }
}

async function scrapInventoryUsage(allocationType, usageRecordId, payload) {
  return runCommand(
    `/api/inventory/usage/${encodeURIComponent(allocationType)}/${encodeURIComponent(usageRecordId)}/scrap`,
    payload,
    "inventory-scrap",
  );
}

async function scrapComputerAsset(computerId, payload) {
  return runCommand(
    `/api/computers/${encodeURIComponent(computerId)}/scrap`,
    payload,
    "computer-scrap",
  );
}

async function returnUsageAllocations(employeeId, allocationType, usageRecordId, notes = "", warehouseId = "") {
  const allocations = await activeAllocations();
  const matches = allocations.filter(
    (item) =>
      String(item.employeeId || "") === String(employeeId || "") &&
      item.allocationType === allocationType &&
      String(item.usageRecordId || "") === String(usageRecordId || ""),
  );
  const recoveryRecords = [];
  for (const allocation of matches) {
    const payload = await runCommand(
      `/api/inventory/allocations/${encodeURIComponent(allocation.id)}/return`,
      { notes, warehouseId: String(warehouseId || "") },
      "inventory-return",
    );
    recoveryRecords.push(...(payload.recoveryRecords || []));
  }
  if (matches.length) return recoveryRecords;

  // Older usage rows predate allocation history. Return them through the
  // transactional compatibility command instead of treating a valid row as
  // an unchecked selection.
  const legacyPayload = await runCommand(
    `/api/inventory/usage/${encodeURIComponent(allocationType)}/${encodeURIComponent(usageRecordId)}/return`,
    { employeeId: String(employeeId || ""), notes, warehouseId: String(warehouseId || "") },
    "inventory-usage-return",
  );
  return legacyPayload.recoveryRecords || [];
}

async function requestDownload(url, body = {}) {
  const csrfToken = cookieValue("oa_csrf");
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
    },
    body: JSON.stringify(body),
    credentials: "same-origin",
  });
  if (!response.ok) {
    const text = await response.text();
    let payload = {};
    try {
      payload = text ? JSON.parse(text) : {};
    } catch (error) {
      payload = {};
    }
    const requestError = new Error(payload.error || `下载失败（${response.status}）`);
    requestError.status = response.status;
    requestError.code = payload.code || "";
    throw requestError;
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const filenameMatch = disposition.match(/filename="([^"]+)"/i);
  const filename = filenameMatch?.[1] || "database-backup.sql.gz";
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  return filename;
}

async function requestFormData(url, formData, options = {}) {
  const method = String(options.method || "POST").toUpperCase();
  const csrfToken = cookieValue("oa_csrf");
  const headers = {
    ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
    ...(options.headers || {}),
  };
  const response = await fetch(url, {
    ...options,
    method,
    headers,
    body: formData,
    credentials: "same-origin",
  });
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch (error) {
    const parseError = new Error(`服务器返回了无效响应（${response.status}）`);
    parseError.status = response.status;
    throw parseError;
  }
  if (!response.ok) {
    const requestError = new Error(payload.error || `Request failed with status ${response.status}`);
    requestError.status = response.status;
    requestError.code = payload.code || "";
    throw requestError;
  }
  return payload;
}

function renderAuthScreen(errorMessage = "") {
  const root = document.querySelector("#authRoot");
  const appShell = document.querySelector("#appShell");
  if (!root || !appShell) return;
  appShell.hidden = true;
  root.hidden = false;
  const appName = settingsState.settings.app_name || "办公资产管理系统";
  const loginNotice = settingsState.settings.login_notice || "";
  const bootstrap = Boolean(authState.bootstrapRequired);
  const form = bootstrap
    ? `<form class="auth-form" data-form="auth-bootstrap">
        ${inputField("管理员账号", "username", "", true, "请输入 3-64 位账号", "text", "", 'autocomplete="username"')}
        ${inputField("显示名称", "displayName", "", true, "例如：IT 管理员")}
        ${inputField("登录密码", "password", "", true, "至少 8 位", "password", "8", 'autocomplete="new-password"')}
        ${inputField("确认密码", "confirmPassword", "", true, "再次输入密码", "password", "8", 'autocomplete="new-password"')}
        <button class="primary-button auth-submit" type="submit">创建管理员并进入系统</button>
      </form>`
    : `<form class="auth-form" data-form="auth-login">
        ${inputField("账号", "username", "", true, "请输入账号", "text", "", 'autocomplete="username"')}
        ${inputField("密码", "password", "", true, "请输入密码", "password", "", 'autocomplete="current-password"')}
        <button class="primary-button auth-submit" type="submit">登录系统</button>
      </form>`;
  root.innerHTML = `
    <main class="auth-page">
      <section class="auth-panel">
        <div class="auth-brand">
          <span class="brand-mark">OA</span>
          <div><strong>${escapeHtml(appName)}</strong><span>办公资产运营平台</span></div>
        </div>
        <div class="auth-heading">
          <span class="eyebrow">${bootstrap ? "FIRST RUN SETUP" : "SECURE SIGN IN"}</span>
          <h1>${bootstrap ? "初始化管理员账号" : "登录系统"}</h1>
          <p>${bootstrap ? "首次使用请创建一名管理员，之后可在设置中维护其他账号。" : "请输入账号和密码继续使用资产管理系统。"}</p>
        </div>
        ${errorMessage ? `<div class="auth-error">${escapeHtml(errorMessage)}</div>` : ""}
        ${loginNotice ? `<div class="auth-notice">${escapeHtml(loginNotice)}</div>` : ""}
        ${form}
        <div class="auth-footer">MySQL 联机模式 · 会话由服务器安全管理</div>
      </section>
    </main>`;
}

function updateAuthenticatedChrome() {
  const appShell = document.querySelector("#appShell");
  const root = document.querySelector("#authRoot");
  if (!appShell || !root) return;
  appShell.hidden = !authState.authenticated;
  root.hidden = authState.authenticated;
  if (!authState.authenticated) return;
  const user = authState.user || {};
  const displayName = user.displayName || user.username || "未登录";
  const initials = [...displayName.replace(/\s+/g, "")].slice(0, 2).join("") || "IT";
  const avatar = document.querySelector("#userAvatar");
  const badge = document.querySelector("#userBadgeText");
  const brandName = document.querySelector("#brandName");
  const brandSubtitle = document.querySelector("#brandSubtitle");
  if (avatar) avatar.textContent = initials;
  if (badge) {
    badge.innerHTML = `<strong>${escapeHtml(displayName)}</strong><small>${escapeHtml(
      `${user.username || ""} · ${authRoleLabel(user.role)}`,
    )}</small>`;
  }
  if (brandName) brandName.textContent = settingsState.settings.app_name || "办公资产";
  if (brandSubtitle) brandSubtitle.textContent = "管理中台";
  appShell.classList.toggle("is-read-only", !canWriteState());
  const quickTicket = document.querySelector('[data-action="quick-create-ticket"]');
  if (quickTicket) quickTicket.hidden = !hasPermission("tickets", "create");
  const notificationButton = document.querySelector('[data-action="open-notifications"]');
  if (notificationButton) notificationButton.hidden = !hasPermission("notifications", "view");
  const notificationCount = document.querySelector("[data-notification-count]");
  const unreadCount = unreadNotificationCount();
  if (notificationCount) {
    notificationCount.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
    notificationCount.hidden = unreadCount < 1;
  }
}

async function refreshNotificationSummary() {
  if (!authState.authenticated || !hasPermission("notifications", "view")) return;
  try {
    const payload = await requestJson(API_NOTIFICATIONS_URL);
    serviceState().notifications = Array.isArray(payload.notifications) ? payload.notifications : [];
    updateAuthenticatedChrome();
  } catch (error) {
    console.error("Unable to load notification summary", error);
  }
}

async function loadSettingsState(options = {}) {
  const settingsPayload = await requestJson(API_SETTINGS_URL);
  settingsState.settings = settingsPayload.settings || {};
  if (options.users && isAdminUser()) {
    const usersPayload = await requestJson(API_USERS_URL);
    settingsState.users = Array.isArray(usersPayload.users) ? usersPayload.users : [];
    await loadAccessControl();
  }
  if (isAdminUser()) {
    const backupsPayload = await requestJson(API_BACKUPS_URL);
    settingsState.backups = Array.isArray(backupsPayload.backups) ? backupsPayload.backups : [];
  } else {
    settingsState.backups = [];
  }
  if (hasPermission("system_updates", "update")) {
    settingsState.updateRepositoryUrl = Object.prototype.hasOwnProperty.call(
      settingsState.settings,
      "update_repository_url",
    )
      ? settingsState.settings.update_repository_url || ""
      : settingsState.updateRepositoryUrl || "";
  } else {
    settingsState.updateRepositoryUrl = "";
  }
  settingsState.loaded = true;
  updateAuthenticatedChrome();
  return settingsState;
}

async function loadAccessControl() {
  if (!isAdminUser()) return;
  const access = accessControlState();
  access.loading = true;
  const payload = await requestJson(API_ACCESS_CONTROL_URL);
  access.modules = Array.isArray(payload.modules)
    ? payload.modules.map((module) => ({
        ...module,
        name: permissionModuleLabel(module),
        displayName: permissionModuleLabel(module),
      }))
    : [];
  access.roles = Array.isArray(payload.roles) ? payload.roles : [];
  access.users = Array.isArray(payload.users) ? payload.users : [];
  access.roles.forEach((role) => {
    if (role.code) roleLabels[role.code] = role.name || role.code;
  });
  if (!access.targetId) {
    access.targetId =
      access.targetType === "role"
        ? String(access.roles[0]?.id || "")
        : String(access.users[0]?.id || "");
  }
  access.loading = false;
  await loadAccessControlTarget();
}

async function loadAccessControlTarget() {
  const access = accessControlState();
  if (!access.targetId) {
    access.permissions = [];
    return true;
  }
  const requestId = beginAsyncRequest("access-control-target");
  const targetType = access.targetType;
  const targetId = access.targetId;
  const endpoint =
    targetType === "role"
      ? `${API_ROLES_URL}/${encodeURIComponent(targetId)}/permissions`
      : `${API_USERS_URL}/${encodeURIComponent(targetId)}/permissions`;
  const payload = await requestJson(endpoint);
  if (
    !isLatestAsyncRequest("access-control-target", requestId) ||
    access.targetType !== targetType ||
    access.targetId !== targetId
  ) {
    return false;
  }
  access.permissions = Array.isArray(payload.permissions) ? payload.permissions : [];
  return true;
}

async function enterAuthenticatedSession(payload) {
  authState = {
    authenticated: true,
    user: payload.user || null,
    bootstrapRequired: false,
    permissions: [],
  };
  try {
    const permissionPayload = await requestJson(API_AUTH_PERMISSIONS_URL);
    authState.permissions = Array.isArray(permissionPayload.permissions) ? permissionPayload.permissions : [];
    if (authState.user) authState.user.isSuperAdmin = Boolean(permissionPayload.isSuperAdmin);
  } catch (error) {
    console.error("Unable to load permissions", error);
  }
  updateAuthenticatedChrome();
  try {
    await loadSettingsState({ users: isAdminUser() });
  } catch (error) {
    console.error("Unable to load authenticated settings", error);
  }
  await hydrateStateFromServer({ toast: false });
  refreshNotificationSummary();
  render();
}

async function startAuth() {
  if (authBootPromise) return authBootPromise;
  authBootPromise = (async () => {
    try {
      const session = await requestJson(API_AUTH_SESSION_URL);
      if (session.authenticated) {
        await enterAuthenticatedSession(session);
        return;
      }
    } catch (error) {
      if (error.status !== 401) {
        renderAuthScreen(`连接认证服务失败：${error.message}`);
        return;
      }
    }
    try {
      const status = await requestJson(API_AUTH_BOOTSTRAP_STATUS_URL);
      settingsState.settings = status.settings || settingsState.settings;
      authState = { authenticated: false, user: null, bootstrapRequired: Boolean(status.required) };
      renderAuthScreen();
    } catch (error) {
      renderAuthScreen(`无法读取登录状态：${error.message}`);
    }
  })();
  return authBootPromise;
}

async function handleAuthSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const isBootstrap = form.dataset.form === "auth-bootstrap";
  const endpoint = isBootstrap ? API_AUTH_BOOTSTRAP_URL : API_AUTH_LOGIN_URL;
  const submit = form.querySelector('button[type="submit"]');
  if (submit) submit.disabled = true;
  try {
    const payload = await requestJson(endpoint, {
      method: "POST",
      body: JSON.stringify(data),
    });
    await enterAuthenticatedSession(payload);
  } catch (error) {
    renderAuthScreen(error.message);
  } finally {
    if (submit) submit.disabled = false;
  }
}

async function logout() {
  try {
    await requestJson(API_AUTH_LOGOUT_URL, { method: "POST", body: "{}" });
  } catch (error) {
    console.error("Unable to log out", error);
  }
  authState = { authenticated: false, user: null, bootstrapRequired: false };
  settingsState = {
    settings: {},
    users: [],
    backups: [],
    loaded: false,
    view: "system",
    updateStatus: null,
    updateChecking: false,
    updateApplying: false,
    updateSelectedSha: "",
    updateRepositoryUrl: "",
    updateSource: "github",
    updateCustomRepositoryUrl: "",
    updateReleaseChannel: DEFAULT_UPDATE_RELEASE_CHANNEL,
    accessControl: {
      modules: [],
      roles: [],
      users: [],
      targetType: "role",
      targetId: "",
      permissions: [],
      loading: false,
    },
  };
  invalidateAsyncRequests();
  lastRenderedPage = "";
  document.querySelector("#modalRoot").innerHTML = "";
  authBootPromise = null;
  startAuth();
}

function applyRemoteState(payload) {
  state = normalizeState({
    ...state,
    ...payload,
  });
  if (!state.expandedOrgIds.length) {
    state.expandedOrgIds = state.orgs.map((org) => org.id);
  }
  syncFilterSearchDraftsFromFilters();
}

function buildAuditLogsUrl(limit = 5000) {
  const params = new URLSearchParams();
  const {
    auditStartDate,
    auditEndDate,
    auditEmployee,
    auditAction,
    auditCategory,
    auditEntityType,
    auditSearch,
  } = state.filters;
  if (auditStartDate) params.set("startDate", auditStartDate);
  if (auditEndDate) params.set("endDate", auditEndDate);
  if (auditEmployee) params.set("employee", auditEmployee.trim());
  if (auditAction) params.set("actionType", auditAction);
  if (auditCategory) params.set("category", auditCategory);
  if (auditEntityType) params.set("entityType", auditEntityType);
  if (auditSearch) params.set("keyword", auditSearch.trim());
  params.set("limit", String(limit));
  return `${API_AUDIT_LOGS_URL}?${params.toString()}`;
}

async function refreshAuditLogs(options = {}) {
  const requestId = beginAsyncRequest("audit-logs");
  const payload = await requestJson(buildAuditLogsUrl(options.limit || 5000));
  if (!isLatestAsyncRequest("audit-logs", requestId)) return null;
  state.auditLogs = normalizeState({ auditLogs: payload.logs || [], auditLogTotal: payload.total || 0 }).auditLogs;
  state.auditLogTotal = Math.max(0, Number(payload.total || state.auditLogs.length));
  if (!options.silent) renderIfCurrentPage("audit");
  return payload;
}

function persistState(syncRemote = false) {
  window.localStorage.setItem(UI_STORAGE_KEY, JSON.stringify(extractUiState(state)));
  if (syncRemote) {
    console.warn("Snapshot writes are retired. Use a resource or command API for business changes.");
  }
  return remoteSyncQueue;
}

async function hydrateStateFromServer(options = {}) {
  const requestId = beginAsyncRequest("domain-state");
  try {
    const payload = await requestJson(API_STATE_URL);
    if (!isLatestAsyncRequest("domain-state", requestId)) return;
    applyRemoteState(payload);
    state.auditLogTotal = state.auditLogs.length;
    window.localStorage.setItem(UI_STORAGE_KEY, JSON.stringify(extractUiState(state)));
    render();
    if (options.toast) showToast("已从数据库加载最新数据");
  } catch (error) {
    console.error("Unable to load database state", error);
    if (options.toast !== false) {
      showToast(`数据库加载失败：${error.message}`, true);
    }
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function compareText(a, b) {
  return String(a || "").localeCompare(String(b || ""), "zh-CN");
}

function sameRecordId(left, right) {
  const leftId = String(left ?? "").trim();
  const rightId = String(right ?? "").trim();
  return Boolean(leftId && rightId && leftId === rightId);
}

function getOrg(id) {
  return state.orgs.find((org) => org.id === id);
}

function getEmployee(id) {
  return state.employees.find((employee) => sameRecordId(employee.id, id));
}

function getLeftEmployee(id) {
  return state.leftEmployees.find((employee) => employee.id === id);
}

function getLeftEmployeeBySource(sourceEmployeeId, employeeNo = "") {
  return state.leftEmployees.find(
    (employee) =>
      (sourceEmployeeId && employee.sourceEmployeeId === sourceEmployeeId) ||
      (employeeNo && employee.employeeNo === employeeNo),
  );
}

function getType(id) {
  return state.nonAssetTypes.find((type) => type.id === id);
}

function normalizeWarehouses(warehouses) {
  return (Array.isArray(warehouses) ? warehouses : []).map((warehouse) => ({
    id: String(warehouse.id || warehouse.warehouseId || ""),
    code: String(warehouse.code || warehouse.warehouseCode || ""),
    name: String(warehouse.name || warehouse.warehouseName || ""),
    orgId: String(warehouse.orgId || warehouse.orgUnitId || ""),
    managerEmployeeId: String(warehouse.managerEmployeeId || ""),
    managerName: String(warehouse.managerName || ""),
    contactPhone: String(warehouse.contactPhone || ""),
    address: String(warehouse.address || ""),
    isActive: warehouse.isActive !== false && Number(warehouse.isActive ?? 1) !== 0,
    remarks: String(warehouse.remarks || ""),
    createdAt: warehouse.createdAt || "",
    updatedAt: warehouse.updatedAt || "",
  })).filter((warehouse) => warehouse.id && warehouse.name);
}

function normalizeWarehouseStocks(stocks) {
  return (Array.isArray(stocks) ? stocks : []).map((stock) => ({
    warehouseId: String(stock.warehouseId || ""),
    modelId: String(stock.modelId || ""),
    quantity: Math.max(0, Number(stock.quantity || 0)),
    typeId: String(stock.typeId || ""),
    brandId: String(stock.brandId || ""),
    typeName: String(stock.typeName || ""),
    brandName: String(stock.brandName || ""),
    modelName: String(stock.modelName || ""),
    unit: String(stock.unit || "件"),
  })).filter((stock) => stock.warehouseId && stock.modelId && stock.quantity > 0);
}

function activeWarehouses() {
  return (state.warehouses || []).filter((warehouse) => warehouse.isActive);
}

function warehouseName(id) {
  return state.warehouses?.find((warehouse) => sameRecordId(warehouse.id, id))?.name || "";
}

function currentUserOrgId() {
  return (
    authState.user?.orgId ||
    getEmployee(authState.user?.employeeId)?.orgId ||
    ""
  );
}

function organizationAncestorIds(orgId) {
  const currentId = String(orgId || "").trim();
  if (!currentId) return [];
  const orgById = new Map((state.orgs || []).map((org) => [String(org.id || ""), org]));
  const ancestors = [];
  const visited = new Set();
  let current = orgById.get(currentId);
  while (current && !visited.has(String(current.id || ""))) {
    const id = String(current.id || "");
    visited.add(id);
    ancestors.push(id);
    current = orgById.get(String(current.parentId || ""));
  }
  return ancestors;
}

function defaultWarehouseIdForOrg(orgId) {
  const ancestors = organizationAncestorIds(orgId);
  if (!ancestors.length) return "";
  for (const ancestorId of ancestors) {
    const candidates = activeWarehouses()
      .filter((warehouse) => sameRecordId(warehouse.orgId, ancestorId))
      .sort((left, right) => compareText(left.name, right.name) || compareText(left.id, right.id));
    if (candidates.length) return candidates[0].id;
  }
  return "";
}

function defaultWarehouseIdForCurrentUser() {
  return defaultWarehouseIdForOrg(currentUserOrgId());
}

function warehouseOptions(selectedId = "", placeholder = "请选择仓库", preferredOrgId = "", useDefaultSelection = true) {
  const preferredAncestors = organizationAncestorIds(preferredOrgId);
  const preferredRank = new Map(preferredAncestors.map((orgId, index) => [orgId, index]));
  const effectiveSelectedId = String(selectedId || "").trim() || (
    useDefaultSelection && preferredOrgId ? defaultWarehouseIdForOrg(preferredOrgId) : ""
  );
  const warehouses = activeWarehouses().sort((left, right) => {
    const leftRank = preferredRank.has(String(left.orgId)) ? preferredRank.get(String(left.orgId)) : Number.MAX_SAFE_INTEGER;
    const rightRank = preferredRank.has(String(right.orgId)) ? preferredRank.get(String(right.orgId)) : Number.MAX_SAFE_INTEGER;
    return leftRank - rightRank || compareText(left.name, right.name) || compareText(left.id, right.id);
  });
  return [{ value: "", label: placeholder }].concat(
    warehouses.map((warehouse) => ({
      value: warehouse.id,
      label: `${warehouse.name}${warehouse.code ? ` · ${warehouse.code}` : ""}${orgName(warehouse.orgId) ? ` · ${orgName(warehouse.orgId)}` : ""}`,
    })),
  ).map((option) => ({
    ...option,
    selected: String(option.value) === effectiveSelectedId,
  }));
}

function warehouseSelectField(
  label,
  name,
  selectedId = "",
  required = false,
  placeholder = "请选择仓库",
  preferredOrgId = "",
) {
  const options = warehouseOptions(selectedId, placeholder, preferredOrgId);
  const selectedValue = options.find((option) => option.selected)?.value || "";
  return selectField(label, name, selectedValue, options, required);
}

function inventoryWarehouseById(id = inventoryWarehouseView) {
  return (state.warehouses || []).find((warehouse) => sameRecordId(warehouse.id, id)) || null;
}

function inventoryModelQuantityInWarehouse(modelId, warehouseId = inventoryWarehouseView) {
  if (!warehouseId) {
    return Math.max(0, Number(getInventoryModel(modelId)?.quantity || 0));
  }
  return Math.max(
    0,
    Number(
      (state.warehouseStocks || []).find(
        (stock) => sameRecordId(stock.warehouseId, warehouseId) && sameRecordId(stock.modelId, modelId),
      )?.quantity || 0,
    ),
  );
}

function inventoryModelForWarehouseView(model, warehouseId = inventoryWarehouseView) {
  return {
    ...model,
    quantity: inventoryModelQuantityInWarehouse(model.id, warehouseId),
  };
}

function inventoryWarehousesForView() {
  return [...(state.warehouses || [])].sort((left, right) => {
    if (left.isActive !== right.isActive) return left.isActive ? -1 : 1;
    return compareText(left.name, right.name);
  });
}

function ensureInventoryWarehouseView() {
  const warehouses = inventoryWarehousesForView();
  if (!warehouses.some((warehouse) => sameRecordId(warehouse.id, inventoryWarehouseView))) {
    inventoryWarehouseView = warehouses.find((warehouse) => warehouse.isActive)?.id || warehouses[0]?.id || "";
  }
  return inventoryWarehouseView;
}

function warehouseInventoryTotal(warehouseId = inventoryWarehouseView) {
  if (!warehouseId) {
    return state.inventoryModels.reduce((sum, model) => sum + Math.max(0, Number(model.quantity || 0)), 0);
  }
  return (state.warehouseStocks || [])
    .filter((stock) => sameRecordId(stock.warehouseId, warehouseId))
    .reduce((sum, stock) => sum + Math.max(0, Number(stock.quantity || 0)), 0);
}

function warehouseInventoryModelCount(warehouseId = inventoryWarehouseView) {
  if (!warehouseId) {
    return state.inventoryModels.filter((model) => Math.max(0, Number(model.quantity || 0)) > 0).length;
  }
  return (state.warehouseStocks || []).filter(
    (stock) => sameRecordId(stock.warehouseId, warehouseId) && Math.max(0, Number(stock.quantity || 0)) > 0,
  ).length;
}

function nextWarehouseCode() {
  const used = new Set((state.warehouses || []).map((warehouse) => String(warehouse.code || "").toUpperCase()));
  let sequence = 1;
  while (used.has(`WH-${String(sequence).padStart(3, "0")}`)) sequence += 1;
  return `WH-${String(sequence).padStart(3, "0")}`;
}

function warehouseOrganizationOptions(selectedId = "") {
  return [{ value: "", label: "请选择所属组织" }].concat(
    [...state.orgs]
      .sort((left, right) => compareText(orgName(left.id), orgName(right.id)))
      .map((org) => ({
        value: org.id,
        label: orgPathName(org.id) || org.name,
        selected: sameRecordId(org.id, selectedId),
      })),
  );
}

function warehouseManagerOptions(orgId = "", selectedId = "") {
  return [{ value: "", label: "未指定负责人" }].concat(
    (state.employees || [])
      .filter((employee) => employee.status === "active" && sameRecordId(employee.orgId, orgId))
      .sort((left, right) => compareText(left.name, right.name))
      .map((employee) => ({
        value: employee.id,
        label: `${employee.name}${employee.employeeNo ? ` · ${employee.employeeNo}` : ""}`,
        selected: sameRecordId(employee.id, selectedId),
      })),
  );
}

function inventoryModelOptionsForWarehouse(warehouseId = "", selectedId = "", includeZero = false) {
  const models = state.inventoryModels
    .map((model) => inventoryModelForWarehouseView(model, warehouseId))
    .filter((model) => includeZero || model.quantity > 0)
    .sort((left, right) => compareText(left.name, right.name));
  return [{ value: "", label: "请选择物资型号" }].concat(
    models.map((model) => {
      const brand = getInventoryBrand(model.brandId);
      const type = getType(model.typeId);
      return {
        value: model.id,
        label: `${type?.name || "未分类"} / ${brand?.name || "未登记品牌"} / ${model.name}（${model.quantity} ${type?.unit || "件"}）`,
        selected: sameRecordId(model.id, selectedId),
      };
    }),
  );
}

function computerInventoryModelOptionsForWarehouse(warehouseId = "", selectedId = "") {
  const models = state.inventoryModels
    .map((model) => inventoryModelForWarehouseView(model, warehouseId))
    .filter((model) => isComputerInventoryType(getType(model.typeId)) && model.quantity > 0)
    .sort((left, right) => compareText(left.name, right.name) || compareText(left.id, right.id));
  return [{ value: "", label: "请选择库存电脑型号" }].concat(
    models.map((model) => ({
      value: model.id,
      label: inventoryModelOptionLabel(model),
      selected: sameRecordId(model.id, selectedId),
    })),
  );
}

function isComputerInventoryType(type) {
  const code = inventoryText(type?.code);
  const name = inventoryText(type?.name);
  return (
    code === "computer" ||
    code === "pc" ||
    ["电脑", "办公终端", "办公设备终端"].includes(name)
  );
}

function isComputerInventoryTypeName(name) {
  const text = inventoryText(name);
  return ["电脑", "办公终端", "办公设备终端", "computer", "pc"].includes(text);
}

function computerInventoryType() {
  return state.nonAssetTypes.find((type) => isComputerInventoryType(type));
}

function computerInventoryTypeId() {
  return computerInventoryType()?.id || "";
}

function isProtectedInventoryType(type) {
  return isComputerInventoryType(type);
}

function defaultMonitorTypeId() {
  const preferred = state.nonAssetTypes.find((type) => {
    const text = `${type.code || ""} ${type.name || ""}`.toLowerCase();
    return text.includes("monitor") || text.includes("display") || text.includes("\u663e\u793a");
  });
  return preferred?.id || state.nonAssetTypes[0]?.id || "mouse";
}

function getInventoryBrand(id) {
  return state.inventoryBrands.find((brand) => brand.id === id);
}

function getInventoryModel(id) {
  return state.inventoryModels.find((model) => model.id === id);
}

function inventoryBrandsForType(typeId) {
  return state.inventoryBrands
    .filter((brand) => brand.typeId === typeId)
    .sort((a, b) => Number(a.sortOrder) - Number(b.sortOrder) || compareText(a.name, b.name));
}

function inventoryModelsForBrand(brandId) {
  return state.inventoryModels
    .filter((model) => model.brandId === brandId)
    .sort((a, b) => Number(a.sortOrder) - Number(b.sortOrder) || compareText(a.name, b.name));
}

const inventoryTypeCodeOverrides = {
  鼠标: "SB",
  键盘: "JP",
  显示屏: "XSP",
  显示器: "XSQ",
  拓展坞: "TZW",
  耳机: "EJ",
  摄像头: "SXT",
  支架: "ZJ",
  笔记本支架: "BJBZJ",
  电脑支架: "DNZJ",
  办公终端支架: "DNZJ",
  USB集线器: "USB",
  电源适配器: "DYSPQ",
  充电器: "CDQ",
  数据线: "SJX",
  电脑: "DN",
  办公终端: "DN",
};

function inventoryCodeBase(name) {
  const text = String(name || "").trim();
  if (!text) return "IT";
  if (inventoryTypeCodeOverrides[text]) return inventoryTypeCodeOverrides[text];
  const ascii = text.replace(/[^A-Za-z0-9]+/g, "").toUpperCase();
  if (ascii) return ascii.slice(0, 8);
  const initials = [...text].map(chineseInitial).join("");
  return (initials || "IT").slice(0, 8);
}

function inventoryTypeCodeFor(name, excludeId = "") {
  const base = inventoryCodeBase(name);
  const siblingCodes = new Set(
    state.nonAssetTypes
      .filter((item) => item.id !== excludeId)
      .map((item) => String(item.code || "").toUpperCase()),
  );
  if (!siblingCodes.has(base)) return base;
  let index = 2;
  while (siblingCodes.has(`${base}${index}`)) index += 1;
  return `${base}${index}`;
}

function nextTypeSortOrder() {
  return state.nonAssetTypes.reduce((max, item) => Math.max(max, Number(item.sortOrder || 0)), 0) + 10;
}

function nextBrandSortOrder(typeId) {
  return state.inventoryBrands
    .filter((item) => item.typeId === typeId)
    .reduce((max, item) => Math.max(max, Number(item.sortOrder || 0)), 0) + 10;
}

function nextModelSortOrder(brandId) {
  return state.inventoryModels
    .filter((item) => item.brandId === brandId)
    .reduce((max, item) => Math.max(max, Number(item.sortOrder || 0)), 0) + 10;
}

function inventoryText(value) {
  return String(value || "").trim().toLowerCase();
}

function inventoryTypeSearchText(type) {
  return inventoryText([type.code, type.name, type.unit].filter(Boolean).join(" "));
}

function inventoryBrandSearchText(brand) {
  return inventoryText(brand.name);
}

function inventoryModelSearchText(model) {
  return inventoryText(
    [
      model.name,
      model.batchKey,
      model.quantity,
      model.inboundDate,
      model.cpu,
      model.memory,
      model.storage,
      model.gpu,
    ]
      .filter((value) => value !== "" && value !== null && value !== undefined)
      .join(" "),
  );
}

function inventoryModelConfigSummary(model) {
  return [
    ["CPU", model.cpu],
    ["内存", model.memory],
    ["存储", model.storage],
    ["显卡", model.gpu],
  ]
    .filter(([, value]) => String(value || "").trim())
    .map(([label, value]) => `${label}: ${value}`)
    .join(" / ");
}

function inventoryModelDisplayMeta(type, model) {
  return [
    `${Math.max(0, Number(model.quantity || 0))} ${type?.unit || "件"}`,
    isComputerInventoryType(type) && model.inboundDate ? `入库：${model.inboundDate}` : "",
    isComputerInventoryType(type) ? inventoryModelConfigSummary(model) : "",
  ]
    .filter(Boolean)
    .join(" / ");
}

function inventoryModelOptionLabel(model) {
  const parts = [`${model.name} (${Math.max(0, Number(model.quantity || 0))})`];
  if (model.batchKey) parts.push(`批次：${model.batchKey}`);
  if (isComputerInventoryType(getType(model.typeId)) && model.inboundDate) {
    parts.push(`入库：${model.inboundDate}`);
  }
  const config = inventoryModelConfigSummary(model);
  if (config) parts.push(config);
  return parts.join(" · ");
}

function normalizeStorageValue(value) {
  const text = String(value || "").trim();
  return /^500\s*g(?:b)?$/i.test(text) ? "512G" : text;
}

function currentTimestampText() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(
    now.getMinutes(),
  )}:${pad(now.getSeconds())}`;
}

function currentDateText() {
  return currentTimestampText().slice(0, 10);
}

function inventoryDirectionLabel(direction) {
  return direction === "decrease" ? "减少" : "增加";
}

function inventoryDirectionClass(direction) {
  return direction === "decrease" ? "audit-action-alert" : "audit-action-added";
}

const flowRecordDefinitions = {
  inventory_receipt: { label: "仓库入库", category: "库存入库", stockDelta: 1 },
  inventory_adjustment: { label: "库存调整", category: "库存管理" },
  inventory_transfer: { label: "仓库调拨", category: "库存调拨", stockDelta: 0 },
  import: { label: "导入入库", category: "库存入库", stockDelta: 1 },
  manual_create: { label: "手工入库", category: "库存入库", stockDelta: 1 },
  manual_adjustment: { label: "库存调整", category: "库存管理" },
  computer_inventory_adjustment: { label: "终端库存调整", category: "库存管理" },
  assignment: { label: "领用发放", category: "领用发放", stockDelta: -1 },
  return: { label: "归还回收", category: "归还回收", stockDelta: 1 },
  return_adjustment: { label: "归还回收", category: "归还回收", stockDelta: 1 },
  employee_device_recovery: { label: "设备回收", category: "归还回收", stockDelta: 1 },
  leave_recovery: { label: "离职回收", category: "归还回收", stockDelta: 1 },
  employee_delete_recovery: { label: "人员删除回收", category: "归还回收", stockDelta: 1 },
  delete_monitor: { label: "显示器回收", category: "归还回收", stockDelta: 1 },
  delete_nonasset: { label: "物资回收", category: "归还回收", stockDelta: 1 },
  delete_type: { label: "删除类型", category: "库存管理", stockDelta: -1 },
  delete_inventory_model: { label: "删除型号", category: "库存管理", stockDelta: -1 },
};

function flowRecordDefinition(logOrAction, direction = "increase") {
  const action =
    typeof logOrAction === "string" ? logOrAction : String(logOrAction?.triggerAction || "manual");
  return (
    flowRecordDefinitions[action] || {
      label: "其他变动",
      category: "库存管理",
      stockDelta: direction === "decrease" ? -1 : 1,
    }
  );
}

function flowRecordActionLabel(log) {
  return flowRecordDefinition(log, log?.direction).label;
}

function flowRecordCategory(log) {
  return flowRecordDefinition(log, log?.direction).category;
}

function flowRecordActionClass(log) {
  const action = String(log?.triggerAction || "");
  if (["assignment", "delete_type", "delete_inventory_model"].includes(action)) return "audit-action-outbound";
  if (
    [
      "return",
      "return_adjustment",
      "employee_device_recovery",
      "leave_recovery",
      "employee_delete_recovery",
      "delete_monitor",
      "delete_nonasset",
    ].includes(action)
  ) {
    return "audit-action-return";
  }
  if (["manual_adjustment", "computer_inventory_adjustment"].includes(action)) return "audit-action-adjustment";
  if (["import", "manual_create"].includes(action)) return "audit-action-inbound";
  return log?.direction === "decrease" ? "audit-action-outbound" : "audit-action-inbound";
}

function flowRecordStockImpact(log) {
  const definition = flowRecordDefinition(log, log?.direction);
  if (definition.stockDelta === 0) return "不变";
  return log?.direction === "decrease" ? "减少" : "增加";
}

function flowRecordImpactClass(log) {
  const impact = flowRecordStockImpact(log);
  if (impact === "不变") return "audit-action-adjustment";
  return inventoryDirectionClass(log.direction);
}

function flowRecordFilterText(value) {
  return String(value || "").trim().toLowerCase();
}

function flowRecordDate(log) {
  return String(log?.occurredAt || "").replace("T", " ").slice(0, 10);
}

function flowRecordTypeOptions() {
  return [...new Set(state.inventoryMovementLogs.map((log) => String(log.typeName || "").trim()).filter(Boolean))].sort(
    (left, right) => left.localeCompare(right, "zh-CN"),
  );
}

function flowRecordActionOptions() {
  return [...new Set(state.inventoryMovementLogs.map((log) => flowRecordActionLabel(log)))].sort((left, right) =>
    left.localeCompare(right, "zh-CN"),
  );
}

function flowRecordCategoryOptions() {
  return [...new Set(state.inventoryMovementLogs.map((log) => flowRecordCategory(log)))].sort((left, right) =>
    left.localeCompare(right, "zh-CN"),
  );
}

function hasFlowRecordFilters() {
  return [
    "flowSearch",
    "flowType",
    "flowAction",
    "flowCategory",
    "flowEmployee",
    "flowSourceTarget",
    "flowStartDate",
    "flowEndDate",
  ].some((key) => Boolean(String(state.filters[key] || "").trim()));
}

function getFilteredFlowRecords() {
  const search = flowRecordFilterText(state.filters.flowSearch);
  const type = String(state.filters.flowType || "");
  const action = String(state.filters.flowAction || "");
  const category = String(state.filters.flowCategory || "");
  const employee = flowRecordFilterText(state.filters.flowEmployee);
  const sourceTarget = flowRecordFilterText(state.filters.flowSourceTarget);
  const startDate = String(state.filters.flowStartDate || "");
  const endDate = String(state.filters.flowEndDate || "");

  return [...state.inventoryMovementLogs]
    .filter((log) => {
      const itemText = flowRecordFilterText([log.typeName, log.brandName, log.modelName, log.note].join(" "));
      const relatedEmployeeText = flowRecordFilterText([log.relatedEmployeeName, log.relatedEmployeeNo].join(" "));
      const sourceTargetText = flowRecordFilterText([log.sourceLabel, log.targetLabel].join(" "));
      const recordDate = flowRecordDate(log);
      return (
        (!search || itemText.includes(search)) &&
        (!type || String(log.typeName || "") === type) &&
        (!action || flowRecordActionLabel(log) === action) &&
        (!category || flowRecordCategory(log) === category) &&
        (!employee || relatedEmployeeText.includes(employee)) &&
        (!sourceTarget || sourceTargetText.includes(sourceTarget)) &&
        (!startDate || (recordDate && recordDate >= startDate)) &&
        (!endDate || (recordDate && recordDate <= endDate))
      );
    })
    .sort((left, right) => String(right.occurredAt || "").localeCompare(String(left.occurredAt || "")));
}

function upsertInventoryMovementLog(entry) {
  const item = {
    id: String(entry.id || createId("invlog")),
    direction: entry.direction === "decrease" ? "decrease" : "increase",
    typeName: entry.typeName || "",
    brandName: entry.brandName || "",
    modelName: entry.modelName || "",
    quantity: Math.max(1, Number(entry.quantity || 1)),
    sourceLabel: entry.sourceLabel || "",
    targetLabel: entry.targetLabel || "",
    note: entry.note || "",
    relatedEmployeeNo: entry.relatedEmployeeNo || "",
    relatedEmployeeName: entry.relatedEmployeeName || "",
    triggerAction: entry.triggerAction || "manual",
    occurredAt: entry.occurredAt || currentTimestampText(),
  };
  const index = state.inventoryMovementLogs.findIndex((log) => log.id === item.id);
  if (index >= 0) state.inventoryMovementLogs[index] = item;
  else state.inventoryMovementLogs.unshift(item);
  return item;
}

function employeeLogLabel(employeeNo = "", employeeName = "") {
  if (employeeName && employeeNo) return `${employeeName} (${employeeNo})`;
  return employeeName || employeeNo || "人员";
}

function modelLogNames(model) {
  if (!model) return { typeName: "", brandName: "", modelName: "" };
  const brand = getInventoryBrand(model.brandId);
  const type = getType(model.typeId);
  return {
    typeName: type?.name || "",
    brandName: brand?.name || "",
    modelName: model.name || "",
  };
}

function recordInventoryMovement(entry) {
  return upsertInventoryMovementLog({
    direction: entry.direction,
    typeName: entry.typeName,
    brandName: entry.brandName,
    modelName: entry.modelName,
    quantity: entry.quantity,
    sourceLabel: entry.sourceLabel,
    targetLabel: entry.targetLabel,
    note: entry.note || "",
    relatedEmployeeNo: entry.relatedEmployeeNo || "",
    relatedEmployeeName: entry.relatedEmployeeName || "",
    triggerAction: entry.triggerAction || "manual",
    occurredAt: entry.occurredAt || currentTimestampText(),
  });
}

function getInventoryFilterContext() {
  const search = inventoryText(state.filters.inventorySearch);
  const typeId = state.filters.inventoryType || "";
  const brandId = state.filters.inventoryBrand || "";
  const selectedBrand = brandId ? getInventoryBrand(brandId) : null;
  return { search, typeId, brandId, selectedBrand };
}

function inventoryTypeFilterOptions() {
  return [{ value: "", label: "全部类型" }].concat(
    state.nonAssetTypes.map((type) => ({ value: type.id, label: type.name })),
  );
}

function inventoryBrandFilterOptions(typeId = "") {
  const brands = typeId ? inventoryBrandsForType(typeId) : [...state.inventoryBrands].sort((a, b) => compareText(a.name, b.name));
  return [{ value: "", label: "全部品牌" }].concat(brands.map((brand) => ({ value: brand.id, label: brand.name })));
}

function buildInventoryTreeNodes() {
  const { search, typeId, brandId, selectedBrand } = getInventoryFilterContext();
  const warehouseId = ensureInventoryWarehouseView();

  return state.nonAssetTypes
    .filter((type) => {
      if (typeId && type.id !== typeId) return false;
      if (selectedBrand && selectedBrand.typeId !== type.id) return false;
      return true;
    })
    .map((type) => {
      const brands = inventoryBrandsForType(type.id)
        .filter((brand) => {
          if (brandId && brand.id !== brandId) return false;
          return true;
        })
        .map((brand) => {
          const models = inventoryModelsForBrand(brand.id)
            .map((model) => inventoryModelForWarehouseView(model, warehouseId))
            .filter((model) => model.quantity > 0)
            .filter((model) => !search || inventoryModelSearchText(model).includes(search));
          const brandVisible =
            !search ||
            brandId === brand.id ||
            inventoryBrandSearchText(brand).includes(search) ||
            models.length > 0;
          return brandVisible ? { ...brand, models } : null;
        })
        .filter(Boolean);

      const typeVisible =
        !search ||
        inventoryTypeSearchText(type).includes(search) ||
        brands.length > 0 ||
        typeId === type.id ||
        (selectedBrand && selectedBrand.typeId === type.id);

      return typeVisible ? { type, brands } : null;
    })
    .filter(Boolean);
}

function inventoryFlatRows() {
  return buildInventoryTreeNodes().flatMap(({ type, brands }) =>
    brands.flatMap((brand) =>
      brand.models.map((model) => ({
        type,
        brand,
        model,
      })),
    ),
  );
}

function resolveInventorySelection(data) {
  const typeId = data.typeId || "";
  const selectedBrand = data.brandId && data.brandId !== "__custom__" ? getInventoryBrand(data.brandId) : null;
  const brand = String(selectedBrand?.name || data.brandCustom || data.brand || "").trim();
  const selectedModel = data.modelId && data.modelId !== "__custom__" ? getInventoryModel(data.modelId) : null;
  const model = String(selectedModel?.name || data.modelCustom || data.model || "").trim();
  const brandId = selectedBrand?.typeId === typeId ? selectedBrand.id : "";
  const modelId =
    selectedModel?.typeId === typeId && selectedModel?.brandId === brandId ? selectedModel.id : "";
  return { typeId, brand, model, inventoryBrandId: brandId, inventoryModelId: modelId };
}

function replaceSelectOptions(select, options, selectedValue = "__custom__") {
  if (!select) return;
  select.innerHTML = options
    .map(
      (option) =>
        `<option value="${escapeHtml(option.value)}" ${
          String(option.value) === String(selectedValue) ? "selected" : ""
        }>${escapeHtml(option.label)}</option>`,
    )
    .join("");
}

function updateNonAssetModuleSummary(form) {
  if (!form || form.dataset.form !== "nonasset") return;
  const summary = form.querySelector(".device-module-header strong");
  if (!summary) return;
  const type = getType(form.elements.typeId?.value || "");
  summary.textContent = type?.name || "非资产设备";
}

function updateDeviceInventorySelectors(form, changedField) {
  const typeId = form.elements.typeId?.value || "";
  const brandSelect = form.elements.brandId;
  const modelSelect = form.elements.modelId;
  const brandCustom = form.elements.brandCustom;
  const modelCustom = form.elements.modelCustom;
  if (changedField === "typeId") {
    replaceSelectOptions(
      brandSelect,
      [{ value: "__custom__", label: "自定义品牌" }].concat(
        inventoryBrandsForType(typeId).map((brand) => ({ value: brand.id, label: brand.name })),
      ),
    );
    replaceSelectOptions(modelSelect, [{ value: "__custom__", label: "自定义型号" }]);
    if (brandCustom) brandCustom.value = "";
    if (modelCustom) modelCustom.value = "";
    updateNonAssetModuleSummary(form);
    return;
  }
  const brandId = brandSelect?.value && brandSelect.value !== "__custom__" ? brandSelect.value : "";
  if (changedField === "brandId") {
    replaceSelectOptions(
      modelSelect,
      [{ value: "__custom__", label: "自定义型号" }].concat(
        inventoryModelsForBrand(brandId).map((model) => ({
          value: model.id,
          label: inventoryModelOptionLabel(model),
        })),
      ),
    );
    if (brandId && brandCustom) brandCustom.value = "";
    if (modelCustom) modelCustom.value = "";
  }
  if (changedField === "modelId" && modelSelect?.value !== "__custom__" && modelCustom) {
    modelCustom.value = "";
  }
}

function getNonAssetItems(employee) {
  if (Array.isArray(employee?.nonAssetItems)) return employee.nonAssetItems;
  return Object.entries(employee?.nonAssets || {}).reduce((items, [typeId, quantity]) => {
    const count = Math.max(0, Number(quantity || 0));
    if (count) {
      items.push({ id: createId("na"), typeId, brand: "", model: "", quantity: count });
    }
    return items;
  }, []);
}

function syncNonAssetAggregate(employee) {
  employee.nonAssets = getNonAssetItems(employee).reduce((aggregate, item) => {
    const quantity = Math.max(0, Number(item.quantity || 0));
    if (quantity) aggregate[item.typeId] = (aggregate[item.typeId] || 0) + quantity;
    return aggregate;
  }, {});
  return employee.nonAssets;
}

function normalizeMacAddress(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const colonFormat = /^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$/i.test(raw);
  const hyphenFormat = /^(?:[0-9a-f]{2}-){5}[0-9a-f]{2}$/i.test(raw);
  if (!colonFormat && !hyphenFormat) return raw;
  const compact = raw.replaceAll(":", "").replaceAll("-", "").toUpperCase();
  return compact.match(/../g).join("-");
}

function isValidMacAddress(value) {
  return !value || /^(?:[0-9A-F]{2}-){5}[0-9A-F]{2}$/.test(String(value).trim());
}

function normalizeComputerRecord(computer, validEmployeeIds = null) {
  const normalized = {
    id: computer.id || createId("pc"),
    deviceName: computer.deviceName || "",
    orgId: computer.orgId || "",
    deviceType: computer.deviceType || "laptop",
    brand: computer.brand || "",
    model: computer.model || "",
    inventoryModelId: computer.inventoryModelId ? String(computer.inventoryModelId) : "",
    inventoryStockAdjusted: Boolean(computer.inventoryStockAdjusted),
    registrationMode:
      computer.registrationMode || (computer.inventoryStockAdjusted ? "warehouse" : "custom"),
    cpu: computer.cpu || "",
    memory: computer.memory || "",
    storage: computer.storage || "",
    gpu: computer.gpu || "",
    fixedAssetCode: computer.fixedAssetCode || "",
    purchaseDate: computer.purchaseDate || "",
    registeredDate: computer.registeredDate || "",
    snSt: computer.snSt || "",
    wifiMac: normalizeMacAddress(computer.wifiMac),
    ethernetMac: normalizeMacAddress(computer.ethernetMac),
    location: computer.location || "",
    department: computer.department || "",
    status: computer.status || "idle",
    userId: computer.userId ? String(computer.userId) : null,
    remarks: computer.remarks || "",
  };

  if (validEmployeeIds instanceof Set && normalized.userId && !validEmployeeIds.has(normalized.userId)) {
    normalized.userId = null;
  }

  if (["repair", "retired", "lost"].includes(normalized.status)) {
    normalized.userId = null;
  }

  if (normalized.userId) {
    normalized.status = "in_use";
  } else if (normalized.status === "in_use") {
    normalized.status = "idle";
  }

  return normalized;
}

function normalizeComputersAgainstEmployees() {
  const employeeIds = new Set(state.employees.map((employee) => employee.id));
  state.computers = state.computers.map((computer) => normalizeComputerRecord(computer, employeeIds));
}

function getCurrentUser(computer) {
  return computer.userId ? getEmployee(computer.userId) : null;
}

function orgName(id) {
  return getOrg(id)?.name || "未分配组织";
}

function orgPathName(id) {
  const path = [];
  let current = getOrg(id);
  const visited = new Set();
  while (current && !visited.has(current.id)) {
    visited.add(current.id);
    path.unshift(current.name);
    current = current.parentId ? getOrg(current.parentId) : null;
  }
  return path.length ? path.join(" / ") : "未分配组织";
}

function statusPill(status) {
  const safeStatus = status || "idle";
  return `<span class="status-pill status-${escapeHtml(safeStatus)}">${escapeHtml(
    statusLabels[safeStatus] || safeStatus,
  )}</span>`;
}

function formatDate(value) {
  if (!value) return "—";
  return value.replaceAll("-", ".");
}

function formatDateTime(value) {
  if (!value) return "—";
  return String(value).replace("T", " ").slice(0, 19);
}

function deviceTypeLabel(value) {
  return deviceTypeLabels[value] || value || "—";
}

function computerConfigSummary(computer) {
  return [
    ["CPU", computer.cpu],
    ["内存", computer.memory],
    ["存储", computer.storage],
    ["显卡", computer.gpu],
  ]
    .filter(([, value]) => String(value || "").trim())
    .map(([label, value]) => `${label}: ${value}`)
    .join(" / ");
}

function orgSortKey(org) {
  return `${String(org.sortOrder).padStart(6, "0")}-${org.code}-${org.name}`;
}

function isRootOrg(org) {
  return !org.parentId || !getOrg(org.parentId);
}

function getOrgChildren(parentId) {
  return [...state.orgs]
    .filter((org) => (org.parentId || "") === (parentId || ""))
    .sort((a, b) => orgSortKey(a).localeCompare(orgSortKey(b), "en"));
}

function getRootOrgs() {
  return [...state.orgs]
    .filter((org) => isRootOrg(org))
    .sort((a, b) => orgSortKey(a).localeCompare(orgSortKey(b), "en"));
}

function getOrgDepth(orgId) {
  let depth = 0;
  let current = getOrg(orgId);
  const visited = new Set();
  while (current?.parentId && !visited.has(current.id)) {
    visited.add(current.id);
    depth += 1;
    current = getOrg(current.parentId);
  }
  return depth;
}

function getDescendantOrgIds(orgId, visited = new Set()) {
  const descendants = [];
  if (visited.has(orgId)) return descendants;
  visited.add(orgId);
  getOrgChildren(orgId).forEach((child) => {
    descendants.push(child.id);
    descendants.push(...getDescendantOrgIds(child.id, visited));
  });
  return descendants;
}

function getSubtreeOrgIds(orgId) {
  return [orgId].concat(getDescendantOrgIds(orgId));
}

function sortEmployees(employees) {
  return [...employees].sort((a, b) => {
    const noCompare = compareText(a.employeeNo, b.employeeNo);
    return noCompare || compareText(a.name, b.name);
  });
}

function getFilteredComputers() {
  const search = (state.filters.computers || "").trim().toLowerCase();
  const statusFilter = state.filters.computerStatus || "";

  return state.computers.filter((computer) => {
    const user = getCurrentUser(computer);
    const searchText = [
      computer.deviceName,
      computer.brand,
      computer.model,
      computer.cpu,
      computer.memory,
      computer.storage,
      computer.gpu,
      computer.fixedAssetCode,
      computer.snSt,
      orgPathName(computer.orgId),
      user?.name,
    ]
      .join(" ")
      .toLowerCase();
    return (!search || searchText.includes(search)) && (!statusFilter || computer.status === statusFilter);
  });
}

function getFilteredEmployees() {
  const search = (state.filters.employees || "").trim().toLowerCase();
  const assetSearch = (state.filters.employeeAssetSearch || "").trim().toLowerCase();
  const statusFilter = state.filters.employeeStatus || "";
  const orgFilter = state.filters.employeeOrg || "";
  const deviceFilter = state.filters.employeeDevice || "";
  const orgScope =
    orgFilter && orgFilter !== "__unassigned__" ? new Set(getSubtreeOrgIds(orgFilter)) : null;

  return sortEmployees(
    state.employees.filter((employee) => {
      const assignedDevices = employeeDevices(employee);
      const searchText = [
        employee.employeeNo,
        employee.name,
        employee.department,
        employee.position,
        orgPathName(employee.orgId),
      ]
        .join(" ")
        .toLowerCase();
      const deviceSearchText = assignedDevices
        .flatMap((device) => [device.label, device.detail, device.brand, device.model])
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      const matchesOrg =
        !orgFilter ||
        (orgFilter === "__unassigned__"
          ? !employee.orgId || !getOrg(employee.orgId)
          : orgScope?.has(employee.orgId || ""));
      const hasDevices = assignedDevices.length > 0;
      const matchesDevice =
        !deviceFilter ||
        (deviceFilter === "assigned" && hasDevices) ||
        (deviceFilter === "unassigned" && !hasDevices);
      return (
        (!search || searchText.includes(search)) &&
        (!assetSearch || deviceSearchText.includes(assetSearch)) &&
        (!statusFilter || employee.status === statusFilter) &&
        matchesOrg &&
        matchesDevice
      );
    }),
  );
}

function getOrgEmployeeCount(orgId, includeDescendants = false) {
  const scope = new Set(includeDescendants ? getSubtreeOrgIds(orgId) : [orgId]);
  return state.employees.filter(
    (employee) =>
      scope.has(employee.orgId || "") &&
      (state.includeSharedInOrgCount || employee.status !== "shared"),
  ).length;
}

function getOrgComputerCount(orgId, includeDescendants = false) {
  const scope = new Set(includeDescendants ? getSubtreeOrgIds(orgId) : [orgId]);
  return state.computers.filter((computer) => scope.has(computer.orgId || "")).length;
}

function getOrgSummary(orgId) {
  return {
    employees: getOrgEmployeeCount(orgId, true),
    computers: getOrgComputerCount(orgId, true),
    children: getDescendantOrgIds(orgId).length,
  };
}

function isOrgExpanded(orgId) {
  return state.expandedOrgIds.includes(orgId);
}

function setOrgExpanded(orgId, expanded) {
  const current = new Set(state.expandedOrgIds);
  if (expanded) current.add(orgId);
  else current.delete(orgId);
  state.expandedOrgIds = [...current];
  persistState(false);
}

function ensureOrgExpanded(orgId) {
  if (!orgId) return;
  const ancestors = [];
  let current = getOrg(orgId);
  const visited = new Set();
  while (current && !visited.has(current.id)) {
    visited.add(current.id);
    ancestors.push(current.id);
    current = current.parentId ? getOrg(current.parentId) : null;
  }
  state.expandedOrgIds = [...new Set(state.expandedOrgIds.concat(ancestors))];
}

function isInventoryTypeExpanded(typeId) {
  return state.expandedInventoryTypeIds.includes(typeId);
}

function setInventoryTypeExpanded(typeId, expanded) {
  const current = new Set(state.expandedInventoryTypeIds);
  if (expanded) current.add(typeId);
  else current.delete(typeId);
  state.expandedInventoryTypeIds = [...current];
  persistState(false);
}

function isInventoryBrandExpanded(brandId) {
  return state.expandedInventoryBrandIds.includes(brandId);
}

function setInventoryBrandExpanded(brandId, expanded) {
  const current = new Set(state.expandedInventoryBrandIds);
  if (expanded) current.add(brandId);
  else current.delete(brandId);
  state.expandedInventoryBrandIds = [...current];
  persistState(false);
}

function ensureInventoryExpanded(typeId, brandId = "") {
  if (typeId) {
    state.expandedInventoryTypeIds = [...new Set(state.expandedInventoryTypeIds.concat(typeId))];
  }
  if (brandId) {
    state.expandedInventoryBrandIds = [...new Set(state.expandedInventoryBrandIds.concat(brandId))];
  }
}

function expandVisibleInventoryNodes() {
  const nodes = buildInventoryTreeNodes();
  state.expandedInventoryTypeIds = [
    ...new Set(state.expandedInventoryTypeIds.concat(nodes.map(({ type }) => type.id))),
  ];
  state.expandedInventoryBrandIds = [
    ...new Set(state.expandedInventoryBrandIds.concat(nodes.flatMap(({ brands }) => brands.map((brand) => brand.id)))),
  ];
  persistState(false);
}

function getOrgSelectOptions(options = {}) {
  const {
    includeBlank = false,
    blankLabel = "未分配组织",
    excludeIds = [],
  } = options;
  const excluded = new Set(excludeIds);
  const rows = [];

  function visit(org, depth) {
    if (!excluded.has(org.id)) {
      rows.push({
        value: org.id,
        label: `${"　".repeat(depth)}${org.name} · ${org.code}`,
      });
      getOrgChildren(org.id).forEach((child) => visit(child, depth + 1));
    }
  }

  getRootOrgs().forEach((org) => visit(org, 0));

  if (includeBlank) {
    rows.unshift({ value: "", label: blankLabel });
  }
  return rows;
}

function employeeDevices(employee) {
  const devices = [];

  state.computers
    .filter((computer) => computer.userId === employee.id)
    .forEach((computer) => {
      devices.push({
        id: computer.id,
        label: computer.deviceName,
        detail: [computer.brand, computer.model].filter(Boolean).join(" ") || deviceTypeLabel(computer.deviceType),
        category: "computer",
      });
    });

  (employee.monitors || []).forEach((monitor) => {
    devices.push({
      label: "显示屏",
      detail: [monitor.brand, monitor.model].filter(Boolean).join(" ") || "未填写品牌型号",
      quantity: 1,
      category: "monitor",
      typeId: monitor.typeId || defaultMonitorTypeId(),
      brand: monitor.brand || "",
      model: monitor.model || "",
      brandId: monitor.inventoryBrandId || "",
      modelId: monitor.inventoryModelId || "",
      stockAdjusted: Boolean(monitor.stockAdjusted),
    });
  });

  getNonAssetItems(employee).forEach((item) => {
    const quantity = Math.max(0, Number(item.quantity || 0));
    const type = getType(item.typeId);
    if (type && quantity > 0) {
      devices.push({
        label: type.name,
        detail: `${[item.brand, item.model].filter(Boolean).join(" ") || "未填写品牌型号"} · ${quantity}${type.unit || "件"}`,
        quantity,
        category: "non-asset",
        typeId: item.typeId,
        brand: item.brand || "",
        model: item.model || "",
        brandId: item.inventoryBrandId || "",
        modelId: item.inventoryModelId || "",
      });
    }
  });

  return devices;
}

function employeeDeviceSnapshot(employee) {
  const snapshot = [];

  state.computers
    .filter((computer) => computer.userId === employee.id)
    .forEach((computer) => {
      snapshot.push({
        category: "computer",
        label: computer.deviceName,
        detail: [computer.brand, computer.model].filter(Boolean).join(" ") || deviceTypeLabel(computer.deviceType),
        quantity: 1,
      });
    });

  (employee.monitors || []).forEach((monitor) => {
    snapshot.push({
      category: "monitor",
      typeId: monitor.typeId || defaultMonitorTypeId(),
      typeName: getType(monitor.typeId || defaultMonitorTypeId())?.name || "\u663e\u793a\u5c4f",
      brandId: monitor.inventoryBrandId || "",
      modelId: monitor.inventoryModelId || "",
      brand: monitor.brand || "",
      model: monitor.model || "",
      label: "显示屏",
      detail: [monitor.brand, monitor.model].filter(Boolean).join(" ") || "未填写品牌型号",
      quantity: 1,
    });
  });

  getNonAssetItems(employee).forEach((item) => {
    const quantity = Math.max(0, Number(item.quantity || 0));
    const type = getType(item.typeId);
    if (type && quantity > 0) {
      snapshot.push({
        category: "non-asset",
        label: type.name,
        detail: [item.brand, item.model].filter(Boolean).join(" ") || "未填写品牌型号",
        quantity,
        typeId: item.typeId,
        typeName: type.name,
        brandId: item.inventoryBrandId || "",
        modelId: item.inventoryModelId || "",
        brand: item.brand || "",
        model: item.model || "",
      });
    }
  });

  return snapshot;
}

function buildArchivedEmployeeRecord(employee, archiveInput = {}) {
  const existing = getLeftEmployeeBySource(employee.id, employee.employeeNo);
  return {
    id: existing?.id || createId("left"),
    sourceEmployeeId: employee.id || "",
    employeeNo: employee.employeeNo || "",
    name: employee.name || "",
    orgId: employee.orgId || "",
    orgPath: orgPathName(employee.orgId),
    department: employee.department || "",
    position: employee.position || "",
    email: employee.email || "",
    mobile: employee.mobile || "",
    leaveDate: archiveInput.leaveDate || existing?.leaveDate || currentDateText(),
    leaveInfo: archiveInput.leaveInfo || existing?.leaveInfo || "",
    leaveRemark: archiveInput.leaveRemark || existing?.leaveRemark || "",
    archivedAt: archiveInput.archivedAt || existing?.archivedAt || currentTimestampText(),
    devices: employeeDeviceSnapshot(employee),
  };
}

function employeeRecoveryDevices(employee) {
  const devices = [];
  state.computers
    .filter((computer) => computer.userId === employee.id)
    .forEach((computer) => {
      devices.push({
        key: `computer:${computer.id}`,
        id: computer.id,
        sourceId: computer.id,
        itemType: "computer",
        category: "computer",
        label: computer.deviceName,
        detail: [computer.brand, computer.model].filter(Boolean).join(" ") || computer.deviceType,
        quantity: 1,
        status: computer.status || "in_use",
      });
    });
  (employee.monitors || []).forEach((monitor) => {
    devices.push({
      key: `monitor:${monitor.id}`,
      id: monitor.id,
      sourceId: monitor.id,
      itemType: "monitor",
      category: "monitor",
      label: "\u663e\u793a\u5c4f",
      detail: [monitor.brand, monitor.model].filter(Boolean).join(" ") || "\u672a\u586b\u5199\u54c1\u724c\u578b\u53f7",
      quantity: 1,
      typeId: monitor.typeId || defaultMonitorTypeId(),
      typeName: getType(monitor.typeId || defaultMonitorTypeId())?.name || "\u663e\u793a\u5c4f",
      brand: monitor.brand || "",
      model: monitor.model || "",
      brandId: monitor.inventoryBrandId || "",
      modelId: monitor.inventoryModelId || "",
      stockAdjusted: Boolean(monitor.stockAdjusted),
    });
  });
  getNonAssetItems(employee).forEach((item) => {
    const type = getType(item.typeId);
    if (!type || Number(item.quantity || 0) <= 0) return;
    devices.push({
      key: `nonasset:${item.id}`,
      id: item.id,
      sourceId: item.id,
      itemType: "non_asset",
      category: "non-asset",
      label: type.name,
      detail: [item.brand, item.model].filter(Boolean).join(" ") || "\u672a\u586b\u5199\u54c1\u724c\u578b\u53f7",
      quantity: Math.max(1, Number(item.quantity || 1)),
      typeId: item.typeId,
      typeName: type.name,
      brand: item.brand || "",
      model: item.model || "",
      brandId: item.inventoryBrandId || "",
      modelId: item.inventoryModelId || "",
      stockAdjusted: Boolean(item.stockAdjusted),
    });
  });
  return devices;
}

function ensureInventoryPathForReturn(device) {
  const selectedModel = device.modelId ? getInventoryModel(device.modelId) : null;
  if (selectedModel) return selectedModel;

  let type = getType(device.typeId);
  if (!type) {
    const typeName = device.typeName || device.label || "Other";
    let sequence = 1;
    let code = `inventory_${Date.now().toString(36)}`;
    while (state.nonAssetTypes.some((item) => item.code === code)) {
      sequence += 1;
      code = `inventory_${Date.now().toString(36)}_${sequence}`;
    }
    type = { id: createId("type"), code, name: typeName, unit: "件" };
    state.nonAssetTypes.push(type);
  }

  const brandName = String(device.brand || "未指定").trim() || "未指定";
  let brand =
    (device.brandId && getInventoryBrand(device.brandId)) ||
    state.inventoryBrands.find((item) => item.typeId === type.id && item.name === brandName);
  if (!brand) {
    brand = { id: createId("brand"), typeId: type.id, name: brandName, sortOrder: 1000 };
    state.inventoryBrands.push(brand);
  }

  const modelName = String(device.model || "未指定").trim() || "未指定";
  let model =
    (device.modelId && getInventoryModel(device.modelId)) ||
    state.inventoryModels.find((item) => item.typeId === type.id && item.brandId === brand.id && item.name === modelName);
  if (!model) {
    model = {
      id: createId("model"),
      typeId: type.id,
      brandId: brand.id,
      name: modelName,
      batchKey: "",
      quantity: 0,
      sortOrder: 1000,
    };
    state.inventoryModels.push(model);
  }
  return model;
}

function returnDeviceToInventory(device, context = {}) {
  if (!["monitor", "non-asset"].includes(device.category)) return;
  const model = ensureInventoryPathForReturn(device);
  const quantity = Math.max(1, Number(device.quantity || 1));
  model.quantity = Math.max(0, Number(model.quantity || 0)) + quantity;
  const names = modelLogNames(model);
  recordInventoryMovement({
    direction: "increase",
    ...names,
    quantity,
    sourceLabel: context.sourceLabel || employeeLogLabel(context.relatedEmployeeNo, context.relatedEmployeeName) || "外部回收",
    targetLabel: context.targetLabel || "IT物资库存",
    note: context.note || "",
    relatedEmployeeNo: context.relatedEmployeeNo || "",
    relatedEmployeeName: context.relatedEmployeeName || "",
    triggerAction: context.triggerAction || "return",
  });
}

function recoveryDeviceFromSelection(employee, kind, id) {
  if (!employee || !id) return null;
  const selectedId = String(id);
  if (kind === "monitor") {
    const monitor = (employee.monitors || []).find((item) => sameRecordId(item.id, selectedId));
    if (!monitor) return null;
    const typeId = monitor.typeId || defaultMonitorTypeId();
    return {
      key: `monitor:${monitor.id}`,
      category: "monitor",
      label: getType(typeId)?.name || "显示屏",
      detail: [monitor.brand, monitor.model].filter(Boolean).join(" ") || "未填写品牌型号",
      quantity: 1,
      typeId,
      typeName: getType(typeId)?.name || "显示屏",
      brand: monitor.brand || "",
      model: monitor.model || "",
      brandId: monitor.inventoryBrandId || "",
      modelId: monitor.inventoryModelId || "",
      stockAdjusted: Boolean(monitor.stockAdjusted),
      sourceId: monitor.id,
    };
  }
  if (kind === "nonasset") {
    const item = getNonAssetItems(employee).find((entry) => sameRecordId(entry.id, selectedId));
    if (!item) return null;
    return {
      key: `nonasset:${item.id}`,
      category: "non-asset",
      label: getType(item.typeId)?.name || "非资产设备",
      detail: [item.brand, item.model].filter(Boolean).join(" ") || "未填写品牌型号",
      quantity: Math.max(1, Number(item.quantity || 1)),
      typeId: item.typeId,
      typeName: getType(item.typeId)?.name || "非资产设备",
      brand: item.brand || "",
      model: item.model || "",
      brandId: item.inventoryBrandId || "",
      modelId: item.inventoryModelId || "",
      stockAdjusted: Boolean(item.stockAdjusted),
      sourceId: item.id,
    };
  }
  return null;
}

function openDeviceRecoveryConfirm(employeeId, kind, selectedDevices = null, selectedWarehouseId = "") {
  const employee = getEmployee(employeeId);
  if (!employee) return;
  const devices = Array.isArray(selectedDevices)
    ? selectedDevices.filter(Boolean)
    : [...document.querySelectorAll("[data-recovery-select]:checked")]
        .filter(
          (input) =>
            String(input.dataset.employeeId || "") === String(employeeId || "") &&
            input.dataset.recoveryKind === kind &&
            input.dataset.id,
        )
        .map((input) => input.dataset.id)
        .map((id) => recoveryDeviceFromSelection(employee, kind, id))
        .filter(Boolean);
  if (!devices.length) {
    showToast(kind === "monitor" ? "请先勾选要回收的显示屏" : "请先勾选要回收的非资产设备", true);
    return;
  }
  const defaultWarehouseId = selectedWarehouseId || defaultWarehouseIdForCurrentUser();
  pendingDeviceRecovery = { employeeId, kind, devices, warehouseId: defaultWarehouseId };
  openModal(
    `${modalHeader("确认回收物资", `${employee.name} · ${employee.employeeNo}`)}
      <form class="confirm-panel" data-form="device-recovery">
        <p>请选择回收目标仓库。有来源仓库的物资也可以回收到其他仓库。</p>
        <div class="recovery-list">
          ${devices
            .map(
              (device) => `
                <div class="recovery-row">
                  <span><strong>${escapeHtml(device.label)}</strong><small>${escapeHtml(
                    `${device.detail}${device.quantity > 1 ? ` x${device.quantity}` : ""}`,
                  )}</small></span>
                </div>`,
            )
            .join("")}
        </div>
        ${warehouseSelectField(
          "回收目标仓库",
          "warehouseId",
          defaultWarehouseId,
          true,
          "请选择回收目标仓库",
          currentUserOrgId(),
        )}
        <div class="confirm-options">
          <button type="button" class="primary-button" data-action="confirm-device-recovery">确定回收</button>
          <button type="button" class="secondary-button" data-action="cancel-device-recovery">取消</button>
        </div>
      </form>`,
    false,
  );
}

async function confirmDeviceRecovery() {
  const pending = pendingDeviceRecovery;
  if (!pending) return;
  const form = document.querySelector('form[data-form="device-recovery"]');
  const warehouseId = String(form?.elements?.warehouseId?.value || pending.warehouseId || "").trim();
  if (!warehouseId) {
    showToast("请选择回收目标仓库。", true);
    return;
  }
  pendingDeviceRecovery = null;
  const employee = getEmployee(pending.employeeId);
  if (!employee) {
    closeModal();
    render();
    return;
  }
  let remainingDevices = [...pending.devices];
  const recoveryRecords = [];
  try {
    for (let index = 0; index < pending.devices.length; index += 1) {
      const device = pending.devices[index];
      const returned = await returnUsageAllocations(
        employee.id,
        pending.kind === "monitor" ? "monitor" : "non_asset",
        device.sourceId,
        device.category === "monitor" ? "Employee monitor recovery" : "Employee device recovery",
        warehouseId,
      );
      if (!returned) {
        throw new Error("This usage record has no tracked allocation. Reconcile it before returning.");
      }
      recoveryRecords.push(...(Array.isArray(returned) ? returned : []));
      remainingDevices = pending.devices.slice(index + 1);
    }
    await reloadDomainState();
  } catch (error) {
    if (!remainingDevices.length) {
      closeModal();
      openDeviceManager(employee.id);
      showToast("物资已回收，但页面刷新失败，请手动刷新后确认结果。", true);
      return;
    }
    showToast(`物资回收失败：${error.message}`, true);
    pendingDeviceRecovery = { ...pending, devices: remainingDevices, warehouseId };
    openDeviceRecoveryConfirm(pending.employeeId, pending.kind, remainingDevices, warehouseId);
    return;
  }
  closeModal();
  openDeviceManager(employee.id);
  showRecoveryResultModal({
    recoveryRecords,
    unrecoveredItems: [],
    subtitle: `${employee.name} · 设备清单，已回收 ${pending.devices.length} 项`,
  });
}

function offboardActionOptions(selected = "recover") {
  return Object.entries(offboardActionLabels)
    .map(
      ([value, label]) =>
        `<option value="${escapeHtml(value)}" ${selected === value ? "selected" : ""}>${escapeHtml(label)}</option>`,
    )
    .join("");
}

function offboardTargetEmployeeOptions(employeeId) {
  return [{ value: "", label: "请选择接收人员" }].concat(
    sortEmployees(state.employees)
      .filter((employee) => employee.id !== employeeId && ["active", "shared"].includes(employee.status))
      .map((employee) => ({
        value: employee.id,
        label: `${employee.name} · ${employee.employeeNo} · ${orgName(employee.orgId)}`,
      })),
  );
}

function offboardItemTypeLabel(item) {
  if (item.itemType === "computer" || item.category === "computer") return "办公终端";
  if (item.itemType === "monitor" || item.category === "monitor") return "显示屏";
  return "非资产物资";
}

function renderEmployeeOffboardItemRow(employee, item) {
  const rowKey = `${item.itemType || item.category}:${item.sourceId || item.id}`;
  const safeRowKey = rowKey.replace(/[^A-Za-z0-9_-]/g, "-");
  const actionId = createControlId(`offboard-action-${safeRowKey}`);
  const targetId = createControlId(`offboard-target-${safeRowKey}`);
  const recoveryWarehouseId = createControlId(`offboard-recovery-warehouse-${safeRowKey}`);
  const noteId = createControlId(`offboard-note-${safeRowKey}`);
  return `
    <article class="offboard-item-row" data-offboard-item-row data-item-type="${escapeHtml(
      item.itemType || item.category,
    )}" data-item-id="${escapeHtml(item.sourceId || item.id || "")}" data-stock-adjusted="${
      item.stockAdjusted ? "1" : "0"
    }">
      <div class="offboard-item-main">
        <span class="status-pill status-idle">${escapeHtml(offboardItemTypeLabel(item))}</span>
        <div>
          <strong>${escapeHtml(item.label || "未命名项目")}</strong>
          <small>${escapeHtml(`${item.detail || "未填写明细"}${item.quantity > 1 ? ` x${item.quantity}` : ""}`)}</small>
        </div>
      </div>
      <div class="form-grid three offboard-item-controls">
        <div class="form-field">
          <label for="${actionId}">处理方式 *</label>
          <select id="${actionId}" data-offboard-action required>${offboardActionOptions("recover")}</select>
        </div>
        <div class="form-field" data-offboard-target-field>
          <label for="${targetId}">接收人员</label>
          <select id="${targetId}" data-offboard-target>
            ${offboardTargetEmployeeOptions(employee.id)
              .map((option) => `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`)
              .join("")}
          </select>
        </div>
        <div class="form-field" data-offboard-recovery-warehouse-field hidden>
          <label for="${recoveryWarehouseId}">回收目标仓库 *</label>
          <select id="${recoveryWarehouseId}" name="recoveryWarehouseId" data-offboard-recovery-warehouse>
            ${warehouseOptions("", "请选择回收目标仓库", currentUserOrgId(), false)
              .map(
                (option) =>
                  `<option value="${escapeHtml(option.value)}" ${
                    option.selected ? "selected" : ""
                  }>${escapeHtml(option.label)}</option>`,
              )
              .join("")}
          </select>
        </div>
        <div class="form-field">
          <label for="${noteId}">处理说明</label>
          <input id="${noteId}" data-offboard-note maxlength="500" placeholder="异常待处理时必填" />
        </div>
      </div>
    </article>`;
}

function updateOffboardItemRow(row) {
  if (!row) return;
  const action = row.querySelector("[data-offboard-action]")?.value || "recover";
  const targetField = row.querySelector("[data-offboard-target-field]");
  const target = row.querySelector("[data-offboard-target]");
  const recoveryWarehouseField = row.querySelector("[data-offboard-recovery-warehouse-field]");
  const recoveryWarehouse = row.querySelector("[data-offboard-recovery-warehouse]");
  const note = row.querySelector("[data-offboard-note]");
  if (targetField) targetField.hidden = action !== "transfer";
  if (target) {
    target.disabled = action !== "transfer";
    target.required = action === "transfer";
    if (action !== "transfer") target.value = "";
  }
  const requiresRecoveryWarehouse = action === "recover";
  if (recoveryWarehouseField) recoveryWarehouseField.hidden = !requiresRecoveryWarehouse;
  if (recoveryWarehouse) {
    recoveryWarehouse.disabled = !requiresRecoveryWarehouse;
    recoveryWarehouse.required = requiresRecoveryWarehouse;
    if (!requiresRecoveryWarehouse) recoveryWarehouse.value = "";
  }
  if (note) {
    note.required = action === "exception";
    note.placeholder = action === "exception" ? "请填写异常原因、后续责任人或处理计划" : "可填写交接或回收说明";
  }
}

function refreshOffboardItemRows(root = document) {
  root.querySelectorAll("[data-offboard-item-row]").forEach((row) => updateOffboardItemRow(row));
}

function recoveryRecordLabel(record) {
  const name = [record.brandName, record.modelName].filter(Boolean).join(" ") || record.typeName || "";
  return [record.typeName, name].filter(Boolean).join(" · ") || "物资";
}

function showRecoveryResultModal(result = {}) {
  const records = Array.isArray(result.recoveryRecords) ? result.recoveryRecords : [];
  const unrecovered = Array.isArray(result.unrecoveredItems) ? result.unrecoveredItems : [];
  const subtitle = String(result.subtitle || "").trim();
  openModal(
    `${modalHeader(
      "回收完成",
      subtitle || `已回收入库 ${records.length} 项，未回收 ${unrecovered.length} 项`,
    )}
      <section class="modal-section">
        <div class="modal-section-title"><div><h3>已回收并生成库存记录</h3><span>共 ${records.length} 项</span></div></div>
        ${
          records.length
            ? `<div class="recovery-list">${records
                .map(
                  (record) => `
            <div class="recovery-row">
              <span><strong>${escapeHtml(recoveryRecordLabel(record))}</strong><small>${escapeHtml(
                `${Number(record.quantity || 0) || 1} 件 · 入库仓库：${record.warehouseName || "—"} · 流转记录 #${
                  record.movementLogId || "-"
                }`,
              )}</small></span>
            </div>`,
                )
                .join("")}</div>`
            : '<div class="empty-state">本次没有产生库存回收记录。</div>'
        }
      </section>
      ${
        unrecovered.length
          ? `<section class="modal-section">
        <div class="modal-section-title"><div><h3>未回收物资</h3><span>共 ${unrecovered.length} 项</span></div></div>
        <div class="recovery-list">${unrecovered
          .map(
            (item) => `
            <div class="recovery-row">
              <span><strong>${escapeHtml(
                [item.label, item.detail].filter(Boolean).join(" · ") || "未命名物资",
              )}</strong><small>${escapeHtml(
                `${Number(item.quantity || 0) || 1} 件 · ${item.reason || "未说明原因"}`,
              )}</small></span>
            </div>`,
          )
          .join("")}</div>
      </section>`
          : ""
      }
      <div class="modal-footer"><button type="button" class="primary-button" data-action="close-modal">知道了</button></div>`,
    true,
  );
}

function openEmployeeOffboardModal(employeeId) {
  const employee = getEmployee(employeeId);
  if (!employee) return;
  const devices = employeeRecoveryDevices(employee);
  const isSharedEmployee = employee.status === "shared";
  openModal(
    `${modalHeader(
      isSharedEmployee ? "删除公用人员" : "办理离职",
      isSharedEmployee
        ? `${employee.name || employee.employeeNo} · 公用人员（占位使用人），确认后删除且不进入离职人员档案`
        : `${employee.name || employee.employeeNo} · 逐项确认资产和物资处理结果`,
    )}
      <form data-form="employee-offboard" data-id="${escapeHtml(employee.id)}">
        <section class="modal-section">
          <div class="form-grid">
            ${inputField("人员编号", "employeeNo", employee.employeeNo || "", false, "", "text", "", 'readonly tabindex="-1"')}
            ${inputField("人员姓名", "employeeName", employee.name || "", false, "", "text", "", 'readonly tabindex="-1"')}
            ${inputField("所属组织", "orgPath", orgPathName(employee.orgId), false, "", "text", "", 'readonly tabindex="-1"')}
            ${inputField("部门", "department", employee.department || "", false, "", "text", "", 'readonly tabindex="-1"')}
            ${inputField("离职日期", "leaveDate", currentDateText(), true, "", "date")}
          </div>
          ${textareaField("离职原因", "leaveReason", "", true, "例如：合同到期、主动离职、岗位调整等", 3)}
          ${textareaField("备注", "leaveRemark", "", true, "记录交接范围、资料归档位置或其他说明", 3)}
        </section>
        <section class="modal-section">
          <div class="modal-section-title"><div><h3>资产与物资处理</h3><span>${devices.length} 项，必须逐项选择处理方式</span></div></div>
          <div class="offboard-item-list">
            ${
              devices.length
                ? devices.map((device) => renderEmployeeOffboardItemRow(employee, device)).join("")
                : '<div class="empty-state">当前人员名下没有待处理资产或物资。</div>'
            }
          </div>
        </section>
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">${
          isSharedEmployee ? "确认删除" : "确认办理离职"
        }</button></div>
      </form>`,
    true,
  );
  refreshOffboardItemRows(document.querySelector('form[data-form="employee-offboard"]') || document);
}

function openLeaveRecoveryModal(employee) {
  openEmployeeOffboardModal(employee?.id || "");
}

function confirmLeaveRecovery() {
  pendingLeaveRecovery = null;
  showToast("请通过“办理离职”表单提交受控离职流程。", true);
  return null;
}

function leftEmployeeDeviceActionText(device) {
  const actionLabel = device.actionLabel || offboardActionLabels[device.action] || "";
  if (!actionLabel) return "";
  const target = [device.targetEmployeeName, device.targetEmployeeNo ? `(${device.targetEmployeeNo})` : ""]
    .filter(Boolean)
    .join(" ");
  return [actionLabel, target ? `接收人：${target}` : "", device.handlingNote || ""].filter(Boolean).join(" · ");
}

async function handleEmployeeOffboardSubmit(form) {
  if (!hasPermission("employees", "update")) return showToast("当前账号没有办理离职权限。", true);
  if (form.dataset.submitting === "1") return;
  const employeeId = form.dataset.id || "";
  const data = Object.fromEntries(new FormData(form).entries());
  const leaveDate = String(data.leaveDate || "").trim();
  const leaveReason = String(data.leaveReason || "").trim();
  const leaveRemark = String(data.leaveRemark || "").trim();
  if (!leaveDate || !leaveReason || !leaveRemark) {
    return showToast("离职日期、离职原因和备注不能为空。", true);
  }
  const items = [...form.querySelectorAll("[data-offboard-item-row]")].map((row) => {
    const action = row.querySelector("[data-offboard-action]")?.value || "";
    return {
      itemType: row.dataset.itemType || "",
      itemId: row.dataset.itemId || "",
      action,
      stockAdjusted: row.dataset.stockAdjusted === "1",
      targetEmployeeId: action === "transfer" ? row.querySelector("[data-offboard-target]")?.value || "" : "",
      recoveryWarehouseId:
        action === "recover"
          ? row.querySelector("[data-offboard-recovery-warehouse]")?.value || ""
          : "",
      note: String(row.querySelector("[data-offboard-note]")?.value || "").trim(),
    };
  });
  if (items.some((item) => !item.action)) return showToast("每项资产或物资都必须选择处理方式。", true);
  if (items.some((item) => item.action === "transfer" && !item.targetEmployeeId)) {
    return showToast("转交他人时必须选择接收人员。", true);
  }
  if (items.some((item) => item.action === "exception" && !item.note)) {
    return showToast("异常待处理必须填写说明。", true);
  }
  if (items.some((item) => item.action === "recover" && !item.recoveryWarehouseId)) {
    return showToast("选择回收时必须指定回收目标仓库。", true);
  }
  form.dataset.submitting = "1";
  const submit = form.querySelector('button[type="submit"]');
  if (submit) submit.disabled = true;
  try {
    const result = await runCommand(
      `${API_EMPLOYEES_URL}/${encodeURIComponent(employeeId)}/offboard`,
      { leaveDate, leaveReason, leaveRemark, items },
      "employee-offboard",
    );
    closeModal();
    await reloadDomainState();
    if (settingsState.loaded && isAdminUser()) {
      const usersPayload = await requestJson(API_USERS_URL);
      settingsState.users = Array.isArray(usersPayload.users) ? usersPayload.users : [];
    }
    render();
    showRecoveryResultModal({
      recoveryRecords: result.recoveryRecords || [],
      unrecoveredItems: result.unrecoveredItems || [],
      subtitle: `离职办理完成，处理 ${result.processedItems || items.length} 项，解绑账号 ${
        result.unboundAccounts || 0
      } 个`,
    });
  } catch (error) {
    showToast(`办理离职失败：${error.message}`, true);
  } finally {
    form.dataset.submitting = "0";
    if (submit?.isConnected) submit.disabled = false;
  }
}

function leftEmployeeDeviceChips(devices) {
  if (!devices.length) return '<span class="secondary-text">暂无离职设备快照</span>';
  return `<div class="device-list">${devices
    .map(
      (device) =>
        `<span class="device-chip">${escapeHtml(device.label)}<small>${escapeHtml(
          [device.detail, device.quantity > 1 ? `x${device.quantity}` : "", leftEmployeeDeviceActionText(device)]
            .filter(Boolean)
            .join(" · "),
        )}</small></span>`,
    )
    .join("")}</div>`;
}

function deviceChips(employee) {
  const devices = employeeDevices(employee);
  if (!devices.length) return '<span class="secondary-text">暂无设备</span>';
  return `<div class="device-list">${devices
    .map(
      (device) =>
        device.category === "computer"
          ? `<button class="device-chip device-chip-button" data-action="open-computer" data-id="${escapeHtml(
              device.id,
            )}" title="查看办公终端信息">${escapeHtml(device.label)}<small>${escapeHtml(device.detail)}</small></button>`
          : `<span class="device-chip">${escapeHtml(device.label)}<small>${escapeHtml(device.detail)}</small></span>`,
    )
    .join("")}</div>`;
}

function render() {
  if (!authState.authenticated) {
    lastRenderedPage = "";
    renderAuthScreen();
    return;
  }
  if (!canViewPage(state.page)) {
    const fallback = [...document.querySelectorAll(".nav-item")]
      .map((item) => item.dataset.page)
      .find((page) => canViewPage(page));
    state.page = fallback || "dashboard";
  }
  const meta = pageMeta[state.page] || pageMeta.dashboard;
  const appName = settingsState.settings.app_name || "办公资产管理系统";
  document.title = `${meta.title} · ${appName}`;
  document.querySelector("#pageTitle").textContent = meta.title;
  ensureServiceNavigation();
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.hidden = !canViewPage(item.dataset.page || "");
    item.classList.toggle("is-active", item.dataset.page === state.page);
  });
  updateAuthenticatedChrome();
  const isPageTransition = lastRenderedPage !== state.page;
  lastRenderedPage = state.page;
  document.querySelector("#appContent").innerHTML = `<div${isPageTransition ? ' class="page-enter"' : ""}>${renderPage()}</div>`;
}

function renderIfCurrentPage(page) {
  if (state.page === page) render();
}

function isDeferredTextFilter(filterName) {
  return deferredTextFilterNames.has(String(filterName || ""));
}

function filterSearchDraftValue(filterName) {
  if (!Object.prototype.hasOwnProperty.call(filterSearchDrafts, filterName)) {
    filterSearchDrafts[filterName] = state.filters[filterName] || "";
  }
  return filterSearchDrafts[filterName] || "";
}

function syncFilterSearchDraftsFromFilters() {
  filterSearchDrafts = Object.fromEntries(
    [...deferredTextFilterNames].map((filterName) => [filterName, state.filters[filterName] || ""]),
  );
}

function applyDeferredTextFilters(filterNames) {
  filterNames.forEach((filterName) => {
    state.filters[filterName] = filterSearchDraftValue(filterName);
  });
  persistState(false);
}

function applyEmployeeSearchFilters() {
  applyDeferredTextFilters(["employees", "employeeAssetSearch"]);
  render();
}

function applyInventorySearchFilter() {
  applyDeferredTextFilters(["inventorySearch"]);
  if (state.filters.inventorySearch) expandVisibleInventoryNodes();
  render();
}

function applyFlowRecordFilters() {
  applyDeferredTextFilters(["flowSearch", "flowEmployee", "flowSourceTarget"]);
  render();
}

function applyAuditFilters() {
  applyDeferredTextFilters(["auditSearch", "auditEmployee"]);
  return refreshAuditLogs();
}

function renderPage() {
  if (state.page === "computers") return renderComputersPage();
  if (state.page === "employees") return renderEmployeesPage();
  if (state.page === "leftEmployees") return renderLeftEmployeesPage();
  if (state.page === "inventory") return renderInventoryPage();
  if (state.page === "flowControl") return renderFlowControlPage();
  if (state.page === "scrapRecords") return renderScrapRecordsPage();
  if (state.page === "inspection") return renderInspectionPage();
  if (state.page === "dictionary") return renderDictionaryPage();
  if (state.page === "audit") return renderAuditPage();
  if (state.page === "tickets") return renderTicketsPage();
  if (state.page === "serviceManagement") return renderServiceManagementPage();
  if (state.page === "formDesigner") return renderServiceFormDesignerPage();
  if (state.page === "governance") return renderGovernancePage();
  if (state.page === "settings") return renderSettingsPage();
  return renderDashboardPage();
}

function renderSettingsUserTable() {
  const users = Array.isArray(settingsState.users) ? settingsState.users : [];
  if (!users.length) {
    return '<div class="empty-state">暂无账号记录</div>';
  }
  return `<div class="table-wrap"><table class="settings-users-table">
    <thead><tr><th>账号</th><th>显示名称</th><th>绑定人员</th><th>角色</th><th>状态</th><th>最后登录</th><th>创建时间</th><th>操作</th></tr></thead>
    <tbody>${users
      .map((user) => {
        const isCurrent = String(user.id) === String(authState.user?.id);
        return `<tr>
          <td><strong>${escapeHtml(user.username)}</strong>${isCurrent ? '<span class="current-account-mark">当前账号</span>' : ""}</td>
          <td>${escapeHtml(user.displayName || "—")}</td>
          <td>${escapeHtml(user.employeeName ? `${user.employeeName} · ${user.department || user.orgName || ""}` : "未绑定")}</td>
          <td><span class="role-pill role-${escapeHtml(user.role)}">${escapeHtml(authRoleLabel(user.role))}</span></td>
          <td>${user.isActive ? '<span class="status-pill status-active">启用</span>' : '<span class="status-pill status-inactive">停用</span>'}</td>
          <td>${escapeHtml(formatDateTime(user.lastLoginAt || ""))}</td>
          <td>${escapeHtml(formatDateTime(user.createdAt || ""))}</td>
          <td><button class="text-button" data-action="open-settings-user" data-id="${escapeHtml(user.id)}">编辑</button></td>
        </tr>`;
      })
      .join("")}</tbody>
  </table></div>`;
}

const permissionActions = [
  ["view", "查看"],
  ["create", "新增"],
  ["update", "修改"],
  ["delete", "删除"],
  ["approve", "审批"],
  ["export", "导出"],
];

function permissionModuleLabel(module) {
  const code = String(typeof module === "string" ? module : module?.code || "").trim();
  const rawName = String(typeof module === "string" ? "" : module?.name || module?.displayName || "").trim();
  const mapped = permissionModuleLabels[code];
  if (mapped) return mapped;
  const normalized = normalizePermissionModuleName(rawName, code);
  return normalized || code;
}

function accessControlState() {
  if (!settingsState.accessControl) {
    settingsState.accessControl = {
      modules: [],
      roles: [],
      users: [],
      targetType: "role",
      targetId: "",
      permissions: [],
      loading: false,
    };
  }
  return settingsState.accessControl;
}

function permissionFlag(action) {
  return `can${action.charAt(0).toUpperCase()}${action.slice(1)}`;
}

function permissionMatrixRows() {
  const access = accessControlState();
  const byKey = new Map(
    (access.permissions || []).map((item) => [`${item.moduleCode}:${item.actionCode}`, item]),
  );
  return (access.modules || []).map((module) => {
    const scope =
      (access.permissions || []).find((item) => item.moduleCode === module.code)?.dataScope || "none";
    return {
      module,
      scope,
      actions: Object.fromEntries(
        permissionActions.map(([action]) => [
          action,
          Boolean(byKey.get(`${module.code}:${action}`)?.[permissionFlag(action)]),
        ]),
      ),
    };
  });
}

function renderPermissionGrid() {
  const access = accessControlState();
  if (!access.targetId) {
    return '<div class="empty-state">请选择角色或用户配置权限。</div>';
  }
  const rows = permissionMatrixRows();
  return `<form data-form="access-permissions" data-target-type="${escapeHtml(
    access.targetType,
  )}" data-target-id="${escapeHtml(access.targetId)}">
    <div class="table-wrap">
      <table class="settings-users-table permission-matrix">
        <thead><tr><th>模块</th>${permissionActions
          .map(([, label]) => `<th>${label}</th>`)
          .join("")}<th>数据范围</th></tr></thead>
        <tbody>${rows
          .map(
            (row) => `<tr>
              <td><strong title="${escapeHtml(row.module.code || "")}">${escapeHtml(
                permissionModuleLabel(row.module),
              )}</strong></td>
              ${permissionActions
                .map(
                  ([action, actionLabel]) =>
                    `<td><input type="checkbox" data-permission="${escapeHtml(
                      `${row.module.code}:${action}`,
                    )}" aria-label="${escapeHtml(`${permissionModuleLabel(row.module)}：${actionLabel}`)}" ${
                      row.actions[action] ? "checked" : ""
                    } /></td>`,
                )
                .join("")}
              <td><select data-permission-scope="${escapeHtml(row.module.code)}" aria-label="${escapeHtml(
                `${permissionModuleLabel(row.module)}：数据范围`,
              )}">
        ${["all", "organization", "own", "submitted", "assigned", "none"]
          .map(
            (scope) =>
                      `<option value="${scope}" ${scope === row.scope ? "selected" : ""}>${{
                        all: "全部数据",
                        organization: "所属部门及下属部门",
                        own: "本人数据",
                        submitted: "本人提交",
                        assigned: "本人负责",
                        none: "无数据",
                      }[scope]}</option>`,
                  )
                  .join("")}
              </select></td>
            </tr>`,
          )
          .join("")}</tbody>
      </table>
    </div>
    <div class="modal-footer settings-form-footer">
      <button class="primary-button" type="submit">保存权限</button>
    </div>
  </form>`;
}

function renderRoleCreationPermissionGrid() {
  const access = accessControlState();
  const modules = access.modules || [];
  if (!modules.length) {
    return '<div class="empty-state">正在读取权限模块...</div>';
  }
  return `<div class="table-wrap">
    <table class="settings-users-table permission-matrix role-create-permission-matrix">
      <thead><tr><th>模块</th>${permissionActions
        .map(([, label]) => `<th>${label}</th>`)
        .join("")}<th>数据范围</th></tr></thead>
      <tbody>${modules
        .map(
          (module) => `<tr>
            <td><strong title="${escapeHtml(module.code || "")}">${escapeHtml(
              permissionModuleLabel(module),
            )}</strong></td>
            ${permissionActions
              .map(
                ([action, actionLabel]) =>
                  `<td><input type="checkbox" data-role-permission="${escapeHtml(
                    `${module.code}:${action}`,
                  )}" aria-label="${escapeHtml(`${permissionModuleLabel(module)}：${actionLabel}`)}" /></td>`,
              )
              .join("")}
            <td><select data-role-permission-scope="${escapeHtml(module.code)}" aria-label="${escapeHtml(
              `${permissionModuleLabel(module)}：数据范围`,
            )}">
              ${[
                ["all", "全部数据"],
                ["organization", "所属部门及下属部门"],
                ["own", "本人数据"],
                ["submitted", "本人提交"],
                ["assigned", "本人负责"],
                ["none", "无数据"],
              ]
                .map(([value, label]) => `<option value="${value}" ${value === "none" ? "selected" : ""}>${label}</option>`)
                .join("")}
            </select></td>
          </tr>`,
        )
        .join("")}</tbody>
    </table>
  </div>`;
}

function renderAccessControlPanel() {
  if (!isAdminUser()) {
    return '<section class="data-panel settings-readonly-note"><strong>角色与权限</strong><span>只有超级管理员可以配置角色、模块权限和数据范围。</span></section>';
  }
  const access = accessControlState();
  const selectedRole = access.targetType === "role" ? String(access.targetId || "") : "";
  const selectedUser = access.targetType === "user" ? String(access.targetId || "") : "";
  return `<div class="settings-access-layout">
    <section class="data-panel settings-panel">
      <div class="section-heading settings-panel-heading">
        <div><h2>权限配置</h2><span>按角色或用户配置模块可见性、操作权限和数据范围。</span></div>
      </div>
      <div class="form-grid">
        <div class="form-field"><label for="access-target-type">配置对象</label><select id="access-target-type" data-access-target-type>
          <option value="role" ${access.targetType === "role" ? "selected" : ""}>角色</option>
          <option value="user" ${access.targetType === "user" ? "selected" : ""}>用户覆盖</option>
        </select></div>
        <div class="form-field"><label for="access-target-id">目标对象</label><select id="access-target-id" data-access-target-id>
          ${
            access.targetType === "role"
              ? (access.roles || [])
                  .map(
                    (role) =>
                      `<option value="${escapeHtml(role.id)}" ${
                        String(role.id) === selectedRole ? "selected" : ""
                      }>${escapeHtml(`${role.name || role.code} · ${role.categoryName || roleCategoryLabels[role.category] || "自定义角色"}`)}</option>`,
                  )
                  .join("")
              : (access.users || [])
                  .map(
                    (user) =>
                      `<option value="${escapeHtml(user.id)}" ${
                        String(user.id) === selectedUser ? "selected" : ""
                      }>${escapeHtml(user.displayName || user.username)}</option>`,
                  )
                  .join("")
          }
        </select></div>
      </div>
      ${renderPermissionGrid()}
    </section>
    <section class="data-panel settings-panel">
      <div class="section-heading settings-panel-heading">
        <div><h2>创建角色</h2><span>创建时确定角色类别、模块权限、操作权限和数据范围。</span></div>
      </div>
      <form data-form="role-create" class="settings-form">
        <div class="form-grid">
          ${inputField("角色编码", "code", "", true, "使用小写字母、数字、点、下划线或连字符")}
          ${inputField("角色名称", "name", "", true, "例如：部门资产管理员")}
          ${selectField("角色类别", "category", "custom", roleCategoryOptions, true)}
          <label class="form-field role-super-admin-toggle"><span>超级管理员</span><input type="checkbox" name="isSuperAdmin" /></label>
        </div>
        <div class="role-create-permissions">
          <div class="section-heading settings-panel-heading">
            <div><h3>初始权限</h3><span>未勾选的模块和操作默认不可用。</span></div>
          </div>
          ${renderRoleCreationPermissionGrid()}
        </div>
        <div class="modal-footer settings-form-footer"><button class="primary-button" type="submit">创建角色</button></div>
      </form>
    </section>
  </div>`;
}

function formatFileSize(value) {
  const bytes = Math.max(0, Number(value || 0));
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = bytes / 1024;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size >= 10 ? size.toFixed(1) : size.toFixed(2)} ${units[index]}`;
}

function databaseBackupTypeLabel(type) {
  return type === "scheduled" ? "定时备份" : "手动备份";
}

function databaseBackupStatusLabel(backup) {
  if (backup.status === "expired") return "已清理";
  if (backup.status === "failed") return "失败";
  return backup.fileAvailable ? "可下载" : "文件缺失";
}

function renderDatabaseBackupTable() {
  const backups = Array.isArray(settingsState.backups) ? settingsState.backups : [];
  if (!backups.length) {
    return '<div class="empty-state">尚无数据库备份记录</div>';
  }
  return `<div class="table-wrap"><table class="settings-backups-table">
    <thead><tr><th>创建时间</th><th>类型</th><th>备份文件</th><th>大小</th><th>创建人</th><th>状态</th><th>操作</th></tr></thead>
    <tbody>${backups
      .map(
        (backup) => `<tr>
          <td>${escapeHtml(formatDateTime(backup.createdAt || ""))}</td>
          <td>${escapeHtml(databaseBackupTypeLabel(backup.backupType))}</td>
          <td><strong>${escapeHtml(backup.fileName || "—")}</strong></td>
          <td>${escapeHtml(formatFileSize(backup.fileSize))}</td>
          <td>${escapeHtml(backup.requestedByName || "系统")}</td>
          <td><span class="backup-status backup-status-${escapeHtml(backup.status || "completed")}">${
            escapeHtml(databaseBackupStatusLabel(backup))
          }</span></td>
          <td><button class="text-button" data-action="open-database-backup-download" data-id="${escapeHtml(
            backup.id,
          )}" ${backup.fileAvailable ? "" : "disabled"}>下载</button></td>
        </tr>`,
      )
      .join("")}</tbody>
  </table></div>`;
}

function updateStatusLabel(status) {
  if (status === "update_available") return "发现可用版本";
  if (status === "queued") return "手动更新已排队";
  if (status === "running") return "更新正在执行";
  if (status === "up_to_date") return "当前已是最新版本";
  if (status === "no_releases") return "暂无已发布版本";
  if (status === "no_release_available") return "暂无更高发布版本";
  return "尚未检查";
}

function updateStatusDetail(status) {
  if (status === "update_available") return "请选择版本号更高的已发布版本，再手动执行更新。推送不会自动部署。";
  if (status === "queued") return "服务器将按所选发布版本构建应用，完成后请刷新页面。";
  if (status === "running") return "应用服务可能会短暂重启，请稍后刷新页面。";
  if (status === "up_to_date") return "当前部署版本与所选项目地址一致。";
  if (status === "no_releases") return "所选项目地址中还没有 vMAJOR.MINOR.PATCH 格式的已发布版本标签。";
  if (status === "no_release_available") return "当前部署版本没有更高的已发布版本，不能直接选择普通提交更新。";
  return "点击按钮读取项目地址中已发布的语义化版本标签。";
}

function updateReleaseChannelLabel(channel) {
  return UPDATE_RELEASE_CHANNELS[channel] || UPDATE_RELEASE_CHANNELS[DEFAULT_UPDATE_RELEASE_CHANNEL];
}

function currentUpdateSource() {
  const selected = String(
    document.querySelector("[data-update-source]")?.value || settingsState.updateSource || "github",
  ).trim();
  return selected === "custom" ? "custom" : "github";
}

function currentUpdateRepositoryUrl() {
  if (currentUpdateSource() === "github") return GITHUB_UPDATE_REPOSITORY_URL;
  return (
    document.querySelector("[data-update-repository-url]")?.value ||
    settingsState.updateCustomRepositoryUrl ||
    settingsState.updateRepositoryUrl ||
    ""
  ).trim();
}

function updateSourceLabel(source) {
  return UPDATE_SOURCES[source] || UPDATE_SOURCES.github;
}

function renderUpdatePanel(canUpdate) {
  if (!canUpdate) {
    return `<section class="data-panel settings-panel settings-readonly-note">
      <strong>版本更新</strong><span>当前账号没有系统更新权限。</span>
    </section>`;
  }
  const status = settingsState.updateStatus || {};
  const checking = settingsState.updateChecking;
  const applying = settingsState.updateApplying;
  const updateSource = currentUpdateSource();
  const customRepositoryUrl =
    settingsState.updateCustomRepositoryUrl ||
    (settingsState.updateRepositoryUrl && settingsState.updateRepositoryUrl !== GITHUB_UPDATE_REPOSITORY_URL
      ? settingsState.updateRepositoryUrl
      : "");
  const repositoryUrl =
    updateSource === "github" ? GITHUB_UPDATE_REPOSITORY_URL : customRepositoryUrl;
  const releaseChannel =
    settingsState.updateReleaseChannel || status.releaseChannel || DEFAULT_UPDATE_RELEASE_CHANNEL;
  const deploymentBusy = ["queued", "running"].includes(status.status);
  const busy = checking || applying || deploymentBusy;
  const currentSha = status.currentShortSha || (status.currentSha ? String(status.currentSha).slice(0, 7) : "-");
  const latestSha = status.latestShortSha || (status.latestSha ? String(status.latestSha).slice(0, 7) : "-");
  const currentVersion = status.currentVersion
    ? `${status.currentVersion} · ${currentSha}`
    : `未发布版本 · ${currentSha}`;
  const latestVersion = status.latestVersion
    ? `${status.latestVersion} · ${(status.latestVersionSha || status.latestSha || latestSha).slice(0, 7)}`
    : "暂无已发布版本";
  const sourceLabel = status.effectiveRepositoryUrl || repositoryUrl || "服务器默认 origin";
  const statusValue = status.status || "";
  const versions = Array.isArray(status.availableVersions) ? status.availableVersions : [];
  const selectedSha = versions.some(
    (version) =>
      version.sha === settingsState.updateSelectedSha && version.isSelectable !== false && !version.isCurrent,
  )
    ? settingsState.updateSelectedSha
    : "";
  const selectedVersion =
    versions.find((version) => version.sha === selectedSha) ||
    versions.find((version) => version.isLatest) ||
    null;
  const releaseNotes = selectedVersion?.releaseNotes || status.latestReleaseNotes || "";
  const versionOptions = versions.length
    ? `<option value="">请选择一个版本</option>${versions
        .map((version) => {
          const shortSha = version.shortSha || String(version.sha || "").slice(0, 7);
          const markers = [
            version.isCurrent ? "当前" : "",
            version.isLatest ? "最新" : "",
            version.isSelectable === false && !version.isCurrent ? "历史" : "",
          ].filter(Boolean);
          const markerText = markers.length ? `（${markers.join("、")}）` : "";
          const label = `${version.version || version.tag || "未知版本"} · ${version.subject || "无提交说明"}${markerText} · ${shortSha} · ${formatDateTime(
            version.authoredAt || "",
          )}`;
          return `<option value="${escapeHtml(version.sha || "")}" ${
            version.isSelectable === false ? "disabled" : ""
          } ${version.sha === selectedSha ? "selected" : ""}>${escapeHtml(label)}</option>`;
        })
        .join("")}`
    : `<option value="">${
        statusValue === "no_releases"
          ? "检查完成：暂无已发布版本"
          : statusValue
            ? "检查完成：暂无更高发布版本"
            : "请先检查版本"
      }</option>`;
  return `<section class="data-panel settings-panel update-panel">
    <div class="section-heading settings-panel-heading">
      <div><h2>版本更新</h2><span>从 GitHub 或 Gitea 读取已发布的语义化版本标签，只能选择版本号更高的版本更新应用。</span></div>
    </div>
    <div class="update-channel-row">
      <div class="update-target-field">
        <label for="updateSource">更新来源</label>
        <select id="updateSource" data-update-source ${busy ? "disabled" : ""}>
          ${Object.entries(UPDATE_SOURCES)
            .map(
              ([value, label]) =>
                `<option value="${value}" ${updateSource === value ? "selected" : ""}>${escapeHtml(label)}</option>`,
            )
            .join("")}
        </select>
      </div>
      <div class="update-channel-description">
        <strong>${escapeHtml(updateSourceLabel(updateSource))}</strong>
        <span>${
          updateSource === "github"
            ? `内置地址：${escapeHtml(GITHUB_UPDATE_REPOSITORY_URL)}`
            : "填写其它 GitHub/Gitea 仓库地址；留空时使用服务器部署目录的默认 origin。"
        }</span>
      </div>
    </div>
    ${
      updateSource === "custom"
        ? `<div class="update-target-field">
      <label for="updateRepositoryUrl">自定义项目地址</label>
      <input id="updateRepositoryUrl" data-update-repository-url type="text" value="${escapeHtml(
        customRepositoryUrl,
      )}" placeholder="留空使用服务器默认 origin，或填写 GitHub/Gitea 仓库地址" ${busy ? "disabled" : ""} />
    </div>`
        : ""
    }
    <div class="update-channel-row">
      <div class="update-target-field">
        <label for="updateReleaseChannel">更新通道</label>
        <select id="updateReleaseChannel" data-update-release-channel ${busy ? "disabled" : ""}>
          ${Object.entries(UPDATE_RELEASE_CHANNELS)
            .map(
              ([value, label]) =>
                `<option value="${value}" ${releaseChannel === value ? "selected" : ""}>${label}</option>`,
            )
            .join("")}
        </select>
      </div>
      <div class="update-channel-description">
        <strong>${escapeHtml(updateReleaseChannelLabel(releaseChannel))}</strong>
        <span>${
          releaseChannel === "release"
            ? "仅检查稳定的 vMAJOR.MINOR.PATCH 正式发行版。"
            : "检查 vMAJOR.MINOR.PATCH-beta.N 等预发布版本；默认使用此通道。"
        }</span>
      </div>
    </div>
    <div class="update-version-grid">
      <div class="update-version-item"><span>当前版本</span><strong>${escapeHtml(currentVersion)}</strong></div>
      <div class="update-version-item"><span>来源最新发布版本</span><strong>${escapeHtml(latestVersion)}</strong></div>
    </div>
    <div class="update-target-field">
      <label for="updateTargetVersion">目标版本</label>
      <select id="updateTargetVersion" data-update-target ${busy ? "disabled" : ""}>
        ${versionOptions}
      </select>
    </div>
    <div class="update-release-notes">
      <div class="update-release-notes-heading"><strong>版本更新说明</strong><span>${
        selectedVersion ? escapeHtml(selectedVersion.version || selectedVersion.tag || "") : "检查后显示"
      }</span></div>
      <div class="update-release-notes-body">${
        releaseNotes ? escapeHtml(releaseNotes) : "该版本暂无匹配的 VERSION_NOTES.md 说明。"
      }</div>
    </div>
    <div class="settings-readonly-note update-status-note">
      <strong>${escapeHtml(updateStatusLabel(statusValue))}</strong>
      <span>${escapeHtml(updateStatusDetail(statusValue))} 来源：${escapeHtml(sourceLabel)}</span>
    </div>
    <div class="modal-footer settings-form-footer">
      <button type="button" class="secondary-button" data-action="check-for-update" ${busy ? "disabled" : ""}>
        ${checking ? "检查中..." : updateSource === "github" ? "从 GitHub 检查更新" : "检查版本"}
      </button>
      <button type="button" class="primary-button" data-action="apply-selected-update" ${
        !selectedSha || busy ? "disabled" : ""
      }>
        ${applying ? "提交中..." : "更新到所选版本"}
      </button>
    </div>
  </section>`;
}

function syncSettingsTabsAndContent() {
  const appContent = document.querySelector("#appContent");
  if (!appContent) return false;
  const currentTabs = appContent.querySelector(".settings-tabs");
  const currentContent = appContent.querySelector(".settings-view-content");
  if (!currentTabs || !currentContent) return false;
  const template = document.createElement("template");
  template.innerHTML = renderSettingsPage().trim();
  const nextTabs = template.content.querySelector(".settings-tabs");
  const nextContent = template.content.querySelector(".settings-view-content");
  if (!nextTabs || !nextContent) return false;
  currentTabs.replaceWith(nextTabs);
  currentContent.replaceWith(nextContent);
  return true;
}

function renderSettingsPage() {
  if (!settingsState.loaded) {
    return `<div class="page-intro"><div><h2>系统设置</h2><p>正在加载设置数据。</p></div></div>
      <section class="data-panel settings-loading">正在读取系统设置...</section>`;
  }
  const settings = settingsState.settings || {};
  const admin = isAdminUser();
  const canUpdate = hasPermission("system_updates", "update");
  const tabs = [
    ["system", "系统参数"],
    ["security", "安全与密码"],
    ...(admin
      ? [
          ["backup", "数据库备份"],
          ["accounts", "账号管理"],
          ["access", "角色与权限"],
        ]
      : []),
    ...(canUpdate ? [["updates", "系统更新"]] : []),
  ];
  if (!tabs.some(([view]) => view === settingsState.view)) {
    settingsState.view = "system";
  }
  const activeView = settingsState.view;
  let content = "";
  if (activeView === "system") {
    content = `<div class="settings-grid">
      <section class="data-panel settings-panel">
        <div class="section-heading settings-panel-heading">
          <div><h2>系统参数</h2><span>${admin ? "管理员可以修改系统级设置。" : "当前账号只能查看系统级设置。"}</span></div>
        </div>
        <form data-form="system-settings" class="settings-form">
          <div class="form-grid">
            ${inputField("系统名称", "app_name", settings.app_name || "办公资产管理系统", true, "办公资产管理系统", "text", "", admin ? "" : "readonly")}
            ${inputField("会话时长（小时）", "session_hours", settings.session_hours || "8", true, "8", "number", "1", admin ? 'max="168"' : 'readonly max="168"')}
          </div>
          ${textareaField("登录页提示语", "login_notice", settings.login_notice || "", false, "例如：请使用公司账号登录", 4, admin ? "" : "readonly")}
          <div class="modal-footer settings-form-footer">${admin ? '<button class="primary-button" type="submit">保存系统设置</button>' : '<span class="secondary-text">只有管理员可以保存系统设置</span>'}</div>
        </form>
      </section>
    </div>`;
  } else if (activeView === "security") {
    content = `<div class="settings-grid">
      <section class="data-panel settings-panel">
        <div class="section-heading settings-panel-heading">
          <div><h2>修改我的密码</h2><span>密码至少 8 位，修改后当前会话仍保持有效，其他会话会退出登录。</span></div>
        </div>
        <form data-form="change-password" class="settings-form">
          ${inputField("当前密码", "currentPassword", "", true, "请输入当前密码", "password", "8", 'autocomplete="current-password"')}
          <div class="form-grid">
            ${inputField("新密码", "newPassword", "", true, "至少 8 位", "password", "8", 'autocomplete="new-password"')}
            ${inputField("确认新密码", "confirmPassword", "", true, "再次输入新密码", "password", "8", 'autocomplete="new-password"')}
          </div>
          <div class="modal-footer settings-form-footer"><button class="primary-button" type="submit">保存新密码</button></div>
        </form>
      </section>
    </div>`;
  } else if (activeView === "backup") {
    content = `<section class="section-block">
      <div class="section-heading">
        <div><h2>数据库备份</h2><span>备份文件仅保存在服务器的非公开目录；下载前需要重新验证当前登录账号密码。</span></div>
        <div class="toolbar-actions"><button type="button" class="primary-button" data-action="create-database-backup">立即备份</button></div>
      </div>
      <div class="settings-grid">
        <section class="data-panel settings-panel">
          <div class="section-heading settings-panel-heading">
            <div><h2>自动备份计划</h2><span>服务运行期间每天在指定时间执行一次备份。</span></div>
          </div>
          <form data-form="backup-schedule" class="settings-form">
            <div class="form-grid">
              <div class="form-field backup-toggle-field">
                <label class="backup-toggle-label"><input type="checkbox" name="backup_enabled" ${
                  ["1", "true", "yes", "on"].includes(String(settings.backup_enabled || "").toLowerCase())
                    ? "checked"
                    : ""
                } /><span>启用每日自动备份</span></label>
                <p class="form-hint">服务重启后会继续按当前设置执行。</p>
              </div>
              ${inputField("每日备份时间", "backup_time", settings.backup_time || "02:00", true, "", "time")}
              ${inputField("保留天数", "backup_retention_days", settings.backup_retention_days || "30", true, "0 表示不自动清理", "number", "0", 'max="3650"')}
            </div>
            <div class="modal-footer settings-form-footer"><button class="primary-button" type="submit">保存备份计划</button></div>
          </form>
        </section>
        <section class="data-panel settings-panel">
          <div class="section-heading settings-panel-heading">
            <div><h2>备份说明</h2><span>手动备份会立即创建一个压缩的 SQL 文件。</span></div>
          </div>
          <div class="settings-readonly-note"><strong>下载保护</strong><span>下载任意备份时，系统会要求再次输入当前管理员账号的登录密码。备份文件不会暴露在网页静态目录中。</span></div>
        </section>
      </div>
      <section class="data-panel settings-backup-list">${renderDatabaseBackupTable()}</section>
    </section>`;
  } else if (activeView === "accounts") {
    content = `<section class="section-block">
      <div class="section-heading">
        <div><h2>账号管理</h2><span>创建账号时填写登录账号和显示名称，再分配角色。</span></div>
        <div class="toolbar-actions"><button class="primary-button" data-action="open-settings-user">＋ 新增账号</button></div>
      </div>
      <section class="data-panel">${renderSettingsUserTable()}</section>
    </section>`;
  } else if (activeView === "access") {
    content = renderAccessControlPanel();
  } else if (activeView === "updates") {
    content = `<div class="settings-grid">${renderUpdatePanel(canUpdate)}</div>`;
  }
  return `
    <div class="page-intro">
      <div><h2>系统设置</h2><p>维护系统显示参数、登录安全和账号信息。</p></div>
    </div>
    <nav class="settings-tabs" aria-label="设置分区">
      ${tabs
        .map(
          ([view, label]) =>
            `<button type="button" class="settings-tab ${activeView === view ? "is-active" : ""}" data-action="settings-view" data-view="${view}">${label}</button>`,
        )
        .join("")}
    </nav>
    <div class="settings-view-content">${content}</div>`;
}

function openSettingsUserModal(id = "") {
  if (!isAdminUser()) {
    showToast("只有管理员可以管理账号", true);
    return;
  }
  const user = settingsState.users.find((item) => String(item.id) === String(id)) || {
    id: "",
    username: "",
    displayName: "",
    role: "operator",
    isActive: true,
  };
  const isEditing = Boolean(user.id);
  const roleOptions = (settingsState.accessControl?.roles || [])
    .filter((role) => role.isActive !== false)
    .map((role) => ({ value: role.code, label: role.name || role.code }));
  const employeeOptions = [{ value: "", label: "仅超级管理员可不绑定人员" }].concat(
    (state.employees || [])
      .filter((employee) => !["left", "shared"].includes(employee.status))
      .map((employee) => ({
        value: employee.id,
        label: `${employee.name} · ${employee.department || orgName(employee.orgId) || "未分配部门"} (${employee.employeeNo || ""})`,
      })),
  );
  openModal(
    `${modalHeader(isEditing ? "编辑账号" : "新增账号", "账号用于登录系统，密码不会显示在页面或日志中。")}
      <form data-form="user-account" data-id="${escapeHtml(user.id)}">
        <div class="form-grid">
          ${inputField("登录账号", "username", user.username, !isEditing, "3-64 位字母、数字、点、下划线或短横线", "text", "", isEditing ? "readonly" : 'autocomplete="username"')}
          ${inputField("显示名称", "displayName", user.displayName, true, "例如：张三")}
          ${selectField("角色", "role", user.role, roleOptions.length ? roleOptions : Object.entries(roleLabels).map(([value, label]) => ({ value, label })), true)}
          ${selectField("绑定人员（普通账号必填）", "employeeId", user.employeeId || "", employeeOptions, false)}
          ${selectField("账号状态", "isActive", user.isActive ? "1" : "0", [
            { value: "1", label: "启用" },
            { value: "0", label: "停用" },
          ], true)}
        </div>
        ${inputField(isEditing ? "重置密码（可选）" : "初始密码", "password", "", !isEditing, isEditing ? "留空表示不修改" : "至少 8 位", "password", "8", 'autocomplete="new-password"')}
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">${isEditing ? "保存账号" : "创建账号"}</button></div>
      </form>`,
    false,
  );
}

function openDatabaseBackupDownloadModal(id = "") {
  if (!isAdminUser()) {
    showToast("只有管理员可以下载数据库备份", true);
    return;
  }
  const backup = (settingsState.backups || []).find((item) => String(item.id) === String(id));
  if (!backup || !backup.fileAvailable) {
    showToast("该备份文件当前不可下载", true);
    return;
  }
  openModal(
    `${modalHeader("下载数据库备份", "请重新输入当前登录账号的密码以确认本次下载。")}
      <form data-form="database-backup-download" data-id="${escapeHtml(backup.id)}">
        <div class="backup-download-file"><strong>${escapeHtml(backup.fileName)}</strong><span>${escapeHtml(
          `${formatFileSize(backup.fileSize)} · ${formatDateTime(backup.createdAt || "")}`,
        )}</span></div>
        ${inputField("当前账号密码", "password", "", true, "请输入当前登录账号密码", "password", "8", 'autocomplete="current-password"')}
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">确认下载</button></div>
      </form>`,
    false,
  );
}

const auditActionLabels = {
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
};

function auditActionLabel(actionType) {
  return auditActionLabels[actionType] || auditActionExtraLabels[actionType] || actionType || "其他操作";
}

const auditActionExtraLabels = {
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

const auditCategoryLabels = {
  inventory: "物资变动",
  employee: "人员变动",
  computer: "办公终端信息变动",
  organization: "组织架构变动",
  other: "其他变动",
};

function auditCategoryForLog(log) {
  if (log?.category) return log.category;
  if (["inventory_type", "inventory_brand", "inventory_model"].includes(log?.entityType)) {
    return "inventory";
  }
  if (["employee", "monitor", "non_asset"].includes(log?.entityType)) {
    return "employee";
  }
  if (log?.entityType === "computer") return "computer";
  if (log?.entityType === "org_unit") return "organization";
  return "other";
}

function auditCategoryLabel(category) {
  return auditCategoryLabels[category] || category || "其他变动";
}

function auditChangeLabel(log) {
  const oldQuantity = Number(log?.oldValue?.quantity || 0);
  const newQuantity = Number(log?.newValue?.quantity || 0);
  if (log?.actionType === "inventory_stock_changed") {
    if (newQuantity > oldQuantity) return "物资库存增加";
    if (newQuantity < oldQuantity) return "物资库存减少";
  }
  if (log?.actionType === "non_asset_quantity_changed") {
    if (newQuantity > oldQuantity) return "人员物资增加";
    if (newQuantity < oldQuantity) return "人员物资减少";
  }
  return log?.changeLabel || auditActionLabel(log?.actionType);
}

function auditCategoryClass(log) {
  return `audit-category-${auditCategoryForLog(log)}`;
}

function getAuditCategoryOptions() {
  return ["inventory", "employee", "computer", "organization"];
}

const auditEntityTypeLabels = {
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

function auditEntityTypeLabel(entityType) {
  return auditEntityTypeLabels[entityType] || entityType || "其他对象";
}

function getAuditEntityTypeOptions() {
  return ["it_inventory", "employee", "computer", "monitor", "non_asset", "org_unit"];
}

function auditValueText(value) {
  if (value === null || value === undefined || value === "") return "无";
  if (typeof value !== "object") return String(value);

  const fieldLabels = {
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
  const parts = [];
  Object.entries(value).forEach(([key, item]) => {
    if (key === "assignment" && item && typeof item === "object") {
      parts.push(`使用人：${item.employeeName || "未分配"}`);
      if (item.employeeNo) parts.push(`编号：${item.employeeNo}`);
      return;
    }
    const label = fieldLabels[key] || key;
    const displayValue = key === "status" ? statusLabels[item] || item : item;
    if (displayValue !== null && displayValue !== undefined && displayValue !== "") {
      parts.push(`${label}：${displayValue}`);
    }
  });
  return parts.join("；") || "无";
}

function auditActionClass(actionType) {
  if (actionType.includes("removed") || actionType.includes("status_changed")) return "audit-action-alert";
  if (actionType.includes("assignment")) return "audit-action-assignment";
  if (actionType.includes("changed")) return "audit-action-assignment";
  return "audit-action-added";
}

function getAuditActionOptions() {
  return Object.keys({ ...auditActionLabels, ...auditActionExtraLabels }).sort((a, b) =>
    auditActionLabel(a).localeCompare(auditActionLabel(b), "zh-CN"),
  );
}

function renderAuditPage() {
  const logs = state.auditLogs || [];
  const actionFilter = state.filters.auditAction || "";
  const entityTypeFilter = state.filters.auditEntityType || "";
  const actionOptions = getAuditActionOptions();
  const entityTypeOptions = getAuditEntityTypeOptions();

  return `
    <div class="page-intro">
      <div><h2>操作日志</h2><p>按操作类别查看物资、人员和办公终端变动，再结合具体变动、人员和日期进行筛选。</p></div>
      <div class="toolbar-actions">
        <button class="secondary-button" data-action="refresh-audit">刷新日志</button>
        <button class="secondary-button" data-action="export-audit" ${logs.length ? "" : "disabled"}>导出当前结果</button>
      </div>
    </div>
    <div class="toolbar">
      <div class="toolbar-actions">
        <label class="select-box audit-date-box"><span>开始</span><input type="date" data-filter="auditStartDate" value="${escapeHtml(
          state.filters.auditStartDate || "",
        )}" /></label>
        <label class="select-box audit-date-box"><span>结束</span><input type="date" data-filter="auditEndDate" value="${escapeHtml(
          state.filters.auditEndDate || "",
        )}" /></label>
        <label class="search-box audit-employee-box"><span>人</span><input data-filter="auditEmployee" value="${escapeHtml(
          filterSearchDraftValue("auditEmployee"),
        )}" placeholder="人员编号或姓名" /></label>
        <label class="search-box"><span>⌕</span><input data-filter="auditSearch" value="${escapeHtml(
          filterSearchDraftValue("auditSearch"),
        )}" placeholder="搜索人员、设备或操作内容..." /></label>
        <label class="select-box"><span>操作类别</span><select data-filter="auditCategory">
          <option value="">全部类别</option>
          ${getAuditCategoryOptions()
            .map(
              (category) =>
                `<option value="${escapeHtml(category)}" ${
                  (state.filters.auditCategory || "") === category ? "selected" : ""
                }>${escapeHtml(auditCategoryLabel(category))}</option>`,
            )
            .join("")}
        </select></label>
        <label class="select-box"><span>具体变动</span><select data-filter="auditAction">
          <option value="">全部变动</option>
          ${actionOptions
            .map(
              (action) =>
                `<option value="${escapeHtml(action)}" ${
                  actionFilter === action ? "selected" : ""
                }>${escapeHtml(auditActionLabel(action))}</option>`,
            )
            .join("")}
        </select></label>
        <label class="select-box"><span>对象范围</span><select data-filter="auditEntityType">
          <option value="">全部对象</option>
          ${entityTypeOptions
            .map(
              (entityType) =>
                `<option value="${escapeHtml(entityType)}" ${
                  entityTypeFilter === entityType ? "selected" : ""
                }>${escapeHtml(auditEntityTypeLabel(entityType))}</option>`,
            )
            .join("")}
        </select></label>
        <button class="primary-button audit-apply-button" data-action="apply-audit-filters">应用筛选</button>
      </div>
      <span class="secondary-text">显示 ${logs.length} / ${state.auditLogTotal || logs.length} 条</span>
    </div>
    <div class="data-panel">${renderAuditTable(logs)}</div>
  `;
}

function renderAuditTable(logs) {
  if (!logs.length) return '<div class="empty-state">暂无符合条件的操作日志</div>';
  return `
    <div class="table-wrap">
      <table class="audit-table">
        <thead><tr><th>时间</th><th>操作类别</th><th>具体变动</th><th>变更对象</th><th>关联人员</th><th>变更前</th><th>变更后</th><th>变更说明</th><th>操作人</th></tr></thead>
        <tbody>
          ${logs
            .map(
              (log) => `<tr>
                <td class="audit-time">${escapeHtml(log.createdAt || "未知时间")}</td>
                <td><span class="audit-category ${auditCategoryClass(log)}">${escapeHtml(
                  auditCategoryLabel(auditCategoryForLog(log)),
                )}</span></td>
                <td><span class="audit-action ${auditActionClass(log.actionType)}">${escapeHtml(
                  auditChangeLabel(log),
                )}</span></td>
                <td><div class="primary-text">${escapeHtml(log.entityName || log.deviceName || "—")}</div><div class="secondary-text">${escapeHtml(
                  auditEntityTypeLabel(log.entityType),
                )}</div></td>
                <td>${
                  log.employeeName
                    ? `<div class="primary-text">${escapeHtml(log.employeeName)}</div><div class="secondary-text mono">${escapeHtml(
                        log.employeeId || "",
                      )}</div>`
                    : '<span class="secondary-text">—</span>'
                }</td>
                <td><span class="audit-value">${escapeHtml(auditValueText(log.oldValue))}</span></td>
                <td><span class="audit-value">${escapeHtml(auditValueText(log.newValue))}</span></td>
                <td class="audit-summary">${escapeHtml(log.summary)}</td>
                <td><div class="primary-text">${escapeHtml(log.actor || "web")}</div><div class="secondary-text">${escapeHtml(
                  log.source || "",
                )}</div></td>
              </tr>`,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function dashboardComputerStatusSummary() {
  const definitions = [
    { key: "in_use", label: statusLabels.in_use, color: "#7367f0" },
    { key: "idle", label: statusLabels.idle, color: "#00cfe8" },
    { key: "repair", label: statusLabels.repair, color: "#ff9f43" },
  ];
  const total = state.computers.length;
  const segments = definitions.map((item) => ({
    ...item,
    count: state.computers.filter((computer) => computer.status === item.key).length,
  }));
  const covered = segments.reduce((sum, item) => sum + item.count, 0);
  if (total > covered) {
    segments.push({ key: "other", label: "其它状态", color: "#aaaaaa", count: total - covered });
  }
  return { total, segments };
}

function renderDashboardComputerStatusChart() {
  const { total, segments } = dashboardComputerStatusSummary();
  const inUse = segments.find((item) => item.key === "in_use")?.count || 0;
  const rate = total ? Math.round((inUse / total) * 100) : 0;
  return `
    <div class="dashboard-status-layout">
      <div class="dashboard-status-orbit" style="--progress:${rate}">
        <div><strong>${rate}%</strong><span>在用率</span></div>
      </div>
      <div class="dashboard-status-summary">
        <div class="dashboard-status-title"><strong>终端运行状态</strong><span>${total} 台办公终端</span></div>
        <ul class="dashboard-status-legend">
          ${segments
            .map(
              (item) => `
                <li>
                  <div class="dashboard-status-line">
                    <span>${escapeHtml(item.label)}</span>
                    <div class="dashboard-status-meter"><span style="width: ${
                      total ? Math.max(0, Math.round((item.count / total) * 100)) : 0
                    }%; background: ${item.color}"></span></div>
                  </div>
                  <strong>${item.count}</strong>
                </li>`,
            )
            .join("")}
        </ul>
        <span class="dashboard-status-note">在用、闲置、维修状态实时汇总</span>
      </div>
    </div>
  `;
}

function getRecentInventoryInboundLogs(limit = 8) {
  return [...state.inventoryMovementLogs]
    .filter((log) => log.direction === "increase")
    .sort((a, b) => String(b.occurredAt || "").localeCompare(String(a.occurredAt || "")))
    .slice(0, limit);
}

function renderDashboardRecentInboundList() {
  const logs = getRecentInventoryInboundLogs();
  if (!logs.length) return '<div class="empty-state">暂无物资入库记录</div>';
  return `
    <div class="dashboard-inbound-list">
      ${logs
        .map(
          (log) => `
            <div class="dashboard-inbound-row">
              <div class="dashboard-inbound-main">
                <strong>${escapeHtml(log.typeName || "未分类物资")}</strong>
                <span>${escapeHtml([log.brandName, log.modelName].filter(Boolean).join(" / ") || "未填写品牌型号")}</span>
                <small>${escapeHtml(formatDateTime(log.occurredAt))} · ${escapeHtml(log.sourceLabel || "未标注来源")}</small>
              </div>
              <strong class="dashboard-inbound-quantity">+${Math.max(1, Number(log.quantity || 1))}</strong>
            </div>`,
        )
        .join("")}
    </div>
  `;
}

function renderDashboardOrgTreeNode(org, depth = 0) {
  const summary = getOrgSummary(org.id);
  const children = getOrgChildren(org.id);
  return `
    <div class="dashboard-org-node" style="--dashboard-org-depth: ${depth}">
      <div class="dashboard-org-row">
        <span class="dashboard-org-marker" aria-hidden="true"></span>
        <div class="dashboard-org-main">
          <div><strong>${escapeHtml(org.name)}</strong><span>${escapeHtml(org.code)}</span></div>
          <small>${summary.employees} 人 · ${summary.computers} 台办公终端${summary.children ? ` · ${summary.children} 个下级` : ""}</small>
        </div>
      </div>
      ${children.length ? `<div class="dashboard-org-children">${children.map((child) => renderDashboardOrgTreeNode(child, depth + 1)).join("")}</div>` : ""}
    </div>
  `;
}

function renderDashboardPage() {
  const computerCount = state.computers.length;
  const inUseCount = state.computers.filter((computer) => computer.status === "in_use").length;
  const idleCount = state.computers.filter((computer) => computer.status === "idle").length;
  const activeEmployees = state.employees.filter((employee) => employee.status === "active").length;
  const nonAssetCount = state.employees.reduce(
    (sum, employee) =>
      sum + getNonAssetItems(employee).reduce((total, item) => total + Math.max(0, Number(item.quantity || 0)), 0),
    0,
  );
  const recentComputers = [...state.computers]
    .sort((a, b) => (b.registeredDate || "").localeCompare(a.registeredDate || ""))
    .slice(0, 5);
  const attentionComputers = state.computers.filter((computer) => ["repair", "lost", "retired"].includes(computer.status));
  const tickets = operationsState.tickets || [];
  const service = serviceState();
  const queueItems = [
    ["待处理工单", tickets.filter((item) => !["closed", "resolved", "cancelled"].includes(item.status)).length, "tickets", "▣"],
    ["待审批事项", (service.approvals || []).filter((item) => item.status === "pending").length, "serviceManagement", "✓"],
    ["进行中变更", (service.changes || []).length, "serviceManagement", "↗"],
    ["问题记录", (service.problems || []).length, "serviceManagement", "?"],
  ];

  return `
    <section class="dashboard-welcome">
      <div class="dashboard-welcome-copy"><span class="eyebrow">ASSET OPERATIONS</span><h2>资产运营工作台</h2><p>${formatDate(new Date().toISOString().slice(0, 10))}，资产数据已连接到 MySQL，可从这里处理日常资产和服务事项。</p><div class="dashboard-welcome-actions">${hasPermission("it_assets", "create") ? '<button class="primary-button" data-action="open-computer"><span>＋</span>新建资产</button>' : ""}${hasPermission("tickets", "create") ? '<button class="secondary-button" data-action="quick-create-ticket">创建工单</button>' : ""}</div></div>
      <div class="dashboard-welcome-visual" aria-hidden="true"><span class="dashboard-visual-card dashboard-visual-card-a">▣</span><span class="dashboard-visual-card dashboard-visual-card-b">✓</span><span class="dashboard-visual-pulse"></span></div>
    </section>

    <div class="stats-grid dashboard-metrics">
      <div class="stat-card metric-card metric-card-primary">
        <div class="stat-label"><span>办公终端资产</span><span class="stat-mark">▣</span></div>
        <div class="stat-value">${computerCount}</div>
        <div class="stat-foot"><span class="metric-trend is-positive">↑ ${computerCount ? Math.round((inUseCount / computerCount) * 100) : 0}%</span>${inUseCount} 台当前在用</div>
      </div>
      <div class="stat-card metric-card">
        <div class="stat-label"><span>使用人员</span><span class="stat-mark">♙</span></div>
        <div class="stat-value">${activeEmployees}</div>
        <div class="stat-foot">${getRootOrgs().length} 个根组织</div>
      </div>
      <div class="stat-card metric-card">
        <div class="stat-label"><span>闲置可用</span><span class="stat-mark">◌</span></div>
        <div class="stat-value">${idleCount}</div>
        <div class="stat-foot">可用于新人员配置</div>
      </div>
      <div class="stat-card metric-card metric-card-warning">
        <div class="stat-label"><span>待关注</span><span class="stat-mark">!</span></div>
        <div class="stat-value">${attentionComputers.length}</div>
        <div class="stat-foot">${nonAssetCount} 件非资产设备在账</div>
      </div>
    </div>

    <div class="dashboard-main-grid">
      <section class="data-panel dashboard-status-panel dashboard-panel-animate">${renderDashboardComputerStatusChart()}</section>
      <section class="data-panel dashboard-queue-panel dashboard-panel-animate"><div class="section-heading"><div><h2>服务工作队列</h2><span>工单、审批、变更和问题</span></div><button class="text-button" data-action="navigate" data-page="serviceManagement">进入服务管理 ›</button></div><div class="dashboard-queue-list">${queueItems.map(([label, value, page, icon]) => `<button class="dashboard-queue-item" data-action="navigate" data-page="${page}"><span class="dashboard-queue-icon">${icon}</span><span>${label}</span><strong>${value}</strong><i>›</i></button>`).join("")}</div></section>
    </div>

    <div class="dashboard-secondary-grid">
      <section class="data-panel dashboard-panel-animate"><div class="section-heading"><div><h2>最近登记资产</h2><span>按注册日期倒序</span></div><button class="text-button" data-action="navigate" data-page="computers">全部资产 ›</button></div>${renderComputerTable(recentComputers, false)}</section>
      <section class="data-panel dashboard-panel-animate"><div class="section-heading"><div><h2>最近入库物资</h2><span>库存增加记录</span></div><button class="text-button" data-action="navigate" data-page="inventory">IT 物资 ›</button></div>${renderDashboardRecentInboundList()}</section>
    </div>
  `;
}

function renderComputersPage() {
  const statusFilter = state.filters.computerStatus || "";
  const computers = getFilteredComputers();
  const selectedCount = state.selectedComputerIds.length;

  return `
    <div class="page-intro">
      <div><h2>办公终端台账</h2><p>共 ${state.computers.length} 台 · 支持按设备名、固资编码、SN/ST、组织和使用用户检索</p></div>
      <div class="toolbar-actions">
        <button class="secondary-button" data-action="select-all-computers">全选当前结果</button>
        <button class="secondary-button" data-action="clear-computer-selection">清空选择</button>
        <button class="secondary-button" data-action="export-computers" ${selectedCount ? "" : "disabled"}>导出选中 ${selectedCount}</button>
        <button class="primary-button" data-action="open-computer">＋ 新增办公终端</button>
      </div>
    </div>
    <div class="toolbar">
      <div class="toolbar-actions">
        <label class="search-box"><span>⌕</span><input data-filter="computers" value="${escapeHtml(
          state.filters.computers || "",
        )}" placeholder="搜索设备名、型号、固资编码..." /></label>
        <label class="select-box"><select data-filter="computerStatus">
          <option value="">全部状态</option>
          ${["in_use", "idle", "repair", "retired", "lost"]
            .map(
              (status) =>
                `<option value="${status}" ${statusFilter === status ? "selected" : ""}>${escapeHtml(
                  statusLabels[status],
                )}</option>`,
            )
            .join("")}
        </select></label>
      </div>
      <span class="secondary-text">显示 ${computers.length} / ${state.computers.length} 台</span>
    </div>
    <div class="data-panel">${renderComputerTable(computers, true, true)}</div>
  `;
}

function renderComputerTable(computers, withActions, selectable = false) {
  if (!computers.length) return '<div class="empty-state">暂无符合条件的办公终端记录</div>';
  const allVisibleComputersSelected =
    selectable && computers.length > 0 && computers.every((computer) => state.selectedComputerIds.includes(computer.id));
  return `
    <div class="table-wrap">
      <table>
        <thead><tr>
          ${
            selectable
              ? `<th class="selector-cell"><input type="checkbox" data-action="toggle-all-computers" title="选择当前结果" ${
                  allVisibleComputersSelected ? "checked" : ""
                } /></th>`
              : ""
          }
          <th>设备名</th><th>所属组织</th><th>设备类型 / 品牌型号</th><th>固资编码</th>
          <th>位置</th><th>使用用户</th><th>状态</th>${withActions ? "<th>操作</th>" : ""}
        </tr></thead>
        <tbody>
          ${computers
            .map((computer) => {
              const user = getCurrentUser(computer);
              const configSummary = computerConfigSummary(computer);
              return `<tr>
                ${
                  selectable
                    ? `<td class="selector-cell"><input type="checkbox" class="row-selector" data-action="toggle-computer-selection" data-id="${escapeHtml(
                        computer.id,
                      )}" ${state.selectedComputerIds.includes(computer.id) ? "checked" : ""} /></td>`
                    : ""
                }
                <td><div class="primary-text">${escapeHtml(computer.deviceName)}</div><div class="secondary-text">${escapeHtml(
                  computer.snSt || "未登记 SN/ST",
                )}</div>${
                  configSummary
                    ? `<div class="secondary-text">${escapeHtml(configSummary)}</div>`
                    : ""
                }</td>
                <td><div class="primary-text">${escapeHtml(orgName(computer.orgId))}</div><div class="secondary-text">${escapeHtml(
                  orgPathName(computer.orgId),
                )}</div></td>
                <td><div class="primary-text">${escapeHtml(deviceTypeLabel(computer.deviceType))}</div><div class="secondary-text">${escapeHtml(
                  [computer.brand, computer.model].filter(Boolean).join(" · ") || "未填写品牌型号",
                )}</div></td>
                <td class="mono">${escapeHtml(computer.fixedAssetCode || "—")}</td>
                <td>${escapeHtml(computer.location || "—")}</td>
                <td>${
                  user
                    ? `<div class="primary-text">${escapeHtml(user.name)}</div><div class="secondary-text">${escapeHtml(
                        `${orgName(user.orgId)} · ${user.department || "—"}`,
                      )}</div>`
                    : '<span class="secondary-text">未分配</span>'
                }</td>
                <td>${statusPill(computer.status)}</td>
                ${
                  withActions
                    ? `<td><div class="inline-actions">
                        <button class="text-button" data-action="open-computer" data-id="${escapeHtml(computer.id)}">编辑</button>
                        ${
                          computer.status === "retired"
                            ? ""
                            : `<button class="text-button danger" data-action="open-computer-scrap" data-id="${escapeHtml(
                                computer.id,
                              )}" data-name="${escapeHtml(computer.deviceName)}">报废</button>`
                        }
                      </div></td>`
                    : ""
                }
              </tr>`;
            })
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderEmployeesPage() {
  const search = (state.filters.employees || "").trim().toLowerCase();
  const assetSearch = (state.filters.employeeAssetSearch || "").trim().toLowerCase();
  const statusFilter = state.filters.employeeStatus || "";
  const orgFilter = state.filters.employeeOrg || "";
  const deviceFilter = state.filters.employeeDevice || "";
  const treeFilterActive = Boolean(search || assetSearch || statusFilter || orgFilter || deviceFilter);
  const filteredEmployees = getFilteredEmployees();

  const employeeIdSet = new Set(filteredEmployees.map((employee) => employee.id));
  const visibleOrgIds = getVisibleOrgIdsForEmployees(search, employeeIdSet, treeFilterActive);
  const rootOrgs = getRootOrgs().filter((org) => !treeFilterActive || visibleOrgIds.has(org.id));
  const unassignedEmployees = filteredEmployees.filter((employee) => !employee.orgId || !getOrg(employee.orgId));
  const directTreeCount = rootOrgs.length + (unassignedEmployees.length ? 1 : 0);
  const selectedCount = state.selectedEmployeeIds.length;

  return `
    <div class="page-intro">
      <div><h2>办公设备使用人员</h2><p>按组织架构树查看人员，节点下直接展示办公终端、显示屏和非资产设备</p></div>
      <div class="toolbar-actions">
        <button class="secondary-button" data-action="select-all-employees">全选当前结果</button>
        <button class="secondary-button" data-action="clear-employee-selection">清空选择</button>
        <button class="secondary-button" data-action="export-employees" ${selectedCount ? "" : "disabled"}>导出选中 ${selectedCount}</button>
        <button class="primary-button" data-action="open-employee">＋ 新增人员</button>
      </div>
    </div>
    <div class="toolbar">
      <div class="toolbar-actions">
        <label class="search-box"><span>⌕</span><input data-filter="employees" value="${escapeHtml(
          filterSearchDraftValue("employees"),
        )}" placeholder="搜索姓名、工号、部门或组织..." /></label>
        <label class="search-box employee-asset-search"><span>IT</span><input data-filter="employeeAssetSearch" value="${escapeHtml(
          filterSearchDraftValue("employeeAssetSearch"),
        )}" placeholder="搜索 IT 物资品牌或型号..." /></label>
        <button class="secondary-button" data-action="apply-employee-search">搜索</button>
        <label class="select-box"><select data-filter="employeeStatus">
          <option value="">全部人员状态</option>
          ${["active", "inactive", "shared"]
            .map(
              (status) =>
                `<option value="${status}" ${statusFilter === status ? "selected" : ""}>${escapeHtml(
                  statusLabels[status],
                )}</option>`,
            )
            .join("")}
        </select></label>
        <label class="select-box employee-org-filter"><select data-filter="employeeOrg">
          <option value="">全部组织</option>
          ${getOrgSelectOptions()
            .map(
              (option) =>
                `<option value="${escapeHtml(option.value)}" ${
                  orgFilter === option.value ? "selected" : ""
                }>${escapeHtml(option.label)}</option>`,
            )
            .join("")}
          <option value="__unassigned__" ${orgFilter === "__unassigned__" ? "selected" : ""}>未分配组织</option>
        </select></label>
        <label class="select-box"><select data-filter="employeeDevice">
          <option value="">全部设备情况</option>
          <option value="assigned" ${deviceFilter === "assigned" ? "selected" : ""}>已分配设备</option>
          <option value="unassigned" ${deviceFilter === "unassigned" ? "selected" : ""}>无设备</option>
        </select></label>
        ${
          treeFilterActive
            ? '<button class="secondary-button" data-action="clear-employee-filters">清除筛选</button>'
            : ""
        }
        <label class="secondary-text"><input type="checkbox" data-org-count-include-shared ${
          state.includeSharedInOrgCount ? "checked" : ""
        } /> 组织树人数含公用人员</label>
      </div>
      <span class="secondary-text">显示 ${filteredEmployees.length} / ${state.employees.length} 人 · ${directTreeCount} 个顶层节点</span>
    </div>

    <div class="stats-grid compact">
      <div class="stat-card">
        <div class="stat-label"><span>组织总数</span><span class="stat-mark">⎇</span></div>
        <div class="stat-value">${state.orgs.length}</div>
        <div class="stat-foot">${getRootOrgs().length} 个根组织</div>
      </div>
      <div class="stat-card">
        <div class="stat-label"><span>在职人员</span><span class="stat-mark">♙</span></div>
        <div class="stat-value">${state.employees.filter((employee) => employee.status === "active").length}</div>
        <div class="stat-foot">支持设备直接维护</div>
      </div>
      <div class="stat-card">
        <div class="stat-label"><span>已分配办公终端</span><span class="stat-mark">▣</span></div>
        <div class="stat-value">${state.computers.filter((computer) => computer.userId).length}</div>
        <div class="stat-foot">和人员树同步联动</div>
      </div>
      <div class="stat-card">
        <div class="stat-label"><span>未挂组织</span><span class="stat-mark">∅</span></div>
        <div class="stat-value">${state.employees.filter((employee) => !employee.orgId || !getOrg(employee.orgId)).length}</div>
        <div class="stat-foot">建议及时整理归属</div>
      </div>
    </div>

    <div class="tree-layout">
      <section class="section-block">
        <div class="section-heading">
          <div><h2>组织人员树</h2><span>组织可折叠，人员节点支持设备维护</span></div>
          <div class="toolbar-actions">
            <button class="secondary-button" data-action="expand-all-orgs">全部展开</button>
            <button class="secondary-button" data-action="collapse-all-orgs">全部收起</button>
          </div>
        </div>
        <div class="data-panel tree-panel">
          ${
            rootOrgs.length || unassignedEmployees.length
              ? `${rootOrgs
                  .map((org) => renderEmployeeOrgNode(org, { visibleOrgIds, employeeIdSet, searchActive: treeFilterActive }))
                  .join("")}
                 ${unassignedEmployees.length ? renderUnassignedEmployeeBlock(unassignedEmployees) : ""}`
              : '<div class="empty-state">暂无符合条件的人员记录</div>'
          }
        </div>
      </section>
    </div>
  `;
}

function getFilteredLeftEmployees() {
  const search = (state.filters.leftEmployees || "").trim().toLowerCase();
  return [...state.leftEmployees]
    .filter((employee) => {
      const searchText = [
        employee.employeeNo,
        employee.name,
        employee.orgPath,
        employee.department,
        employee.position,
        employee.leaveInfo,
        employee.leaveRemark,
      ]
        .join(" ")
        .toLowerCase();
      return !search || searchText.includes(search);
    })
    .sort((a, b) => {
      const dateCompare = String(b.leaveDate || b.archivedAt || "").localeCompare(String(a.leaveDate || a.archivedAt || ""));
      return dateCompare || compareText(a.employeeNo, b.employeeNo) || compareText(a.name, b.name);
    });
}

function renderLeftEmployeesPage() {
  const employees = getFilteredLeftEmployees();
  return `
    <div class="page-intro">
      <div><h2>离职人员</h2><p>离职人员会从组织树移出，并保留离职时间、离职说明、备注和离职时设备快照，点击详情可查看完整归档内容</p></div>
      <div class="toolbar-actions">
        <button class="secondary-button" data-action="navigate" data-page="employees">返回使用人员</button>
      </div>
    </div>
    <div class="toolbar">
      <div class="toolbar-actions">
        <label class="search-box"><span>⌕</span><input data-filter="leftEmployees" value="${escapeHtml(
          state.filters.leftEmployees || "",
        )}" placeholder="搜索姓名、编号、组织、部门或离职说明..." /></label>
      </div>
      <span class="secondary-text">显示 ${employees.length} / ${state.leftEmployees.length} 人</span>
    </div>
    <div class="data-panel">${renderLeftEmployeeTable(employees)}</div>
  `;
}

function renderLeftEmployeeTable(employees) {
  if (!employees.length) return '<div class="empty-state">暂无离职人员记录</div>';
  return `
    <div class="table-wrap">
      <table>
        <thead><tr><th>人员</th><th>原组织 / 部门</th><th>岗位</th><th>离职日期</th><th>离职设备快照</th><th>归档信息</th></tr></thead>
        <tbody>
          ${employees
            .map(
              (employee) => `<tr>
                <td><div class="primary-text">${escapeHtml(employee.name)}</div><div class="secondary-text mono">${escapeHtml(
                  employee.employeeNo,
                )}</div></td>
                <td><div class="primary-text">${escapeHtml(employee.orgPath || orgPathName(employee.orgId))}</div><div class="secondary-text">${escapeHtml(
                  employee.department || "未填写部门",
                )}</div></td>
                <td>${escapeHtml(employee.position || "—")}</td>
                <td>${escapeHtml(employee.leaveDate || "—")}</td>
                <td>${leftEmployeeDeviceChips(employee.devices || [])}</td>
                <td><button class="text-button" data-action="open-left-employee" data-id="${escapeHtml(
                  employee.id,
                )}">查看详情</button></td>
              </tr>`,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function inventoryTreeRows() {
  const nodes = buildInventoryTreeNodes();
  if (!nodes.length) return "";

  return nodes
    .map(({ type, brands }) => {
      const typeQuantity = brands.reduce(
        (sum, brand) =>
          sum + brand.models.reduce((brandSum, model) => brandSum + Math.max(0, Number(model.quantity || 0)), 0),
        0,
      );
      const typeModelCount = brands.reduce((sum, brand) => sum + brand.models.length, 0);
      const typeExpanded = isInventoryTypeExpanded(type.id);
      const brandRows = brands.length
        ? brands
            .map((brand) => {
              const brandQuantity = brand.models.reduce(
                (sum, model) => sum + Math.max(0, Number(model.quantity || 0)),
                0,
              );
              const brandExpanded = isInventoryBrandExpanded(brand.id);
              return `
                <div class="inventory-node inventory-brand-node">
                  <div class="inventory-node-row">
                    <div class="inventory-node-head">
                      <button class="tree-toggle inventory-toggle" data-action="toggle-inventory-brand" data-id="${escapeHtml(
                        brand.id,
                      )}" aria-expanded="${brandExpanded ? "true" : "false"}">${brandExpanded ? "-" : "+"}</button>
                      <div class="inventory-node-main">
                        <strong>${escapeHtml(brand.name)}</strong>
                        <span>${brand.models.length} 个型号 / ${brandQuantity} ${escapeHtml(type.unit || "件")}</span>
                      </div>
                    </div>
                    <div class="inline-actions">
                      <button class="text-button" data-action="open-inventory-brand" data-type-id="${escapeHtml(
                        type.id,
                      )}" data-id="${escapeHtml(brand.id)}">编辑品牌</button>
                      <button class="text-button" data-action="open-inventory-model" data-type-id="${escapeHtml(
                        type.id,
                      )}" data-brand-id="${escapeHtml(brand.id)}">新增型号</button>
                      <button class="text-button danger" data-action="delete-inventory-brand" data-id="${escapeHtml(
                        brand.id,
                      )}">删除</button>
                    </div>
                  </div>
                  ${
                    brandExpanded
                      ? `<div class="inventory-model-list">
                      ${
                        brand.models.length
                          ? brand.models
                              .map(
                                (model) => {
                                  const modelMeta = inventoryModelDisplayMeta(type, model);
                                  return `
                                  <div class="inventory-model-row">
                                    <div><span>${escapeHtml(model.name)}</span><small>${escapeHtml(modelMeta)}</small></div>
                                    <div class="inline-actions">
                                      <button class="text-button" data-action="open-inventory-model" data-type-id="${escapeHtml(
                                        type.id,
                                      )}" data-brand-id="${escapeHtml(brand.id)}" data-id="${escapeHtml(
                                        model.id,
                                      )}">编辑</button>
                                      <button class="text-button danger" data-action="delete-inventory-model" data-id="${escapeHtml(
                                        model.id,
                                      )}">删除</button>
                                    </div>
                                  </div>
                                `;
                                },
                              )
                              .join("")
                          : '<div class="inventory-empty">当前没有型号记录</div>'
                      }
                    </div>`
                      : ""
                  }
                </div>
              `;
            })
            .join("")
        : '<div class="inventory-empty">当前没有品牌记录</div>';

      return `
        <section class="inventory-node inventory-type-node">
          <div class="inventory-node-row">
            <div class="inventory-node-head">
              <button class="tree-toggle inventory-toggle" data-action="toggle-inventory-type" data-id="${escapeHtml(
                type.id,
              )}" aria-expanded="${typeExpanded ? "true" : "false"}">${typeExpanded ? "-" : "+"}</button>
              <div class="inventory-node-main">
                <strong>${escapeHtml(type.name)}</strong>
                <span>${brands.length} 个品牌 / ${typeModelCount} 个型号 / ${typeQuantity} ${escapeHtml(type.unit || "件")}</span>
              </div>
            </div>
            <div class="inline-actions">
              <button class="text-button" data-action="open-type" data-id="${escapeHtml(type.id)}">编辑类型</button>
              <button class="text-button" data-action="open-inventory-brand" data-type-id="${escapeHtml(type.id)}">新增品牌</button>
              <button class="text-button danger" data-action="delete-type" data-id="${escapeHtml(type.id)}" ${
                isProtectedInventoryType(type) ? 'disabled title="系统保留类型不可删除"' : ""
              }>删除</button>
            </div>
          </div>
          ${typeExpanded ? `<div class="inventory-children">${brandRows}</div>` : ""}
        </section>
      `;
    })
    .join("");
}

function renderInventoryPage() {
  const warehouseId = ensureInventoryWarehouseView();
  const warehouse = inventoryWarehouseById(warehouseId);
  const warehouses = inventoryWarehousesForView();
  const totalQuantity = warehouseInventoryTotal(warehouseId);
  const nodes = buildInventoryTreeNodes();
  const visibleBrandCount = nodes.reduce((sum, node) => sum + node.brands.length, 0);
  const visibleModelCount = nodes.reduce(
    (sum, node) => sum + node.brands.reduce((brandSum, brand) => brandSum + brand.models.length, 0),
    0,
  );
  const visibleQuantity = nodes.reduce(
    (sum, node) =>
      sum +
      node.brands.reduce(
        (brandSum, brand) =>
          brandSum + brand.models.reduce((modelSum, model) => modelSum + Math.max(0, Number(model.quantity || 0)), 0),
        0,
      ),
    0,
  );
  const purchaseLogs = warehouseId
    ? (state.inventoryPurchaseLogs || []).filter((log) => sameRecordId(log.warehouseId, warehouseId))
    : state.inventoryPurchaseLogs || [];
  const canManageWarehouses = hasPermission("warehouse_management", "view");
  const canCreateWarehouses = hasPermission("warehouse_management", "create");
  const canTransferInventory =
    hasPermission("warehouse_management", "create") && hasPermission("inventory_operations", "update");
  const canCreateCatalog = hasPermission("inventory_catalog", "create");
  const canExportCatalog = hasPermission("inventory_catalog", "export");
  const canCreateOperations = hasPermission("inventory_operations", "create");
  const warehouseTabs = warehouses.length
    ? `<nav class="inventory-warehouse-tabs" aria-label="库存仓库">
        ${warehouses
          .map(
            (item) => `<button type="button" class="inventory-warehouse-tab ${
              sameRecordId(item.id, warehouseId) ? "is-active" : ""
            }" data-action="select-inventory-warehouse" data-id="${escapeHtml(item.id)}" aria-pressed="${
              sameRecordId(item.id, warehouseId) ? "true" : "false"
            }">
              <strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.code || "未设编码")}</span>
            </button>`,
          )
          .join("")}
      </nav>`
    : "";

  return `
    <div class="page-intro">
      <div><h2>IT物资</h2><p>按仓库、类型、品牌和型号管理未分配的办公物资库存。</p></div>
      <div class="toolbar-actions">
        ${canManageWarehouses ? '<button class="secondary-button" data-action="open-warehouse-directory">仓库管理</button>' : ""}
        ${canTransferInventory ? '<button class="secondary-button" data-action="open-inventory-transfer">库存调拨</button>' : ""}
        ${canCreateOperations ? '<button class="secondary-button" data-action="open-inventory-import">＋ 入库</button>' : ""}
        ${canExportCatalog ? '<button class="secondary-button" data-action="export-inventory">导出当前仓库</button>' : ""}
        ${canCreateCatalog ? '<button class="primary-button" data-action="open-type">新增类型</button>' : ""}
        <button class="secondary-button" data-action="navigate" data-page="dashboard">返回工作台</button>
      </div>
    </div>
    ${warehouseTabs}
    ${
      warehouse
        ? `<section class="inventory-warehouse-summary">
            <div class="inventory-warehouse-heading">
              <div><h3>${escapeHtml(warehouse.name)}</h3><span>${escapeHtml(warehouse.code || "未设仓库编码")}</span></div>
              <span class="status-pill ${warehouse.isActive ? "status-idle" : "status-retired"}">${
                warehouse.isActive ? "启用" : "已停用"
              }</span>
            </div>
            <dl class="inventory-warehouse-details">
              <div><dt>所属组织</dt><dd>${escapeHtml(orgPathName(warehouse.orgId))}</dd></div>
              <div><dt>负责人</dt><dd>${escapeHtml(warehouse.managerName || "未指定")}</dd></div>
              <div><dt>库存型号</dt><dd>${warehouseInventoryModelCount(warehouseId)} 个</dd></div>
              <div><dt>库存总量</dt><dd>${totalQuantity} 件</dd></div>
            </dl>
          </section>`
        : `<section class="inventory-warehouse-summary is-empty">
            <div><h3>尚未配置可见仓库</h3><p>仓库库存迁移完成后，可在此按仓库维护入库、领用、归还和调拨。</p></div>
            ${canCreateWarehouses ? '<button class="primary-button" data-action="open-warehouse">新增仓库</button>' : ""}
          </section>`
    }
    <div class="toolbar">
      <div class="toolbar-actions">
        <label class="search-box"><span>⌕</span><input data-filter="inventorySearch" value="${escapeHtml(
          filterSearchDraftValue("inventorySearch"),
        )}" placeholder="搜索类型、品牌或型号..." /></label>
        <button class="secondary-button" data-action="apply-inventory-search">查询</button>
        <label class="select-box"><select data-filter="inventoryType">
          ${inventoryTypeFilterOptions()
            .map(
              (option) =>
                `<option value="${escapeHtml(option.value)}" ${
                  (state.filters.inventoryType || "") === option.value ? "selected" : ""
                }>${escapeHtml(option.label)}</option>`,
            )
            .join("")}
        </select></label>
        <label class="select-box"><select data-filter="inventoryBrand">
          ${inventoryBrandFilterOptions(state.filters.inventoryType || "")
            .map(
              (option) =>
                `<option value="${escapeHtml(option.value)}" ${
                  (state.filters.inventoryBrand || "") === option.value ? "selected" : ""
                }>${escapeHtml(option.label)}</option>`,
            )
            .join("")}
        </select></label>
        ${
          state.filters.inventorySearch || state.filters.inventoryType || state.filters.inventoryBrand
            ? '<button class="secondary-button" data-action="clear-inventory-filters">清除筛选</button>'
            : ""
        }
      </div>
      <span class="secondary-text">当前仓库显示 ${visibleModelCount} 个型号 · ${visibleBrandCount} 个品牌 · ${visibleQuantity} / ${totalQuantity} 件</span>
    </div>
    <div class="stats-grid compact">
      <div class="stat-card"><div class="stat-label"><span>设备类型</span><span class="stat-mark">T</span></div><div class="stat-value">${
        state.nonAssetTypes.length
      }</div><div class="stat-foot">库存一级分组</div></div>
      <div class="stat-card"><div class="stat-label"><span>品牌组</span><span class="stat-mark">B</span></div><div class="stat-value">${
        visibleBrandCount
      }</div><div class="stat-foot">当前仓库库存品牌</div></div>
      <div class="stat-card"><div class="stat-label"><span>型号组</span><span class="stat-mark">M</span></div><div class="stat-value">${
        warehouseInventoryModelCount(warehouseId)
      }</div><div class="stat-foot">当前仓库可用型号</div></div>
      <div class="stat-card"><div class="stat-label"><span>可用数量</span><span class="stat-mark">Q</span></div><div class="stat-value">${totalQuantity}</div><div class="stat-foot">未分配库存总量</div></div>
    </div>
    <section class="section-block">
      <div class="section-heading">
        <div><h2>类型 / 品牌 / 型号 / 数量</h2><span>已分配到人员名下的物资不在此库存中体现。</span></div>
        <div class="toolbar-actions inventory-tree-actions">
          <button class="secondary-button" data-action="expand-all-inventory" ${nodes.length ? "" : "disabled"}>展开全部</button>
          <button class="secondary-button" data-action="collapse-all-inventory" ${nodes.length ? "" : "disabled"}>收起全部</button>
        </div>
      </div>
      <div class="data-panel inventory-panel">${inventoryTreeRows() || '<div class="empty-state">当前没有库存分组</div>'}</div>
    </section>
    <section class="section-block">
      <div class="section-heading">
        <div><h2>采购入库信息</h2><span>${purchaseLogs.length} 条当前仓库入库记录，普通物资不在库存型号上显示入库日期</span></div>
        <div class="toolbar-actions">
          <button class="secondary-button" data-action="export-inventory-purchase" ${
            purchaseLogs.length && canExportCatalog ? "" : "disabled"
          }>导出当前仓库入库表</button>
        </div>
      </div>
      <div class="data-panel">${renderInventoryPurchaseTable(purchaseLogs)}</div>
    </section>
  `;
}

function renderWarehouseDirectory() {
  const warehouses = inventoryWarehousesForView();
  const canCreate = hasPermission("warehouse_management", "create");
  const canUpdate = hasPermission("warehouse_management", "update");
  const canDelete = hasPermission("warehouse_management", "delete");
  return `
    ${modalHeader("仓库管理", "维护仓库资料、组织归属和负责人；已有库存或流转记录的仓库不能删除。")}
    <section class="modal-section warehouse-directory-section">
      <div class="section-heading">
        <div><h2>仓库目录</h2><span>${warehouses.length} 个可见仓库</span></div>
        ${canCreate ? '<button type="button" class="primary-button" data-action="open-warehouse">新增仓库</button>' : ""}
      </div>
      <div class="data-panel">
        ${
          warehouses.length
            ? `<div class="table-wrap"><table class="warehouse-directory-table"><thead><tr><th>仓库</th><th>所属组织</th><th>负责人</th><th>联系方式</th><th>库存</th><th>状态</th><th>操作</th></tr></thead><tbody>${warehouses
                .map(
                  (item) => `<tr>
                    <td><div class="primary-text">${escapeHtml(item.name)}</div><div class="secondary-text mono">${escapeHtml(item.code || "—")}</div></td>
                    <td>${escapeHtml(orgPathName(item.orgId))}</td>
                    <td>${escapeHtml(item.managerName || "未指定")}</td>
                    <td><div>${escapeHtml(item.contactPhone || "—")}</div><div class="secondary-text">${escapeHtml(item.address || "")}</div></td>
                    <td>${warehouseInventoryModelCount(item.id)} 个型号 / ${warehouseInventoryTotal(item.id)} 件</td>
                    <td><span class="status-pill ${item.isActive ? "status-idle" : "status-retired"}">${
                      item.isActive ? "启用" : "已停用"
                    }</span></td>
                    <td><div class="inline-actions">
                      ${canUpdate ? `<button type="button" class="text-button" data-action="open-warehouse" data-id="${escapeHtml(item.id)}">编辑</button>` : ""}
                      ${
                        canDelete && item.code !== "WH-001"
                          ? `<button type="button" class="text-button danger" data-action="delete-warehouse" data-id="${escapeHtml(item.id)}">删除</button>`
                          : ""
                      }
                    </div></td>
                  </tr>`,
                )
                .join("")}</tbody></table></div>`
            : '<div class="empty-state">当前权限范围内暂无仓库</div>'
        }
      </div>
    </section>
    <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">关闭</button></div>
  `;
}

function openWarehouseDirectoryModal() {
  openModal(renderWarehouseDirectory(), true);
}

function openWarehouseModal(id = "") {
  const existing = inventoryWarehouseById(id);
  if (id && !existing) return showToast("未找到仓库记录，请刷新后重试。", true);
  const defaultOrgId = getRootOrgs()[0]?.id || state.orgs[0]?.id || "";
  const warehouse = existing || {
    id: "",
    code: nextWarehouseCode(),
    name: "",
    orgId: defaultOrgId,
    managerEmployeeId: "",
    contactPhone: "",
    address: "",
    isActive: true,
    remarks: "",
  };
  const isDefaultWarehouse = warehouse.code === "WH-001";
  openModal(
    `${modalHeader(id ? "编辑仓库" : "新增仓库", "仓库归属组织架构，负责人必须为该组织中的在职人员。")}
      <form data-form="warehouse" data-id="${escapeHtml(warehouse.id)}">
        <section class="modal-section">
          <div class="form-grid">
            ${inputField(
              "仓库编码",
              "code",
              warehouse.code,
              true,
              "WH-002",
              "text",
              "",
              isDefaultWarehouse ? 'readonly aria-readonly="true"' : 'maxlength="64" autocomplete="off"',
            )}
            ${inputField("仓库名称", "name", warehouse.name, true, "华东备件仓", "text", "", 'maxlength="120"')}
            ${selectField("所属组织", "orgId", warehouse.orgId, warehouseOrganizationOptions(warehouse.orgId), true)}
            ${selectField(
              "负责人",
              "managerEmployeeId",
              warehouse.managerEmployeeId,
              warehouseManagerOptions(warehouse.orgId, warehouse.managerEmployeeId),
            )}
            ${inputField("联系电话", "contactPhone", warehouse.contactPhone, false, "13800000000", "tel", "", 'maxlength="64"')}
            ${inputField("地址", "address", warehouse.address, false, "填写仓库所在地点", "text", "", 'maxlength="255"')}
            <label class="form-field warehouse-active-toggle"><span>仓库状态</span><span class="warehouse-active-control"><input type="checkbox" name="isActive" ${
              warehouse.isActive ? "checked" : ""
            } /> 启用仓库</span></label>
            ${textareaField("备注", "remarks", warehouse.remarks, false, "记录仓库用途、管理约定等", 3, 'maxlength="500"')}
          </div>
        </section>
        <div class="modal-footer">
          <button type="button" class="secondary-button" data-action="close-modal">取消</button>
          <button class="primary-button" type="submit">保存仓库</button>
        </div>
      </form>`,
    true,
  );
}

function refreshWarehouseManagerOptions(form) {
  if (!form || form.dataset.form !== "warehouse") return;
  const managerSelect = form.elements.managerEmployeeId;
  if (!managerSelect) return;
  replaceSelectOptions(
    managerSelect,
    warehouseManagerOptions(form.elements.orgId?.value || "", managerSelect.value || ""),
    managerSelect.value || "",
  );
}

async function handleWarehouseSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const id = form.dataset.id || "";
  const code = String(data.code || "").trim().toUpperCase();
  const name = String(data.name || "").trim();
  const orgId = String(data.orgId || "").trim();
  if (!code || !name || !orgId) return showToast("请填写仓库编码、仓库名称并选择所属组织。", true);
  const payload = {
    code,
    name,
    orgId,
    managerEmployeeId: String(data.managerEmployeeId || "").trim(),
    contactPhone: String(data.contactPhone || "").trim(),
    address: String(data.address || "").trim(),
    isActive: Boolean(form.elements.isActive?.checked),
    remarks: String(data.remarks || "").trim(),
  };
  try {
    await requestJson(`/api/inventory/warehouses${id ? `/${encodeURIComponent(id)}` : ""}`, {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    closeModal();
    await reloadDomainState();
    render();
    showToast(id ? "仓库已更新" : "仓库已创建");
  } catch (error) {
    showToast(`保存仓库失败：${error.message}`, true);
  }
}

async function deleteWarehouse(id) {
  const warehouse = inventoryWarehouseById(id);
  if (!warehouse) return showToast("未找到仓库记录，请刷新后重试。", true);
  if (warehouse.code === "WH-001") return showToast("默认仓库“仓库1”不能删除，可编辑或停用。", true);
  if (!window.confirm(`确定删除仓库“${warehouse.name}”吗？没有库存和历史流转记录的仓库才可删除。`)) return;
  try {
    await requestJson(`/api/inventory/warehouses/${encodeURIComponent(warehouse.id)}`, { method: "DELETE" });
    if (sameRecordId(inventoryWarehouseView, warehouse.id)) inventoryWarehouseView = "";
    closeModal();
    await reloadDomainState();
    render();
    showToast("仓库已删除");
  } catch (error) {
    showToast(`删除仓库失败：${error.message}`, true);
  }
}

function openInventoryTransferModal() {
  const warehouses = activeWarehouses();
  if (warehouses.length < 2) {
    return showToast("至少需要两个启用仓库才能进行库存调拨。", true);
  }
  const sourceWarehouseId = warehouses.some((warehouse) => sameRecordId(warehouse.id, inventoryWarehouseView))
    ? inventoryWarehouseView
    : warehouses[0].id;
  const targetWarehouseId = warehouses.find((warehouse) => !sameRecordId(warehouse.id, sourceWarehouseId))?.id || "";
  openModal(
    `${modalHeader("库存调拨", "调拨在同一事务内扣减调出仓库并增加调入仓库，同时写入物资流转记录和审计日志。")}
      <form data-form="inventory-transfer">
        <section class="modal-section">
          <div class="form-grid">
            ${selectField("调出仓库", "sourceWarehouseId", sourceWarehouseId, warehouseOptions(sourceWarehouseId, "请选择调出仓库"), true)}
            ${selectField("调入仓库", "targetWarehouseId", targetWarehouseId, warehouseOptions(targetWarehouseId, "请选择调入仓库"), true)}
            ${selectField(
              "物资型号",
              "modelId",
              "",
              inventoryModelOptionsForWarehouse(sourceWarehouseId, "", false),
              true,
            )}
            ${inputField("调拨数量", "quantity", 1, true, "1", "number", "1", "1")}
            ${textareaField("调拨备注", "note", "", false, "填写调拨原因、用途或交接说明", 3, 'maxlength="500"')}
          </div>
        </section>
        <div class="modal-footer">
          <button type="button" class="secondary-button" data-action="close-modal">取消</button>
          <button class="primary-button" type="submit">确认调拨</button>
        </div>
      </form>`,
  );
}

function refreshInventoryTransferModelOptions(form) {
  if (!form || form.dataset.form !== "inventory-transfer") return;
  const modelSelect = form.elements.modelId;
  if (!modelSelect) return;
  replaceSelectOptions(
    modelSelect,
    inventoryModelOptionsForWarehouse(form.elements.sourceWarehouseId?.value || "", modelSelect.value || "", false),
    modelSelect.value || "",
  );
}

async function handleInventoryTransferSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const sourceWarehouseId = String(data.sourceWarehouseId || "").trim();
  const targetWarehouseId = String(data.targetWarehouseId || "").trim();
  const modelId = String(data.modelId || "").trim();
  const quantity = Math.max(0, Number(data.quantity || 0));
  if (!sourceWarehouseId || !targetWarehouseId || !modelId || quantity < 1) {
    return showToast("请选择调出仓库、调入仓库、物资型号并填写调拨数量。", true);
  }
  if (sameRecordId(sourceWarehouseId, targetWarehouseId)) {
    return showToast("调出仓库和调入仓库不能相同。", true);
  }
  const available = inventoryModelQuantityInWarehouse(modelId, sourceWarehouseId);
  if (quantity > available) return showToast(`调出仓库可用库存不足，当前仅有 ${available} 件。`, true);
  try {
    await runCommand(
      "/api/inventory/transfers",
      {
        sourceWarehouseId,
        targetWarehouseId,
        modelId,
        quantity,
        note: String(data.note || "").trim(),
      },
      "inventory-transfer",
    );
    closeModal();
    await reloadDomainState();
    render();
    showToast("库存调拨已完成");
  } catch (error) {
    showToast(`库存调拨失败：${error.message}`, true);
  }
}

function renderFlowRecordNoteEditor(log) {
  const effectiveNote = String(log.effectiveNote || log.note || "").trim();
  const originalNote = String(log.originalNote || log.note || "").trim();
  const correctionCount = Array.isArray(log.noteCorrections) ? log.noteCorrections.length : 0;
  return `
    <div class="flow-record-note-editor">
      <div>${escapeHtml(effectiveNote || "—")}</div>
      ${
        correctionCount
          ? `<div class="secondary-text">已更正 ${escapeHtml(correctionCount)} 次${
              originalNote && originalNote !== effectiveNote ? ` · 原始：${escapeHtml(originalNote)}` : ""
            }</div>`
          : ""
      }
      <button class="text-button flow-record-note-save" type="button" data-action="edit-inventory-log-note" data-id="${escapeHtml(
        log.id,
      )}">更正备注</button>
    </div>
  `;
}

function renderFlowControlRecordTable(logs) {
  if (!logs.length) return '<div class="empty-state">暂无物资流转记录</div>';
  return `
    <div class="table-wrap">
      <table class="audit-table">
        <thead><tr><th>时间</th><th>业务类型</th><th>业务分类</th><th>物资类型</th><th>品牌 / 型号</th><th>数量</th><th>库存影响</th><th>调出方</th><th>接收方</th><th>关联人员</th><th>备注</th></tr></thead>
        <tbody>
          ${logs
            .map((log) => {
              const relatedEmployee = [log.relatedEmployeeName, log.relatedEmployeeNo].filter(Boolean).join(" / ");
              return `<tr>
                <td class="audit-time">${escapeHtml(formatDateTime(log.occurredAt))}</td>
                <td><span class="audit-action ${flowRecordActionClass(log)}">${escapeHtml(flowRecordActionLabel(log))}</span></td>
                <td>${escapeHtml(flowRecordCategory(log))}</td>
                <td>${escapeHtml(log.typeName || "未分类物资")}</td>
                <td><div class="primary-text">${escapeHtml(log.brandName || "未登记品牌")}</div><div class="secondary-text">${escapeHtml(
                  log.modelName || "未登记型号",
                )}</div></td>
                <td>${escapeHtml(log.quantity)}</td>
                <td><span class="audit-action ${flowRecordImpactClass(log)}">${escapeHtml(flowRecordStockImpact(log))}</span></td>
                <td>${escapeHtml(log.sourceLabel || "—")}</td>
                <td>${escapeHtml(log.targetLabel || "—")}</td>
                <td>${escapeHtml(relatedEmployee || "—")}</td>
                <td>${renderFlowRecordNoteEditor(log)}</td>
              </tr>`;
            })
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderFlowControlPage() {
  const records = getFilteredFlowRecords();
  const typeOptions = flowRecordTypeOptions();
  const actionOptions = flowRecordActionOptions();
  const categoryOptions = flowRecordCategoryOptions();
  return `
    <div class="page-intro">
      <div><h2>物资流转记录</h2><p>按物品、关联人员、流转类型、来源去向和时间区间查看自动登记的物资流转信息。</p></div>
      <div class="toolbar-actions">
        <button class="secondary-button" data-action="export-flow-records" ${records.length ? "" : "disabled"}>导出当前结果</button>
      </div>
    </div>
    <div class="toolbar flow-record-toolbar">
      <div class="toolbar-actions">
        <label class="search-box"><span>⌕</span><input data-filter="flowSearch" value="${escapeHtml(
          filterSearchDraftValue("flowSearch"),
        )}" placeholder="物品、品牌、型号或备注" /></label>
        <label class="select-box"><select data-filter="flowType">
          <option value="">全部物资类型</option>
          ${typeOptions
            .map(
              (option) =>
                `<option value="${escapeHtml(option)}" ${
                  state.filters.flowType === option ? "selected" : ""
                }>${escapeHtml(option)}</option>`,
            )
            .join("")}
        </select></label>
        <label class="select-box"><select data-filter="flowAction">
          <option value="">全部业务类型</option>
          ${actionOptions
            .map(
              (option) =>
                `<option value="${escapeHtml(option)}" ${
                  state.filters.flowAction === option ? "selected" : ""
                }>${escapeHtml(option)}</option>`,
            )
            .join("")}
        </select></label>
        <label class="select-box"><select data-filter="flowCategory">
          <option value="">全部业务分类</option>
          ${categoryOptions
            .map(
              (option) =>
                `<option value="${escapeHtml(option)}" ${
                  state.filters.flowCategory === option ? "selected" : ""
                }>${escapeHtml(option)}</option>`,
            )
            .join("")}
        </select></label>
        <label class="search-box flow-record-person-box"><span>人</span><input data-filter="flowEmployee" value="${escapeHtml(
          filterSearchDraftValue("flowEmployee"),
        )}" placeholder="人员姓名或编号" /></label>
        <label class="search-box flow-record-source-box"><span>向</span><input data-filter="flowSourceTarget" value="${escapeHtml(
          filterSearchDraftValue("flowSourceTarget"),
        )}" placeholder="来源或去向" /></label>
        <label class="select-box audit-date-box"><span>开始</span><input type="date" data-filter="flowStartDate" value="${escapeHtml(
          state.filters.flowStartDate || "",
        )}" /></label>
        <label class="select-box audit-date-box"><span>结束</span><input type="date" data-filter="flowEndDate" value="${escapeHtml(
          state.filters.flowEndDate || "",
        )}" /></label>
        <button class="secondary-button" data-action="apply-flow-record-filters">查询</button>
        ${
          hasFlowRecordFilters()
            ? '<button class="secondary-button" data-action="clear-flow-record-filters">清除筛选</button>'
            : ""
        }
      </div>
      <span class="secondary-text">显示 ${records.length} / ${state.inventoryMovementLogs.length} 条</span>
    </div>
    <section class="section-block">
      <div class="section-heading">
        <div><h2>物资流转记录表</h2><span>物资动作自动识别业务类型和业务分类，共 ${records.length} 条</span></div>
      </div>
      <div class="data-panel">${renderFlowControlRecordTable(records)}</div>
    </section>
  `;
}

function isComputerPurchaseLog(log) {
  const type = log?.typeId ? getType(log.typeId) : null;
  return isComputerInventoryType(type) || isComputerInventoryTypeName(log?.typeName || "");
}

function sortInventoryPurchaseLogs(logs) {
  return [...logs].sort((a, b) =>
    String(b.inboundDate || b.createdAt || "").localeCompare(String(a.inboundDate || a.createdAt || "")),
  );
}

function renderInventoryPurchaseNoteEditor(log) {
  return `
    <form class="purchase-note-editor" data-form="inventory-purchase-note" data-id="${escapeHtml(log.id)}">
      <input
        class="purchase-note-input"
        type="text"
        name="note"
        maxlength="500"
        value="${escapeHtml(log.note || "")}"
        placeholder="填写备注"
        aria-label="采购入库备注"
      />
      <button class="text-button purchase-note-save" type="submit">保存</button>
    </form>
  `;
}

function renderInventoryPurchaseRows(rows, computer = false) {
  return rows
    .map((log) => {
      if (computer) {
        return `<tr>
          <td class="audit-time">${escapeHtml(log.inboundDate || "—")}</td>
          <td>${escapeHtml(log.brandName || "—")}</td>
          <td class="primary-text purchase-model">${escapeHtml(log.modelName || "—")}</td>
          <td>${escapeHtml(log.quantity)}</td>
          <td>${escapeHtml(log.cpu || "—")}</td>
          <td>${escapeHtml(log.memory || "—")}</td>
          <td>${escapeHtml(log.storage || "—")}</td>
          <td>${escapeHtml(log.gpu || "—")}</td>
          <td>${escapeHtml(log.sourceLabel || "—")}</td>
          <td>${renderInventoryPurchaseNoteEditor(log)}</td>
        </tr>`;
      }
      return `<tr>
        <td class="audit-time">${escapeHtml(log.inboundDate || "—")}</td>
        <td>${escapeHtml(log.typeName || "—")}</td>
        <td>${escapeHtml(log.brandName || "—")}</td>
        <td class="primary-text purchase-model">${escapeHtml(log.modelName || "—")}</td>
        <td>${escapeHtml(log.quantity)}</td>
        <td>${escapeHtml(log.sourceLabel || "—")}</td>
        <td>${renderInventoryPurchaseNoteEditor(log)}</td>
      </tr>`;
    })
    .join("");
}

function renderInventoryPurchaseTable(logs) {
  if (!logs.length) return '<div class="empty-state">暂无采购入库信息</div>';
  const sortedLogs = sortInventoryPurchaseLogs(logs);
  const standardLogs = sortedLogs.filter((log) => !isComputerPurchaseLog(log));
  const computerLogs = sortedLogs.filter((log) => isComputerPurchaseLog(log));
  const sections = [];

  if (standardLogs.length) {
    sections.push(`
      <section class="purchase-table-group">
        <div class="purchase-table-heading">
          <strong>普通物资入库</strong>
          <span>${standardLogs.length} 条记录</span>
        </div>
        <div class="table-wrap">
          <table class="audit-table purchase-table purchase-table-standard">
            <thead><tr><th>入库时间</th><th>物资类型</th><th>品牌</th><th>型号</th><th>数量</th><th>来源</th><th>备注</th></tr></thead>
            <tbody>${renderInventoryPurchaseRows(standardLogs)}</tbody>
          </table>
        </div>
      </section>
    `);
  }

  if (computerLogs.length) {
    sections.push(`
      <section class="purchase-table-group">
        <div class="purchase-table-heading">
          <strong>办公终端入库</strong>
          <span>${computerLogs.length} 条记录</span>
        </div>
        <div class="table-wrap">
          <table class="audit-table purchase-table purchase-table-computer">
            <thead><tr><th>入库时间</th><th>品牌</th><th>型号</th><th>数量</th><th>CPU</th><th>内存</th><th>存储</th><th>显卡</th><th>来源</th><th>备注</th></tr></thead>
            <tbody>${renderInventoryPurchaseRows(computerLogs, true)}</tbody>
          </table>
        </div>
      </section>
    `);
  }

  return sections.join("");
}

function openInventoryBrandModal(typeId, id = "") {
  const type = getType(typeId);
  if (!type) return;
  const existing = getInventoryBrand(id);
  const brand = existing || { id: "", typeId, name: "", sortOrder: 1000 };
  openModal(
    `${modalHeader(id ? "编辑库存品牌" : "新增库存品牌", `${type.name} / 品牌分组`)}
      <form data-form="inventory-brand" data-id="${escapeHtml(brand.id)}" data-type-id="${escapeHtml(type.id)}">
        <div class="form-grid">${inputField("品牌名称", "name", brand.name, true, "罗技")}${inputField(
          "排序",
          "sortOrder",
          brand.sortOrder || 1000,
          true,
          "1000",
          "number",
          "0",
        )}</div>
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">保存品牌</button></div>
      </form>`,
  );
}

function openInventoryModelModal(typeId, brandId, id = "") {
  const type = getType(typeId);
  const brand = getInventoryBrand(brandId);
  if (!type || !brand) return;
  const computerModel = isComputerInventoryType(type);
  const existing = getInventoryModel(id);
  const warehouseId = ensureInventoryWarehouseView();
  const warehouse = inventoryWarehouseById(warehouseId);
  const model = existing || {
    id: "",
    typeId,
    brandId,
    name: "",
    quantity: 0,
    inboundDate: computerModel ? currentDateText() : "",
    cpu: "",
    memory: "",
    storage: "",
    gpu: "",
    sortOrder: 1000,
  };
  openModal(
    `${modalHeader(id ? "编辑库存型号" : "新增库存型号", `${type.name} / ${brand.name}`)}
      <form data-form="inventory-model" data-id="${escapeHtml(model.id)}" data-type-id="${escapeHtml(
        type.id,
      )}" data-brand-id="${escapeHtml(brand.id)}">
        <div class="form-grid">${warehouseSelectField(
          "库存仓库",
          "warehouseId",
          warehouseId,
          true,
          "请选择库存仓库",
        )}${inputField("型号", "name", model.name, true, "M332")}${inputField(
          "可用数量",
          "quantity",
          existing ? inventoryModelQuantityInWarehouse(existing.id, warehouseId) : 0,
          true,
          "0",
          "number",
          "0",
          "0",
        )}<div class="form-field inventory-model-warehouse-note"><span class="readonly-label">当前仓库</span><div class="readonly-value">${escapeHtml(
          warehouse?.name || "未选择仓库",
        )}</div></div>${computerModel ? `${inputField(
          "入库时间",
          "inboundDate",
          model.inboundDate || (id ? "" : currentDateText()),
          true,
          "",
          "date",
        )}${inputField(
          "CPU",
          "cpu",
          model.cpu || "",
          false,
          "i5-14500HX",
        )}${inputField("内存", "memory", model.memory || "", false, "16G")}${inputField(
          "存储",
          "storage",
          model.storage || "",
          false,
          "512G",
        )}${inputField("显卡", "gpu", model.gpu || "", false, "RTX4060TI")}` : ""}${inputField(
          "排序",
          "sortOrder",
          model.sortOrder || 1000,
          true,
          "1000",
          "number",
          "0",
        )}</div>
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">保存型号</button></div>
      </form>`,
  );
}

function findInventoryTypeByName(name) {
  const target = inventoryText(name);
  return state.nonAssetTypes.find((type) => inventoryText(type.name) === target || inventoryText(type.code) === target);
}

function findInventoryBrandByName(typeId, name) {
  const target = inventoryText(name);
  return inventoryBrandsForType(typeId).find((brand) => inventoryText(brand.name) === target);
}

function findInventoryModelByName(brandId, name) {
  const target = inventoryText(name);
  return inventoryModelsForBrand(brandId).find((model) => inventoryText(model.name) === target);
}

function renderInventoryImportComputerFields(typeName = "") {
  const visible = isComputerInventoryTypeName(typeName);
  const disabledAttr = visible ? "" : "disabled";
  return `
    <div class="form-grid" data-inventory-computer-config ${visible ? "" : "hidden"}>
      ${inputField("CPU", "cpu", "", false, "i5-14500HX", "text", "", disabledAttr)}
      ${inputField("内存", "memory", "", false, "16G", "text", "", disabledAttr)}
      ${inputField("存储", "storage", "", false, "512G", "text", "", disabledAttr)}
      ${inputField("显卡", "gpu", "", false, "RTX4060TI", "text", "", disabledAttr)}
    </div>
  `;
}

function toggleInventoryImportComputerFields(form) {
  if (!form || form.dataset.form !== "inventory-import") return;
  const panel = form.querySelector("[data-inventory-computer-config]");
  if (!panel) return;
  const visible = isComputerInventoryTypeName(form.elements.type?.value || "");
  panel.hidden = !visible;
  panel.querySelectorAll("input, select, textarea").forEach((field) => {
    field.disabled = !visible;
  });
  if (visible && form.elements.inboundDate && !form.elements.inboundDate.value) {
    form.elements.inboundDate.value = currentDateText();
  }
}

function openInventoryImportModal() {
  const type = state.nonAssetTypes.find((item) => item.id === state.filters.inventoryType) || null;
  const warehouseId = ensureInventoryWarehouseView();
  openModal(
    `${modalHeader("导入IT物资", "输入类型、品牌、型号和数量，已有项目会自动归类到对应层级，不存在则自动创建")}
      <form data-form="inventory-import">
        <div class="form-grid">
          ${warehouseSelectField("入库仓库", "warehouseId", warehouseId, true, "请选择入库仓库")}
          ${inputField("设备类型", "type", type?.name || "", true, "鼠标")}
          ${inputField("品牌", "brand", "", true, "罗技")}
          ${inputField("型号", "model", "", true, "M330")}
          ${inputField("数量", "quantity", 1, true, "1", "number", "1")}
          ${inputField("入库时间", "inboundDate", currentDateText(), true, "", "date")}
        </div>
        ${renderInventoryImportComputerFields(type?.name || "")}
        ${textareaField("备注", "note", "", false, "如采购入库、盘点回库、临时补货等，可作为来源日志标注", 3)}
        <div class="modal-footer">
          <button type="button" class="secondary-button" data-action="close-modal">取消</button>
          <button class="primary-button" type="submit">导入物资</button>
        </div>
      </form>`,
  );
}

function openInventoryMovementNoteModal(id) {
  const log = state.inventoryMovementLogs.find((item) => item.id === id);
  if (!log) return;
  const originalNote = String(log.originalNote || log.note || "").trim();
  const effectiveNote = String(log.effectiveNote || log.note || "").trim();
  const corrections = [...(Array.isArray(log.noteCorrections) ? log.noteCorrections : [])].sort((left, right) =>
    String(right.createdAt || "").localeCompare(String(left.createdAt || "")),
  );
  const history = corrections.length
    ? `<section class="modal-section">
        <div class="modal-section-title"><h3>更正历史</h3><span>每次更正均保留原始事务记录和审计日志。</span></div>
        <div class="audit-list">${corrections
          .map(
            (correction) => `<div class="audit-item">
              <div><strong>${escapeHtml(correction.correctedNote || "—")}</strong><span>${escapeHtml(
                correction.correctionReason || "",
              )}</span></div>
              <small>${escapeHtml(correction.createdBy || "系统")} · ${escapeHtml(
                formatDateTime(correction.createdAt || ""),
              )}</small>
            </div>`,
          )
          .join("")}</div>
      </section>`
    : '<section class="modal-section"><div class="empty-state">尚无备注更正记录</div></section>';
  openModal(
    `${modalHeader("更正物资流转备注", `${log.typeName} / ${[log.brandName, log.modelName].filter(Boolean).join(" / ")}`)}
      <form data-form="inventory-log-note-correction" data-id="${escapeHtml(log.id)}">
        <section class="modal-section">
          <div class="form-grid">
            ${textareaField("原始备注", "originalNote", originalNote || "—", false, "", 3, 'readonly tabindex="-1"')}
            ${textareaField("当前有效备注", "currentNote", effectiveNote || "—", false, "", 3, 'readonly tabindex="-1"')}
          </div>
        </section>
        <section class="modal-section">
          <div class="form-grid">
            ${textareaField("更正后的备注", "correctedNote", effectiveNote, true, "填写更正后的说明", 4)}
            ${textareaField("更正原因", "correctionReason", "", true, "说明为什么需要更正，以及核验依据", 4)}
          </div>
        </section>
        ${history}
        <div class="modal-footer">
          <button type="button" class="secondary-button" data-action="close-modal">取消</button>
          <button class="primary-button" type="submit">提交更正</button>
        </div>
      </form>`,
  );
}

async function handleInventoryMovementNoteSubmit(form) {
  const log = state.inventoryMovementLogs.find((item) => item.id === form.dataset.id);
  if (!log) return;
  const data = Object.fromEntries(new FormData(form).entries());
  const correctedNote = String(data.correctedNote || "").trim();
  const correctionReason = String(data.correctionReason || "").trim();
  if (!correctedNote || !correctionReason) {
    showToast("请填写更正后的备注和更正原因。", true);
    return;
  }
  if (correctedNote === String(log.effectiveNote || log.note || "").trim()) {
    showToast("备注未发生变化");
    return;
  }
  try {
    await runCommand(
      `/api/inventory/movement-logs/${encodeURIComponent(log.id)}/note-corrections`,
      { correctedNote, correctionReason },
      "inventory-movement-note-correction",
    );
    closeModal();
    await reloadDomainState();
    render();
    showToast("流转备注已更正，原始事务记录和更正历史已保留。");
  } catch (error) {
    showToast(`更正流转备注失败：${error.message}`, true);
  }
}

function handleInventoryPurchaseNoteSubmit(form) {
  const log = state.inventoryPurchaseLogs.find((item) => item.id === form.dataset.id);
  if (!log) return;
  const data = Object.fromEntries(new FormData(form).entries());
  const note = String(data.note || "").trim();
  if (note === String(log.note || "").trim()) {
    showToast("备注未发生变化");
    return;
  }
  showToast("采购入库日志为事务结果，只能通过新的入库命令产生，暂不支持单独改写。", true);
}

function getVisibleOrgIdsForEmployees(search, employeeIdSet, treeFilterActive = false) {
  const orgFilter = state.filters.employeeOrg || "";
  if (!treeFilterActive) {
    return new Set(state.orgs.map((org) => org.id));
  }

  const visible = new Set();
  if (orgFilter && orgFilter !== "__unassigned__" && getOrg(orgFilter)) {
    addOrgWithAncestors(visible, orgFilter);
    addOrgWithDescendants(visible, orgFilter);
  }

  state.orgs.forEach((org) => {
    const orgText = `${org.code} ${org.name} ${orgPathName(org.id)}`.toLowerCase();
    if (search && orgText.includes(search)) {
      addOrgWithAncestors(visible, org.id);
      addOrgWithDescendants(visible, org.id);
    }
  });

  state.employees.forEach((employee) => {
    if (employeeIdSet.has(employee.id) && employee.orgId && getOrg(employee.orgId)) {
      addOrgWithAncestors(visible, employee.orgId);
    }
  });

  return visible;
}

function addOrgWithAncestors(bucket, orgId) {
  let current = getOrg(orgId);
  const visited = new Set();
  while (current && !visited.has(current.id)) {
    visited.add(current.id);
    bucket.add(current.id);
    current = current.parentId ? getOrg(current.parentId) : null;
  }
}

function addOrgWithDescendants(bucket, orgId) {
  bucket.add(orgId);
  getDescendantOrgIds(orgId).forEach((childId) => bucket.add(childId));
}

function renderEmployeeOrgNode(org, context) {
  const depth = getOrgDepth(org.id);
  const children = getOrgChildren(org.id).filter((child) => !context.searchActive || context.visibleOrgIds.has(child.id));
  const directEmployees = sortEmployees(
    state.employees.filter(
      (employee) => employee.orgId === org.id && (!context.searchActive || context.employeeIdSet.has(employee.id)),
    ),
  );
  const hasVisibleBody = directEmployees.length || children.length;
  const expanded = context.searchActive ? true : isOrgExpanded(org.id);
  const summary = getOrgSummary(org.id);

  if (context.searchActive && !context.visibleOrgIds.has(org.id) && !hasVisibleBody) {
    return "";
  }

  return `
    <section class="tree-node" style="--tree-depth:${depth}">
      <div class="tree-node-header">
        <button class="tree-toggle" data-action="toggle-org" data-id="${escapeHtml(org.id)}" aria-expanded="${
          expanded ? "true" : "false"
        }" title="${expanded ? "收起部门" : "展开部门"}">${expanded ? "▾" : "▸"}</button>
        <div class="tree-node-main">
          <div class="tree-node-title"><span>${escapeHtml(org.name)}</span><span class="tree-node-code">${escapeHtml(
            org.code,
          )}</span></div>
          <div class="tree-node-meta">排序 ${escapeHtml(org.sortOrder)} · ${summary.employees} 人 · ${summary.computers} 台办公终端 · ${escapeHtml(
            orgPathName(org.id),
          )}</div>
        </div>
        <div class="inline-actions">
          <button class="text-button" data-action="open-employee" data-org-id="${escapeHtml(org.id)}">新增人员</button>
          <button class="text-button" data-action="open-org" data-id="${escapeHtml(org.id)}" data-parent-id="${escapeHtml(
            org.parentId || "",
          )}">编辑组织</button>
          <button class="text-button" data-action="open-org" data-parent-id="${escapeHtml(org.id)}">新增下级</button>
        </div>
      </div>
      ${
        expanded
          ? `<div class="tree-node-body">
              ${directEmployees.map((employee) => renderEmployeeTreeRow(employee)).join("")}
              ${children.map((child) => renderEmployeeOrgNode(child, context)).join("")}
              ${!hasVisibleBody ? '<div class="tree-empty">当前组织下暂无人员</div>' : ""}
            </div>`
          : ""
      }
    </section>
  `;
}

function renderEmployeeTreeRow(employee) {
  return `
    <article class="employee-tree-row">
      <div class="employee-tree-selector">
        <input type="checkbox" class="row-selector" data-action="toggle-employee-selection" data-id="${escapeHtml(
          employee.id,
        )}" ${state.selectedEmployeeIds.includes(employee.id) ? "checked" : ""} title="选择人员" />
      </div>
      <div class="employee-tree-main">
        <div class="employee-tree-head">
          <div>
            <button class="employee-tree-title employee-tree-title-button" data-action="open-employee" data-id="${escapeHtml(
              employee.id,
            )}" title="查看人员信息">${escapeHtml(employee.name)} <span class="employee-tree-code">${escapeHtml(
              employee.employeeNo,
            )}</span></button>
            <div class="employee-tree-meta">${escapeHtml(
              `${orgName(employee.orgId)} · ${employee.department || "未填写部门"} · ${employee.position || "未填写岗位"}`,
            )}</div>
          </div>
          <div class="employee-tree-status">${statusPill(employee.status)}</div>
        </div>
        <div class="employee-tree-devices">${deviceChips(employee)}</div>
      </div>
      <div class="inline-actions">
        <button class="text-button" data-action="manage-devices" data-id="${escapeHtml(employee.id)}">设备</button>
        <button class="text-button" data-action="open-employee" data-id="${escapeHtml(employee.id)}">编辑</button>
        ${
          hasPermission("employees", "update") && employee.status !== "left"
            ? `<button class="text-button danger" data-action="open-employee-offboard" data-id="${escapeHtml(
                employee.id,
              )}">${employee.status === "shared" ? "删除" : "办理离职"}</button>`
            : ""
        }
      </div>
    </article>
  `;
}

function renderUnassignedEmployeeBlock(employees) {
  return `
    <section class="tree-node tree-node-unassigned" style="--tree-depth:0">
      <div class="tree-node-header">
        <button class="tree-toggle is-placeholder">•</button>
        <div class="tree-node-main">
          <div class="tree-node-title"><span>未分配组织</span><span class="tree-node-code">UNASSIGNED</span></div>
          <div class="tree-node-meta">${employees.length} 人</div>
        </div>
      </div>
      <div class="tree-node-body">
        ${employees.map((employee) => renderEmployeeTreeRow(employee)).join("")}
      </div>
    </section>
  `;
}

function renderDictionaryPage() {
  const search = (state.filters.dictionary || "").trim().toLowerCase();
  const visibleOrgIds = getVisibleOrgIdsForDictionary(search);
  const visibleRoots = getRootOrgs().filter((org) => !search || visibleOrgIds.has(org.id));
  const types = state.nonAssetTypes.filter((type) => `${type.code} ${type.name}`.toLowerCase().includes(search));

  return `
    <div class="page-intro">
      <div><h2>基础字典</h2><p>组织树结构与人员页面共享同一套层级和排序规则</p></div>
      <div class="toolbar-actions">
        <button class="secondary-button" data-action="open-type">＋ 新增设备类型</button>
        <button class="primary-button" data-action="open-org">＋ 新增根组织</button>
      </div>
    </div>
    <div class="toolbar">
      <label class="search-box"><span>⌕</span><input data-filter="dictionary" value="${escapeHtml(
        state.filters.dictionary || "",
      )}" placeholder="搜索组织编码、组织名称或设备类型..." /></label>
    </div>
    <div class="dictionary-grid">
      <section class="section-block">
        <div class="section-heading"><div><h2>组织架构树</h2><span>${state.orgs.length} 个组织</span></div></div>
        <div class="data-panel tree-panel">
          ${
            visibleRoots.length
              ? visibleRoots.map((org) => renderDictionaryOrgNode(org, { visibleOrgIds, searchActive: Boolean(search) })).join("")
              : '<div class="empty-state">暂无符合条件的组织</div>'
          }
        </div>
      </section>
      <section class="section-block">
        <div class="section-heading"><div><h2>非资产设备类型</h2><span>${types.length} 个类型</span></div></div>
        <div class="data-panel">${renderTypeTable(types)}</div>
      </section>
    </div>
  `;
}

function getVisibleOrgIdsForDictionary(search) {
  if (!search) return new Set(state.orgs.map((org) => org.id));
  const visible = new Set();
  state.orgs.forEach((org) => {
    const text = `${org.code} ${org.name} ${orgPathName(org.id)}`.toLowerCase();
    if (text.includes(search)) {
      addOrgWithAncestors(visible, org.id);
      addOrgWithDescendants(visible, org.id);
    }
  });
  return visible;
}

function renderDictionaryOrgNode(org, context) {
  const depth = getOrgDepth(org.id);
  const children = getOrgChildren(org.id).filter((child) => !context.searchActive || context.visibleOrgIds.has(child.id));
  const expanded = context.searchActive ? true : isOrgExpanded(org.id);
  const summary = getOrgSummary(org.id);

  return `
    <section class="tree-node" style="--tree-depth:${depth}">
      <div class="tree-node-header">
        <button class="tree-toggle" data-action="toggle-org" data-id="${escapeHtml(org.id)}" aria-expanded="${
          expanded ? "true" : "false"
        }" title="${expanded ? "收起组织" : "展开组织"}">${expanded ? "▾" : "▸"}</button>
        <div class="tree-node-main">
          <div class="tree-node-title"><span>${escapeHtml(org.name)}</span><span class="tree-node-code">${escapeHtml(
            org.code,
          )}</span></div>
          <div class="tree-node-meta">排序 ${escapeHtml(org.sortOrder)} · ${summary.employees} 人 · ${summary.computers} 台办公终端 · ${
            summary.children
          } 个下级</div>
        </div>
        <div class="inline-actions">
          <button class="text-button" data-action="open-org" data-parent-id="${escapeHtml(org.id)}">新增下级</button>
          <button class="text-button" data-action="open-org" data-id="${escapeHtml(org.id)}">编辑</button>
          <button class="text-button danger" data-action="delete-org" data-id="${escapeHtml(org.id)}">删除</button>
        </div>
      </div>
      ${
        expanded
          ? `<div class="tree-node-body">
              ${children.map((child) => renderDictionaryOrgNode(child, context)).join("")}
              ${
                !children.length
                  ? `<div class="tree-empty">组织路径：${escapeHtml(orgPathName(org.id))}</div>`
                  : ""
              }
            </div>`
          : ""
      }
    </section>
  `;
}

function renderTypeTable(types) {
  if (!types.length) return '<div class="empty-state">暂无符合条件的设备类型</div>';
  return `<div class="table-wrap"><table><thead><tr><th>编码</th><th>名称</th><th>计量单位</th><th>引用人数</th><th>操作</th></tr></thead><tbody>
    ${types
      .map((type) => {
        const usageCount = state.employees.filter((employee) =>
          getNonAssetItems(employee).some((item) => item.typeId === type.id && Number(item.quantity) > 0),
        ).length;
        return `<tr>
          <td class="mono">${escapeHtml(type.code)}</td>
          <td class="primary-text">${escapeHtml(type.name)}</td>
          <td>${escapeHtml(type.unit || "件")}</td>
          <td>${usageCount}</td>
          <td><div class="inline-actions">
            <button class="text-button" data-action="open-type" data-id="${escapeHtml(type.id)}">编辑</button>
            <button class="text-button danger" data-action="delete-type" data-id="${escapeHtml(type.id)}" ${
              isProtectedInventoryType(type) ? 'disabled title="系统保留类型不可删除"' : ""
            }>删除</button>
          </div></td>
        </tr>`;
      })
      .join("")}
  </tbody></table></div>`;
}

function scrapKindLabel(kind) {
  return kind === "asset" ? "办公终端" : "IT物资";
}

function scrapRecordTitle(record) {
  if (record.kind === "asset") return record.deviceName || "办公终端";
  return [record.brandName, record.modelName].filter(Boolean).join(" ") || record.typeName || "IT物资";
}

function scrapRecordSubtitle(record) {
  if (record.kind === "asset") {
    return [record.brandName, record.modelName].filter(Boolean).join(" · ") || "未填写品牌型号";
  }
  return [record.typeName, record.warehouseName].filter(Boolean).join(" · ") || "未关联库存类型";
}

function hasScrapFilters() {
  return Boolean(
    String(state.filters.scrapKind || "").trim() || String(state.filters.scrapSearch || "").trim(),
  );
}

function getFilteredScrapRecords() {
  const kind = String(state.filters.scrapKind || "");
  const search = String(state.filters.scrapSearch || "").trim().toLowerCase();
  return (scrapState.records || []).filter((record) => {
    if (kind && record.kind !== kind) return false;
    if (!search) return true;
    return [
      record.deviceName,
      record.brandName,
      record.modelName,
      record.typeName,
      record.reason,
      record.employeeName,
      record.employeeNo,
      record.operatedByName,
      record.notes,
      record.fixedAssetCode,
      record.snSt,
      record.warehouseName,
    ].some((value) => String(value || "").toLowerCase().includes(search));
  });
}

function applyScrapFilters() {
  state.filters.scrapSearch = String(filterSearchDrafts.scrapSearch ?? "").trim();
  persistState(false);
  render();
}

function clearScrapFilters() {
  state.filters.scrapKind = "";
  state.filters.scrapSearch = "";
  filterSearchDrafts.scrapSearch = "";
  persistState(false);
  render();
}

function renderScrapRecordTable(records) {
  if (!records.length) return '<div class="empty-state">暂无符合条件报废记录</div>';
  return `
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>报废时间</th><th>类型</th><th>物品</th><th>数量</th><th>使用人</th>
          <th>报废原因</th><th>操作人</th><th>库存影响</th><th>操作</th>
        </tr></thead>
        <tbody>
          ${records
            .map(
              (record) => `<tr>
                <td class="mono">${escapeHtml(record.scrapAt || "")}</td>
                <td>${escapeHtml(scrapKindLabel(record.kind))}</td>
                <td><div class="primary-text">${escapeHtml(scrapRecordTitle(record))}</div><div class="secondary-text">${escapeHtml(
                  scrapRecordSubtitle(record),
                )}</div></td>
                <td>${escapeHtml(`${Number(record.quantity || 0) || 1} 件`)}</td>
                <td>${
                  record.employeeName
                    ? `<div class="primary-text">${escapeHtml(record.employeeName)}</div><div class="secondary-text">${escapeHtml(
                        record.employeeNo || "",
                      )}</div>`
                    : '<span class="secondary-text">未登记</span>'
                }</td>
                <td>${escapeHtml(record.reason || "未填写")}</td>
                <td>${escapeHtml(record.operatedByName || "—")}</td>
                <td>${
                  Number(record.stockAdjusted) === 1
                    ? '<span class="secondary-text">已扣库存 · 不返还</span>'
                    : '<span class="secondary-text">未扣库存 · 无变化</span>'
                }</td>
                <td><div class="inline-actions"><button class="text-button" data-action="open-scrap-record" data-id="${escapeHtml(
                  `${record.kind}:${record.id}`,
                )}">详情</button></div></td>
              </tr>`,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderScrapRecordsPage() {
  const records = getFilteredScrapRecords();
  const total = (scrapState.records || []).length;
  return `
    <div class="page-intro">
      <div><h2>报废记录</h2><p>共 ${total} 条 · 报废物资不回收、不回补库存，办公终端报废后软归档并保留追溯</p></div>
      <div class="toolbar-actions">
        <button class="secondary-button" data-action="refresh-scrap-records">刷新</button>
        <button class="secondary-button" data-action="export-scrap-records" ${records.length ? "" : "disabled"}>导出当前结果</button>
      </div>
    </div>
    <div class="toolbar">
      <div class="toolbar-actions">
        <label class="search-box"><span>⌕</span><input data-filter="scrapSearch" value="${escapeHtml(
          filterSearchDraftValue("scrapSearch"),
        )}" placeholder="物品、型号、人员、报废原因或备注" /></label>
        <label class="select-box"><select data-filter="scrapKind">
          <option value="">全部类型</option>
          <option value="inventory" ${state.filters.scrapKind === "inventory" ? "selected" : ""}>IT物资</option>
          <option value="asset" ${state.filters.scrapKind === "asset" ? "selected" : ""}>办公终端</option>
        </select></label>
        <button class="secondary-button" data-action="apply-scrap-filters">查询</button>
        ${
          hasScrapFilters()
            ? '<button class="secondary-button" data-action="clear-scrap-filters">清除筛选</button>'
            : ""
        }
      </div>
      <span class="secondary-text">显示 ${records.length} / ${total} 条</span>
    </div>
    <div class="data-panel">${renderScrapRecordTable(records)}</div>
  `;
}

function scrapRecordDetailFields(record) {
  if (record.kind === "asset") {
    return [
      ["报废时间", record.scrapAt],
      ["资产编号", record.fixedAssetCode],
      ["设备名", record.deviceName],
      ["设备类型", deviceTypeLabel(record.deviceType)],
      ["品牌型号", [record.brandName, record.modelName].filter(Boolean).join(" · ")],
      ["CPU", record.cpu],
      ["内存", record.memory],
      ["存储", record.storage],
      ["显卡", record.gpu],
      ["SN / ST", record.snSt],
      ["报废前状态", statusLabels[record.previousStatus] || record.previousStatus],
      ["使用人员", [record.employeeName, record.employeeNo].filter(Boolean).join(" · ")],
      ["报废原因", record.reason],
      ["操作人", record.operatedByName],
      ["备注", record.notes],
      ["附件说明", record.attachmentRef],
    ];
  }
  return [
    ["报废时间", record.scrapAt],
    ["物资类型", record.typeName],
    ["品牌型号", [record.brandName, record.modelName].filter(Boolean).join(" · ")],
    ["数量", `${Number(record.quantity || 0) || 1} 件`],
    ["使用人员", [record.employeeName, record.employeeNo].filter(Boolean).join(" · ")],
    ["原领用仓库", record.warehouseName],
    ["库存处理", Number(record.stockAdjusted) === 1 ? "已扣减库存，报废不返还" : "未扣减库存，无库存变化"],
    ["报废原因", record.reason],
    ["操作人", record.operatedByName],
    ["备注", record.notes],
    ["附件说明", record.attachmentRef],
  ];
}

async function openScrapRecordDetail(recordId) {
  try {
    const payload = await requestJson(`${API_SCRAP_RECORDS_URL}/${encodeURIComponent(recordId)}`);
    const record = payload.record || {};
    openModal(
      `${modalHeader(
        `报废详情 · ${scrapRecordTitle(record)}`,
        `${scrapKindLabel(record.kind)} · ${record.scrapAt || ""}`,
      )}
        <section class="modal-section">
          <div class="scrap-detail-grid">
            ${scrapRecordDetailFields(record)
              .map(
                ([label, value]) =>
                  `<div class="scrap-detail-item"><span class="secondary-text">${escapeHtml(
                    label,
                  )}</span><span class="primary-text">${escapeHtml(
                    String(value || "").trim() || "—",
                  )}</span></div>`,
              )
              .join("")}
          </div>
        </section>
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">关闭</button></div>`,
      true,
    );
  } catch (error) {
    showToast(`报废记录加载失败：${error.message}`, true);
  }
}

function exportScrapRecords() {
  const records = getFilteredScrapRecords();
  if (!records.length) return showToast("当前筛选条件下没有可导出的报废记录", true);
  downloadExcel(`办公资产-报废记录-${exportDateStamp()}.xls`, [
    {
      name: "报废记录",
      headers: [
        "报废时间",
        "类型",
        "物品",
        "品牌",
        "型号",
        "数量",
        "固资编码",
        "SN/ST",
        "使用人",
        "人员编号",
        "报废原因",
        "库存影响",
        "操作人",
        "备注",
        "附件说明",
      ],
      rows: records.map((record) => [
        record.scrapAt || "",
        scrapKindLabel(record.kind),
        record.kind === "asset" ? record.deviceName || "" : record.typeName || "",
        record.brandName || "",
        record.modelName || "",
        Number(record.quantity || 0) || 1,
        record.fixedAssetCode || "",
        record.snSt || "",
        record.employeeName || "",
        record.employeeNo || "",
        record.reason || "",
        Number(record.stockAdjusted) === 1 ? "已扣库存不返还" : "未扣库存无变化",
        record.operatedByName || "",
        record.notes || "",
        record.attachmentRef || "",
      ]),
    },
  ]);
  showToast(`已导出 ${records.length} 条报废记录`);
}

function scrapReasonOptions(kind) {
  const options = scrapReasonsFor(kind).map((reason) => ({ value: reason.code, label: reason.name }));
  return options.length ? options : [{ value: "other", label: "其他原因" }];
}

function scrapFormFields(kind) {
  return `
    <div class="form-grid three">
      ${selectField("报废原因", "reasonCode", "damaged_unrepairable", scrapReasonOptions(kind), true)}
      ${inputField("其他原因说明", "reason", "", false, "选择“其他原因”时填写")}
    </div>
    <div class="form-grid">
      ${inputField("备注", "notes", "", false, "可填写故障现象、处理结果等")}
      ${inputField("附件说明", "attachmentRef", "", false, "预留字段：可填写附件编号或说明")}
    </div>`;
}

async function openComputerScrapModal(computerId, deviceName) {
  if (!computerId) return;
  await loadScrapReasons();
  openModal(
    `${modalHeader(
      `办公终端报废 · ${deviceName || ""}`,
      "报废后设备退出在用台账并软归档，不回收库存且保留报废记录",
    )}
      <form data-form="scrap" data-kind="asset" data-computer-id="${escapeHtml(computerId)}">
        <section class="modal-section">
          ${scrapFormFields("asset")}
          <p class="secondary-text">报废后：设备不再显示为在用设备，不增加任何库存，资产主记录保留用于追溯。</p>
        </section>
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">确认报废</button></div>
      </form>`,
    true,
  );
}

async function openUsageScrapModal(kind, usageRecordId, employeeId, label) {
  if (!usageRecordId) return;
  await loadScrapReasons();
  const allocationType = kind === "monitor" ? "monitor" : "non_asset";
  openModal(
    `${modalHeader(
      `物资报废 · ${label || ""}`,
      "发放中的 IT 物资直接报废，不进入回收仓库、不增加库存",
    )}
      <form data-form="scrap" data-kind="inventory" data-allocation-type="${escapeHtml(
        allocationType,
      )}" data-usage-record-id="${escapeHtml(usageRecordId)}" data-employee-id="${escapeHtml(employeeId || "")}">
        <section class="modal-section">
          ${scrapFormFields("inventory")}
          <p class="secondary-text">报废后：使用记录保留并标记为已报废，已扣减的库存不返还，未扣库存的登记物资不产生库存变化。</p>
        </section>
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">确认报废</button></div>
      </form>`,
    true,
  );
}

async function handleScrapSubmit(form) {
  const kind = form.dataset.kind;
  const payload = {
    reasonCode: String(form.querySelector('[name="reasonCode"]')?.value || "").trim(),
    reason: String(form.querySelector('[name="reason"]')?.value || "").trim(),
    notes: String(form.querySelector('[name="notes"]')?.value || "").trim(),
    attachmentRef: String(form.querySelector('[name="attachmentRef"]')?.value || "").trim(),
  };
  const submitButton = form.querySelector('button[type="submit"]');
  if (submitButton) submitButton.disabled = true;
  try {
    if (kind === "asset") {
      const computerId = form.dataset.computerId || "";
      const result = await scrapComputerAsset(computerId, payload);
      closeModal();
      await reloadDomainState();
      showToast(`办公终端已报废并归档：${result.deviceName || ""}`);
    } else {
      const employeeId = form.dataset.employeeId || "";
      const result = await scrapInventoryUsage(
        form.dataset.allocationType,
        form.dataset.usageRecordId,
        payload,
      );
      closeModal();
      await reloadDomainState();
      showToast(`物资已报废，数量 ${result.quantity || 0}，库存未发生变化`);
      if (employeeId) openDeviceManager(employeeId);
    }
    if (scrapState.loaded && state.page === "scrapRecords") {
      await loadScrapRecords();
    }
    render();
  } catch (error) {
    showToast(`报废失败：${error.message}`, true);
  } finally {
    if (submitButton) submitButton.disabled = false;
  }
}

function openModal(content, wide = false) {
  const root = document.querySelector("#modalRoot");
  root.innerHTML = `<dialog class="modal-dialog" data-action="close-modal">
    <div class="modal-panel ${wide ? "wide" : ""}">${content}</div>
  </dialog>`;
  const dialog = root.querySelector("dialog");
  document.body.classList.add("modal-open");
  if (!dialog) return;
  // 原生 <dialog> 提供 ESC 关闭、焦点陷阱与顶层渲染；关闭时统一清理内容。
  dialog.addEventListener("close", () => {
    if (document.querySelector("#modalRoot dialog") === dialog) {
      root.innerHTML = "";
      document.body.classList.remove("modal-open");
    }
  });
  if (typeof dialog.showModal === "function") {
    dialog.showModal();
  } else {
    dialog.setAttribute("open", "");
  }
}

function closeModal() {
  const root = document.querySelector("#modalRoot");
  const dialog = root.querySelector("dialog");
  if (dialog && dialog.open && typeof dialog.close === "function") {
    dialog.close();
  }
  root.innerHTML = "";
  document.body.classList.remove("modal-open");
}

function modalHeader(title, description) {
  return `<div class="modal-header"><div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(description)}</p></div><button class="close-button" data-action="close-modal" title="关闭">×</button></div>`;
}

function openComputerModal(id = "") {
  const computer = state.computers.find((item) => item.id === id) || {
    id: "",
    deviceName: "",
    orgId: state.orgs[0]?.id || "",
    deviceType: "laptop",
    brand: "",
    model: "",
    inventoryModelId: "",
    inventoryStockAdjusted: false,
    registrationMode: "custom",
    warehouseId: "",
    cpu: "",
    memory: "",
    storage: "",
    gpu: "",
    fixedAssetCode: "",
    purchaseDate: "",
    registeredDate: "",
    snSt: "",
    wifiMac: "",
    ethernetMac: "",
    location: "",
    department: "",
    status: "idle",
    userId: "",
  };
  const isEditing = Boolean(id);
  openModal(
    `${modalHeader(isEditing ? "编辑办公终端" : "新增办公终端", "登记设备基础信息、资产信息和当前使用人")}
      <form data-form="computer" data-id="${escapeHtml(computer.id)}">
        <section class="modal-section">
          <div class="form-grid three">
            ${inputField("设备名", "deviceName", computer.deviceName, true, "PC-IT-0001")}
            ${selectField(
              "设备类型",
              "deviceType",
              computer.deviceType,
              Object.entries(deviceTypeLabels).map(([value, label]) => ({ value, label })),
              true,
            )}
            ${selectField(
              "IT 资产状态",
              "status",
              computer.status,
              ["in_use", "idle", "repair", "retired", "lost"].map((value) => ({
                value,
                label: statusLabels[value],
              })),
              true,
            )}
            ${renderComputerInventorySelectionFields(computer, isEditing)}
            ${selectField(
              "所属组织",
              "orgId",
              computer.orgId,
              getOrgSelectOptions({ includeBlank: true }),
              false,
            )}
          </div>
        </section>
        <section class="modal-section">
          <div class="form-grid three">
            ${inputField("CPU", "cpu", computer.cpu, false, "Intel Core i5-12400")}
            ${inputField("内存", "memory", computer.memory, false, "16GB")}
            ${inputField("存储", "storage", computer.storage, false, "512GB SSD")}
            ${inputField("显卡", "gpu", computer.gpu, false, "集成显卡 / RTX 4060")}
          </div>
        </section>
        <section class="modal-section">
          <div class="form-grid three">
            ${inputField("固资编码", "fixedAssetCode", computer.fixedAssetCode, false, "FA-2026-0001")}
            ${inputField("SN / ST", "snSt", computer.snSt, false, "序列号")}
            ${inputField("位置", "location", computer.location, false, "总部 / IT")}
            ${inputField("购置日期", "purchaseDate", computer.purchaseDate, false, "", "date")}
            ${inputField("注册日期", "registeredDate", computer.registeredDate, false, "", "date")}
            ${inputField("Wifi MAC", "wifiMac", computer.wifiMac, false, "11-22-33-44-55-66")}
            ${inputField("网口 MAC", "ethernetMac", computer.ethernetMac, false, "11-22-33-44-55-66")}
            ${inputField("部门", "department", computer.department, false, "IT")}
          </div>
        </section>
        <section class="modal-section">
          <div class="form-grid">
            ${selectField(
              "使用用户",
              "userId",
              computer.userId || "",
              [{ value: "", label: "未分配" }].concat(
                sortEmployees(state.employees).map((employee) => ({
                  value: employee.id,
                  label: `${employee.name} · ${employee.employeeNo} · ${orgName(employee.orgId)}`,
                })),
              ),
              false,
            )}
            ${inputField("备注", "remarks", computer.remarks || "", false, "可填写采购批次、工单号等")}
          </div>
        </section>
        ${
          isEditing
            ? `<section class="modal-section">
                <div class="modal-section-title"><div><h3>设备流转记录</h3><span>分配、归还与生命周期状态变更</span></div></div>
                <div class="computer-movement-history" data-computer-movement-history="${escapeHtml(computer.id)}">
                  <div class="empty-state">正在加载设备流转记录...</div>
                </div>
              </section>`
            : ""
        }
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">保存办公终端</button></div>
      </form>`,
    true,
  );
  const computerForm = document.querySelector('form[data-form="computer"]');
  if (computerForm && !isEditing) updateComputerRegistrationFields(computerForm, "registrationMode");
  if (isEditing) loadComputerMovementHistory(computer.id);
}

function computerMovementEventLabel(event) {
  if (event.type === "assigned") return "分配";
  if (event.type === "returned") return "归还";
  return "状态变更";
}

function renderComputerMovementHistory(events) {
  if (!events.length) return '<div class="empty-state">暂未记录设备流转。</div>';
  return `<ol class="computer-movement-timeline">${events
    .map((event) => {
      const employee = [event.employeeName, event.employeeNo ? `(${event.employeeNo})` : ""]
        .filter(Boolean)
        .join(" ");
      const status =
        event.type === "status_changed"
          ? `${statusLabels[event.previousStatus] || event.previousStatus || "未设置"} → ${
              statusLabels[event.nextStatus] || event.nextStatus || "未设置"
            }`
          : statusLabels[event.nextStatus] || event.nextStatus || "";
      return `<li class="computer-movement-item">
        <div class="computer-movement-marker" aria-hidden="true"></div>
        <div class="computer-movement-body">
          <div class="computer-movement-heading">
            <strong>${escapeHtml(computerMovementEventLabel(event))}</strong>
            <span>${escapeHtml(formatDateTime(event.occurredAt))}</span>
          </div>
          <div class="computer-movement-meta">
            ${employee ? `<span>使用人：${escapeHtml(employee)}</span>` : ""}
            ${status ? `<span>状态：${escapeHtml(status)}</span>` : ""}
            ${event.operatedBy ? `<span>操作人：${escapeHtml(event.operatedBy)}</span>` : ""}
          </div>
          ${event.notes ? `<p>${escapeHtml(event.notes)}</p>` : ""}
        </div>
      </li>`;
    })
    .join("")}</ol>`;
}

async function loadComputerMovementHistory(computerId) {
  const container = document.querySelector(
    `[data-computer-movement-history="${CSS.escape(String(computerId))}"]`,
  );
  if (!container) return;
  try {
    const payload = await requestJson(
      `/api/computers/${encodeURIComponent(computerId)}/movement-history`,
    );
    if (!container.isConnected) return;
    container.innerHTML = renderComputerMovementHistory(
      Array.isArray(payload.events) ? payload.events : [],
    );
  } catch (error) {
    if (!container.isConnected) return;
    container.innerHTML = `<div class="empty-state">无法加载设备流转记录：${escapeHtml(error.message)}</div>`;
  }
}

function openEmployeeModal(id = "", presetOrgId = "") {
  const employee = state.employees.find((item) => item.id === id) || {
    id: "",
    employeeNo: "",
    name: "",
    orgId: presetOrgId || state.orgs[0]?.id || "",
    department: "",
    position: "",
    email: "",
    mobile: "",
    status: "active",
  };
  const isEditing = Boolean(id);
  const hasExistingNumber = Boolean(String(employee.employeeNo || "").trim());
  const initialEmployeeNo = hasExistingNumber ? employee.employeeNo : employeeNumberFor(employee.orgId, employee.id, employee.status);
  openModal(
    `${modalHeader(isEditing ? "编辑使用人员" : "新增使用人员", "人员归属到组织树节点后，会同步出现在树状视图中")}
      <form data-form="employee" data-id="${escapeHtml(employee.id)}">
        <section class="modal-section">
          <div class="form-grid">
            ${inputField(
              "人员编号",
              "employeeNo",
              initialEmployeeNo,
              true,
              "例如 EMP-0001",
              "text",
              "",
              `data-employee-number data-original-number="${escapeHtml(employee.employeeNo || "")}" data-generated="${hasExistingNumber ? "false" : "true"}"`,
            )}
            ${inputField("人员姓名", "name", employee.name, true, "姓名")}
            ${selectField(
              "所属组织",
              "orgId",
              employee.orgId,
              getOrgSelectOptions({ includeBlank: true }),
              false,
            )}
            ${selectField(
              "人员状态",
              "status",
              employee.status,
              ["active", "inactive", "shared"].map((value) => ({ value, label: statusLabels[value] })),
              true,
            )}
            ${inputField("部门", "department", employee.department, false, "IT")}
            ${inputField("岗位", "position", employee.position, false, "IT 管理员")}
            ${inputField("邮箱", "email", employee.email, false, "name@example.com", "email")}
            ${inputField("手机号", "mobile", employee.mobile, false, "138****0000")}
          </div>
        </section>
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">保存人员</button></div>
      </form>`,
  );
}

function leftEmployeeReadonlyField(label, value, type = "text") {
  return inputField(label, `readonly-${label}`, value, false, "", type, "", 'readonly tabindex="-1"');
}

function openLeftEmployeeModal(id = "") {
  const employee = getLeftEmployee(id);
  if (!employee) return;
  openModal(
    `${modalHeader(`${employee.name} · 离职人员档案`, `${employee.employeeNo} · 已归档信息可在此查看`)}
      <section class="modal-section">
        <div class="form-grid">
          ${leftEmployeeReadonlyField("人员编号", employee.employeeNo || "—")}
          ${leftEmployeeReadonlyField("人员姓名", employee.name || "—")}
          ${leftEmployeeReadonlyField("原组织路径", employee.orgPath || orgPathName(employee.orgId))}
          ${leftEmployeeReadonlyField("部门", employee.department || "—")}
          ${leftEmployeeReadonlyField("岗位", employee.position || "—")}
          ${leftEmployeeReadonlyField("离职日期", employee.leaveDate || "—")}
          ${leftEmployeeReadonlyField("归档时间", formatDateTime(employee.archivedAt || ""))}
          ${leftEmployeeReadonlyField("手机号", employee.mobile || "—")}
        </div>
      </section>
      <section class="modal-section">
        <div class="form-grid">
          ${textareaField("离职信息", "left-detail-info", employee.leaveInfo || "", false, "", 4, 'readonly tabindex="-1"')}
          ${textareaField("备注", "left-detail-remark", employee.leaveRemark || "", false, "", 4, 'readonly tabindex="-1"')}
        </div>
      </section>
      <section class="modal-section">
        <div class="modal-section-title"><div><h3>离职时设备快照</h3><span>${(employee.devices || []).length} 条</span></div></div>
        ${leftEmployeeDeviceChips(employee.devices || [])}
      </section>
      <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">关闭</button></div>`,
    true,
  );
}

function inventoryBrandOptions(typeId, selectedId = "", currentName = "") {
  const brands = inventoryBrandsForType(typeId);
  const matched = brands.find((brand) => brand.id === selectedId || (currentName && brand.name === currentName));
  return [{ value: "__custom__", label: "自定义品牌" }].concat(
    brands.map((brand) => ({ value: brand.id, label: brand.name })),
  ).map((option) => ({
    ...option,
    selected: String(option.value) === String(matched?.id || "__custom__"),
  }));
}

function inventoryModelOptions(brandId, selectedId = "", currentName = "") {
  const models = inventoryModelsForBrand(brandId);
  const matched = models.find((model) => model.id === selectedId || (currentName && model.name === currentName));
  return [{ value: "__custom__", label: "自定义型号" }].concat(
    models.map((model) => ({ value: model.id, label: inventoryModelOptionLabel(model) })),
  ).map((option) => ({
    ...option,
    selected: String(option.value) === String(matched?.id || "__custom__"),
  }));
}

function inventorySelectField(label, name, options, required = false) {
  const controlId = createControlId(name);
  return `<div class="form-field"><label for="${controlId}">${escapeHtml(label)}${required ? " *" : ""}</label><select id="${controlId}" name="${escapeHtml(
    name,
  )}" data-inventory-select="${escapeHtml(name)}" ${required ? "required" : ""}>${options
    .map(
      (option) =>
        `<option value="${escapeHtml(option.value)}" ${option.selected ? "selected" : ""}>${escapeHtml(
          option.label,
        )}</option>`,
    )
    .join("")}</select></div>`;
}

function renderInventorySelectionFields(item = {}, includeType = true) {
  const typeId = item.typeId || defaultMonitorTypeId();
  const selectedBrand = getInventoryBrand(item.inventoryBrandId) || inventoryBrandsForType(typeId).find(
    (brand) => brand.name === item.brand,
  );
  const selectedModel = getInventoryModel(item.inventoryModelId) || inventoryModelsForBrand(selectedBrand?.id || "").find(
    (model) => model.name === item.model,
  );
  const brandOptions = inventoryBrandOptions(typeId, selectedBrand?.id || "", item.brand || "");
  const modelOptions = inventoryModelOptions(selectedBrand?.id || "", selectedModel?.id || "", item.model || "");
  return `
    ${
      includeType
        ? selectField(
            "设备类型",
            "typeId",
            typeId,
            state.nonAssetTypes.map((type) => ({ value: type.id, label: type.name })),
            true,
          )
        : ""
    }
    ${inventorySelectField("库存品牌", "brandId", brandOptions, false)}
    ${inputField("品牌 / 自定义", "brandCustom", selectedBrand ? "" : item.brand || "", false, "自定义品牌")}
    ${inventorySelectField("库存型号", "modelId", modelOptions, false)}
    ${inputField("型号 / 自定义", "modelCustom", selectedModel ? "" : item.model || "", false, "自定义型号")}
  `;
}

function renderComputerInventorySelectionFields(computer = {}, isEditing = false) {
  const typeId = computerInventoryTypeId();
  if (!typeId) {
    return `
      ${inputField("设备品牌", "brand", computer.brand, false, "Dell / Lenovo / HP")}
      ${inputField("型号", "model", computer.model, false, "Latitude 5440")}
    `;
  }
  const registrationMode = computer.registrationMode || (
    computer.inventoryStockAdjusted ? "warehouse" : "custom"
  );
  const linkedModel = getInventoryModel(computer.inventoryModelId);
  const linkedModelLabel = linkedModel
    ? `${getInventoryBrand(linkedModel.brandId)?.name || "未登记品牌"} / ${inventoryModelOptionLabel(linkedModel)}`
    : "无库存型号关联";
  if (isEditing) {
    return `
      ${inputField(
        "登记方式",
        "registrationModeLabel",
        registrationMode === "warehouse" ? "从仓库库存登记" : "自定义品牌型号",
        false,
        "",
        "text",
        "",
        'readonly tabindex="-1"',
      )}
      <input type="hidden" name="registrationMode" value="${escapeHtml(registrationMode)}" />
      ${inputField(
        "库存关联",
        "inventoryAssociation",
        linkedModelLabel,
        false,
        "",
        "text",
        "",
        'readonly tabindex="-1"',
      )}
      ${inputField("设备品牌", "brand", computer.brand, false, "Dell / Lenovo / HP")}
      ${inputField("型号", "model", computer.model, false, "Latitude 5440")}
    `;
  }
  return `
    ${selectField(
      "登记方式",
      "registrationMode",
      registrationMode,
      [
        { value: "custom", label: "自定义品牌型号" },
        { value: "warehouse", label: "从仓库库存登记" },
      ],
      true,
    )}
    <div data-computer-custom-fields>
      ${inputField("设备品牌", "brand", computer.brand, false, "Dell / Lenovo / HP")}
      ${inputField("型号", "model", computer.model, false, "Latitude 5440")}
    </div>
    <div data-computer-warehouse-fields hidden>
      ${warehouseSelectField(
        "分配仓库",
        "warehouseId",
        computer.warehouseId || "",
        true,
        "请选择分配仓库",
        currentUserOrgId(),
      )}
      ${inventorySelectField(
        "库存电脑型号",
        "computerInventoryModelId",
        computerInventoryModelOptionsForWarehouse(computer.warehouseId || defaultWarehouseIdForCurrentUser(), computer.inventoryModelId),
        false,
      )}
    </div>
  `;
}

function updateComputerRegistrationFields(form, changedField) {
  if (!form || form.dataset.form !== "computer") return;
  const mode = form.elements.registrationMode?.value || "custom";
  const warehouseMode = mode === "warehouse";
  const customFields = form.querySelector("[data-computer-custom-fields]");
  const warehouseFields = form.querySelector("[data-computer-warehouse-fields]");
  if (customFields) customFields.hidden = warehouseMode;
  if (warehouseFields) warehouseFields.hidden = !warehouseMode;

  const warehouseSelect = form.elements.warehouseId;
  const modelSelect = form.elements.computerInventoryModelId;
  if (warehouseSelect) {
    warehouseSelect.required = warehouseMode;
    warehouseSelect.disabled = !warehouseMode;
  }
  if (modelSelect) {
    modelSelect.required = warehouseMode;
    modelSelect.disabled = !warehouseMode;
  }
  if (!warehouseMode || !warehouseSelect || !modelSelect) return;
  if (changedField === "registrationMode" || changedField === "warehouseId") {
    replaceSelectOptions(
      modelSelect,
      computerInventoryModelOptionsForWarehouse(warehouseSelect.value || "", ""),
      "",
    );
    if (changedField === "warehouseId") {
      ["brand", "model", "cpu", "memory", "storage", "gpu", "purchaseDate"].forEach((fieldName) => {
        if (form.elements[fieldName]) form.elements[fieldName].value = "";
      });
    }
    return;
  }

  if (changedField === "computerInventoryModelId") {
    const model = modelSelect.value && modelSelect.value !== "__custom__" ? getInventoryModel(modelSelect.value) : null;
    if (!model) return;
    const brand = getInventoryBrand(model.brandId);
    if (form.elements.brand && brand) form.elements.brand.value = brand.name;
    if (form.elements.model) form.elements.model.value = model.name || "";
    if (form.elements.cpu) form.elements.cpu.value = model.cpu || "";
    if (form.elements.memory) form.elements.memory.value = model.memory || "";
    if (form.elements.storage) form.elements.storage.value = normalizeStorageValue(model.storage || "");
    if (form.elements.gpu) form.elements.gpu.value = model.gpu || "";
    if (form.elements.purchaseDate && !form.elements.purchaseDate.value && model.inboundDate) {
      form.elements.purchaseDate.value = model.inboundDate;
    }
  }
}

function renderMonitorModule(employeeId, monitor = {}, isDraft = false) {
  const id = monitor.id || "";
  const summary = [monitor.brand, monitor.model].filter(Boolean).join(" ") || "新增显示屏";
  const removeAction = id ? "" : "remove-device-module";
  return `
    <form class="device-module monitor-module" data-form="monitor" data-employee-id="${escapeHtml(
      employeeId,
    )}" data-id="${escapeHtml(id)}" ${isDraft ? 'data-draft="true"' : ""}>
      <div class="device-module-header">
        <div><strong>${escapeHtml(summary)}</strong><small>可关联 IT 物资库存中的类型、品牌、型号，也可自定义填写。</small></div>
        <div class="device-module-header-actions">
          ${
            id
              ? `<label class="device-recover-select"><input type="checkbox" data-recovery-select data-recovery-kind="monitor" data-employee-id="${escapeHtml(
                  employeeId,
                )}" data-id="${escapeHtml(id)}" />回收</label>`
              : ""
          }
          ${
            id
              ? `<button type="button" class="text-button danger" data-action="open-usage-scrap" data-kind="monitor" data-id="${escapeHtml(
                  id,
                )}" data-employee-id="${escapeHtml(employeeId)}" data-label="${escapeHtml(summary)}">报废</button>`
              : ""
          }
          ${
            removeAction
              ? `<button type="button" class="text-button danger" data-action="${removeAction}">移除草稿</button>`
              : ""
          }
        </div>
      </div>
      <div class="device-module-grid">
        ${renderInventorySelectionFields({ ...monitor, typeId: monitor.typeId || defaultMonitorTypeId() }, true)}
      </div>
      <div class="device-module-actions"><button class="primary-button" type="submit">${
        id ? "保存修改" : "保存显示屏"
      }</button></div>
    </form>`;
}

function renderNonAssetModule(employeeId, item = {}, isDraft = false) {
  const id = item.id || "";
  const typeId = item.typeId || state.nonAssetTypes[0]?.id || "mouse";
  const type = getType(typeId);
  const summary = type?.name || "非资产设备";
  const removeAction = id ? "" : "remove-device-module";
  return `
    <form class="device-module nonasset-module" data-form="nonasset" data-employee-id="${escapeHtml(
      employeeId,
    )}" data-id="${escapeHtml(id)}" ${isDraft ? 'data-draft="true"' : ""}>
      <div class="device-module-header">
        <div><strong>${escapeHtml(summary)}</strong><small>可关联 IT 物资库存中的类型、品牌、型号，也可自定义填写。</small></div>
        <div class="device-module-header-actions">
          ${
            id
              ? `<label class="device-recover-select"><input type="checkbox" data-recovery-select data-recovery-kind="nonasset" data-employee-id="${escapeHtml(
                  employeeId,
                )}" data-id="${escapeHtml(id)}" />回收</label>`
              : ""
          }
          ${
            id
              ? `<button type="button" class="text-button danger" data-action="open-usage-scrap" data-kind="nonasset" data-id="${escapeHtml(
                  id,
                )}" data-employee-id="${escapeHtml(employeeId)}" data-label="${escapeHtml(summary)}">报废</button>`
              : ""
          }
          ${
            removeAction
              ? `<button type="button" class="text-button danger" data-action="${removeAction}">移除草稿</button>`
              : ""
          }
        </div>
      </div>
      <div class="device-module-grid">
        ${renderInventorySelectionFields({ ...item, typeId }, true)}
        ${inputField("Quantity", "quantity", Math.max(1, Number(item.quantity || 1)), true, "1", "number", "1")}
      </div>
      <div class="device-module-actions"><button class="primary-button" type="submit">${
        id ? "保存修改" : "保存非资产设备"
      }</button></div>
    </form>`;
}

function openDeviceManager(employeeId) {
  const employee = getEmployee(employeeId);
  if (!employee) return;
  const assignedComputers = state.computers.filter((computer) => computer.userId === employeeId);
  const availableComputers = state.computers.filter(
    (computer) => !computer.userId && !["retired", "lost"].includes(computer.status),
  );
  const monitors = employee.monitors || [];
  const nonAssetItems = getNonAssetItems(employee);
  const defaultNonAssetTypeId = state.nonAssetTypes.find((type) => type.id === "mouse")?.id || state.nonAssetTypes[0]?.id || "mouse";

  openModal(
    `${modalHeader(`${employee.name} · 设备清单`, `${employee.employeeNo} · ${orgPathName(employee.orgId)} · ${employee.department || "未填写部门"}`)}
      <section class="modal-section">
        <div class="modal-section-title"><h3>办公终端</h3><span>${assignedComputers.length} 台</span></div>
        ${
          assignedComputers.length
            ? assignedComputers
                .map(
                  (computer) => `<div class="assignment-row">
                    <div><strong>${escapeHtml(computer.deviceName)}</strong><small>${escapeHtml(
                      [computer.brand, computer.model].filter(Boolean).join(" · ") || "未填写品牌型号",
                    )} · ${escapeHtml(computer.fixedAssetCode || "未登记固资编码")} · ${escapeHtml(
                      orgPathName(computer.orgId),
                    )}</small></div>
                    <div class="inline-actions"><button class="text-button" data-action="open-computer" data-id="${escapeHtml(
                      computer.id,
                    )}">编辑台账</button><button class="text-button danger" data-action="release-computer" data-id="${escapeHtml(
                      computer.id,
                    )}" data-employee-id="${escapeHtml(employee.id)}">解除</button>${
                      computer.status === "retired"
                        ? ""
                        : `<button class="text-button danger" data-action="open-computer-scrap" data-id="${escapeHtml(
                            computer.id,
                          )}" data-name="${escapeHtml(computer.deviceName)}">报废</button>`
                    }</div>
                  </div>`,
                )
                .join("")
            : '<div class="empty-state">当前没有分配办公终端</div>'
        }
        <div class="assignment-form">
          <select data-assign-computer="${escapeHtml(employee.id)}">
            <option value="">选择一台可分配办公终端</option>
            ${availableComputers
              .map(
                (computer) =>
                  `<option value="${escapeHtml(computer.id)}">${escapeHtml(computer.deviceName)} · ${escapeHtml(
                    computer.model || "未填写型号",
                  )} · ${escapeHtml(orgName(computer.orgId))}</option>`,
              )
              .join("")}
          </select>
          <button class="primary-button" data-action="assign-computer" data-employee-id="${escapeHtml(
            employee.id,
          )}">分配</button>
        </div>
      </section>

      <section class="modal-section">
        <div class="modal-section-title">
          <div><h3>显示屏</h3><span>${monitors.length} 个模块，仅记录品牌和型号</span></div>
        </div>
        <div class="device-module-list" data-monitor-list="${escapeHtml(employee.id)}">
          ${
            monitors.length
              ? monitors.map((monitor) => renderMonitorModule(employee.id, monitor)).join("")
              : renderMonitorModule(employee.id, {}, true)
          }
        </div>
        <div class="module-list-footer">
          <button type="button" class="secondary-button" data-action="recover-selected-devices" data-kind="monitor" data-employee-id="${escapeHtml(
            employee.id,
          )}">回收选中</button>
          <button type="button" class="add-module-button" data-action="add-monitor-module" data-employee-id="${escapeHtml(
            employee.id,
          )}">＋ 添加显示屏</button>
        </div>
      </section>

      <section class="modal-section">
        <div class="modal-section-title">
          <div><h3>非资产设备</h3><span>默认显示 1 个鼠标模块，可按需继续添加</span></div>
        </div>
        <div class="device-module-list" data-nonasset-list="${escapeHtml(employee.id)}">
          ${
            nonAssetItems.length
              ? nonAssetItems.map((item) => renderNonAssetModule(employee.id, item)).join("")
              : renderNonAssetModule(employee.id, { typeId: defaultNonAssetTypeId, quantity: 1 }, true)
          }
        </div>
        <div class="module-list-footer">
          <button type="button" class="secondary-button" data-action="recover-selected-devices" data-kind="nonasset" data-employee-id="${escapeHtml(
            employee.id,
          )}">回收选中</button>
          <button type="button" class="add-module-button" data-action="add-nonasset-module" data-employee-id="${escapeHtml(
            employee.id,
          )}">＋ 添加非资产设备</button>
        </div>
      </section>`,
    true,
  );
}

function openOrgModal(id = "", presetParentId = "") {
  const existing = state.orgs.find((item) => item.id === id);
  const org = existing || { id: "", code: "", name: "", parentId: presetParentId, sortOrder: 1000 };
  const excludeIds = existing ? [existing.id].concat(getDescendantOrgIds(existing.id)) : [];
  openModal(
    `${modalHeader(id ? "编辑组织" : "新增组织", "组织会用于树状视图展示和办公终端、人员归属")}
      <form data-form="org" data-id="${escapeHtml(org.id)}">
        <div class="form-grid">
          ${inputField(
            "组织编码",
            "code",
            org.code || orgCodeFor(org, org.parentId, org.id),
            true,
            "ITQ",
            "text",
            "",
            `data-org-code data-original-code="${escapeHtml(org.code || "")}" data-generated="${id ? "false" : "true"}"`,
          )}
          ${inputField("组织名称", "name", org.name, true, "人力资源部")}
          ${selectField(
            "上级组织",
            "parentId",
            org.parentId || "",
            getOrgSelectOptions({
              includeBlank: true,
              blankLabel: "作为根组织",
              excludeIds,
            }),
            false,
          )}
          ${inputField("排序值", "sortOrder", org.sortOrder || 1000, true, "10", "number", "0")}
        </div>
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">保存组织</button></div>
      </form>`,
  );
}

function openTypeModal(id = "") {
  const type = state.nonAssetTypes.find((item) => item.id === id) || { id: "", code: "", name: "", unit: "件" };
  openModal(
    `${modalHeader(id ? "编辑非资产设备类型" : "新增非资产设备类型", "用于人员设备清单中的数量统计")}
      <form data-form="type" data-id="${escapeHtml(type.id)}">
        <div class="form-grid">${inputField("类型编码", "code", type.code, true, "mouse")}${inputField(
          "类型名称",
          "name",
          type.name,
          true,
          "鼠标",
        )}${inputField("计量单位", "unit", type.unit, true, "件")}</div>
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">保存类型</button></div>
      </form>`,
  );
}

function inputField(
  label,
  name,
  value,
  required = false,
  placeholder = "",
  type = "text",
  min = "",
  extraAttributes = "",
) {
  const controlId = createControlId(name);
  const numericConstraint = type !== "password" && min ? `min="${escapeHtml(min)}"` : "";
  const passwordConstraint =
    type === "password"
      ? 'minlength="8" maxlength="256" spellcheck="false" data-password-input'
      : "";
  const passwordHint =
    type === "password"
      ? '<small class="form-hint password-hint">8-256 位，不允许首尾空格。</small>'
      : "";
  return `<div class="form-field"><label for="${controlId}">${escapeHtml(label)}${required ? " *" : ""}</label><input id="${controlId}" type="${type}" name="${escapeHtml(
    name,
  )}" value="${escapeHtml(value)}" placeholder="${escapeHtml(placeholder)}" ${required ? "required" : ""} ${numericConstraint} ${passwordConstraint} ${extraAttributes} />${passwordHint}</div>`;
}

function selectField(label, name, value, options, required = false) {
  if (Array.isArray(value) && !Array.isArray(options)) {
    const suppliedOptions = value;
    value = options;
    options = suppliedOptions;
  }
  const controlId = createControlId(name);
  return `<div class="form-field"><label for="${controlId}">${escapeHtml(label)}${required ? " *" : ""}</label><select id="${controlId}" name="${escapeHtml(
    name,
  )}" ${required ? "required" : ""}>${options
    .map(
      (option) =>
        `<option value="${escapeHtml(option.value)}" ${String(value) === String(option.value) ? "selected" : ""}>${escapeHtml(
          option.label,
        )}</option>`,
    )
    .join("")}</select></div>`;
}

function textareaField(label, name, value, required = false, placeholder = "", rows = 3, extraAttributes = "") {
  const controlId = createControlId(name);
  return `<div class="form-field"><label for="${controlId}">${escapeHtml(label)}${required ? " *" : ""}</label><textarea id="${controlId}" name="${escapeHtml(
    name,
  )}" rows="${rows}" placeholder="${escapeHtml(placeholder)}" ${required ? "required" : ""} ${extraAttributes}>${escapeHtml(
    value,
  )}</textarea></div>`;
}

function createControlId(name) {
  controlIdSequence += 1;
  const normalizedName =
    String(name || "control")
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "") || "control";
  return `field-${normalizedName}-${controlIdSequence}`;
}

async function handleSystemSettingsSubmit(form) {
  if (!isAdminUser()) return showToast("只有管理员可以修改系统设置", true);
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    const payload = await requestJson(API_SETTINGS_URL, {
      method: "PUT",
      body: JSON.stringify({
        settings: {
          app_name: data.app_name,
          login_notice: data.login_notice,
          session_hours: data.session_hours,
        },
      }),
    });
    settingsState.settings = payload.settings || settingsState.settings;
    updateAuthenticatedChrome();
    render();
    showToast("系统设置已保存");
  } catch (error) {
    showToast(`保存系统设置失败：${error.message}`, true);
  }
}

async function handleBackupScheduleSubmit(form) {
  if (!isAdminUser()) return showToast("只有管理员可以修改数据库备份设置", true);
  const enabled = form.querySelector('input[name="backup_enabled"]')?.checked;
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    const payload = await requestJson(API_SETTINGS_URL, {
      method: "PUT",
      body: JSON.stringify({
        settings: {
          backup_enabled: enabled ? "1" : "0",
          backup_time: data.backup_time,
          backup_retention_days: data.backup_retention_days,
        },
      }),
    });
    settingsState.settings = payload.settings || settingsState.settings;
    render();
    showToast("数据库备份计划已保存");
  } catch (error) {
    showToast(`保存数据库备份计划失败：${error.message}`, true);
  }
}

async function handleUpdateCheck(button) {
  if (!hasPermission("system_updates", "update")) return showToast("当前账号没有系统更新权限", true);
  const updateSource = currentUpdateSource();
  const repositoryUrl = currentUpdateRepositoryUrl();
  const releaseChannel =
    document.querySelector("[data-update-release-channel]")?.value ||
    settingsState.updateReleaseChannel ||
    DEFAULT_UPDATE_RELEASE_CHANNEL;
  settingsState.updateSource = updateSource;
  settingsState.updateRepositoryUrl = repositoryUrl;
  if (updateSource === "custom") settingsState.updateCustomRepositoryUrl = repositoryUrl;
  settingsState.updateReleaseChannel = releaseChannel;
  settingsState.updateChecking = true;
  if (button) button.disabled = true;
  render();
  try {
    const payload = await requestJson(API_UPDATE_CHECK_URL, {
      method: "POST",
      body: JSON.stringify({
        repositoryUrl,
        releaseChannel,
        persistRepositoryUrl: updateSource === "custom",
      }),
    });
    settingsState.updateStatus = payload;
    const hasRepositoryUrl = Object.prototype.hasOwnProperty.call(payload, "repositoryUrl");
    settingsState.updateRepositoryUrl = hasRepositoryUrl ? payload.repositoryUrl || "" : repositoryUrl;
    if (updateSource === "custom") {
      settingsState.updateCustomRepositoryUrl = settingsState.updateRepositoryUrl;
      settingsState.settings.update_repository_url = settingsState.updateRepositoryUrl;
    }
    settingsState.updateReleaseChannel = payload.releaseChannel || releaseChannel;
    const versions = Array.isArray(payload.availableVersions) ? payload.availableVersions : [];
    settingsState.updateSelectedSha =
      payload.status === "update_available"
        ? versions.find((version) => version.isSelectable && !version.isCurrent)?.sha || ""
        : "";
    const status = payload.status || "";
    if (status === "up_to_date") {
      showToast(`当前已是${updateReleaseChannelLabel(releaseChannel)}最新版本 ${payload.currentVersion || payload.currentShortSha || ""}`);
    } else if (status === "update_available") {
      showToast(`发现可用${updateReleaseChannelLabel(releaseChannel)} ${payload.latestVersion || ""}，请选择后手动更新`);
    } else if (status === "no_releases") {
      showToast("检查完成：项目地址中暂无已发布版本", true);
    } else if (status === "no_release_available") {
      showToast("检查完成：当前没有版本号更高的已发布版本");
    } else {
      showToast("版本列表已更新");
    }
  } catch (error) {
    showToast(`检查版本更新失败：${error.message}`, true);
  } finally {
    settingsState.updateChecking = false;
    render();
  }
}

async function handleApplySelectedUpdate() {
  if (!hasPermission("system_updates", "update")) return showToast("当前账号没有系统更新权限", true);
  const repositoryUrl = currentUpdateRepositoryUrl();
  const releaseChannel =
    document.querySelector("[data-update-release-channel]")?.value ||
    settingsState.updateReleaseChannel ||
    DEFAULT_UPDATE_RELEASE_CHANNEL;
  const checkedRepositoryUrl = settingsState.updateStatus?.repositoryUrl || "";
  const checkedReleaseChannel =
    settingsState.updateStatus?.releaseChannel || DEFAULT_UPDATE_RELEASE_CHANNEL;
  if (repositoryUrl !== checkedRepositoryUrl || releaseChannel !== checkedReleaseChannel) {
    return showToast("项目地址或更新通道已变化，请先重新检查版本", true);
  }
  const targetSha =
    settingsState.updateSelectedSha || document.querySelector("[data-update-target]")?.value || "";
  const version = settingsState.updateStatus?.availableVersions?.find((item) => item.sha === targetSha);
  if (!targetSha || !version || version.isCurrent || version.isSelectable === false) {
    return showToast("请先检查并选择一个目标版本", true);
  }
  const targetLabel = version.version || version.tag || version.shortSha || targetSha.slice(0, 7);
  if (!window.confirm(`确定更新到 ${targetLabel}：${version.subject || ""} 吗？`)) {
    return;
  }
  settingsState.updateSelectedSha = targetSha;
  settingsState.updateApplying = true;
  render();
  try {
    const payload = await requestJson(API_UPDATE_APPLY_URL, {
      method: "POST",
      body: JSON.stringify({ targetSha, repositoryUrl, releaseChannel }),
    });
    settingsState.updateStatus = payload;
    const hasRepositoryUrl = Object.prototype.hasOwnProperty.call(payload, "repositoryUrl");
    settingsState.updateRepositoryUrl = hasRepositoryUrl ? payload.repositoryUrl || "" : repositoryUrl;
    settingsState.updateReleaseChannel = payload.releaseChannel || releaseChannel;
    settingsState.updateSelectedSha = payload.targetSha || targetSha;
    if (payload.status === "queued" || payload.status === "running") {
      showToast(`版本 ${payload.targetVersion || targetLabel} 已进入手动更新队列`);
      window.setTimeout(() => window.location.reload(), 7000);
    } else if (payload.status === "up_to_date") {
      showToast("当前已经是所选版本");
    } else {
      showToast("版本更新请求已完成");
    }
  } catch (error) {
    showToast(`执行版本更新失败：${error.message}`, true);
  } finally {
    settingsState.updateApplying = false;
    render();
  }
}

async function handleDatabaseBackupCreate(button) {
  if (!isAdminUser()) return showToast("只有管理员可以创建数据库备份", true);
  if (button) button.disabled = true;
  try {
    const payload = await requestJson(API_BACKUPS_URL, {
      method: "POST",
      body: "{}",
    });
    settingsState.backups = Array.isArray(payload.backups) ? payload.backups : settingsState.backups;
    render();
    showToast(`数据库备份已创建：${payload.backup?.fileName || ""}`);
  } catch (error) {
    showToast(`创建数据库备份失败：${error.message}`, true);
  } finally {
    if (button?.isConnected) button.disabled = false;
  }
}

async function handleDatabaseBackupDownloadSubmit(form) {
  if (!isAdminUser()) return showToast("只有管理员可以下载数据库备份", true);
  const backupId = form.dataset.id || "";
  const data = Object.fromEntries(new FormData(form).entries());
  const submit = form.querySelector('button[type="submit"]');
  if (submit) submit.disabled = true;
  try {
    const filename = await requestDownload(`${API_BACKUPS_URL}/${encodeURIComponent(backupId)}/download`, {
      password: data.password || "",
    });
    closeModal();
    showToast(`已开始下载：${filename}`);
  } catch (error) {
    showToast(`下载数据库备份失败：${error.message}`, true);
  } finally {
    if (submit?.isConnected) submit.disabled = false;
  }
}

async function handleChangePasswordSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    await requestJson(API_AUTH_CHANGE_PASSWORD_URL, {
      method: "POST",
      body: JSON.stringify(data),
    });
    form.reset();
    showToast("密码已修改");
  } catch (error) {
    showToast(`修改密码失败：${error.message}`, true);
  }
}

async function handleUserAccountSubmit(form) {
  if (!isAdminUser()) return showToast("只有管理员可以管理账号", true);
  if (form.dataset.submitting === "1") return;
  form.dataset.submitting = "1";
  const submit = form.querySelector('button[type="submit"]');
  const data = Object.fromEntries(new FormData(form).entries());
  const id = form.dataset.id || "";
  const payload = {
    username: String(data.username || "").trim(),
    displayName: String(data.displayName || "").trim(),
    role: data.role,
    employeeId: data.employeeId || "",
    isActive: data.isActive === "1",
  };
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$/.test(payload.username)) {
    form.dataset.submitting = "0";
    return showToast("登录账号需使用 3-64 位字母、数字、点、下划线或短横线。", true);
  }
  if (String(data.password || "").trim()) payload.password = data.password;
  if (submit) submit.disabled = true;
  try {
    await requestJson(id ? `${API_USERS_URL}/${encodeURIComponent(id)}` : API_USERS_URL, {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    const usersPayload = await requestJson(API_USERS_URL);
    settingsState.users = Array.isArray(usersPayload.users) ? usersPayload.users : [];
    closeModal();
    render();
    showToast(id ? "账号已更新" : "账号已创建");
  } catch (error) {
    showToast(`保存账号失败：${error.message}`, true);
  } finally {
    form.dataset.submitting = "0";
    if (submit?.isConnected) submit.disabled = false;
  }
}

function handleComputerSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const id = form.dataset.id;
  const previous = state.computers.find((computer) => computer.id === id);
  const duplicate = state.computers.find((computer) => computer.deviceName === data.deviceName && computer.id !== id);
  if (duplicate) return showToast("设备名已经存在", true);
  const selectedInventoryModel =
    data.computerInventoryModelId && data.computerInventoryModelId !== "__custom__"
      ? getInventoryModel(data.computerInventoryModelId)
      : null;
  const selectedInventoryBrand = selectedInventoryModel ? getInventoryBrand(selectedInventoryModel.brandId) : null;
  if (!id && selectedInventoryModel && Number(selectedInventoryModel.quantity || 0) < 1) {
    return showToast(`库存型号 ${selectedInventoryModel.name} 当前没有可用库存。`, true);
  }
  const wifiMac = normalizeMacAddress(data.wifiMac);
  const ethernetMac = normalizeMacAddress(data.ethernetMac);
  if (!isValidMacAddress(wifiMac)) {
    return showToast("Wifi MAC 格式不正确，请输入 11-22-33-44-55-66 或 11:22:33:44:55:66", true);
  }
  if (!isValidMacAddress(ethernetMac)) {
    return showToast("网口 MAC 格式不正确，请输入 11-22-33-44-55-66 或 11:22:33:44:55:66", true);
  }

  const computer = normalizeComputerRecord({
    id: id || createId("pc"),
    deviceName: data.deviceName,
    orgId: data.orgId,
    deviceType: data.deviceType,
    brand: selectedInventoryBrand?.name || data.brand,
    model: selectedInventoryModel?.name || data.model,
    inventoryModelId: selectedInventoryModel?.id || "",
    cpu: selectedInventoryModel?.cpu || data.cpu,
    memory: selectedInventoryModel?.memory || data.memory,
    storage: normalizeStorageValue(selectedInventoryModel?.storage || data.storage),
    gpu: selectedInventoryModel?.gpu || data.gpu,
    fixedAssetCode: data.fixedAssetCode,
    purchaseDate: data.purchaseDate || selectedInventoryModel?.inboundDate || "",
    registeredDate: data.registeredDate,
    snSt: data.snSt,
    wifiMac,
    ethernetMac,
    location: data.location,
    department: data.department,
    status: data.status,
    userId: ["repair", "retired", "lost"].includes(data.status) ? null : data.userId || null,
    inventoryStockAdjusted: Boolean(
      selectedInventoryModel &&
        (!previous || previous.inventoryStockAdjusted || previous.inventoryModelId !== selectedInventoryModel.id),
    ),
    remarks: data.remarks,
  });

  const movements = new Map();
  const addMovement = (modelId, delta) => {
    if (!modelId || !delta) return;
    movements.set(modelId, (movements.get(modelId) || 0) + delta);
  };
  if (previous?.inventoryStockAdjusted && previous.inventoryModelId !== computer.inventoryModelId) {
    addMovement(previous.inventoryModelId, 1);
  }
  if (computer.inventoryStockAdjusted && previous?.inventoryModelId !== computer.inventoryModelId) {
    addMovement(computer.inventoryModelId, -1);
  }
  const stockMovements = [...movements.entries()].map(([modelId, delta]) => ({ modelId, delta }));
  if (stockMovements.length) {
    applyStockMovement(stockMovements);
    stockMovements.forEach(({ modelId, delta }) => {
      const model = getInventoryModel(modelId);
      const brand = model ? getInventoryBrand(model.brandId) : null;
      const type = model ? getType(model.typeId) : null;
      recordInventoryMovement({
        direction: delta < 0 ? "decrease" : "increase",
        typeName: type?.name || "办公终端",
        brandName: brand?.name || "",
        modelName: model?.name || "",
        quantity: Math.abs(delta),
        sourceLabel: delta < 0 ? "IT物资库存" : `${previous?.deviceName || computer.deviceName}（办公终端）`,
        targetLabel: delta < 0 ? `${computer.deviceName}（办公终端）` : "IT物资库存",
        note: delta < 0 ? "新增或更换办公终端时自动扣减库存" : "更换办公终端库存型号时归还原库存",
        triggerAction: "computer_inventory_adjustment",
      });
    });
  }

  const index = state.computers.findIndex((item) => item.id === id);
  if (index >= 0) state.computers[index] = computer;
  else state.computers.unshift(computer);

  normalizeComputersAgainstEmployees();
  persistState(true);
  closeModal();
  render();
  showToast(id ? "办公终端信息已更新" : "办公终端已新增");
}

function handleEmployeeSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const id = form.dataset.id;
  const employeeNo = String(data.employeeNo || "").trim() || employeeNumberFor(data.orgId, id, data.status);
  const duplicate = state.employees.find((employee) => employee.employeeNo === employeeNo && employee.id !== id);
  if (duplicate) return showToast("人员编号已存在", true);

  const previous = state.employees.find((employee) => employee.id === id);
  if (data.status === "left") {
    const archiveEmployeeRecord = {
      ...previous,
      id: previous?.id || id || createId("emp"),
      employeeNo,
      name: data.name,
      orgId: data.orgId,
      department: data.department,
      position: data.position,
      email: data.email,
      mobile: data.mobile,
      status: "left",
      monitors: previous?.monitors || [],
      nonAssetItems: previous ? getNonAssetItems(previous) : [],
      nonAssets: {},
    };
    syncNonAssetAggregate(archiveEmployeeRecord);
    openLeaveRecoveryModal(archiveEmployeeRecord, {
      leaveDate: data.leaveDate || currentDateText(),
      leaveInfo: data.leaveInfo || "",
      leaveRemark: data.leaveRemark || "",
      archivedAt: currentTimestampText(),
    });
    return;
  }

  const employee = {
    ...previous,
    id: id || createId("emp"),
    employeeNo,
    name: data.name,
    orgId: data.orgId,
    department: data.department,
    position: data.position,
    email: data.email,
    mobile: data.mobile,
    status: data.status,
    monitors: previous?.monitors || [],
    nonAssetItems: previous
      ? getNonAssetItems(previous)
      : [
          {
            id: createId("na"),
            typeId: state.nonAssetTypes.find((type) => type.id === "mouse")?.id || state.nonAssetTypes[0]?.id || "mouse",
            brand: "",
            model: "",
            quantity: 1,
            inventoryBrandId: "",
            inventoryModelId: "",
            stockAdjusted: false,
          },
        ],
    nonAssets: {},
  };
  syncNonAssetAggregate(employee);

  const index = state.employees.findIndex((item) => item.id === id);
  if (index >= 0) state.employees[index] = employee;
  else state.employees.unshift(employee);

  ensureOrgExpanded(employee.orgId);
  normalizeComputersAgainstEmployees();
  persistState(true);
  closeModal();
  render();
  showToast(id ? "人员信息已更新" : "人员已新增");
}

function inventoryModelForItem(item) {
  if (item.inventoryModelId) {
    const selected = getInventoryModel(item.inventoryModelId);
    if (selected && selected.typeId === item.typeId) return selected;
  }
  const brand = state.inventoryBrands.find(
    (candidate) => candidate.typeId === item.typeId && candidate.name === item.brand,
  );
  return brand ? inventoryModelsForBrand(brand.id).find((model) => model.name === item.model) : null;
}

function openDeviceStockConfirm(kind, employeeId, item, previous, selections = {}) {
  const employee = getEmployee(employeeId);
  const sourceWarehouseId =
    selections.sourceWarehouseId || defaultWarehouseIdForOrg(employee?.orgId);
  const returnWarehouseId =
    selections.returnWarehouseId || defaultWarehouseIdForCurrentUser();
  pendingDeviceSave = {
    kind,
    employeeId,
    item,
    previous,
    sourceWarehouseId,
    returnWarehouseId,
  };
  const detail = [item.brand, item.model].filter(Boolean).join(" ") || "自定义物资";
  const quantity = Math.max(1, Number(item.quantity || 1));
  const sourceWarehouseControlId = createControlId("device-stock-source-warehouse");
  const returnWarehouseControlId = createControlId("device-stock-return-warehouse");
  openModal(
    `${modalHeader("是否同步修改 IT 物资库存", `${detail} x${quantity}`)}
      <form class="confirm-panel" data-form="device-stock-confirm">
        <p>请选择本次人员物资分配是否同步影响库存数量。</p>
        <div class="form-field">
          <label for="${sourceWarehouseControlId}">新领用来源仓库</label>
          <select id="${sourceWarehouseControlId}" name="sourceWarehouseId">
            ${warehouseOptions(sourceWarehouseId, "请选择来源仓库", employee?.orgId)
              .map(
                (option) =>
                  `<option value="${escapeHtml(option.value)}" ${
                    option.selected ? "selected" : ""
                  }>${escapeHtml(option.label)}</option>`,
              )
              .join("")}
          </select>
        </div>
        ${
          previous?.stockAdjusted
            ? `<div class="form-field">
                <label for="${returnWarehouseControlId}">旧记录回收目标仓库</label>
                <select id="${returnWarehouseControlId}" name="returnWarehouseId">
                  ${warehouseOptions(returnWarehouseId, "请选择回收目标仓库", currentUserOrgId())
                    .map(
                      (option) =>
                        `<option value="${escapeHtml(option.value)}" ${
                          option.selected ? "selected" : ""
                        }>${escapeHtml(option.label)}</option>`,
                    )
                    .join("")}
                </select>
              </div>`
            : ""
        }
        <div class="confirm-options">
          <button type="button" class="primary-button" data-action="commit-device-stock">同步扣减库存</button>
          <button type="button" class="secondary-button" data-action="commit-device-register">仅登记不扣减</button>
          <button type="button" class="secondary-button" data-action="cancel-device-confirm">取消</button>
        </div>
      </form>`,
    false,
  );
}

function handleMonitorSubmit(form) {
  const employee = getEmployee(form.dataset.employeeId);
  if (!employee) return;
  const data = Object.fromEntries(new FormData(form).entries());
  const resolved = resolveInventorySelection(data);
  if (!resolved.typeId || !resolved.brand || !resolved.model) {
    return showToast("请填写设备类型、品牌和型号。", true);
  }
  const previous = (employee.monitors || []).find((monitor) => monitor.id === form.dataset.id);
  const item = {
    id: form.dataset.id || createId("mon"),
    ...resolved,
    quantity: 1,
    stockAdjusted: Boolean(previous?.stockAdjusted),
  };
  openDeviceStockConfirm("monitor", employee.id, item, previous);
}

function handleNonAssetSubmit(form) {
  const employee = getEmployee(form.dataset.employeeId);
  if (!employee) return;
  const data = Object.fromEntries(new FormData(form).entries());
  const quantity = Math.max(1, Number(data.quantity || 0));
  const resolved = resolveInventorySelection(data);
  if (!resolved.typeId || !resolved.brand || !resolved.model || !quantity) {
    return showToast("请填写设备类型、品牌、型号和数量。", true);
  }
  const previous = getNonAssetItems(employee).find((item) => item.id === form.dataset.id);
  const item = {
    id: form.dataset.id || createId("na"),
    ...resolved,
    quantity,
    stockAdjusted: Boolean(previous?.stockAdjusted),
  };
  openDeviceStockConfirm("nonasset", employee.id, item, previous);
}

function handleOrgSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const orgId = form.dataset.id;
  const code = String(data.code || "").trim() || orgCodeFor({ name: data.name }, data.parentId, orgId);
  const duplicate = state.orgs.find(
    (org) => org.code.toUpperCase() === code.toUpperCase() && org.id !== orgId && (org.parentId || "") === (data.parentId || ""),
  );
  if (duplicate) return showToast("组织编码已经存在", true);

  if (orgId && data.parentId === orgId) {
    return showToast("上级组织不能选择当前组织", true);
  }

  if (orgId && data.parentId && getDescendantOrgIds(orgId).includes(data.parentId)) {
    return showToast("上级组织不能选择当前组织的下级节点", true);
  }

  const item = {
    id: orgId || createId("org"),
    code,
    name: data.name,
    parentId: data.parentId || "",
    sortOrder: Math.max(0, Number(data.sortOrder || 1000)),
  };

  const index = state.orgs.findIndex((org) => org.id === orgId);
  if (index >= 0) state.orgs[index] = item;
  else state.orgs.push(item);

  ensureOrgExpanded(item.parentId);
  ensureOrgExpanded(item.id);
  persistState(true);
  closeModal();
  render();
  showToast(index >= 0 ? "组织已更新" : "组织已新增");
}

function handleTypeSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const duplicate = state.nonAssetTypes.find((type) => type.code === data.code && type.id !== form.dataset.id);
  if (duplicate) return showToast("类型编码已经存在", true);

  const item = {
    id: form.dataset.id || createId("type"),
    code: data.code,
    name: data.name,
    unit: data.unit || "件",
  };

  const index = state.nonAssetTypes.findIndex((type) => type.id === form.dataset.id);
  if (index >= 0) state.nonAssetTypes[index] = item;
  else state.nonAssetTypes.push(item);

  ensureInventoryExpanded(item.id);
  persistState(true);
  closeModal();
  render();
  showToast(index >= 0 ? "设备类型已更新" : "设备类型已新增");
}

function handleInventoryBrandSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const typeId = form.dataset.typeId;
  const id = form.dataset.id;
  const name = String(data.name || "").trim();
  if (!typeId || !name) return showToast("请填写品牌名称。", true);
  const duplicate = state.inventoryBrands.find(
    (brand) => brand.typeId === typeId && brand.name.toLowerCase() === name.toLowerCase() && brand.id !== id,
  );
  if (duplicate) return showToast("该设备类型下已存在同名品牌。", true);

  const previous = getInventoryBrand(id);
  const item = {
    id: id || createId("brand"),
    typeId,
    name,
    sortOrder: Math.max(0, Number(data.sortOrder || 1000)),
  };
  const index = state.inventoryBrands.findIndex((brand) => brand.id === id);
  if (index >= 0) state.inventoryBrands[index] = item;
  else state.inventoryBrands.push(item);

  // Inventory brand records act as stock catalogs only.
  // Assigned devices keep their own brand snapshot and should not be rewritten here.
  ensureInventoryExpanded(typeId, item.id);
  persistState(true);
  closeModal();
  render();
  showToast(index >= 0 ? "库存品牌已更新" : "库存品牌已新增");
}

function handleInventoryModelSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const typeId = form.dataset.typeId;
  const brandId = form.dataset.brandId;
  const id = form.dataset.id;
  const name = String(data.name || "").trim();
  if (!typeId || !brandId || !name) return showToast("请填写型号名称。", true);
  const previous = getInventoryModel(id);
  const isComputerModel = isComputerInventoryType(getType(typeId));
  const batchKey = previous?.batchKey || (isComputerModel ? createId("batch") : "");
  const inboundDate = isComputerModel ? String(data.inboundDate || previous?.inboundDate || "").trim() : "";
  if (isComputerModel && !/^\d{4}-\d{2}-\d{2}$/.test(inboundDate)) {
    return showToast("办公终端库存型号必须填写有效的入库时间。", true);
  }
  const duplicate = state.inventoryModels.find(
    (model) =>
      model.brandId === brandId &&
      model.name.toLowerCase() === name.toLowerCase() &&
      (model.batchKey || "") === batchKey &&
      model.id !== id,
  );
  if (duplicate) return showToast("该品牌下已存在同名型号。", true);

  const item = {
    id: id || createId("model"),
    typeId,
    brandId,
    name,
    batchKey,
    quantity: Math.max(0, Number(data.quantity || 0)),
    inboundDate,
    cpu: isComputerModel ? data.cpu || "" : "",
    memory: isComputerModel ? data.memory || "" : "",
    storage: isComputerModel ? normalizeStorageValue(data.storage) : "",
    gpu: isComputerModel ? data.gpu || "" : "",
    sortOrder: Math.max(0, Number(data.sortOrder || 1000)),
  };
  const index = state.inventoryModels.findIndex((model) => model.id === id);
  if (index >= 0) state.inventoryModels[index] = item;
  else state.inventoryModels.push(item);

  // Inventory model records act as stock catalogs only.
  // Assigned devices keep their own model snapshot and should not be rewritten here.
  const oldQuantity = Math.max(0, Number(previous?.quantity || 0));
  const newQuantity = Math.max(0, Number(item.quantity || 0));
  if (!previous && newQuantity > 0) {
    recordInventoryMovement({
      direction: "increase",
      typeName: getType(typeId)?.name || "",
      brandName: getInventoryBrand(brandId)?.name || "",
      modelName: item.name,
      quantity: newQuantity,
      sourceLabel: "手工新增",
      targetLabel: "IT物资库存",
      triggerAction: "manual_create",
    });
    state.inventoryPurchaseLogs.unshift({
      id: createId("purchase"),
      typeId,
      brandId,
      modelId: item.id,
      typeName: getType(typeId)?.name || "",
      brandName: getInventoryBrand(brandId)?.name || "",
      modelName: item.name,
      quantity: newQuantity,
      inboundDate: currentDateText(),
      cpu: isComputerModel ? item.cpu : "",
      memory: isComputerModel ? item.memory : "",
      storage: isComputerModel ? item.storage : "",
      gpu: isComputerModel ? item.gpu : "",
      sourceLabel: "手工新增",
      note: "通过库存型号页面手工新增库存",
      sourceMovementLogId: "",
      createdAt: currentTimestampText(),
    });
  } else if (previous && oldQuantity !== newQuantity) {
    recordInventoryMovement({
      direction: newQuantity > oldQuantity ? "increase" : "decrease",
      typeName: getType(typeId)?.name || "",
      brandName: getInventoryBrand(brandId)?.name || "",
      modelName: item.name,
      quantity: Math.abs(newQuantity - oldQuantity),
      sourceLabel: newQuantity > oldQuantity ? "手工调整" : "IT物资库存",
      targetLabel: newQuantity > oldQuantity ? "IT物资库存" : "手工调整",
      triggerAction: "manual_adjustment",
    });
  }
  ensureInventoryExpanded(typeId, brandId);
  persistState(true);
  closeModal();
  render();
  showToast(index >= 0 ? "库存型号已更新" : "库存型号已新增");
}

function handleInventoryImportSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const typeName = String(data.type || "").trim();
  const brandName = String(data.brand || "").trim();
  const modelName = String(data.model || "").trim();
  const quantity = Math.max(1, Number(data.quantity || 0));
  if (!typeName || !brandName || !modelName || !quantity) {
    return showToast("请填写类型、品牌、型号和数量。", true);
  }

  const isComputerImport = isComputerInventoryTypeName(typeName);
  const inboundDate = String(data.inboundDate || currentDateText()).trim();
  let type = isComputerImport ? computerInventoryType() || findInventoryTypeByName(typeName) : findInventoryTypeByName(typeName);
  if (!type) {
    type = {
      id: createId("type"),
      code: isComputerImport ? "computer" : inventoryTypeCodeFor(typeName),
      name: isComputerImport ? "办公终端" : typeName,
      unit: isComputerImport ? "台" : "件",
      sortOrder: nextTypeSortOrder(),
    };
    state.nonAssetTypes.push(type);
  } else if (isComputerImport) {
    type.name = "办公终端";
    type.code = type.code || "computer";
    type.unit = "台";
  }

  let brand = findInventoryBrandByName(type.id, brandName);
  if (!brand) {
    brand = {
      id: createId("brand"),
      typeId: type.id,
      name: brandName,
      sortOrder: nextBrandSortOrder(type.id),
    };
    state.inventoryBrands.push(brand);
  }

  let model = isComputerImport ? null : findInventoryModelByName(brand.id, modelName);
  if (!model) {
    model = {
      id: createId("model"),
      typeId: type.id,
      brandId: brand.id,
      name: modelName,
      batchKey: isComputerImport ? createId("batch") : "",
      quantity: 0,
      inboundDate: isComputerImport ? inboundDate : "",
      cpu: isComputerImport ? String(data.cpu || "").trim() : "",
      memory: isComputerImport ? String(data.memory || "").trim() : "",
      storage: isComputerImport ? normalizeStorageValue(data.storage) : "",
      gpu: isComputerImport ? String(data.gpu || "").trim() : "",
      sortOrder: nextModelSortOrder(brand.id),
    };
    state.inventoryModels.push(model);
  } else {
    model.batchKey = model.batchKey || "";
    if (isComputerImport) {
      model.inboundDate = model.inboundDate || inboundDate;
      model.cpu = model.cpu || String(data.cpu || "").trim();
      model.memory = model.memory || String(data.memory || "").trim();
      model.storage = model.storage || normalizeStorageValue(data.storage);
      model.gpu = model.gpu || String(data.gpu || "").trim();
    } else {
      model.inboundDate = "";
      model.cpu = "";
      model.memory = "";
      model.storage = "";
      model.gpu = "";
    }
  }
  model.quantity = Math.max(0, Number(model.quantity || 0)) + quantity;
  const configNote = inventoryModelConfigSummary(model);
  const noteParts = [
    String(data.note || "").trim(),
    isComputerImport && configNote ? `配置：${configNote}` : "",
  ].filter(Boolean);
  const movement = recordInventoryMovement({
    direction: "increase",
    typeName: type.name,
    brandName: brand.name,
    modelName: model.name,
    quantity,
    sourceLabel: isComputerImport ? "办公终端入库" : "外部导入",
    targetLabel: "IT物资库存",
    note: noteParts.join("；"),
    triggerAction: "import",
  });
  state.inventoryPurchaseLogs.unshift({
    id: createId("purchase"),
    typeId: type.id,
    brandId: brand.id,
    modelId: model.id,
    typeName: type.name,
    brandName: brand.name,
    modelName: model.name,
    quantity,
    inboundDate,
    cpu: isComputerImport ? model.cpu : "",
    memory: isComputerImport ? model.memory : "",
    storage: isComputerImport ? model.storage : "",
    gpu: isComputerImport ? model.gpu : "",
    sourceLabel: isComputerImport ? "办公终端入库" : "外部导入",
    note: String(data.note || "").trim(),
    sourceMovementLogId: movement.id,
    createdAt: currentTimestampText(),
  });

  state.filters.inventoryType = type.id;
  state.filters.inventoryBrand = brand.id;
  ensureInventoryExpanded(type.id, brand.id);
  persistState(true);
  closeModal();
  render();
  showToast(`已导入 ${type.name} / ${brand.name} / ${model.name}，数量 +${quantity}`);
}

function assignComputer(employeeId) {
  const select = document.querySelector(`[data-assign-computer="${CSS.escape(employeeId)}"]`);
  const computer = state.computers.find((item) => item.id === select?.value);
  if (!computer) return showToast("请选择可分配的办公终端", true);

  computer.userId = employeeId;
  normalizeComputersAgainstEmployees();
  persistState(true);
  openDeviceManager(employeeId);
  render();
  showToast("办公终端已分配");
}

function releaseComputer(computerId, employeeId) {
  const computer = state.computers.find((item) => item.id === computerId);
  if (!computer) return;

  computer.userId = null;
  computer.status = "idle";

  normalizeComputersAgainstEmployees();
  persistState(true);
  openDeviceManager(employeeId);
  render();
  showToast("办公终端已解除分配");
}

function xmlEscape(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function safeSheetName(name) {
  return String(name || "Sheet1")
    .replace(/[\[\]\*\?\/\\:]/g, "")
    .slice(0, 31) || "Sheet1";
}

function excelCell(value, type = "String", styleId = "") {
  const style = styleId ? ` ss:StyleID="${styleId}"` : "";
  if (value === null || value === undefined || value === "") {
    return `<Cell${style}/>`;
  }
  return `<Cell${style}><Data ss:Type="${type}">${xmlEscape(value)}</Data></Cell>`;
}

function excelSheet(sheet) {
  const columns = sheet.headers
    .map((header) => `<Column ss:AutoFitWidth="0" ss:Width="${Math.min(260, Math.max(90, String(header).length * 10 + 28))}"/>`)
    .join("");
  const headerRow = `<Row>${sheet.headers.map((header) => excelCell(header, "String", "Header")).join("")}</Row>`;
  const rows = sheet.rows
    .map((row) => `<Row>${row.map((cell) => excelCell(cell.value ?? cell, cell.type || "String", cell.style || "")).join("")}</Row>`)
    .join("");

  return `<Worksheet ss:Name="${xmlEscape(safeSheetName(sheet.name))}"><Table>${columns}${headerRow}${rows}</Table></Worksheet>`;
}

function createExcelWorkbook(sheets) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
  xmlns:o="urn:schemas-microsoft-com:office:office"
  xmlns:x="urn:schemas-microsoft-com:office:excel"
  xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
  xmlns:html="http://www.w3.org/TR/REC-html40">
  <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
    <Author>办公资产中台</Author>
    <Created>${new Date().toISOString()}</Created>
  </DocumentProperties>
  <Styles>
    <Style ss:ID="Default" ss:Name="Normal">
      <Alignment ss:Vertical="Center"/>
      <Font ss:FontName="Microsoft YaHei" ss:Size="10"/>
    </Style>
    <Style ss:ID="Header">
      <Font ss:FontName="Microsoft YaHei" ss:Size="10" ss:Bold="1" ss:Color="#FFFFFF"/>
      <Interior ss:Color="#17324D" ss:Pattern="Solid"/>
      <Alignment ss:Vertical="Center"/>
    </Style>
  </Styles>
  ${sheets.map(excelSheet).join("")}
</Workbook>`;
}

function downloadExcel(filename, sheets) {
  if (!sheets.length) return;
  const blob = new Blob([`\ufeff${createExcelWorkbook(sheets)}`], {
    type: "application/vnd.ms-excel;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportDateStamp() {
  return new Date().toISOString().slice(0, 10).replaceAll("-", "");
}

function employeeDeviceExportSummary(employee) {
  const devices = employeeDevices(employee);
  const computerNames = devices
    .filter((device) => device.category === "computer")
    .map((device) => device.label);
  const monitorDetails = devices
    .filter((device) => device.category === "monitor")
    .map((device) => device.detail || device.label);
  const accessoryDetails = devices
    .filter((device) => device.category === "non-asset")
    .map((device) => `${device.label}${device.detail ? ` ${device.detail}` : ""}`);

  return {
    computers: computerNames.join("、"),
    monitors: monitorDetails.join("、"),
    accessories: accessoryDetails.join("、"),
  };
}

function employeeExportRows(employees) {
  return employees.map((employee) => {
    const deviceSummary = employeeDeviceExportSummary(employee);
    return [
      employee.employeeNo,
      employee.name,
      orgName(employee.orgId),
      orgPathName(employee.orgId),
      employee.department || "",
      employee.position || "",
      statusLabels[employee.status] || employee.status,
      deviceSummary.computers,
      deviceSummary.monitors,
      deviceSummary.accessories,
      employee.email || "",
      employee.mobile || "",
    ];
  });
}

function employeeDeviceExportRows(employees) {
  return employees.flatMap((employee) =>
    employeeDevices(employee).map((device) => [
      employee.employeeNo,
      employee.name,
      orgPathName(employee.orgId),
      device.category === "computer" ? "办公终端" : device.category === "monitor" ? "显示屏" : "非资产设备",
      device.label,
      device.detail,
      device.quantity || 1,
    ]),
  );
}

function computerExportRows(computers) {
  return computers.map((computer) => {
    const user = getCurrentUser(computer);
    return [
      computer.deviceName,
      orgName(computer.orgId),
      orgPathName(computer.orgId),
      deviceTypeLabel(computer.deviceType),
      computer.brand || "",
      computer.model || "",
      computer.cpu || "",
      computer.memory || "",
      computer.storage || "",
      computer.gpu || "",
      computer.fixedAssetCode || "",
      computer.purchaseDate || "",
      computer.registeredDate || "",
      computer.snSt || "",
      computer.wifiMac || "",
      computer.ethernetMac || "",
      computer.location || "",
      computer.department || "",
      user?.name || "",
      statusLabels[computer.status] || computer.status,
    ];
  });
}

function inventoryDetailExportRows(rows, warehouse) {
  return rows.map(({ type, brand, model }) => {
    return [
      warehouse?.name || "",
      warehouse?.code || "",
      type.name,
      brand.name,
      model.name,
      Math.max(0, Number(model.quantity || 0)),
      type.unit || "件",
    ];
  });
}

function inventoryMovementLogExportRows(logs) {
  return logs.map((log) => [
    formatDateTime(log.occurredAt),
    inventoryDirectionLabel(log.direction),
    log.typeName || "",
    log.brandName || "",
    log.modelName || "",
    log.quantity,
    log.sourceLabel || "",
    log.targetLabel || "",
    log.relatedEmployeeNo || "",
    log.relatedEmployeeName || "",
    log.triggerAction || "",
    log.note || "",
  ]);
}

function exportInventory() {
  const warehouse = inventoryWarehouseById(ensureInventoryWarehouseView());
  if (!warehouse) return showToast("请先选择可访问的仓库。", true);
  const rows = inventoryFlatRows();
  if (!rows.length) return showToast("当前筛选条件下没有可导出的IT物资", true);

  downloadExcel(`办公资产-IT物资-${warehouse.code || "仓库"}-${exportDateStamp()}.xls`, [
    {
      name: "IT物资明细",
      headers: ["仓库名称", "仓库编码", "设备类型", "品牌", "型号", "数量", "单位"],
      rows: inventoryDetailExportRows(rows, warehouse),
    },
  ]);
  showToast(`已导出 ${rows.length} 条 IT 物资明细`);
}

function exportInventoryMovementLogs() {
  const logs = state.inventoryMovementLogs || [];
  if (!logs.length) return showToast("当前没有可导出的物资变动日志", true);
  downloadExcel(`办公资产-IT物资变动日志-${exportDateStamp()}.xls`, [
    {
      name: "物资变动日志",
      headers: ["时间", "增减", "设备类型", "品牌", "型号", "数量", "来源", "流向", "相关人员编号", "相关人员姓名", "触发动作", "标注"],
      rows: inventoryMovementLogExportRows(logs),
    },
  ]);
  showToast(`已导出 ${logs.length} 条物资变动日志`);
}

function flowRecordExportRows(logs) {
  return logs.map((log) => [
    formatDateTime(log.occurredAt),
    flowRecordActionLabel(log),
    flowRecordCategory(log),
    log.typeName || "",
    log.brandName || "",
    log.modelName || "",
    log.quantity,
    flowRecordStockImpact(log),
    log.sourceLabel || "",
    log.targetLabel || "",
    log.relatedEmployeeNo || "",
    log.relatedEmployeeName || "",
    log.triggerAction || "",
    log.note || "",
  ]);
}

function exportFlowRecords() {
  const logs = getFilteredFlowRecords();
  if (!logs.length) return showToast("当前筛选条件下没有可导出的物资流转记录", true);
  downloadExcel(`办公资产-物资流转记录-${exportDateStamp()}.xls`, [
    {
      name: "物资流转记录",
      headers: [
        "流转时间",
        "业务类型",
        "业务分类",
        "物资类型",
        "品牌",
        "型号",
        "数量",
        "库存影响",
        "调出方",
        "接收方",
        "人员编号",
        "关联人员",
        "触发动作",
        "备注",
      ],
      rows: flowRecordExportRows(logs),
    },
  ]);
  showToast(`已导出 ${logs.length} 条物资流转记录`);
}

function exportInventoryPurchaseLogs() {
  const warehouse = inventoryWarehouseById(ensureInventoryWarehouseView());
  if (!warehouse) return showToast("请先选择可访问的仓库。", true);
  const logs = (state.inventoryPurchaseLogs || []).filter((log) => sameRecordId(log.warehouseId, warehouse.id));
  if (!logs.length) return showToast("当前没有可导出的采购入库记录", true);
  const standardLogs = logs.filter((log) => !isComputerPurchaseLog(log));
  const computerLogs = logs.filter((log) => isComputerPurchaseLog(log));
  const sheets = [];
  if (standardLogs.length) {
    sheets.push({
      name: "普通物资入库",
      headers: ["仓库名称", "仓库编码", "入库日期", "物资类型", "品牌", "型号", "数量", "来源", "备注", "记录时间"],
      rows: standardLogs
        .sort((a, b) =>
          String(b.inboundDate || b.createdAt || "").localeCompare(String(a.inboundDate || a.createdAt || "")),
        )
        .map((log) => [
          warehouse.name,
          warehouse.code || "",
          log.inboundDate || "",
          log.typeName || "",
          log.brandName || "",
          log.modelName || "",
          log.quantity,
          log.sourceLabel || "",
          log.note || "",
          log.createdAt || "",
        ]),
    });
  }
  if (computerLogs.length) {
    sheets.push({
      name: "办公终端入库",
      headers: ["仓库名称", "仓库编码", "入库日期", "品牌", "型号", "数量", "CPU", "内存", "存储", "显卡", "来源", "备注", "记录时间"],
      rows: computerLogs
        .sort((a, b) =>
          String(b.inboundDate || b.createdAt || "").localeCompare(String(a.inboundDate || a.createdAt || "")),
        )
        .map((log) => [
          warehouse.name,
          warehouse.code || "",
          log.inboundDate || "",
          log.brandName || "",
          log.modelName || "",
          log.quantity,
          log.cpu || "",
          log.memory || "",
          log.storage || "",
          log.gpu || "",
          log.sourceLabel || "",
          log.note || "",
          log.createdAt || "",
        ]),
    });
  }
  downloadExcel(`办公资产-IT物资采购入库-${warehouse.code || "仓库"}-${exportDateStamp()}.xls`, sheets);
  showToast(`已导出 ${logs.length} 条采购入库记录`);
}

function exportSelectedEmployees() {
  const employees = sortEmployees(state.employees.filter((employee) => state.selectedEmployeeIds.includes(employee.id)));
  if (!employees.length) return showToast("请先选择至少一名使用人员", true);

  downloadExcel(`办公资产-使用人员-${exportDateStamp()}.xls`, [
    {
      name: "使用人员",
      headers: [
        "人员编号",
        "人员姓名",
        "所属组织",
        "组织路径",
        "部门",
        "岗位",
        "人员状态",
        "办公终端",
        "显示屏",
        "其它配件",
        "邮箱",
        "手机号",
      ],
      rows: employeeExportRows(employees),
    },
    {
      name: "人员设备明细",
      headers: ["人员编号", "人员姓名", "组织路径", "设备类别", "设备名称", "型号或数量", "数量"],
      rows: employeeDeviceExportRows(employees),
    },
  ]);
  showToast(`已导出 ${employees.length} 名使用人员`);
}

function exportSelectedComputers() {
  const computers = state.computers.filter((computer) => state.selectedComputerIds.includes(computer.id));
  if (!computers.length) return showToast("请先选择至少一台办公终端", true);

  downloadExcel(`办公资产-办公终端-${exportDateStamp()}.xls`, [
    {
      name: "办公终端",
      headers: [
        "设备名",
        "所属组织",
        "组织路径",
        "设备类型",
        "设备品牌",
        "型号",
        "CPU",
        "内存",
        "存储",
        "显卡",
        "固资编码",
        "购置日期",
        "注册日期",
        "SN/ST",
        "Wifi MAC",
        "网口 MAC",
        "位置",
        "部门",
        "使用用户",
        "IT资产状态",
      ],
      rows: computerExportRows(computers),
    },
  ]);
  showToast(`已导出 ${computers.length} 台办公终端`);
}

function auditExportRows(logs) {
  return logs.map((log) => [
    log.createdAt || "",
    auditCategoryLabel(auditCategoryForLog(log)),
    auditChangeLabel(log),
    auditEntityTypeLabel(log.entityType),
    log.entityName || "",
    log.employeeId || "",
    log.employeeName || "",
    log.deviceName || "",
    auditValueText(log.oldValue),
    auditValueText(log.newValue),
    log.summary || "",
    log.actor || "",
    log.source || "",
  ]);
}

async function exportAuditLogs() {
  const payload = await requestJson(buildAuditLogsUrl(5000));
  const logs = Array.isArray(payload.logs) ? payload.logs : [];
  if (!logs.length) return showToast("当前筛选条件下没有可导出的日志", true);

  downloadExcel(`办公资产-操作日志-${exportDateStamp()}.xls`, [
    {
      name: "操作日志",
      headers: [
        "时间",
        "操作类别",
        "具体变动",
        "对象类别",
        "对象名称",
        "人员编号",
        "人员姓名",
        "设备名",
        "旧值",
        "新值",
        "说明",
        "操作人",
        "来源",
      ],
      rows: auditExportRows(logs),
    },
  ]);
  showToast(`已导出 ${logs.length} 条操作日志`);
}

function showToast(message, isError = false) {
  const root = document.querySelector("#toastRoot");
  const toast = document.createElement("div");
  toast.className = `toast${isError ? " error" : ""}`;
  toast.textContent = message;
  root.appendChild(toast);
  window.setTimeout(() => toast.remove(), 2600);
}

document.addEventListener("click", (event) => {
  const actionElement = event.target.closest("[data-action]");
  if (!actionElement) return;
  const action = actionElement.dataset.action;

  if (action === "logout") {
    logout();
    return;
  }

  if (action === "toggle-theme") {
    toggleTheme();
    return;
  }

  if (action === "quick-create-ticket") {
    if (!hasPermission("tickets", "create")) {
      showToast("当前账号没有新建工单权限。", true);
      return;
    }
    openTicketModal();
    return;
  }

  if (action === "open-notifications") {
    if (!hasPermission("notifications", "view")) {
      showToast("当前账号没有查看消息提醒权限。", true);
      return;
    }
    const page = "serviceManagement";
    state.page = page;
    serviceState().view = "notifications";
    persistState(false);
    render();
    loadServiceManagement()
      .then(() => renderIfCurrentPage(page))
      .catch((error) => showToast(`消息提醒加载失败：${error.message}`, true));
    return;
  }

  if (action === "settings-view") {
    settingsState.view = actionElement.dataset.view || "system";
    if (!syncSettingsTabsAndContent()) {
      render();
    }
    return;
  }

  if (action === "check-for-update") {
    handleUpdateCheck(actionElement);
    return;
  }

  if (action === "apply-selected-update") {
    handleApplySelectedUpdate();
    return;
  }

  if (action === "open-computer-scrap") {
    if (!hasPermission("scrap_management", "create")) {
      showToast("当前账号没有报废处理权限。", true);
      return;
    }
    openComputerScrapModal(actionElement.dataset.id, actionElement.dataset.name || "");
    return;
  }

  if (action === "open-usage-scrap") {
    if (!hasPermission("scrap_management", "create")) {
      showToast("当前账号没有报废处理权限。", true);
      return;
    }
    openUsageScrapModal(
      actionElement.dataset.kind || "",
      actionElement.dataset.id || "",
      actionElement.dataset.employeeId || "",
      actionElement.dataset.label || "",
    );
    return;
  }

  if (action === "open-scrap-record") {
    openScrapRecordDetail(actionElement.dataset.id || "");
    return;
  }

  if (action === "refresh-scrap-records") {
    loadScrapRecords({ toast: true })
      .then(() => renderIfCurrentPage("scrapRecords"))
      .catch((error) => showToast(`报废记录加载失败：${error.message}`, true));
    return;
  }

  if (action === "export-scrap-records") {
    exportScrapRecords();
    return;
  }

  if (action === "apply-scrap-filters") {
    applyScrapFilters();
    return;
  }

  if (action === "clear-scrap-filters") {
    clearScrapFilters();
    return;
  }

  if (action === "close-modal") {
    // 点击对话框本体（即原生 ::backdrop 区域）才关闭；点击面板内部不关闭。
    if (actionElement.tagName === "DIALOG" && event.target !== actionElement) return;
    closeModal();
    return;
  }

  if (action === "toggle-employee-selection") {
    const employeeId = actionElement.dataset.id;
    const selected = new Set(state.selectedEmployeeIds);
    if (actionElement.checked) selected.add(employeeId);
    else selected.delete(employeeId);
    state.selectedEmployeeIds = [...selected];
    persistState(false);
    render();
    return;
  }

  if (action === "toggle-computer-selection") {
    const computerId = actionElement.dataset.id;
    const selected = new Set(state.selectedComputerIds);
    if (actionElement.checked) selected.add(computerId);
    else selected.delete(computerId);
    state.selectedComputerIds = [...selected];
    persistState(false);
    render();
    return;
  }

  if (action === "toggle-all-computers" || action === "select-all-computers") {
    const currentIds = getFilteredComputers().map((computer) => computer.id);
    const selected = new Set(state.selectedComputerIds);
    const allSelected = currentIds.length > 0 && currentIds.every((id) => selected.has(id));
    currentIds.forEach((id) => {
      if (allSelected) selected.delete(id);
      else selected.add(id);
    });
    state.selectedComputerIds = [...selected];
    persistState(false);
    render();
    return;
  }

  if (action === "clear-computer-selection") {
    state.selectedComputerIds = [];
    persistState(false);
    render();
    return;
  }

  if (action === "select-all-employees") {
    const selected = new Set(state.selectedEmployeeIds);
    getFilteredEmployees().forEach((employee) => selected.add(employee.id));
    state.selectedEmployeeIds = [...selected];
    persistState(false);
    render();
    return;
  }

  if (action === "clear-employee-selection") {
    state.selectedEmployeeIds = [];
    persistState(false);
    render();
    return;
  }

  if (action === "clear-employee-filters") {
    state.filters.employees = "";
    state.filters.employeeAssetSearch = "";
    state.filters.employeeStatus = "";
    state.filters.employeeOrg = "";
    state.filters.employeeDevice = "";
    syncFilterSearchDraftsFromFilters();
    persistState(false);
    render();
    return;
  }

  if (action === "apply-employee-search") {
    applyEmployeeSearchFilters();
    return;
  }

  if (action === "clear-inventory-filters") {
    state.filters.inventorySearch = "";
    state.filters.inventoryType = "";
    state.filters.inventoryBrand = "";
    syncFilterSearchDraftsFromFilters();
    persistState(false);
    render();
    return;
  }

  if (action === "apply-inventory-search") {
    applyInventorySearchFilter();
    return;
  }

  if (action === "clear-flow-record-filters") {
    state.filters.flowSearch = "";
    state.filters.flowType = "";
    state.filters.flowAction = "";
    state.filters.flowCategory = "";
    state.filters.flowEmployee = "";
    state.filters.flowSourceTarget = "";
    state.filters.flowStartDate = "";
    state.filters.flowEndDate = "";
    syncFilterSearchDraftsFromFilters();
    persistState(false);
    render();
    return;
  }

  if (action === "apply-flow-record-filters") {
    applyFlowRecordFilters();
    return;
  }

  if (action === "export-employees") {
    exportSelectedEmployees();
    return;
  }

  if (action === "export-computers") {
    exportSelectedComputers();
    return;
  }

  if (action === "export-inventory") {
    exportInventory();
    return;
  }

  if (action === "export-inventory-purchase") {
    exportInventoryPurchaseLogs();
    return;
  }

  if (action === "export-inventory-log") {
    exportInventoryMovementLogs();
    return;
  }

  if (action === "export-flow-records") {
    exportFlowRecords();
    return;
  }

  if (action === "refresh-audit") {
    refreshAuditLogs()
      .then(() => showToast("已刷新操作日志"))
      .catch((error) => {
        console.error("Unable to load audit logs", error);
        showToast(`日志加载失败：${error.message}`, true);
      });
    return;
  }

  if (action === "apply-audit-filters") {
    applyAuditFilters()
      .then(() => showToast("已应用日志筛选"))
      .catch((error) => {
        console.error("Unable to apply audit filters", error);
        showToast(`日志筛选失败：${error.message}`, true);
      });
    return;
  }

  if (action === "export-audit") {
    exportAuditLogs().catch((error) => {
      console.error("Unable to export audit logs", error);
      showToast(`日志导出失败：${error.message}`, true);
    });
    return;
  }

  if (action === "navigate") {
    const targetPage = actionElement.dataset.page || "dashboard";
    if (targetPage === state.page) return;
    state.page = targetPage;
    persistState(false);
    render();
    if (state.page === "settings" && !settingsState.loaded) {
      loadSettingsState({ users: isAdminUser() })
        .then(() => renderIfCurrentPage(targetPage))
        .catch((error) => {
          console.error("Unable to load settings", error);
          showToast(`设置加载失败：${error.message}`, true);
        });
    }
    if (state.page === "audit") {
      refreshAuditLogs({ silent: true })
        .then(() => renderIfCurrentPage(targetPage))
        .catch((error) => {
          console.error("Unable to load audit logs", error);
          showToast(`日志加载失败：${error.message}`, true);
        });
    }
    if (state.page === "scrapRecords") {
      loadScrapReasons().catch(() => {});
      loadScrapRecords()
        .then(() => renderIfCurrentPage(targetPage))
        .catch((error) => {
          console.error("Unable to load scrap records", error);
          showToast(`报废记录加载失败：${error.message}`, true);
        });
    }
    if (state.page === "tickets") {
      loadTickets()
        .then(() => renderIfCurrentPage(targetPage))
        .catch((error) => {
          console.error("Unable to load tickets", error);
          showToast(`工单加载失败：${error.message}`, true);
        });
    }
    if (state.page === "inspection") {
      loadInspectionData({ force: true })
        .then(() => {
          renderIfCurrentPage(targetPage);
          maybeStartInspectionFromHash();
        })
        .catch((error) => {
          console.error("Unable to load inspection data", error);
          showToast(`巡检数据加载失败：${error.message}`, true);
        });
    }
    if (state.page === "serviceManagement") {
      loadServiceManagement()
        .then(() => renderIfCurrentPage(targetPage))
        .catch((error) => {
          console.error("Unable to load service management", error);
          showToast(`服务管理加载失败：${error.message}`, true);
        });
    }
    if (state.page === "governance") {
      loadGovernance()
        .then(() => renderIfCurrentPage(targetPage))
        .catch((error) => {
          console.error("Unable to load governance data", error);
          showToast(`治理数据加载失败：${error.message}`, true);
        });
    }
    return;
  }

  if (action === "toggle-org") {
    const orgId = actionElement.dataset.id;
    setOrgExpanded(orgId, !isOrgExpanded(orgId));
    render();
    return;
  }

  if (action === "expand-all-orgs") {
    state.expandedOrgIds = state.orgs.map((org) => org.id);
    persistState(false);
    render();
    return;
  }

  if (action === "collapse-all-orgs") {
    state.expandedOrgIds = [];
    persistState(false);
    render();
    return;
  }

  if (action === "toggle-inventory-type") {
    const typeId = actionElement.dataset.id || "";
    setInventoryTypeExpanded(typeId, !isInventoryTypeExpanded(typeId));
    render();
    return;
  }

  if (action === "toggle-inventory-brand") {
    const brandId = actionElement.dataset.id || "";
    setInventoryBrandExpanded(brandId, !isInventoryBrandExpanded(brandId));
    render();
    return;
  }

  if (action === "expand-all-inventory") {
    expandVisibleInventoryNodes();
    render();
    return;
  }

  if (action === "collapse-all-inventory") {
    state.expandedInventoryTypeIds = [];
    state.expandedInventoryBrandIds = [];
    persistState(false);
    render();
    return;
  }

  if (action === "open-computer") openComputerModal(actionElement.dataset.id || "");
  if (action === "open-employee") openEmployeeModal(actionElement.dataset.id || "", actionElement.dataset.orgId || "");
  if (action === "open-employee-offboard") {
    openEmployeeOffboardModal(actionElement.dataset.id || "");
    return;
  }
  if (action === "create-database-backup") {
    handleDatabaseBackupCreate(actionElement);
    return;
  }
  if (action === "open-database-backup-download") {
    openDatabaseBackupDownloadModal(actionElement.dataset.id || "");
    return;
  }
  if (action === "open-settings-user") {
    openSettingsUserModal(actionElement.dataset.id || "");
    return;
  }
  if (action === "open-left-employee") {
    openLeftEmployeeModal(actionElement.dataset.id || "");
    return;
  }
  if (action === "manage-devices") openDeviceManager(actionElement.dataset.id);
  if (action === "open-org") openOrgModal(actionElement.dataset.id || "", actionElement.dataset.parentId || "");
  if (action === "open-type") openTypeModal(actionElement.dataset.id || "");
  if (action === "open-inventory-import") {
    openInventoryImportModal();
    return;
  }
  if (action === "open-inventory-brand") {
    openInventoryBrandModal(actionElement.dataset.typeId, actionElement.dataset.id || "");
    return;
  }
  if (action === "open-inventory-model") {
    openInventoryModelModal(actionElement.dataset.typeId, actionElement.dataset.brandId, actionElement.dataset.id || "");
    return;
  }
  if (action === "select-inventory-warehouse") {
    const warehouseId = String(actionElement.dataset.id || "");
    if (!warehouseId) return;
    inventoryWarehouseView = warehouseId;
    persistState(false);
    render();
    return;
  }
  if (action === "open-warehouse-directory") {
    openWarehouseDirectoryModal();
    return;
  }
  if (action === "open-warehouse") {
    openWarehouseModal(actionElement.dataset.id || "");
    return;
  }
  if (action === "delete-warehouse") {
    deleteWarehouse(actionElement.dataset.id || "");
    return;
  }
  if (action === "open-inventory-transfer") {
    openInventoryTransferModal();
    return;
  }
  if (action === "edit-inventory-log-note") {
    openInventoryMovementNoteModal(actionElement.dataset.id || "");
    return;
  }
  if (action === "commit-device-stock") {
    finishDeviceSave("deduct");
    return;
  }
  if (action === "commit-device-register") {
    finishDeviceSave("register");
    return;
  }
  if (action === "cancel-device-confirm") {
    pendingDeviceSave = null;
    closeModal();
    return;
  }
  if (action === "recover-selected-devices") {
    openDeviceRecoveryConfirm(actionElement.dataset.employeeId || "", actionElement.dataset.kind || "");
    return;
  }
  if (action === "confirm-device-recovery") {
    confirmDeviceRecovery();
    return;
  }
  if (action === "cancel-device-recovery") {
    const pending = pendingDeviceRecovery;
    pendingDeviceRecovery = null;
    closeModal();
    if (pending?.employeeId) openDeviceManager(pending.employeeId);
    return;
  }
  if (action === "confirm-leave-recovery") {
    confirmLeaveRecovery();
    return;
  }
  if (action === "cancel-leave-recovery") {
    pendingLeaveRecovery = null;
    closeModal();
    return;
  }
  if (action === "assign-computer") assignComputer(actionElement.dataset.employeeId);
  if (action === "release-computer") releaseComputer(actionElement.dataset.id, actionElement.dataset.employeeId);
  if (action === "edit-monitor") openDeviceManager(actionElement.dataset.employeeId);

  if (action === "add-monitor-module") {
    const employeeId = actionElement.dataset.employeeId;
    const list = document.querySelector(`[data-monitor-list="${CSS.escape(employeeId)}"]`);
    if (list) {
      list.insertAdjacentHTML("beforeend", renderMonitorModule(employeeId, {}, true));
      list.lastElementChild?.querySelector('input[name="brand"]')?.focus();
    }
    return;
  }

  if (action === "add-nonasset-module") {
    const employeeId = actionElement.dataset.employeeId;
    const list = document.querySelector(`[data-nonasset-list="${CSS.escape(employeeId)}"]`);
    const typeId = state.nonAssetTypes.find((type) => type.id === "mouse")?.id || state.nonAssetTypes[0]?.id || "mouse";
    if (list) {
      list.insertAdjacentHTML("beforeend", renderNonAssetModule(employeeId, { typeId, quantity: 1 }, true));
      list.lastElementChild?.querySelector('select[name="typeId"]')?.focus();
    }
    return;
  }

  if (action === "remove-device-module") {
    actionElement.closest(".device-module")?.remove();
    return;
  }

  if (action === "delete-computer") {
    return showToast("终端不支持直接删除，请通过编辑将生命周期状态调整为报废。", true);
    /*
    const computer = state.computers.find((item) => item.id === actionElement.dataset.id);
    if (computer && window.confirm(`确定删除办公终端 ${computer.deviceName} 吗？`)) {
      state.computers = state.computers.filter((item) => item.id !== computer.id);
      state.selectedComputerIds = state.selectedComputerIds.filter((id) => id !== computer.id);
      persistState(true);
      render();
      showToast("办公终端已删除");
    }
    */
  }

  if (action === "delete-employee") {
    return showToast("人员不支持直接删除，请通过受控离职回收流程处理。", true);
    /*
    const employee = getEmployee(actionElement.dataset.id);
    if (employee && window.confirm(`确定删除人员 ${employee.name} 吗？名下办公终端会变为未分配。`)) {
      employeeRecoveryDevices(employee)
        .filter((device) => device.category !== "computer")
        .forEach((device) => {
          const matchedMonitor = (employee.monitors || []).find((item) => `monitor:${item.id}` === device.key);
          const matchedAsset = getNonAssetItems(employee).find((item) => `nonasset:${item.id}` === device.key);
          if (matchedMonitor?.stockAdjusted || matchedAsset?.stockAdjusted) {
            returnDeviceToInventory(device, {
              sourceLabel: employeeLogLabel(employee.employeeNo, employee.name),
              targetLabel: "IT物资库存",
              note: "删除人员时回收入库",
              relatedEmployeeNo: employee.employeeNo || "",
              relatedEmployeeName: employee.name || "",
              triggerAction: "employee_delete_recovery",
            });
          }
        });
      state.computers.forEach((computer) => {
        if (computer.userId === employee.id) {
          computer.userId = null;
          computer.status = "idle";
        }
      });
      state.employees = state.employees.filter((item) => item.id !== employee.id);
      state.selectedEmployeeIds = state.selectedEmployeeIds.filter((id) => id !== employee.id);
      normalizeComputersAgainstEmployees();
      persistState(true);
      render();
      showToast("人员已删除");
    }
    */
  }

  if (action === "delete-monitor") {
    return showToast("已登记物资只能通过回收命令归还，不能直接删除。", true);
    /*
    const employee = getEmployee(actionElement.dataset.employeeId);
    if (employee && window.confirm("确定删除这条显示屏记录吗？")) {
      const removed = (employee.monitors || []).find((monitor) => monitor.id === actionElement.dataset.id);
      if (removed?.stockAdjusted) {
        returnDeviceToInventory({
          category: "monitor",
          quantity: 1,
          typeId: removed.typeId || defaultMonitorTypeId(),
          typeName: getType(removed.typeId || defaultMonitorTypeId())?.name || "显示屏",
          brand: removed.brand || "",
          model: removed.model || "",
          brandId: removed.inventoryBrandId || "",
          modelId: removed.inventoryModelId || "",
        }, {
          sourceLabel: employeeLogLabel(employee.employeeNo, employee.name),
          targetLabel: "IT物资库存",
          note: "删除显示屏记录回收入库",
          relatedEmployeeNo: employee.employeeNo || "",
          relatedEmployeeName: employee.name || "",
          triggerAction: "delete_monitor",
        });
      }
      employee.monitors = employee.monitors.filter((monitor) => monitor.id !== actionElement.dataset.id);
      persistState(true);
      openDeviceManager(employee.id);
      render();
      showToast("显示屏记录已删除");
    }
    */
  }

  if (action === "delete-nonasset") {
    return showToast("已登记物资只能通过回收命令归还，不能直接删除。", true);
    /*
    const employee = getEmployee(actionElement.dataset.employeeId);
    if (employee && window.confirm("确定删除这条非资产设备记录吗？")) {
      const removed = getNonAssetItems(employee).find((item) => item.id === actionElement.dataset.id);
      if (removed?.stockAdjusted) {
        returnDeviceToInventory({
          category: "non-asset",
          quantity: Math.max(1, Number(removed.quantity || 1)),
          typeId: removed.typeId,
          typeName: getType(removed.typeId)?.name || "非资产设备",
          brand: removed.brand || "",
          model: removed.model || "",
          brandId: removed.inventoryBrandId || "",
          modelId: removed.inventoryModelId || "",
        }, {
          sourceLabel: employeeLogLabel(employee.employeeNo, employee.name),
          targetLabel: "IT物资库存",
          note: "删除非资产设备记录回收入库",
          relatedEmployeeNo: employee.employeeNo || "",
          relatedEmployeeName: employee.name || "",
          triggerAction: "delete_nonasset",
        });
      }
      employee.nonAssetItems = getNonAssetItems(employee).filter((item) => item.id !== actionElement.dataset.id);
      syncNonAssetAggregate(employee);
      persistState(true);
      openDeviceManager(employee.id);
      render();
      showToast("非资产设备记录已删除");
    }
    */
  }

  if (action === "delete-org") {
    return showToast("组织不支持直接删除，请先调整组织关系后再由迁移处理。", true);
    /*
    const org = getOrg(actionElement.dataset.id);
    if (org && window.confirm(`确定删除组织 ${org.name} 吗？直接挂在该组织上的记录会变为未分配，下级组织会提升为根组织。`)) {
      state.employees.forEach((employee) => {
        if (employee.orgId === org.id) employee.orgId = "";
      });
      state.computers.forEach((computer) => {
        if (computer.orgId === org.id) computer.orgId = "";
      });
      state.orgs.forEach((item) => {
        if (item.parentId === org.id) item.parentId = "";
      });
      state.orgs = state.orgs.filter((item) => item.id !== org.id);
      state.expandedOrgIds = state.expandedOrgIds.filter((id) => id !== org.id);
      persistState(true);
      render();
      showToast("组织已删除");
    }
    */
  }

  if (action === "delete-type") {
    return showToast("字典类型删除已暂时禁用，避免绕过库存和审计事务。", true);
    /*
    const type = getType(actionElement.dataset.id);
    if (!type) return;
    if (isProtectedInventoryType(type)) {
      return showToast("办公终端类型为系统保留分组，不能删除。", true);
    }
    const assignedCount = state.employees.reduce((sum, employee) => {
      const monitorCount = (employee.monitors || []).filter((item) => item.typeId === type.id).length;
      const nonAssetCount = getNonAssetItems(employee).filter((item) => item.typeId === type.id).length;
      return sum + monitorCount + nonAssetCount;
    }, 0);
    if (assignedCount > 0) {
      return showToast(`类型 ${type.name} 仍被 ${assignedCount} 条人员设备记录引用，无法删除。`, true);
    }
    const stockCount =
      state.inventoryBrands.filter((item) => item.typeId === type.id).length +
      state.inventoryModels.filter((item) => item.typeId === type.id).length;
    if (
      stockCount > 0 &&
      !window.confirm(`类型 ${type.name} 下还有 ${stockCount} 条库存记录，确认删除吗？删除后将同步清理下级品牌和型号。`)
    ) {
      return;
    }
      state.inventoryModels
        .filter((item) => item.typeId === type.id && Number(item.quantity || 0) > 0)
        .forEach((item) => {
          const brand = getInventoryBrand(item.brandId);
          recordInventoryMovement({
            direction: "decrease",
            typeName: type.name,
            brandName: brand?.name || "",
            modelName: item.name || "",
            quantity: Math.max(1, Number(item.quantity || 0)),
            sourceLabel: "IT物资库存",
            targetLabel: "删除设备类型",
            note: "删除类型时清空库存",
            triggerAction: "delete_type",
          });
        });
      const removedBrandIds = new Set(
        state.inventoryBrands.filter((item) => item.typeId === type.id).map((item) => item.id),
      );
      state.inventoryModels = state.inventoryModels.filter(
        (item) => item.typeId !== type.id && !removedBrandIds.has(item.brandId),
      );
      state.inventoryBrands = state.inventoryBrands.filter((item) => item.typeId !== type.id);
      state.nonAssetTypes = state.nonAssetTypes.filter((item) => item.id !== type.id);
      state.expandedInventoryTypeIds = state.expandedInventoryTypeIds.filter((id) => id !== type.id);
      state.expandedInventoryBrandIds = state.expandedInventoryBrandIds.filter((id) => !removedBrandIds.has(id));
      persistState(true);
      render();
      showToast("设备类型已删除");
  }
  */
  }

  if (action === "delete-inventory-brand") {
    return showToast("库存品牌删除已暂时禁用，避免绕过库存和审计事务。", true);
    /*
    const brand = getInventoryBrand(actionElement.dataset.id);
    const models = brand ? inventoryModelsForBrand(brand.id) : [];
    if (!brand) return;
    if (models.length) return showToast("请先删除或迁移该品牌下的全部型号。", true);
    const brandInUse = state.employees.some(
      (employee) =>
        (employee.monitors || []).some((item) => item.inventoryBrandId === brand.id) ||
        getNonAssetItems(employee).some((item) => item.inventoryBrandId === brand.id),
    );
    if (brandInUse) return showToast("该品牌仍被人员名下物资引用，无法删除。", true);
    if (!window.confirm(`确定删除库存品牌 ${brand.name} 吗？`)) return;
    state.inventoryBrands = state.inventoryBrands.filter((item) => item.id !== brand.id);
    state.expandedInventoryBrandIds = state.expandedInventoryBrandIds.filter((id) => id !== brand.id);
    persistState(true);
    render();
    showToast("库存品牌已删除");
    */
  }

  if (action === "delete-inventory-model") {
    return showToast("库存型号删除已暂时禁用，避免绕过库存和审计事务。", true);
    /*
    const model = getInventoryModel(actionElement.dataset.id);
    const modelInUse = state.employees.some(
      (employee) =>
        (employee.monitors || []).some((item) => item.inventoryModelId === model?.id) ||
        getNonAssetItems(employee).some((item) => item.inventoryModelId === model?.id),
    );
    if (modelInUse) return showToast("该型号仍被人员名下物资引用，无法删除。", true);
    const terminalInUse = state.computers.some((computer) => computer.inventoryModelId === model?.id);
    if (terminalInUse) return showToast("该型号仍被办公终端引用，无法删除。", true);
    if (!model || !window.confirm(`确定删除库存型号 ${model.name} 吗？`)) return;
    if (Number(model.quantity || 0) > 0) {
      const brand = getInventoryBrand(model.brandId);
      const type = getType(model.typeId);
      recordInventoryMovement({
        direction: "decrease",
        typeName: type?.name || "",
        brandName: brand?.name || "",
        modelName: model.name || "",
        quantity: Math.max(1, Number(model.quantity || 0)),
        sourceLabel: "IT物资库存",
        targetLabel: "删除型号",
        note: "删除型号时清空库存",
        triggerAction: "delete_inventory_model",
      });
    }
    state.inventoryModels = state.inventoryModels.filter((item) => item.id !== model.id);
    persistState(true);
    render();
    showToast("库存型号已删除");
    */
  }

  if (action === "reset-data" && window.confirm("确定从数据库重新加载吗？当前页面未保存的改动会被覆盖。")) {
    hydrateStateFromServer({ toast: true });
  }
});

function ticketStatusLabel(status) {
  return {
    new: "新建",
    assigned: "已分派",
    in_progress: "处理中",
    pending: "待处理",
    resolved: "已解决",
    closed: "已关闭",
    cancelled: "已取消",
  }[status] || status;
}

function ticketSlaLabel(state) {
  return {
    running: "计时中",
    breached: "已超时",
    stopped: "已停止",
    not_configured: "未配置",
  }[state] || state || "未配置";
}

function ticketApprovalLabel(status) {
  return {
    not_required: "无需审批",
    pending: "审批中",
    approved: "已通过",
    rejected: "已拒绝",
  }[status] || status || "无需审批";
}

function ticketSlaRemaining(ticket) {
  if (ticket.slaState === "not_configured") return "—";
  const minutes = Number(ticket.slaRemainingMinutes);
  if (!Number.isFinite(minutes)) return "—";
  const absolute = Math.abs(minutes);
  const value = absolute >= 60 ? `${Math.floor(absolute / 60)} 小时 ${absolute % 60} 分` : `${absolute} 分`;
  return minutes < 0 ? `超时 ${value}` : `剩余 ${value}`;
}

function renderTicketTable() {
  const tickets = Array.isArray(operationsState.tickets) ? operationsState.tickets : [];
  const serviceLoading = serviceState().loading;
  return `
    ${
      operationsState.ticketLoading || serviceLoading
        ? '<div class="empty-state">正在加载工单...</div>'
        : tickets.length
          ? `<div class="table-wrap"><table>
              <thead><tr><th>编号</th><th>类型</th><th>主题</th><th>优先级</th><th>状态</th><th>SLA</th><th>请求人</th><th>处理人</th><th>更新时间</th></tr></thead>
              <tbody>${tickets
                .map(
                  (ticket) => `<tr data-action="open-ticket-detail" data-id="${escapeHtml(ticket.id)}">
                    <td>${escapeHtml(ticket.number || "")}</td>
                    <td>${ticket.type === "incident" ? "事件" : "请求"}</td>
                    <td>${escapeHtml(ticket.title || "")}</td>
                    <td>${escapeHtml(servicePriorityLabel(ticket.priority))}</td>
                    <td>${escapeHtml(ticketStatusLabel(ticket.status))}</td>
                    <td>${escapeHtml(ticketSlaLabel(ticket.slaState))}</td>
                    <td>${escapeHtml(ticket.requesterName || "—")}</td>
                    <td>${escapeHtml(ticket.assignedToName || "—")}</td>
                    <td>${escapeHtml(formatDateTime(ticket.updatedAt || ""))}</td>
                  </tr>`,
                )
                .join("")}</tbody>
            </table></div>`
          : '<div class="empty-state">暂无工单</div>'
    }`;
}

function renderTicketsPage() {
  return `
    <div class="page-intro">
      <div><h2>工单</h2><p>事件用于恢复服务，请求用于交付标准服务。</p></div>
      <div class="toolbar-actions">
        <button class="secondary-button" data-action="refresh-tickets">刷新</button>
        ${hasPermission("tickets", "create") ? '<button class="primary-button" data-action="open-ticket">新建工单</button>' : ""}
      </div>
    </div>
    <section class="data-panel">${renderTicketTable()}</section>
  `;
}

function renderServiceTickets() {
  return `<section class="data-panel service-tickets-panel">
    <div class="section-heading">
      <div><h2>工单</h2><span>事件用于恢复服务，请求用于交付标准服务。</span></div>
      <div class="toolbar-actions">
        <button class="secondary-button" data-action="refresh-tickets">刷新</button>
        ${hasPermission("tickets", "create") ? '<button class="primary-button" data-action="open-ticket">新建工单</button>' : ""}
      </div>
    </div>
    ${renderTicketTable()}
  </section>`;
}

function syncSourceLabel(sourceCode) {
  return (
    {
      manual: "手工维护",
      excel: "Excel 导入",
      hr: "人事目录",
    }[String(sourceCode || "")] || String(sourceCode || "")
  );
}

function syncRunStatusLabel(status) {
  return (
    {
      staged: "已暂存",
      validated: "校验通过",
      applied: "已应用",
      failed: "失败",
      cancelled: "已取消",
    }[String(status || "")] || String(status || "")
  );
}

function renderGovernancePage() {
  const runs = Array.isArray(operationsState.syncRuns) ? operationsState.syncRuns : [];
  const issues = Array.isArray(operationsState.qualityIssues) ? operationsState.qualityIssues : [];
  return `
    <div class="page-intro">
      <div><h2>同步与质量</h2><p>外部数据先进入暂存区，校验通过后再由管理员应用。</p></div>
      <div class="toolbar-actions">
        <button class="secondary-button" data-action="refresh-governance">刷新</button>
        <button class="secondary-button" data-action="run-data-quality">运行质量检查</button>
        <button class="primary-button" data-action="open-sync-stage">暂存同步数据</button>
      </div>
    </div>
    <section class="section-block">
      <div class="section-heading"><div><h2>同步暂存批次</h2><span>无效记录不会进入生产主数据。</span></div></div>
      <div class="data-panel">
        ${
          runs.length
            ? `<div class="table-wrap"><table>
                <thead><tr><th>来源</th><th>状态</th><th>总数</th><th>有效</th><th>无效</th><th>已应用</th><th>开始时间</th><th>操作</th></tr></thead>
                <tbody>${runs
                  .map(
                    (run) => `<tr>
                      <td>${escapeHtml(syncSourceLabel(run.sourceCode))}</td>
                      <td>${escapeHtml(syncRunStatusLabel(run.status))}</td>
                      <td>${escapeHtml(run.recordsTotal || 0)}</td>
                      <td>${escapeHtml(run.recordsValid || 0)}</td>
                      <td>${escapeHtml(run.recordsInvalid || 0)}</td>
                      <td>${escapeHtml(run.recordsApplied || 0)}</td>
                      <td>${escapeHtml(formatDateTime(run.startedAt || ""))}</td>
                      <td>${
                        isAdminUser() && run.status === "validated" && Number(run.recordsInvalid || 0) === 0
                          ? `<button class="text-button" data-action="apply-sync-run" data-id="${escapeHtml(run.id)}">应用</button>`
                          : "—"
                      }</td>
                    </tr>`,
                  )
                  .join("")}</tbody>
              </table></div>`
            : '<div class="empty-state">暂无同步批次</div>'
        }
      </div>
    </section>
    <section class="section-block">
      <div class="section-heading"><div><h2>数据质量问题</h2><span>发现后可修正主数据，或由操作员标记为已处理。</span></div></div>
      <div class="data-panel">
        ${
          issues.length
            ? `<div class="table-wrap"><table>
                <thead><tr><th>严重性</th><th>规则</th><th>对象</th><th>问题</th><th>发现时间</th><th>操作</th></tr></thead>
                <tbody>${issues
                  .map(
                    (issue) => `<tr>
                      <td>${escapeHtml(issue.severityLabel || issue.severity || "")}</td>
                      <td>${escapeHtml(issue.ruleLabel || issue.ruleCode || "")}</td>
                      <td>${escapeHtml(`${issue.entityTypeLabel || issue.entityType || ""} ${issue.entityId || ""}`)}</td>
                      <td>${escapeHtml(issue.title || "")}</td>
                      <td>${escapeHtml(formatDateTime(issue.lastDetectedAt || ""))}</td>
                      <td>${
                        hasPermission("quality", "approve")
                          ? `<button class="text-button" data-action="resolve-quality-issue" data-id="${escapeHtml(issue.id)}">解决</button>
                             <button class="text-button" data-action="ignore-quality-issue" data-id="${escapeHtml(issue.id)}">忽略</button>`
                          : "—"
                      }</td>
                    </tr>`,
                  )
                  .join("")}</tbody>
              </table></div>`
            : '<div class="empty-state">没有打开的数据质量问题</div>'
        }
      </div>
    </section>
  `;
}

async function loadTickets() {
  const requestId = beginAsyncRequest("tickets");
  operationsState.ticketLoading = true;
  renderIfCurrentPage("tickets");
  try {
    const payload = await requestJson(API_TICKETS_URL);
    if (!isLatestAsyncRequest("tickets", requestId)) return false;
    operationsState.tickets = Array.isArray(payload.tickets) ? payload.tickets : [];
    return true;
  } finally {
    if (isLatestAsyncRequest("tickets", requestId)) {
      operationsState.ticketLoading = false;
    }
  }
}

async function loadGovernance() {
  const requestId = beginAsyncRequest("governance");
  operationsState.governanceLoading = true;
  renderIfCurrentPage("governance");
  try {
    const [runsPayload, issuesPayload] = await Promise.all([
      requestJson(API_SYNC_RUNS_URL),
      requestJson(`${API_QUALITY_ISSUES_URL}?status=open`),
    ]);
    if (!isLatestAsyncRequest("governance", requestId)) return false;
    operationsState.syncRuns = Array.isArray(runsPayload.runs) ? runsPayload.runs : [];
    operationsState.qualityIssues = Array.isArray(issuesPayload.issues) ? issuesPayload.issues : [];
    return true;
  } finally {
    if (isLatestAsyncRequest("governance", requestId)) {
      operationsState.governanceLoading = false;
    }
  }
}

function ticketFormByCode(code) {
  return (ticketFormDraft.forms || []).find((form) => form.code === code) || ticketFormDraft.forms[0] || null;
}

function ticketCustomFieldInput(field) {
  const key = `custom_${field.key}`;
  const label = field.label || field.key;
  const controlId = createControlId(key);
  const required = field.required ? "required" : "";
  const placeholder = escapeHtml(field.placeholder || "");
  const options = Array.isArray(field.options) ? field.options : [];
  if (field.type === "system") {
    const sourceLabels = Object.fromEntries(designerSystemSources);
    return `<div class="form-field"><label for="${controlId}">${escapeHtml(label)}</label><input id="${controlId}" type="text" value="${escapeHtml(sourceLabels[(field.config || {}).source] || "系统自动带出")}" readonly tabindex="-1" /></div>`;
  }
  if (field.type === "textarea") {
    return `<div class="form-field full"><label for="${controlId}">${escapeHtml(label)}${field.required ? " *" : ""}</label><textarea id="${controlId}" name="${escapeHtml(key)}" rows="4" placeholder="${placeholder}" ${required}></textarea></div>`;
  }
  if (field.type === "select" || field.type === "multiselect") {
    return `<div class="form-field"><label for="${controlId}">${escapeHtml(label)}${field.required ? " *" : ""}</label><select id="${controlId}" name="${escapeHtml(key)}" ${field.type === "multiselect" ? "multiple" : ""} ${required}><option value="">请选择</option>${options.map((option) => `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label || option.value)}</option>`).join("")}</select></div>`;
  }
  if (field.type === "checkbox") {
    return `<label class="form-field"><span>${escapeHtml(label)}</span><input id="${controlId}" type="checkbox" name="${escapeHtml(key)}" value="true" /></label>`;
  }
  if (field.type === "employee") {
    return selectField(label, key, [{ value: "", label: "未选择人员" }].concat(state.employees.map((employee) => ({ value: employee.id, label: `${employee.name} (${employee.employeeNo})` }))), "", field.required);
  }
  if (field.type === "asset") {
    return selectField(label, key, [{ value: "", label: "未选择资产" }].concat(state.computers.map((computer) => ({ value: computer.id, label: computer.deviceName }))), "", field.required);
  }
  if (field.type === "organization") {
    return selectField(label, key, getOrgSelectOptions({ includeBlank: true }), "", field.required);
  }
  const type = field.type === "number" ? "number" : field.type === "date" ? "date" : field.type === "datetime" ? "datetime-local" : "text";
  return `<div class="form-field"><label for="${controlId}">${escapeHtml(label)}${field.required ? " *" : ""}</label><input id="${controlId}" type="${type}" name="${escapeHtml(key)}" placeholder="${placeholder}" ${required} /></div>`;
}

function readonlyField(label, value) {
  const controlId = createControlId(`readonly-${label}`);
  return `<div class="form-field"><label for="${controlId}">${escapeHtml(label)}</label><input id="${controlId}" readonly value="${escapeHtml(
    value,
  )}" /></div>`;
}

function renderTicketModal(selectedCode = "") {
  const selectedForm = ticketFormByCode(selectedCode || ticketFormDraft.selectedCode);
  ticketFormDraft.selectedCode = selectedForm?.code || "";
  const formOptions = (ticketFormDraft.forms || []).map((form) => ({ value: form.code, label: form.name || form.code }));
  const customFields = (selectedForm?.fields || []).map(ticketCustomFieldInput).join("");
  return `${modalHeader("新建工单", "事件用于恢复服务，请求用于交付标准服务。")}
      <form data-form="ticket">
        <div class="form-grid">
          ${selectField("类型", "type", [
            { value: "incident", label: "事件" },
            { value: "request", label: "服务请求" },
          ], "incident", true)}
          ${selectField("工单表单", "formCode", formOptions.length ? formOptions : [{ value: "", label: "默认表单" }], ticketFormDraft.selectedCode)}
          ${selectField("影响", "impact", [
            { value: "low", label: "低" },
            { value: "medium", label: "中" },
            { value: "high", label: "高" },
          ], "medium", true)}
          ${selectField("紧急度", "urgency", [
            { value: "low", label: "低" },
            { value: "medium", label: "中" },
            { value: "high", label: "高" },
          ], "medium", true)}
          ${selectField(
            "请求人",
            "requesterEmployeeId",
            [{ value: "", label: "未关联人员" }].concat(
              state.employees.map((employee) => ({ value: employee.id, label: `${employee.name} (${employee.employeeNo})` })),
            ),
            "",
          )}
          ${selectField("关联终端", "relatedComputerId", [{ value: "", label: "未关联终端" }].concat(
            state.computers.map((computer) => ({ value: computer.id, label: computer.deviceName })),
          ), "")}
          ${selectField("组织", "orgId", getOrgSelectOptions({ includeBlank: true }), "")}
        </div>
        ${inputField("主题", "title", "", true, "例如：无法连接内网")}
        ${textareaField("描述", "description", "", true, "现象、影响范围和期望处理结果", 6)}
        ${customFields ? `<section class="modal-section"><div class="modal-section-title"><h3>${escapeHtml(selectedForm?.name || "业务字段")}</h3><span>按所选表单填写业务信息。</span></div><div class="form-grid">${customFields}</div></section>` : ""}
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">创建工单</button></div>
      </form>`;
}

async function openTicketModal(selectedCode = "") {
  try {
    const payload = await requestJson(`${API_SERVICE_FORMS_URL}?recordType=ticket&forSubmission=1`);
    ticketFormDraft.forms = Array.isArray(payload.forms) ? payload.forms : [];
    ticketFormDraft.selectedCode = selectedCode || ticketFormDraft.selectedCode || ticketFormDraft.forms[0]?.code || "";
  } catch (error) {
    ticketFormDraft.forms = [];
    ticketFormDraft.selectedCode = "";
    showToast(`读取工单表单失败：${error.message}`, true);
  }
  openModal(
    renderTicketModal(ticketFormDraft.selectedCode),
    false,
  );
}

async function openTicketDetail(ticketId) {
  try {
    const payload = await requestJson(`${API_TICKETS_URL}/${encodeURIComponent(ticketId)}`);
    const ticket = payload.ticket || {};
    const history = Array.isArray(ticket.history) ? ticket.history : [];
    const transitionOptions = {
      new: ["assigned", "in_progress", "cancelled"],
      assigned: ["in_progress", "pending", "resolved", "cancelled"],
      in_progress: ["pending", "resolved", "cancelled"],
      pending: ["in_progress", "resolved", "cancelled"],
      resolved: ["closed", "in_progress"],
      closed: [],
      cancelled: [],
    }[ticket.status] || [];
    openModal(
      `${modalHeader(ticket.number || "工单", ticket.title || "")}
        <section class="modal-section"><p>${escapeHtml(ticket.description || "")}</p>
          <div class="form-grid">
            ${readonlyField("状态", ticketStatusLabel(ticket.status))}
            ${readonlyField("优先级", servicePriorityLabel(ticket.priority))}
            ${readonlyField("SLA 状态", ticketSlaLabel(ticket.slaState))}
            ${readonlyField("SLA 剩余时间", ticketSlaRemaining(ticket))}
            ${readonlyField("审批状态", ticketApprovalLabel(ticket.approvalStatus))}
            ${readonlyField("请求人", ticket.requesterName || "")}
            ${readonlyField("关联终端", ticket.relatedComputerName || "")}
          </div>
        </section>
        ${
          Object.keys(ticket.customFields || {}).length
            ? `<section class="modal-section"><h3>业务字段</h3><div class="form-grid">${Object.entries(ticket.customFields || {})
                .map(([key, value]) => readonlyField(key, Array.isArray(value) ? value.join("、") : String(value ?? "")))
                .join("")}</div></section>`
            : ""
        }
        <section class="modal-section"><h3>处理历史</h3>
          <div class="audit-list">${history.map((entry) => `<div class="audit-entry"><strong>${escapeHtml(entry.entryType || "")}</strong><span>${escapeHtml(entry.content || "")}</span><small>${escapeHtml(`${entry.createdBy || ""} ${formatDateTime(entry.createdAt || "")}`)}</small></div>`).join("") || "<div class=\"empty-state\">暂无历史</div>"}</div>
        </section>
        ${
          hasPermission("tickets", "update")
            ? `<form data-form="ticket-note" data-id="${escapeHtml(ticket.id)}">
                ${textareaField("追加说明", "content", "", true, "记录排查、沟通或处理进展", 3)}
                <div class="modal-footer"><button class="secondary-button" type="submit">追加说明</button></div>
              </form>`
            : ""
        }
        ${
          hasPermission("tickets", "update") && transitionOptions.length
            ? `<form data-form="ticket-transition" data-id="${escapeHtml(ticket.id)}">
                <div class="form-grid">
                  ${selectField("下一状态", "status", transitionOptions.map((value) => ({ value, label: ticketStatusLabel(value) })), transitionOptions[0], true)}
                  ${selectField("处理人", "assignedToUserId", [{ value: "", label: "未分派" }].concat(
                    (settingsState.users || []).filter((user) => ["admin", "operator"].includes(user.role)).map((user) => ({ value: user.id, label: user.displayName || user.username })),
                  ), ticket.assignedToUserId || "")}
                </div>
                ${textareaField("解决方案", "resolution", ticket.resolution || "", false, "解决时必填", 3)}
                ${textareaField("状态说明", "note", "", false, "可选", 2)}
                <div class="modal-footer"><button class="primary-button" type="submit">更新工单</button></div>
              </form>`
            : ""
        }`,
      false,
    );
  } catch (error) {
    showToast(`加载工单失败：${error.message}`, true);
  }
}

async function handleTicketSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const selectedForm = ticketFormByCode(data.formCode);
  const customFields = {};
  for (const field of selectedForm?.fields || []) {
    const key = `custom_${field.key}`;
    if (field.type === "checkbox") {
      customFields[field.key] = form.querySelector(`[name="${CSS.escape(key)}"]`)?.checked || false;
    } else if (field.type === "multiselect") {
      customFields[field.key] = [...(form.querySelector(`[name="${CSS.escape(key)}"]`)?.selectedOptions || [])]
        .map((option) => option.value)
        .filter(Boolean);
    } else if (Object.prototype.hasOwnProperty.call(data, key)) {
      customFields[field.key] = data[key];
    }
  }
  data.customFields = customFields;
  try {
    await requestJson(API_TICKETS_URL, { method: "POST", body: JSON.stringify(data) });
    closeModal();
    await loadTickets();
    render();
    showToast("工单已创建");
  } catch (error) {
    showToast(`创建工单失败：${error.message}`, true);
  }
}

async function handleTicketNoteSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    await requestJson(`${API_TICKETS_URL}/${encodeURIComponent(form.dataset.id || "")}/notes`, {
      method: "POST",
      body: JSON.stringify({ content: data.content, isPublic: true }),
    });
    await loadTickets();
    await openTicketDetail(form.dataset.id || "");
  } catch (error) {
    showToast(`追加说明失败：${error.message}`, true);
  }
}

async function handleTicketTransitionSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    await requestJson(`${API_TICKETS_URL}/${encodeURIComponent(form.dataset.id || "")}/transitions`, {
      method: "POST",
      body: JSON.stringify(data),
    });
    await loadTickets();
    await openTicketDetail(form.dataset.id || "");
  } catch (error) {
    showToast(`更新工单失败：${error.message}`, true);
  }
}

function openSyncStageModal() {
  openModal(
    `${modalHeader("暂存外部同步数据", "JSON 数组中每条记录需包含 entityType、externalId、action 和 data。")}
      <form data-form="sync-stage">
        <div class="form-grid">
          ${selectField("来源", "sourceCode", [
            { value: "manual", label: "手工维护" },
            { value: "excel", label: "Excel 导入" },
            { value: "hr", label: "人事目录" },
          ], "manual", true)}
          ${inputField("来源批次标识", "sourceReference", "", false, "例如 HR-20260814")}
        </div>
        ${textareaField("记录 JSON", "recordsJson", '[{"entityType":"employee","externalId":"E-1001","action":"upsert","data":{"employeeNo":"E-1001","name":"Example User"}}]', true, "", 12)}
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">暂存并校验</button></div>
      </form>`,
    false,
  );
}

async function handleSyncStageSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  let records;
  try {
    records = JSON.parse(data.recordsJson || "[]");
  } catch (error) {
    return showToast("记录 JSON 格式无效。", true);
  }
  try {
    await requestJson(API_SYNC_RUNS_URL, {
      method: "POST",
      body: JSON.stringify({
        sourceCode: data.sourceCode,
        sourceReference: data.sourceReference || "",
        records,
      }),
    });
    closeModal();
    await loadGovernance();
    render();
    showToast("同步数据已暂存并完成校验");
  } catch (error) {
    showToast(`暂存同步数据失败：${error.message}`, true);
  }
}

async function applySyncRun(runId) {
  try {
    await runCommand(`${API_SYNC_RUNS_URL}/${encodeURIComponent(runId)}/apply`, {}, "sync-apply");
    await reloadDomainState();
    await loadGovernance();
    render();
    showToast("同步批次已应用");
  } catch (error) {
    showToast(`应用同步批次失败：${error.message}`, true);
  }
}

async function runDataQuality() {
  try {
    await runCommand("/api/data-quality/run", {}, "data-quality");
    await loadGovernance();
    render();
    showToast("数据质量检查已完成");
  } catch (error) {
    showToast(`数据质量检查失败：${error.message}`, true);
  }
}

function openQualityIssueResolveModal(issueId) {
  const issue = operationsState.qualityIssues.find((item) => String(item.id) === String(issueId));
  if (!issue) return;
  openModal(
    `${modalHeader("解决数据质量问题", issue.ruleLabel || issue.title || "数据质量问题")}
      <form data-form="quality-issue-resolution" data-id="${escapeHtml(issue.id)}">
        <section class="modal-section">
          <div class="form-grid">
            ${inputField("严重性", "severityLabel", issue.severityLabel || issue.severity || "", false, "", "text", "", 'readonly tabindex="-1"')}
            ${inputField("对象", "entityLabel", `${issue.entityTypeLabel || issue.entityType || ""} ${issue.entityId || ""}`.trim(), false, "", "text", "", 'readonly tabindex="-1"')}
          </div>
          ${textareaField("问题说明", "issueTitle", issue.title || "", false, "", 3, 'readonly tabindex="-1"')}
        </section>
        <section class="modal-section">
          ${textareaField("处理结果", "resolutionResult", "", true, "说明已采取的修正、核验结果或后续措施", 5)}
        </section>
        <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">确认解决</button></div>
      </form>`,
  );
}

async function resolveQualityIssue(issueId, ignored, resolutionResult = "") {
  try {
    await runCommand(
      `/api/data-quality/issues/${encodeURIComponent(issueId)}/${ignored ? "ignore" : "resolve"}`,
      ignored ? {} : { resolutionResult },
      ignored ? "quality-ignore" : "quality-resolve",
    );
    await loadGovernance();
    render();
    return true;
  } catch (error) {
    showToast(`更新质量问题失败：${error.message}`, true);
    return false;
  }
}

async function handleQualityIssueResolutionSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const resolutionResult = String(data.resolutionResult || "").trim();
  if (!resolutionResult) {
    showToast("请填写处理结果。", true);
    return;
  }
  if (await resolveQualityIssue(form.dataset.id || "", false, resolutionResult)) {
    closeModal();
  }
}

document.addEventListener("click", (event) => {
  const actionElement = event.target.closest("[data-action]");
  if (!actionElement) return;
  const action = actionElement.dataset.action || "";
  if (action === "open-ticket") openTicketModal();
  if (action === "open-ticket-detail") openTicketDetail(actionElement.dataset.id || "");
  if (action === "refresh-tickets") {
    loadTickets()
      .then(() => renderIfCurrentPage("tickets"))
      .catch((error) => showToast(`加载工单失败：${error.message}`, true));
  }
  if (action === "open-sync-stage") openSyncStageModal();
  if (action === "refresh-governance") {
    loadGovernance()
      .then(() => renderIfCurrentPage("governance"))
      .catch((error) => showToast(`加载治理数据失败：${error.message}`, true));
  }
  if (action === "apply-sync-run") applySyncRun(actionElement.dataset.id || "");
  if (action === "run-data-quality") runDataQuality();
  if (action === "resolve-quality-issue") openQualityIssueResolveModal(actionElement.dataset.id || "");
  if (action === "ignore-quality-issue") resolveQualityIssue(actionElement.dataset.id || "", true);
});

async function handleComputerSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const id = form.dataset.id || "";
  const registrationMode = String(data.registrationMode || "custom").trim() || "custom";
  const selectedModel =
    registrationMode === "warehouse" && data.computerInventoryModelId
      ? getInventoryModel(data.computerInventoryModelId)
      : null;
  const wifiMac = normalizeMacAddress(data.wifiMac);
  const ethernetMac = normalizeMacAddress(data.ethernetMac);
  if (!data.deviceName || !isValidMacAddress(wifiMac) || !isValidMacAddress(ethernetMac)) {
    return showToast("请填写设备名并输入有效的 MAC 地址。", true);
  }
  if (!id && registrationMode === "warehouse" && (!data.warehouseId || !selectedModel)) {
    return showToast("从仓库库存登记时必须选择仓库和库存电脑型号。", true);
  }
  if (!id && !["custom", "warehouse"].includes(registrationMode)) {
    return showToast("请选择有效的登记方式。", true);
  }

  let serverComputer = null;
  if (id) {
    try {
      const serverState = await requestJson(API_STATE_URL);
      serverComputer =
        Array.isArray(serverState.computers)
          ? serverState.computers.find((computer) => sameRecordId(computer.id, id)) || null
          : null;
    } catch (error) {
      serverComputer = state.computers.find((computer) => sameRecordId(computer.id, id)) || null;
    }
  }

  const currentUserId = String(serverComputer?.userId || "");
  const desiredUserId = String(data.userId || "");
  const currentStatus = String(serverComputer?.status || data.status || "idle");
  const targetStatus = String(data.status || "idle");
  const shouldAssign = Boolean(desiredUserId) && !sameRecordId(desiredUserId, currentUserId);
  const shouldReturn = !desiredUserId && Boolean(currentUserId);
  const statusForSave = desiredUserId ? "in_use" : shouldReturn ? currentStatus : targetStatus;
  const returnStatus = targetStatus === "in_use" ? "idle" : targetStatus;

  try {
    const saved = await saveResource("computer", id, {
      deviceName: data.deviceName,
      orgId: data.orgId || "",
      deviceType: data.deviceType,
      registrationMode,
      warehouseId: !id && registrationMode === "warehouse" ? data.warehouseId || "" : "",
      brand: data.brand || "",
      model: data.model || "",
      inventoryModelId: selectedModel?.id || "",
      cpu: data.cpu || "",
      memory: data.memory || "",
      storage: normalizeStorageValue(data.storage || ""),
      gpu: data.gpu || "",
      fixedAssetCode: data.fixedAssetCode || "",
      purchaseDate: data.purchaseDate || "",
      registeredDate: data.registeredDate || "",
      snSt: data.snSt || "",
      wifiMac,
      ethernetMac,
      location: data.location || "",
      department: data.department || "",
      position: data.position || "",
      status: statusForSave,
      remarks: data.remarks || "",
    });

    const computerId = id || saved?.computer?.id || "";
    if (!computerId) {
      throw new Error("保存后未获取到办公终端编号。");
    }
    if (shouldAssign) {
      await runCommand(
        `/api/computers/${encodeURIComponent(computerId)}/assignments`,
        { employeeId: desiredUserId, notes: "Assigned from computer asset form" },
        "computer-assignment",
      );
    } else if (shouldReturn) {
      await runCommand(
        `/api/computers/${encodeURIComponent(computerId)}/assignments/return`,
        { nextStatus: returnStatus, notes: "Returned from computer asset form" },
        "computer-return",
      );
    }
    closeModal();
    await reloadDomainState();
    showToast(id ? "办公终端已更新" : "办公终端已创建");
  } catch (error) {
    showToast(`保存办公终端失败：${error.message}`, true);
  }
}

async function handleEmployeeSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const id = form.dataset.id || "";
  if (data.status === "left") {
    return showToast("离职归档仍需通过受控回收流程，暂不允许从编辑表单直接提交。", true);
  }
  const employeeNo = String(data.employeeNo || "").trim() || employeeNumberFor(data.orgId, id, data.status);
  if (!data.name || !employeeNo) return showToast("人员编号和姓名不能为空。", true);
  try {
    await saveResource("employee", id, {
      employeeNo,
      name: data.name,
      orgId: data.orgId || "",
      department: data.department || "",
      position: data.position || "",
      email: data.email || "",
      mobile: data.mobile || "",
      status: data.status || "active",
    });
    closeModal();
    await reloadDomainState();
    showToast(id ? "人员已更新" : "人员已创建");
  } catch (error) {
    showToast(`保存人员失败：${error.message}`, true);
  }
}

async function handleOrgSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const id = form.dataset.id || "";
  const code = String(data.code || "").trim() || orgCodeFor({ name: data.name }, data.parentId, id);
  if (!code || !data.name) return showToast("组织编码和名称不能为空。", true);
  try {
    await saveResource("organization", id, {
      code,
      name: data.name,
      parentId: data.parentId || "",
      sortOrder: Math.max(0, Number(data.sortOrder || 1000)),
    });
    closeModal();
    await reloadDomainState();
    showToast(id ? "组织已更新" : "组织已创建");
  } catch (error) {
    showToast(`保存组织失败：${error.message}`, true);
  }
}

async function handleTypeSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const id = form.dataset.id || "";
  if (!data.code || !data.name) return showToast("类型编码和名称不能为空。", true);
  try {
    await saveResource("inventory-type", id, {
      code: data.code,
      name: data.name,
      unit: data.unit || "件",
    });
    closeModal();
    await reloadDomainState();
    showToast(id ? "物资类型已更新" : "物资类型已创建");
  } catch (error) {
    showToast(`保存物资类型失败：${error.message}`, true);
  }
}

async function handleInventoryBrandSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const id = form.dataset.id || "";
  const typeId = form.dataset.typeId || "";
  if (!typeId || !data.name) return showToast("请选择类型并填写品牌名称。", true);
  try {
    await saveResource("inventory-brand", id, {
      typeId,
      name: data.name,
      sortOrder: Math.max(0, Number(data.sortOrder || 1000)),
    });
    closeModal();
    await reloadDomainState();
    showToast(id ? "库存品牌已更新" : "库存品牌已创建");
  } catch (error) {
    showToast(`保存库存品牌失败：${error.message}`, true);
  }
}

async function handleInventoryModelSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const id = form.dataset.id || "";
  const typeId = form.dataset.typeId || "";
  const brandId = form.dataset.brandId || "";
  const warehouseId = String(data.warehouseId || "").trim();
  const previous = getInventoryModel(id);
  const desiredQuantity = Math.max(0, Number(data.quantity || 0));
  const isComputerModel = isComputerInventoryType(getType(typeId));
  if (!typeId || !brandId || !data.name || !warehouseId) {
    return showToast("请选择库存仓库、类型、品牌并填写型号。", true);
  }
  try {
    const result = await saveResource("inventory-model", id, {
      typeId,
      brandId,
      name: data.name,
      batchKey: previous?.batchKey || (isComputerModel ? createId("batch") : ""),
      inboundDate: isComputerModel ? data.inboundDate || "" : "",
      cpu: isComputerModel ? data.cpu || "" : "",
      memory: isComputerModel ? data.memory || "" : "",
      storage: isComputerModel ? normalizeStorageValue(data.storage || "") : "",
      gpu: isComputerModel ? data.gpu || "" : "",
      sortOrder: Math.max(0, Number(data.sortOrder || 1000)),
    });
    const modelId = result.inventoryModel?.id || id;
    const quantityDelta =
      desiredQuantity - (previous ? inventoryModelQuantityInWarehouse(previous.id, warehouseId) : 0);
    if (quantityDelta > 0) {
      await runCommand(
        "/api/inventory/receipts",
        {
          modelId,
          warehouseId,
          quantity: quantityDelta,
          inboundDate: data.inboundDate || currentDateText(),
          sourceLabel: "库存型号维护入库",
          note: "通过库存型号维护设置当前仓库数量",
        },
        "inventory-receipt",
      );
    } else if (quantityDelta < 0) {
      await runCommand(
        "/api/inventory/adjustments",
        {
          modelId,
          warehouseId,
          quantityDelta,
          note: "通过库存型号维护调整当前仓库数量",
        },
        "inventory-adjust",
      );
    }
    closeModal();
    await reloadDomainState();
    showToast(id ? "库存型号已更新" : "库存型号已创建");
  } catch (error) {
    showToast(`保存库存型号失败：${error.message}`, true);
  }
}

async function handleInventoryImportSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const typeName = String(data.type || "").trim();
  const brandName = String(data.brand || "").trim();
  const modelName = String(data.model || "").trim();
  const warehouseId = String(data.warehouseId || "").trim();
  const quantity = Math.max(1, Number(data.quantity || 0));
  if (!warehouseId || !typeName || !brandName || !modelName || !quantity) {
    return showToast("请选择入库仓库并填写类型、品牌、型号和数量。", true);
  }
  const isComputerImport = isComputerInventoryTypeName(typeName);
  try {
    let type = isComputerImport ? computerInventoryType() || findInventoryTypeByName(typeName) : findInventoryTypeByName(typeName);
    if (!type) {
      const result = await saveResource("inventory-type", "", {
        code: isComputerImport ? "computer" : inventoryTypeCodeFor(typeName),
        name: isComputerImport ? "办公终端" : typeName,
        unit: isComputerImport ? "台" : "件",
      });
      type = result.inventoryType;
    }
    let brand = findInventoryBrandByName(type.id, brandName);
    if (!brand) {
      const result = await saveResource("inventory-brand", "", {
        typeId: type.id,
        name: brandName,
        sortOrder: nextBrandSortOrder(type.id),
      });
      brand = result.inventoryBrand;
    }
    let model = isComputerImport ? null : findInventoryModelByName(brand.id, modelName);
    if (!model) {
      const result = await saveResource("inventory-model", "", {
        typeId: type.id,
        brandId: brand.id,
        name: modelName,
        batchKey: isComputerImport ? createId("batch") : "",
        inboundDate: isComputerImport ? data.inboundDate || currentDateText() : "",
        cpu: isComputerImport ? data.cpu || "" : "",
        memory: isComputerImport ? data.memory || "" : "",
        storage: isComputerImport ? normalizeStorageValue(data.storage || "") : "",
        gpu: isComputerImport ? data.gpu || "" : "",
        sortOrder: nextModelSortOrder(brand.id),
      });
      model = result.inventoryModel;
    }
    await runCommand(
      "/api/inventory/receipts",
      {
        modelId: model.id,
        warehouseId,
        quantity,
        inboundDate: data.inboundDate || currentDateText(),
        sourceLabel: isComputerImport ? "办公终端入库" : "IT物资入库",
        note: data.note || "",
      },
      "inventory-receipt",
    );
    closeModal();
    await reloadDomainState();
    showToast(`已入库 ${type.name} / ${brand.name} / ${model.name}，数量 +${quantity}`);
  } catch (error) {
    showToast(`物资入库失败：${error.message}`, true);
  }
}

async function finishDeviceSave(mode) {
  const pending = pendingDeviceSave;
  if (!pending) return;
  const confirmForm = document.querySelector('form[data-form="device-stock-confirm"]');
  const sourceWarehouseId = String(
    confirmForm?.elements?.sourceWarehouseId?.value || pending.sourceWarehouseId || "",
  ).trim();
  const returnWarehouseId = String(
    confirmForm?.elements?.returnWarehouseId?.value || pending.returnWarehouseId || "",
  ).trim();
  const employee = getEmployee(pending.employeeId);
  const model = inventoryModelForItem(pending.item);
  if (!employee) {
    pendingDeviceSave = null;
    return showToast("未找到使用人员，请刷新后重试。", true);
  }
  if (mode === "deduct" && !model) {
    showToast("同步扣减库存必须关联已登记的库存型号。", true);
    openDeviceStockConfirm(pending.kind, pending.employeeId, pending.item, pending.previous, {
      sourceWarehouseId,
      returnWarehouseId,
    });
    return;
  }
  if (mode === "deduct" && !sourceWarehouseId) {
    showToast("同步扣减库存必须选择来源仓库。", true);
    openDeviceStockConfirm(pending.kind, pending.employeeId, pending.item, pending.previous, {
      sourceWarehouseId,
      returnWarehouseId,
    });
    return;
  }
  if (pending.previous?.stockAdjusted && !returnWarehouseId) {
    showToast("编辑已扣减库存的物资时，必须选择旧记录的回收目标仓库。", true);
    openDeviceStockConfirm(pending.kind, pending.employeeId, pending.item, pending.previous, {
      sourceWarehouseId,
      returnWarehouseId,
    });
    return;
  }
  pendingDeviceSave = null;
  try {
    if (pending.previous?.id) {
      const returned = await returnUsageAllocations(
        employee.id,
        pending.kind === "monitor" ? "monitor" : "non_asset",
        pending.previous.id,
        "Superseded by a new allocation",
        pending.previous.stockAdjusted ? returnWarehouseId : "",
      );
      if (!returned) {
        throw new Error("Existing usage has no tracked allocation. Create a reconciled allocation before editing it.");
      }
    }
    const brandName = pending.item.brand || "";
    const modelName = pending.item.model || "";
    await runCommand(
      "/api/inventory/allocations",
      {
        allocationType: pending.kind === "monitor" ? "monitor" : "non_asset",
        employeeId: employee.id,
        modelId: model?.id || "",
        typeId: pending.item.typeId || "",
        inventoryBrandId: pending.item.inventoryBrandId || "",
        brand: brandName,
        model: modelName,
        displayName: pending.kind === "monitor" ? brandName : "",
        quantity: pending.kind === "monitor" ? 1 : Math.max(1, Number(pending.item.quantity || 1)),
        notes: mode === "deduct" ? "Inventory issued to employee" : "Registered without stock deduction",
        stockAdjusted: mode === "deduct",
        warehouseId: mode === "deduct" ? sourceWarehouseId : "",
      },
      "inventory-allocation",
    );
    closeModal();
    await reloadDomainState();
    openDeviceManager(employee.id);
    showToast(mode === "deduct" ? "领用已完成并扣减库存" : "领用已登记，库存未扣减");
  } catch (error) {
    pendingDeviceSave = {
      ...pending,
      sourceWarehouseId,
      returnWarehouseId,
    };
    showToast(`保存领用失败：${error.message}`, true);
  }
}

async function handleRoleCreateSubmit(form) {
  if (!isAdminUser()) return showToast("只有管理员可以创建角色。", true);
  if (form.dataset.submitting === "1") return;
  form.dataset.submitting = "1";
  const submit = form.querySelector('button[type="submit"]');
  const data = Object.fromEntries(new FormData(form).entries());
  const usernamePattern = /^[a-z][a-z0-9._-]{2,63}$/;
  const permissions = [];
  const access = accessControlState();
  for (const module of access.modules || []) {
    const scope =
      form.querySelector(`[data-role-permission-scope="${CSS.escape(module.code)}"]`)?.value || "none";
    for (const [action] of permissionActions) {
      const checkbox = form.querySelector(
        `[data-role-permission="${CSS.escape(`${module.code}:${action}`)}"]`,
      );
      permissions.push({
        moduleCode: module.code,
        actionCode: action,
        canView: action === "view" ? Boolean(checkbox?.checked) : false,
        canCreate: action === "create" ? Boolean(checkbox?.checked) : false,
        canUpdate: action === "update" ? Boolean(checkbox?.checked) : false,
        canDelete: action === "delete" ? Boolean(checkbox?.checked) : false,
        canApprove: action === "approve" ? Boolean(checkbox?.checked) : false,
        canExport: action === "export" ? Boolean(checkbox?.checked) : false,
        dataScope: scope,
      });
    }
  }
  if (!usernamePattern.test(String(data.code || "").trim())) {
    form.dataset.submitting = "0";
    return showToast("角色编码需使用 3-64 位小写字母、数字、点、下划线或短横线。", true);
  }
  if (submit) submit.disabled = true;
  try {
    const payload = await requestJson(API_ROLES_URL, {
      method: "POST",
      body: JSON.stringify({
        code: String(data.code || "").trim(),
        name: String(data.name || "").trim(),
        category: data.category || "custom",
        isSuperAdmin: data.isSuperAdmin === "on",
        permissions,
      }),
    });
    const role = payload.role || {};
    access.targetType = "role";
    access.targetId = String(role.id || "");
    form.reset();
    await loadAccessControl();
    if (role.id) {
      access.targetType = "role";
      access.targetId = String(role.id);
      await loadAccessControlTarget();
    }
    settingsState.view = "access";
    render();
    showToast("角色已创建。");
  } catch (error) {
    showToast(`创建角色失败：${error.message}`, true);
  } finally {
    form.dataset.submitting = "0";
    if (submit?.isConnected) submit.disabled = false;
  }
}

async function handleAccessPermissionsSubmit(form) {
  if (!isAdminUser()) return showToast("只有管理员可以修改权限。", true);
  const access = accessControlState();
  const entries = [];
  for (const module of access.modules || []) {
    const scope =
      form.querySelector(`[data-permission-scope="${CSS.escape(module.code)}"]`)?.value || "none";
    for (const [action] of permissionActions) {
      const checkbox = form.querySelector(
        `[data-permission="${CSS.escape(`${module.code}:${action}`)}"]`,
      );
      entries.push({
        moduleCode: module.code,
        actionCode: action,
        canView: action === "view" ? Boolean(checkbox?.checked) : false,
        canCreate: action === "create" ? Boolean(checkbox?.checked) : false,
        canUpdate: action === "update" ? Boolean(checkbox?.checked) : false,
        canDelete: action === "delete" ? Boolean(checkbox?.checked) : false,
        canApprove: action === "approve" ? Boolean(checkbox?.checked) : false,
        canExport: action === "export" ? Boolean(checkbox?.checked) : false,
        dataScope: scope,
      });
    }
  }
  const endpoint =
    access.targetType === "role"
      ? `${API_ROLES_URL}/${encodeURIComponent(access.targetId)}/permissions`
      : `${API_USERS_URL}/${encodeURIComponent(access.targetId)}/permissions`;
  try {
    const payload = await requestJson(endpoint, {
      method: "PUT",
      body: JSON.stringify({ permissions: entries }),
    });
    access.permissions = Array.isArray(payload.permissions) ? payload.permissions : entries;
    render();
    showToast("权限已保存。");
  } catch (error) {
    showToast(`权限保存失败：${error.message}`, true);
  }
}

async function assignComputer(employeeId) {
  const select = document.querySelector(`[data-assign-computer="${CSS.escape(employeeId)}"]`);
  const computerId = select?.value || "";
  if (!computerId) return showToast("请选择可分配的办公终端。", true);
  try {
    await runCommand(
      `/api/computers/${encodeURIComponent(computerId)}/assignments`,
      { employeeId, notes: "Assigned from employee device manager" },
      "computer-assignment",
    );
    await reloadDomainState();
    openDeviceManager(employeeId);
    showToast("办公终端已分配");
  } catch (error) {
    showToast(`分配办公终端失败：${error.message}`, true);
  }
}

async function releaseComputer(computerId, employeeId) {
  try {
    await runCommand(
      `/api/computers/${encodeURIComponent(computerId)}/assignments/return`,
      { nextStatus: "idle", notes: "Returned from employee device manager" },
      "computer-return",
    );
    await reloadDomainState();
    openDeviceManager(employeeId);
    showToast("办公终端已归还");
  } catch (error) {
    showToast(`归还办公终端失败：${error.message}`, true);
  }
}

document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-form]");
  if (!form) return;

  event.preventDefault();
  const type = form.dataset.form;

  if (type === "auth-login" || type === "auth-bootstrap") {
    handleAuthSubmit(form);
    return;
  }
  if (type === "system-settings") {
    handleSystemSettingsSubmit(form);
    return;
  }
  if (type === "backup-schedule") {
    handleBackupScheduleSubmit(form);
    return;
  }
  if (type === "database-backup-download") {
    handleDatabaseBackupDownloadSubmit(form);
    return;
  }
  if (type === "change-password") {
    handleChangePasswordSubmit(form);
    return;
  }
  if (type === "user-account") {
    handleUserAccountSubmit(form);
    return;
  }
  if (type === "role-create") {
    handleRoleCreateSubmit(form);
    return;
  }
  if (type === "access-permissions") {
    handleAccessPermissionsSubmit(form);
    return;
  }
  if (type === "ticket") {
    handleTicketSubmit(form);
    return;
  }
  if (type === "ticket-note") {
    handleTicketNoteSubmit(form);
    return;
  }
  if (type === "ticket-transition") {
    handleTicketTransitionSubmit(form);
    return;
  }
  if (type === "sync-stage") {
    handleSyncStageSubmit(form);
    return;
  }
  if (type === "service-form") {
    handleServiceFormSubmit(form);
    return;
  }
  if (type === "sla-policy") {
    handleSlaPolicySubmit(form);
    return;
  }
  if (type === "approval-workflow") {
    handleApprovalWorkflowSubmit(form);
    return;
  }
  if (type === "service-change") {
    handleServiceChangeSubmit(form);
    return;
  }
  if (type === "service-problem") {
    handleServiceProblemSubmit(form);
    return;
  }
  if (type === "service-knowledge") {
    handleServiceKnowledgeSubmit(form);
    return;
  }
  if (type === "service-transition") {
    handleServiceTransitionSubmit(form);
    return;
  }
  if (type === "service-approval") {
    handleServiceApprovalSubmit(form);
    return;
  }
  if (type === "computer") handleComputerSubmit(form);
  if (type === "employee") handleEmployeeSubmit(form);
  if (type === "employee-offboard") handleEmployeeOffboardSubmit(form);
  if (type === "monitor") handleMonitorSubmit(form);
  if (type === "nonasset") handleNonAssetSubmit(form);
  if (type === "org") handleOrgSubmit(form);
  if (type === "type") handleTypeSubmit(form);
  if (type === "inventory-brand") handleInventoryBrandSubmit(form);
  if (type === "inventory-model") handleInventoryModelSubmit(form);
  if (type === "inventory-import") handleInventoryImportSubmit(form);
  if (type === "warehouse") handleWarehouseSubmit(form);
  if (type === "inventory-transfer") handleInventoryTransferSubmit(form);
  if (type === "inventory-log-note-correction") handleInventoryMovementNoteSubmit(form);
  if (type === "inventory-purchase-note") handleInventoryPurchaseNoteSubmit(form);
  if (type === "quality-issue-resolution") handleQualityIssueResolutionSubmit(form);
  if (type === "scrap") handleScrapSubmit(form);
});

document.addEventListener("change", (event) => {
  const sharedOrgCountToggle = event.target.closest("[data-org-count-include-shared]");
  if (sharedOrgCountToggle) {
    state.includeSharedInOrgCount = Boolean(sharedOrgCountToggle.checked);
    persistState(false);
    render();
    return;
  }

  const ticketFormSelect = event.target.closest('form[data-form="ticket"] select[name="formCode"]');
  if (ticketFormSelect) {
    ticketFormDraft.selectedCode = ticketFormSelect.value || "";
    openTicketModal(ticketFormDraft.selectedCode);
    return;
  }

  const accessTargetType = event.target.closest("[data-access-target-type]");
  if (accessTargetType) {
    const access = accessControlState();
    access.targetType = accessTargetType.value === "user" ? "user" : "role";
    access.targetId =
      access.targetType === "role"
        ? String(access.roles[0]?.id || "")
        : String(access.users[0]?.id || "");
    loadAccessControlTarget()
      .then((loaded) => {
        if (loaded) renderIfCurrentPage("settings");
      })
      .catch((error) => showToast(`Unable to load permissions: ${error.message}`, true));
    return;
  }

  const accessTargetId = event.target.closest("[data-access-target-id]");
  if (accessTargetId) {
    const access = accessControlState();
    access.targetId = accessTargetId.value || "";
    loadAccessControlTarget()
      .then((loaded) => {
        if (loaded) renderIfCurrentPage("settings");
      })
      .catch((error) => showToast(`Unable to load permissions: ${error.message}`, true));
    return;
  }

  const updateReleaseChannel = event.target.closest("[data-update-release-channel]");
  if (updateReleaseChannel) {
    const nextChannel = updateReleaseChannel.value || DEFAULT_UPDATE_RELEASE_CHANNEL;
    if (nextChannel !== settingsState.updateReleaseChannel) {
      settingsState.updateReleaseChannel = nextChannel;
      settingsState.updateStatus = null;
      settingsState.updateSelectedSha = "";
      render();
    }
    return;
  }

  const updateSource = event.target.closest("[data-update-source]");
  if (updateSource) {
    const nextSource = updateSource.value === "custom" ? "custom" : "github";
    if (nextSource !== settingsState.updateSource) {
      settingsState.updateSource = nextSource;
      settingsState.updateStatus = null;
      settingsState.updateSelectedSha = "";
      render();
    }
    return;
  }

  const updateRepositoryUrl = event.target.closest("[data-update-repository-url]");
  if (updateRepositoryUrl) {
    const nextUrl = updateRepositoryUrl.value.trim();
    if (nextUrl !== settingsState.updateCustomRepositoryUrl) {
      settingsState.updateCustomRepositoryUrl = nextUrl;
      settingsState.updateRepositoryUrl = nextUrl;
      settingsState.updateStatus = null;
      settingsState.updateSelectedSha = "";
      render();
    }
    return;
  }

  const updateTarget = event.target.closest("[data-update-target]");
  if (updateTarget) {
    settingsState.updateSelectedSha = updateTarget.value || "";
    render();
    return;
  }

  const inventoryImportForm = event.target.closest('form[data-form="inventory-import"]');
  if (inventoryImportForm && event.target.name === "type") {
    toggleInventoryImportComputerFields(inventoryImportForm);
  }
  const computerForm = event.target.closest('form[data-form="computer"]');
  if (
    computerForm &&
    ["registrationMode", "warehouseId", "computerInventoryModelId"].includes(event.target.name)
  ) {
    updateComputerRegistrationFields(computerForm, event.target.name);
    return;
  }
  const deviceForm = event.target.closest('form[data-form="monitor"], form[data-form="nonasset"]');
  if (deviceForm && ["typeId", "brandId", "modelId"].includes(event.target.name)) {
    updateDeviceInventorySelectors(deviceForm, event.target.name);
    return;
  }
  const warehouseForm = event.target.closest('form[data-form="warehouse"]');
  if (warehouseForm && event.target.name === "orgId") {
    refreshWarehouseManagerOptions(warehouseForm);
    return;
  }
  const transferForm = event.target.closest('form[data-form="inventory-transfer"]');
  if (transferForm && event.target.name === "sourceWarehouseId") {
    refreshInventoryTransferModelOptions(transferForm);
    return;
  }
  const inventoryModelForm = event.target.closest('form[data-form="inventory-model"]');
  if (inventoryModelForm && event.target.name === "warehouseId") {
    const modelId = inventoryModelForm.dataset.id || "";
    const quantityInput = inventoryModelForm.elements.quantity;
    if (quantityInput && modelId) {
      quantityInput.value = inventoryModelQuantityInWarehouse(modelId, event.target.value || "");
    }
    const warehouseNote = inventoryModelForm.querySelector(".inventory-model-warehouse-note .readonly-value");
    if (warehouseNote) {
      warehouseNote.textContent = warehouseName(event.target.value || "") || "未选择仓库";
    }
    return;
  }
  const offboardForm = event.target.closest('form[data-form="employee-offboard"]');
  if (offboardForm && event.target.matches("[data-offboard-action]")) {
    updateOffboardItemRow(event.target.closest("[data-offboard-item-row]"));
    return;
  }
  const employeeForm = event.target.closest('form[data-form="employee"]');
  if (employeeForm && event.target.name === "orgId") {
    const numberInput = employeeForm.querySelector('input[name="employeeNo"]');
    if (
      numberInput &&
      (numberInput.dataset.generated === "true" ||
        numberInput.value === (numberInput.dataset.originalNumber || ""))
    ) {
      numberInput.value = employeeNumberFor(
        event.target.value,
        employeeForm.dataset.id || "",
        employeeForm.querySelector('select[name="status"]')?.value || "active",
      );
      numberInput.dataset.generated = "true";
    }
  }
  if (employeeForm && event.target.name === "status") {
    const numberInput = employeeForm.querySelector('input[name="employeeNo"]');
    const orgInput = employeeForm.querySelector('select[name="orgId"]');
    if (numberInput && numberInput.dataset.generated === "true") {
      numberInput.value = employeeNumberFor(
        orgInput?.value || "",
        employeeForm.dataset.id || "",
        event.target.value || "active",
      );
    }
  }
  const orgForm = event.target.closest('form[data-form="org"]');
  if (orgForm && ["name", "parentId"].includes(event.target.name)) {
    const codeInput = orgForm.querySelector('input[name="code"]');
    if (
      codeInput &&
      (!codeInput.value ||
        codeInput.dataset.generated === "true" ||
        codeInput.value.toUpperCase() === (codeInput.dataset.originalCode || "").toUpperCase())
    ) {
      codeInput.value = orgCodeFor(
        { id: orgForm.dataset.id || "", name: orgForm.elements.name?.value || "" },
        orgForm.elements.parentId?.value || "",
        orgForm.dataset.id || "",
      );
      codeInput.dataset.generated = "true";
    }
  }
  const filter = event.target.closest("[data-filter]");
  if (!filter) return;
  const filterName = filter.dataset.filter;
  if (isDeferredTextFilter(filterName)) {
    filterSearchDrafts[filterName] = filter.value;
    return;
  }
  state.filters[filterName] = filter.value;
  if (filterName === "inventoryType") {
    const selectedBrand = getInventoryBrand(state.filters.inventoryBrand || "");
    if (selectedBrand && selectedBrand.typeId !== filter.value) {
      state.filters.inventoryBrand = "";
    }
    expandVisibleInventoryNodes();
  }
  if (filterName === "inventoryBrand") {
    const brand = getInventoryBrand(filter.value);
    if (brand) {
      state.filters.inventoryType = brand.typeId;
      ensureInventoryExpanded(brand.typeId, brand.id);
    }
    expandVisibleInventoryNodes();
  }
  persistState(false);
  if (String(filterName).startsWith("audit")) {
    refreshAuditLogs({ silent: true })
      .then(() => renderIfCurrentPage("audit"))
      .catch((error) => {
        console.error("Unable to refresh audit logs", error);
        showToast(`日志加载失败：${error.message}`, true);
      });
    return;
  }
  render();
});

document.addEventListener("input", (event) => {
  const inventoryImportForm = event.target.closest('form[data-form="inventory-import"]');
  if (inventoryImportForm && event.target.name === "type") {
    toggleInventoryImportComputerFields(inventoryImportForm);
  }
  const computerForm = event.target.closest('form[data-form="computer"]');
  if (computerForm && ["wifiMac", "ethernetMac"].includes(event.target.name)) {
    const normalized = normalizeMacAddress(event.target.value);
    if (normalized !== String(event.target.value || "").trim()) {
      event.target.value = normalized;
    }
  }
  const employeeForm = event.target.closest('form[data-form="employee"]');
  if (employeeForm && event.target.name === "employeeNo") {
    event.target.dataset.generated = "false";
  }
  const orgForm = event.target.closest('form[data-form="org"]');
  if (orgForm && event.target.name === "code") {
    event.target.dataset.generated = "false";
  }
  if (orgForm && event.target.name === "name") {
    const codeInput = orgForm.querySelector('input[name="code"]');
    if (
      codeInput &&
      (codeInput.dataset.generated === "true" ||
        codeInput.value.toUpperCase() === (codeInput.dataset.originalCode || "").toUpperCase())
    ) {
      codeInput.value = orgCodeFor(
        { id: orgForm.dataset.id || "", name: event.target.value },
        orgForm.elements.parentId?.value || "",
        orgForm.dataset.id || "",
      );
      codeInput.dataset.generated = "true";
    }
  }
});

document.addEventListener("input", (event) => {
  const filter = event.target.closest("[data-filter]");
  if (!filter) return;
  if (!isDeferredTextFilter(filter.dataset.filter)) return;
  filterSearchDrafts[filter.dataset.filter] = filter.value;
});

document.addEventListener("keydown", (event) => {
  const textFilter = event.target.closest("[data-filter]");
  if (!textFilter || event.key !== "Enter") {
    if (event.key === "Escape" && document.querySelector("#modalRoot").innerHTML) closeModal();
    return;
  }
  const filterName = textFilter.dataset.filter;
  if (["employees", "employeeAssetSearch"].includes(filterName)) {
    event.preventDefault();
    filterSearchDrafts[filterName] = textFilter.value;
    applyEmployeeSearchFilters();
    return;
  }
  if (filterName === "inventorySearch") {
    event.preventDefault();
    filterSearchDrafts[filterName] = textFilter.value;
    applyInventorySearchFilter();
    return;
  }
  if (["flowSearch", "flowEmployee", "flowSourceTarget"].includes(filterName)) {
    event.preventDefault();
    filterSearchDrafts[filterName] = textFilter.value;
    applyFlowRecordFilters();
    return;
  }
  if (filterName === "scrapSearch") {
    event.preventDefault();
    filterSearchDrafts[filterName] = textFilter.value;
    applyScrapFilters();
    return;
  }
  if (["auditSearch", "auditEmployee"].includes(filterName)) {
    event.preventDefault();
    filterSearchDrafts[filterName] = textFilter.value;
    applyAuditFilters().catch((error) => {
      console.error("Unable to apply audit filters", error);
      showToast(`日志筛选失败：${error.message}`, true);
    });
  }
});

const serviceViewLabels = {
  tickets: "工单",
  changes: "变更管理",
  problems: "问题管理",
  knowledge: "知识库",
  forms: "服务表单",
  policies: "SLA 管理",
  approvals: "审批流程",
  notifications: "消息通知",
};

const serviceRecordTypeLabels = {
  ticket: "工单",
  change: "变更管理",
  problem: "问题管理",
};

const servicePriorityLabels = {
  high: "高",
  medium: "中",
  low: "低",
};

const serviceChangeTypeLabels = {
  standard: "标准变更",
  normal: "普通变更",
  emergency: "紧急变更",
};

const serviceStatusLabels = {
  draft: "草稿",
  submitted: "已提交",
  assessing: "评估中",
  approved: "已批准",
  rejected: "已拒绝",
  scheduled: "已排期",
  implementing: "实施中",
  verified: "已验证",
  closed: "已关闭",
  cancelled: "已取消",
  new: "新建",
  investigating: "调查中",
  known_error: "已知错误",
  resolved: "已解决",
  review: "审核中",
  published: "已发布",
  archived: "已归档",
  pending: "待审批",
};

function serviceState() {
  if (!operationsState.service) {
    operationsState.service = {
      view: "tickets",
      loading: false,
      changes: [],
      problems: [],
      articles: [],
      forms: [],
      policies: [],
      approvals: [],
      notifications: [],
    };
  }
  return operationsState.service;
}

function serviceRecordTypeLabel(recordType) {
  const code = String(recordType || "").trim();
  return serviceRecordTypeLabels[code] || code;
}

function servicePriorityLabel(priority) {
  const code = String(priority || "").trim();
  return servicePriorityLabels[code] || code;
}

function serviceChangeTypeLabel(type) {
  const code = String(type || "").trim();
  return serviceChangeTypeLabels[code] || code;
}

function serviceWorkflowAssigneeLabel(step) {
  const service = serviceState();
  if (step?.approverType === "user") {
    const user = (service.workflowUsers || []).find((item) => String(item.id) === String(step.approverUserId));
    return user?.displayName || user?.username || `用户 ${step?.approverUserId || "未配置"}`;
  }
  const role = (service.workflowRoles || []).find((item) => item.code === step?.approverRoleCode);
  return role?.name || role?.code || `角色 ${step?.approverRoleCode || "未配置"}`;
}

function ensureServiceNavigation() {
  const nav = document.querySelector("#sidebarNav");
  if (!nav || nav.querySelector('[data-page="serviceManagement"]')) return;
  nav.insertAdjacentHTML(
    "beforeend",
    `<div class="sidebar-section-title sidebar-section-title-spaced">服务管理</div>
     <button class="nav-item" data-action="navigate" data-page="serviceManagement">
       <span class="nav-icon">◎</span><span>工单与服务管理</span>
     </button>`,
  );
}

async function loadServiceManagement() {
  const requestId = beginAsyncRequest("service-management");
  const isCurrentRequest = () => isLatestAsyncRequest("service-management", requestId);
  const service = serviceState();
  service.loading = true;
  renderIfCurrentPage("serviceManagement");
  const jobs = [];
  const view = normalizeServiceView();
  if (view === "tickets" && hasPermission("tickets", "view")) {
    jobs.push(
      requestJson(API_TICKETS_URL).then((payload) => {
        if (isCurrentRequest()) operationsState.tickets = payload.tickets || [];
      }),
    );
  }
  if (view === "changes" && hasPermission("changes", "view")) {
    jobs.push(requestJson(API_CHANGES_URL).then((payload) => {
      if (isCurrentRequest()) service.changes = payload.changes || [];
    }));
  }
  if (view === "problems" && hasPermission("problems", "view")) {
    jobs.push(requestJson(API_PROBLEMS_URL).then((payload) => {
      if (isCurrentRequest()) service.problems = payload.problems || [];
    }));
  }
  if (view === "knowledge" && hasPermission("knowledge", "view")) {
    jobs.push(requestJson(API_KNOWLEDGE_URL).then((payload) => {
      if (isCurrentRequest()) service.articles = payload.articles || [];
    }));
  }
  if (view === "forms" && hasPermission("forms", "view")) {
    jobs.push(requestJson(API_SERVICE_FORMS_URL).then((payload) => {
      if (isCurrentRequest()) service.forms = payload.forms || [];
    }));
  }
  if (view === "policies" && hasPermission("sla", "view")) {
    jobs.push(requestJson(API_SLA_POLICIES_URL).then((payload) => {
      if (isCurrentRequest()) service.policies = payload.policies || [];
    }));
  }
  if (view === "approvals" && hasPermission("approvals", "view")) {
    jobs.push(requestJson(API_APPROVALS_URL).then((payload) => {
      if (isCurrentRequest()) service.approvals = payload.approvals || [];
    }));
    jobs.push(requestJson(API_WORKFLOWS_URL).then((payload) => {
      if (isCurrentRequest()) service.workflows = payload.workflows || [];
    }));
  }
  if (view === "notifications" && hasPermission("notifications", "view")) {
    jobs.push(requestJson(API_NOTIFICATIONS_URL).then((payload) => {
      if (isCurrentRequest()) service.notifications = payload.notifications || [];
    }));
  }
  try {
    await Promise.all(jobs);
    return isCurrentRequest();
  } finally {
    if (isCurrentRequest()) {
      service.loading = false;
      updateAuthenticatedChrome();
    }
  }
}

function serviceTableEmpty(text = "暂无数据") {
  return `<div class="empty-state">${escapeHtml(text)}</div>`;
}

function renderServiceTabs() {
  const service = serviceState();
  return `<div class="service-tabs">${Object.entries(serviceViewLabels)
    .filter(([view]) => canViewServiceView(view))
    .map(
      ([view, label]) =>
        `<button type="button" class="secondary-button service-tab ${service.view === view ? "is-active" : ""}" data-action="service-view" data-view="${view}" aria-pressed="${service.view === view}">${label}</button>`,
    )
    .join("")}</div>`;
}

function renderServiceChanges() {
  const service = serviceState();
  return `<section class="data-panel"><div class="section-heading"><div><h2>变更管理</h2><span>计划、评估、审批、实施和验证均保留记录。</span></div>
    ${hasPermission("changes", "create") ? '<button class="primary-button" data-action="open-service-change">新建变更</button>' : ""}
  </div>
  ${
    service.changes.length
      ? `<div class="table-wrap"><table><thead><tr><th>编号</th><th>标题</th><th>类型</th><th>状态</th><th>风险</th><th>处理人</th><th>更新时间</th><th>操作</th></tr></thead><tbody>${service.changes
          .map(
            (item) =>
              `<tr><td>${escapeHtml(item.number || "")}</td><td>${escapeHtml(item.title || "")}</td><td>${escapeHtml(serviceChangeTypeLabel(item.type))}</td><td>${escapeHtml(serviceStatusLabels[item.status] || item.status || "")}</td><td>${escapeHtml(servicePriorityLabel(item.risk))}</td><td>${escapeHtml(item.assignedToName || "—")}</td><td>${escapeHtml(formatDateTime(item.updatedAt || ""))}</td><td>${hasPermission("changes", "update") ? `<button class="text-button" data-action="open-service-transition" data-record-type="change" data-id="${escapeHtml(item.id)}" data-status="${escapeHtml(item.status)}">流转</button>` : "—"}</td></tr>`,
          )
          .join("")}</tbody></table></div>`
      : serviceTableEmpty("暂无变更记录")
  }</section>`;
}

function renderServiceProblems() {
  const service = serviceState();
  return `<section class="data-panel"><div class="section-heading"><div><h2>问题管理</h2><span>针对重复事件、根因、已知错误和永久解决方案进行跟踪。</span></div>
    ${hasPermission("problems", "create") ? '<button class="primary-button" data-action="open-service-problem">新建问题</button>' : ""}
  </div>
  ${
    service.problems.length
      ? `<div class="table-wrap"><table><thead><tr><th>编号</th><th>标题</th><th>状态</th><th>影响</th><th>处理人</th><th>更新时间</th><th>操作</th></tr></thead><tbody>${service.problems
          .map(
            (item) =>
              `<tr><td>${escapeHtml(item.number || "")}</td><td>${escapeHtml(item.title || "")}</td><td>${escapeHtml(serviceStatusLabels[item.status] || item.status || "")}</td><td>${escapeHtml(servicePriorityLabel(item.impact))}</td><td>${escapeHtml(item.assignedToName || "—")}</td><td>${escapeHtml(formatDateTime(item.updatedAt || ""))}</td><td>${hasPermission("problems", "update") ? `<button class="text-button" data-action="open-service-transition" data-record-type="problem" data-id="${escapeHtml(item.id)}" data-status="${escapeHtml(item.status)}">流转</button>` : "—"}</td></tr>`,
          )
          .join("")}</tbody></table></div>`
      : serviceTableEmpty("暂无问题记录")
  }</section>`;
}

function renderServiceKnowledge() {
  const service = serviceState();
  return `<section class="data-panel"><div class="section-heading"><div><h2>知识库</h2><span>将常见故障、标准操作和解决方案沉淀为可检索文章。</span></div>
    ${hasPermission("knowledge", "create") ? '<button class="primary-button" data-action="open-service-knowledge">新建文章</button>' : ""}
  </div>
  ${
    service.articles.length
      ? `<div class="table-wrap"><table><thead><tr><th>编号</th><th>标题</th><th>分类</th><th>状态</th><th>负责人</th><th>更新时间</th><th>操作</th></tr></thead><tbody>${service.articles
          .map(
            (item) =>
              `<tr><td>${escapeHtml(item.number || "")}</td><td>${escapeHtml(item.title || "")}</td><td>${escapeHtml(item.category || "")}</td><td>${escapeHtml(serviceStatusLabels[item.status] || item.status || "")}</td><td>${escapeHtml(item.ownerName || "—")}</td><td>${escapeHtml(formatDateTime(item.updatedAt || ""))}</td><td>${hasPermission("knowledge", "approve") ? `<button class="text-button" data-action="open-service-transition" data-record-type="knowledge" data-id="${escapeHtml(item.id)}" data-status="${escapeHtml(item.status)}">发布</button>` : "—"}</td></tr>`,
          )
          .join("")}</tbody></table></div>`
      : serviceTableEmpty("暂无知识文章")
  }</section>`;
}

function renderServicePolicies() {
  const service = serviceState();
  return `<section class="data-panel"><div class="section-heading"><div><h2>SLA 管理</h2><span>按优先级设定响应和解决时限，工单创建后自动开始计时。</span></div>${hasPermission("sla", "create") ? '<button class="primary-button" data-action="open-sla-policy">新建 SLA 策略</button>' : ""}</div>
  ${
    service.policies.length
      ? `<div class="table-wrap"><table><thead><tr><th>编码</th><th>名称</th><th>优先级</th><th>响应时限</th><th>解决时限</th><th>状态</th><th>操作</th></tr></thead><tbody>${service.policies
          .map(
            (item) =>
              `<tr><td>${escapeHtml(item.code || "")}</td><td>${escapeHtml(item.name || "")}</td><td>${escapeHtml(servicePriorityLabel(item.priority))}</td><td>${escapeHtml(item.responseMinutes || 0)} 分钟</td><td>${escapeHtml(item.resolutionMinutes || 0)} 分钟</td><td>${item.isActive ? "启用" : "停用"}</td><td>${hasPermission("sla", "update") ? `<button class="text-button" data-action="open-sla-policy" data-id="${escapeHtml(item.id)}">编辑</button>` : "—"}</td></tr>`,
          )
          .join("")}</tbody></table></div>`
      : serviceTableEmpty("暂无 SLA 策略")
  }</section>`;
}

function renderServiceApprovals() {
  const service = serviceState();
  const workflowSection = `<section class="data-panel"><div class="section-heading"><div><h2>审批流程配置</h2><span>按业务类型设置多级审批人，可指定角色或单个用户。</span></div>${hasPermission("approvals", "create") ? '<button class="primary-button" data-action="open-approval-workflow">新建审批流程</button>' : ""}</div>
  ${
    service.workflows.length
      ? `<div class="table-wrap"><table><thead><tr><th>编码</th><th>名称</th><th>业务类型</th><th>步骤</th><th>状态</th><th>操作</th></tr></thead><tbody>${service.workflows
          .map((workflow) => {
            const stepText = (workflow.steps || [])
              .map((step) => `${step.order}. ${step.name}（${serviceWorkflowAssigneeLabel(step)}）`)
              .join("；");
            return `<tr><td>${escapeHtml(workflow.code || "")}</td><td>${escapeHtml(workflow.name || "")}</td><td>${escapeHtml(serviceRecordTypeLabel(workflow.recordType))}</td><td>${escapeHtml(stepText)}</td><td>${workflow.isActive ? "启用" : "停用"}</td><td>${hasPermission("approvals", "update") ? `<button class="text-button" data-action="open-approval-workflow" data-id="${escapeHtml(workflow.id)}">编辑</button>` : "—"}</td></tr>`;
          })
          .join("")}</tbody></table></div>`
      : serviceTableEmpty("暂无审批流程")
  }</section>`;
  return `${workflowSection}<section class="data-panel"><div class="section-heading"><div><h2>待审批</h2><span>审批通过后才可进入后续服务管理状态。</span></div></div>
  ${
    service.approvals.length
      ? `<div class="table-wrap"><table><thead><tr><th>业务类型</th><th>记录编号</th><th>流程</th><th>当前步骤</th><th>申请人</th><th>创建时间</th><th>操作</th></tr></thead><tbody>${service.approvals
          .map(
            (item) =>
              `<tr><td>${escapeHtml(serviceRecordTypeLabel(item.recordType))}</td><td>${escapeHtml(item.recordId || "")}</td><td>${escapeHtml(item.workflowName || "")}</td><td>${escapeHtml(item.currentStepOrder || 1)}</td><td>${escapeHtml(item.requestedBy || "—")}</td><td>${escapeHtml(formatDateTime(item.createdAt || ""))}</td><td>${hasPermission("approvals", "approve") ? `<button class="text-button" data-action="open-approval-decision" data-id="${escapeHtml(item.id)}">审批</button>` : "—"}</td></tr>`,
          )
          .join("")}</tbody></table></div>`
      : serviceTableEmpty("暂无待审批记录")
  }</section>`;
}

function renderServiceNotifications() {
  const service = serviceState();
  return `<section class="data-panel"><div class="section-heading"><div><h2>消息通知</h2><span>状态变化、审批结果和分派信息会自动生成站内通知。</span></div></div>
  ${
    service.notifications.length
      ? `<div class="notification-list">${service.notifications
          .map(
            (item) =>
              `<div class="notification-item ${item.isRead ? "" : "is-unread"}"><strong>${escapeHtml(item.title || "")}</strong><p>${escapeHtml(item.content || "")}</p><small>${escapeHtml(formatDateTime(item.createdAt || ""))}</small>${item.isRead ? "" : `<button class="text-button" data-action="read-notification" data-id="${escapeHtml(item.id)}">标记已读</button>`}</div>`,
          )
          .join("")}</div>`
      : serviceTableEmpty("暂无通知")
  }</section>`;
}

function renderServiceManagementPage() {
  const service = serviceState();
  normalizeServiceView();
  let content = "";
  if (service.view === "changes") content = renderServiceChanges();
  else if (service.view === "problems") content = renderServiceProblems();
  else if (service.view === "knowledge") content = renderServiceKnowledge();
  else if (service.view === "forms") content = renderServiceFormsDesignerList();
  else if (service.view === "policies") content = renderServicePolicies();
  else if (service.view === "approvals") content = renderServiceApprovals();
  else if (service.view === "notifications") content = renderServiceNotifications();
  else content = renderServiceTickets();
  return `<div class="page-intro"><div><h2>工单与服务管理</h2><p>工单、变更、问题、知识库、SLA、审批和通知统一管理。</p></div><div class="toolbar-actions"><button class="secondary-button" data-action="refresh-service">刷新</button></div></div>${renderServiceTabs()}${content}`;
}

const serviceFormFieldTypes = [
  { value: "text", label: "单行文本" },
  { value: "textarea", label: "多行文本" },
  { value: "number", label: "数字" },
  { value: "date", label: "日期" },
  { value: "datetime", label: "日期时间" },
  { value: "select", label: "单选" },
  { value: "multiselect", label: "多选" },
  { value: "checkbox", label: "勾选" },
  { value: "employee", label: "人员" },
  { value: "asset", label: "资产" },
  { value: "organization", label: "组织" },
];

function serviceRecordDraft(recordType) {
  return serviceRecordFormDrafts[recordType] || { forms: [], selectedCode: "" };
}

function serviceRecordFormByCode(recordType, code) {
  const draft = serviceRecordDraft(recordType);
  return (draft.forms || []).find((form) => form.code === code) || draft.forms[0] || null;
}

function renderServiceRecordCustomFields(recordType, selectedCode) {
  const selectedForm = serviceRecordFormByCode(recordType, selectedCode);
  const fields = (selectedForm?.fields || []).map(ticketCustomFieldInput).join("");
  if (!fields) return "";
  return `<section class="modal-section"><div class="modal-section-title"><h3>${escapeHtml(selectedForm?.name || "业务字段")}</h3><span>按所选表单填写业务信息。</span></div><div class="form-grid">${fields}</div></section>`;
}

async function loadServiceRecordForms(recordType, selectedCode = "") {
  const draft = serviceRecordDraft(recordType);
  try {
    const payload = await requestJson(`${API_SERVICE_FORMS_URL}?recordType=${encodeURIComponent(recordType)}&forSubmission=1`);
    draft.forms = Array.isArray(payload.forms) ? payload.forms : [];
    const defaultCode = `${recordType}_default`;
    draft.selectedCode =
      selectedCode ||
      draft.selectedCode ||
      draft.forms.find((form) => form.code === defaultCode)?.code ||
      draft.forms[0]?.code ||
      "";
  } catch (error) {
    draft.forms = [];
    draft.selectedCode = "";
    showToast(`读取业务表单失败：${error.message}`, true);
  }
  return draft;
}

function collectServiceCustomFields(form, recordType, formCode) {
  const selectedForm = serviceRecordFormByCode(recordType, formCode);
  const values = new FormData(form);
  const customFields = {};
  for (const field of selectedForm?.fields || []) {
    const key = `custom_${field.key}`;
    if (field.type === "checkbox") {
      customFields[field.key] = form.querySelector(`[name="${CSS.escape(key)}"]`)?.checked || false;
    } else if (field.type === "multiselect") {
      customFields[field.key] = [...(form.querySelector(`[name="${CSS.escape(key)}"]`)?.selectedOptions || [])]
        .map((option) => option.value)
        .filter(Boolean);
    } else if (values.has(key)) {
      customFields[field.key] = values.get(key);
    }
  }
  return customFields;
}

function serviceFormOptions(recordType) {
  const draft = serviceRecordDraft(recordType);
  return (draft.forms || []).map((form) => ({ value: form.code, label: form.name || form.code }));
}

async function openServiceChangeModal(selectedCode = "") {
  const draft = await loadServiceRecordForms("change", selectedCode);
  openModal(`${modalHeader("新建变更", "变更需要经过评估和审批后才能实施。")}
    <form data-form="service-change">
      <div class="form-grid">
        ${selectField("变更类型", "type", [{ value: "standard", label: "标准变更" }, { value: "normal", label: "普通变更" }, { value: "emergency", label: "紧急变更" }], "normal", true)}
        ${selectField("影响", "impact", [{ value: "low", label: "低" }, { value: "medium", label: "中" }, { value: "high", label: "高" }], "medium", true)}
        ${selectField("风险", "risk", [{ value: "low", label: "低" }, { value: "medium", label: "中" }, { value: "high", label: "高" }], "medium", true)}
        ${selectField("变更表单", "formCode", serviceFormOptions("change").length ? serviceFormOptions("change") : [{ value: "", label: "默认表单" }], draft.selectedCode)}
      </div>
      ${inputField("标题", "title", "", true, "例如：更换核心交换机")}
      ${textareaField("变更说明", "description", "", true, "说明原因、范围、回退方案和验证方式。", 6)}
      <div data-service-custom-fields="change">${renderServiceRecordCustomFields("change", draft.selectedCode)}</div>
      <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">创建变更</button></div>
    </form>`, false);
}

async function openServiceProblemModal(selectedCode = "") {
  const draft = await loadServiceRecordForms("problem", selectedCode);
  openModal(`${modalHeader("新建问题", "用于分析重复事件并记录根因和永久解决方案。")}
    <form data-form="service-problem">
      <div class="form-grid">
        ${selectField("影响", "impact", [{ value: "low", label: "低" }, { value: "medium", label: "中" }, { value: "high", label: "高" }], "medium", true)}
        ${selectField("问题表单", "formCode", serviceFormOptions("problem").length ? serviceFormOptions("problem") : [{ value: "", label: "默认表单" }], draft.selectedCode)}
      </div>
      ${inputField("标题", "title", "", true, "例如：同一部门网络间歇中断")}
      ${textareaField("问题说明", "description", "", true, "描述现象、影响和已知信息。", 6)}
      <div data-service-custom-fields="problem">${renderServiceRecordCustomFields("problem", draft.selectedCode)}</div>
      <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">创建问题</button></div>
    </form>`, false);
}

function openServiceKnowledgeModal() {
  openModal(`${modalHeader("新建知识文章", "沉淀标准操作、常见故障和解决方案。")}
    <form data-form="service-knowledge">
      ${inputField("标题", "title", "", true, "例如：VPN 无法连接排查步骤")}
      ${inputField("摘要", "summary", "", false, "用于搜索结果预览")}
      ${inputField("分类", "category", "通用", true, "例如：网络、终端、账号")}
      ${textareaField("正文", "body", "", true, "支持纯文本内容。", 10)}
      <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">创建文章</button></div>
    </form>`, false);
}

function serviceFormOptionsText(field) {
  return (field.options || [])
    .map((option) => `${option.value || ""}|${option.label || option.value || ""}`)
    .join("\n");
}

const designerFieldCatalog = [
  { type: "text", label: "单行文本", category: "基础控件" },
  { type: "textarea", label: "多行文本", category: "基础控件" },
  { type: "number", label: "数字", category: "基础控件" },
  { type: "date", label: "日期", category: "基础控件" },
  { type: "datetime", label: "日期时间", category: "基础控件" },
  { type: "select", label: "下拉单选", category: "基础控件" },
  { type: "multiselect", label: "下拉多选", category: "基础控件" },
  { type: "checkbox", label: "复选框", category: "基础控件" },
  { type: "employee", label: "人员选择", category: "本系统组件" },
  { type: "asset", label: "资产选择", category: "本系统组件" },
  { type: "organization", label: "组织选择", category: "本系统组件" },
  { type: "system", label: "当前人员信息", category: "系统组件" },
];

function renderServiceFormsDesignerList() {
  const forms = serviceState().forms || [];
  const rows = forms.map((item) => `
    <tr>
      <td>${escapeHtml(item.code || "")}</td>
      <td>${escapeHtml(item.name || "")}</td>
      <td>${escapeHtml(serviceRecordTypeLabel(item.recordType))}</td>
      <td>${escapeHtml(item.version || 1)}</td>
      <td>${escapeHtml((item.fields || []).length)}</td>
      <td>${escapeHtml(formatDateTime(item.updatedAt || ""))}</td>
      <td>${hasPermission("forms", "update") ? `<button class="text-button" data-action="open-form-designer" data-id="${escapeHtml(item.id)}">设计</button>` : "—"}</td>
    </tr>`).join("");
  return `<section class="data-panel">
    <div class="section-heading">
      <div><h2>表单</h2><span>设计工单、变更和问题的字段、流程、列表与权限。</span></div>
      ${hasPermission("forms", "create") ? '<button class="primary-button" data-action="open-form-designer">新建表单</button>' : ""}
    </div>
    ${forms.length ? `<div class="table-wrap"><table><thead><tr><th>编码</th><th>名称</th><th>业务类型</th><th>版本</th><th>字段数</th><th>更新时间</th><th>操作</th></tr></thead><tbody>${rows}</tbody></table></div>` : serviceTableEmpty("暂无表单")}
  </section>`;
}

const designerSystemSources = [
  ["current_user_name", "当前账号名称"],
  ["current_employee_name", "当前人员姓名"],
  ["current_employee_no", "当前人员编号"],
  ["current_department", "当前部门"],
  ["current_org", "当前组织"],
  ["current_position", "当前职位"],
  ["current_user_email", "当前账号邮箱"],
  ["current_user_mobile", "当前账号手机"],
  ["current_datetime", "当前日期时间"],
];

function designerForm() {
  return formDesignerState.form || {
    id: "",
    code: "",
    name: "",
    recordType: "ticket",
    description: "",
    fields: [],
    layout: { columns: 1, labelPosition: "top" },
    workflow: { steps: [] },
    listConfig: { columns: [] },
    settings: { submitMessage: "提交成功", allowDraft: true },
  };
}

function designerFieldKey(field) {
  return String(field?.key || "").trim();
}

function designerNewField(type = "text") {
  const base = designerFieldCatalog.find((item) => item.type === type) || designerFieldCatalog[0];
  const suffix = Math.random().toString(36).slice(2, 7);
  return {
    key: `${base.type}_${suffix}`,
    label: base.label,
    type: base.type,
    placeholder: "",
    options: ["select", "multiselect"].includes(base.type) ? [{ value: "option_1", label: "选项 1" }] : [],
    config: base.type === "system" ? { source: "current_employee_name", readonly: true } : {},
    required: false,
    readonly: base.type === "system",
    sortOrder: 0,
  };
}

function designerNormalizeForm(form) {
  const value = form || {};
  value.fields = Array.isArray(value.fields) ? value.fields.map((field) => ({
    ...field,
    key: designerFieldKey(field) || designerNewField("text").key,
    config: field.config && typeof field.config === "object" ? field.config : {},
    options: Array.isArray(field.options) ? field.options : [],
  })) : [];
  value.layout = value.layout && typeof value.layout === "object" ? value.layout : { columns: 1, labelPosition: "top" };
  value.workflow = value.workflow && typeof value.workflow === "object" ? value.workflow : { steps: [] };
  value.workflow.steps = Array.isArray(value.workflow.steps)
    ? value.workflow.steps.map((step, index) => ({
        nodeType: step.nodeType || "approval",
        name: step.name || (step.nodeType === "handler" ? "经办节点" : step.nodeType === "cc" ? "抄送节点" : `审批节点 ${index + 1}`),
        approverType: step.approverType || (step.approverUserId ? "user" : "role"),
        approverRoleCode: step.approverRoleCode || "",
        approverUserId: step.approverUserId || "",
        required: step.required !== false,
        notify: step.notify !== false,
      }))
    : [];
  value.listConfig = value.listConfig && typeof value.listConfig === "object" ? value.listConfig : { columns: [] };
  value.settings = value.settings && typeof value.settings === "object" ? value.settings : { submitMessage: "提交成功", allowDraft: true };
  return value;
}

function designerSelectedField() {
  return designerForm().fields.find((field) => designerFieldKey(field) === formDesignerState.selectedFieldKey) || null;
}

function designerPreviewField(field) {
  const key = escapeHtml(field.key || "");
  const placeholder = escapeHtml(field.placeholder || "");
  if (field.type === "textarea") return `<textarea disabled rows="3" placeholder="${placeholder}"></textarea>`;
  if (field.type === "checkbox") return `<input type="checkbox" disabled />`;
  if (field.type === "select" || field.type === "multiselect") {
    return `<select disabled ${field.type === "multiselect" ? "multiple" : ""}><option>${field.type === "multiselect" ? "可多选" : "请选择"}</option></select>`;
  }
  if (field.type === "system") return `<div class="designer-readonly-value">${escapeHtml((field.config || {}).source || "系统自动带出")}</div>`;
  return `<input disabled type="${field.type === "datetime" ? "datetime-local" : field.type}" placeholder="${placeholder}" data-field-preview="${key}" />`;
}

function renderDesignerPalette() {
  const groups = new Map();
  designerFieldCatalog.forEach((item) => {
    if (!groups.has(item.category)) groups.set(item.category, []);
    groups.get(item.category).push(item);
  });
  return [...groups.entries()].map(([category, items]) => `
    <section class="designer-palette-group">
      <h3>${escapeHtml(category)}</h3>
      <div class="designer-palette-grid">${items.map((item) => `
        <button type="button" class="designer-palette-item" draggable="true" data-action="designer-add-field" data-type="${escapeHtml(item.type)}" title="拖入画布或点击添加">
          <span class="designer-palette-icon">${item.type === "system" ? "◎" : item.type === "employee" ? "人" : item.type === "asset" ? "箱" : "+"}</span>
          <span>${escapeHtml(item.label)}</span>
        </button>`).join("")}</div>
    </section>`).join("");
}

function renderDesignerCanvas() {
  const fields = designerForm().fields;
  return `<div class="designer-canvas-head"><div><span class="eyebrow">FORM CANVAS</span><h2>${escapeHtml(designerForm().name || "未命名表单")}</h2></div><span class="designer-canvas-hint">拖动字段调整顺序</span></div>
    <div class="designer-canvas" data-designer-dropzone>
      ${fields.length ? fields.map((field, index) => `
        <article class="designer-field-card ${designerFieldKey(field) === formDesignerState.selectedFieldKey ? "is-selected" : ""}" draggable="true" data-designer-field="${escapeHtml(field.key)}" data-index="${index}">
          <div class="designer-field-card-head"><span class="designer-drag-handle" title="拖动排序">⋮⋮</span><strong>${escapeHtml(field.label || field.key)}</strong>${field.required ? '<span class="designer-required">必填</span>' : ""}<button type="button" class="icon-button" data-action="designer-delete-field" data-key="${escapeHtml(field.key)}" title="删除字段">×</button></div>
          <div class="designer-field-preview">${designerPreviewField(field)}</div>
        </article>`).join("") : `<div class="designer-empty-canvas"><strong>从左侧添加控件</strong><span>点击控件或拖入此区域开始设计</span></div>`}
    </div>`;
}

function designerInput(label, name, value, type = "text") {
  return `<label class="designer-property-field"><span>${escapeHtml(label)}</span><input data-designer-property="${escapeHtml(name)}" type="${type}" value="${escapeHtml(value ?? "")}" /></label>`;
}

function designerFormInput(label, name, value, type = "text") {
  return `<label class="designer-property-field"><span>${escapeHtml(label)}</span><input data-designer-form-property="${escapeHtml(name)}" type="${type}" value="${escapeHtml(value ?? "")}" /></label>`;
}

function renderDesignerProperties() {
  const field = designerSelectedField();
  if (!field) return `<div class="designer-properties-empty"><strong>选择一个控件</strong><span>右侧将显示控件属性</span></div>`;
  const source = (field.config || {}).source || "current_employee_name";
  return `<div class="designer-properties-head"><span class="eyebrow">FIELD PROPERTIES</span><h2>${escapeHtml(field.label || field.key)}</h2></div>
    ${designerInput("字段名称", "label", field.label)}
    ${designerInput("字段标识", "key", field.key)}
    <label class="designer-property-field"><span>字段类型</span><select data-designer-property="type">${designerFieldCatalog.map((item) => `<option value="${item.type}" ${item.type === field.type ? "selected" : ""}>${escapeHtml(item.label)}</option>`).join("")}</select></label>
    ${designerInput("占位提示", "placeholder", field.placeholder)}
    ${["select", "multiselect"].includes(field.type) ? `<label class="designer-property-field"><span>选项</span><textarea data-designer-property="options" rows="5">${escapeHtml(serviceFormOptionsText(field))}</textarea></label>` : ""}
    ${field.type === "system" ? `<label class="designer-property-field"><span>自动带出</span><select data-designer-property="systemSource">${designerSystemSources.map(([value, label]) => `<option value="${value}" ${value === source ? "selected" : ""}>${label}</option>`).join("")}</select></label>` : ""}
    <label class="designer-switch"><input type="checkbox" data-designer-property="required" ${field.required ? "checked" : ""} /> <span>必填</span></label>
    <label class="designer-switch"><input type="checkbox" data-designer-property="readonly" ${field.readonly || field.type === "system" ? "checked" : ""} ${field.type === "system" ? "disabled" : ""} /> <span>只读</span></label>`;
}

function renderDesignerSettings() {
  const form = designerForm();
  return `<div class="designer-settings-panel">
    <div class="designer-settings-section"><h2>表单属性</h2>${designerFormInput("表单编码", "formCode", form.code)}${designerFormInput("表单名称", "formName", form.name)}<label class="designer-property-field"><span>业务类型</span><select data-designer-form-property="recordType"><option value="ticket" ${form.recordType === "ticket" ? "selected" : ""}>工单</option><option value="change" ${form.recordType === "change" ? "selected" : ""}>变更管理</option><option value="problem" ${form.recordType === "problem" ? "selected" : ""}>问题管理</option></select></label><label class="designer-property-field"><span>说明</span><textarea data-designer-form-property="description" rows="3">${escapeHtml(form.description || "")}</textarea></label></div>
    <div class="designer-settings-section"><h2>权限对象</h2><p class="designer-muted">按角色或用户控制查看、提交、修改、删除、审批和导出。</p>${renderDesignerPermissionRows()}</div>
    <div class="designer-settings-section"><h2>提交设置</h2>${designerFormInput("提交成功提示", "submitMessage", form.settings.submitMessage || "提交成功")}<label class="designer-switch"><input type="checkbox" data-designer-form-property="allowDraft" ${form.settings.allowDraft !== false ? "checked" : ""} /> <span>允许保存草稿</span></label></div>
  </div>`;
}

function designerWorkflowSteps() {
  const form = designerForm();
  if (!form.workflow || typeof form.workflow !== "object") form.workflow = { steps: [] };
  if (!Array.isArray(form.workflow.steps)) form.workflow.steps = [];
  return form.workflow.steps;
}

function designerWorkflowOptions() {
  const service = serviceState();
  return {
    roles: [{ value: "", label: "选择角色" }].concat(
      (service.workflowRoles || []).map((role) => ({ value: role.code, label: role.name || role.code })),
    ),
    users: [{ value: "", label: "选择用户" }].concat(
      (service.workflowUsers || []).map((user) => ({ value: user.id, label: user.displayName || user.username })),
    ),
  };
}

function renderDesignerWorkflowNode(step, index) {
  const nodeType = step.nodeType || "approval";
  const nodeTypeLabel = { handler: "经办节点", approval: "审批节点", cc: "抄送节点" }[nodeType] || "审批节点";
  const personnel =
    nodeType === "cc"
      ? step.approverType === "user"
        ? (serviceState().workflowUsers || []).find((user) => String(user.id) === String(step.approverUserId))?.displayName
        : (serviceState().workflowRoles || []).find((role) => role.code === step.approverRoleCode)?.name
      : nodeType === "handler"
        ? step.approverType === "user"
          ? (serviceState().workflowUsers || []).find((user) => String(user.id) === String(step.approverUserId))?.displayName
          : (serviceState().workflowRoles || []).find((role) => role.code === step.approverRoleCode)?.name
        : step.approverType === "user"
          ? (serviceState().workflowUsers || []).find((user) => String(user.id) === String(step.approverUserId))?.displayName
          : (serviceState().workflowRoles || []).find((role) => role.code === step.approverRoleCode)?.name;
  return `<div class="designer-flow-node-wrap">
    ${index > 0 ? '<span class="designer-flow-connector" aria-hidden="true"></span>' : ""}
    <button type="button" class="designer-flow-node ${formDesignerState.selectedWorkflowStepIndex === index ? "is-selected" : ""}" data-designer-workflow-step="${index}">
      <span class="designer-flow-node-icon">${nodeType === "handler" ? "↗" : nodeType === "cc" ? "⌁" : "✓"}</span>
      <span class="designer-flow-node-copy"><strong>${escapeHtml(step.name || nodeTypeLabel)}</strong><small>${escapeHtml(nodeTypeLabel)} · ${escapeHtml(personnel || "未配置人员")}</small></span>
      <span class="designer-flow-node-state">${step.required === false ? "可选" : "必经"}</span>
    </button>
  </div>`;
}

function renderDesignerWorkflowProperties() {
  const steps = designerWorkflowSteps();
  const index =
    formDesignerState.selectedWorkflowStepIndex >= 0
      ? formDesignerState.selectedWorkflowStepIndex
      : steps.length
        ? 0
        : -1;
  if (index >= 0 && formDesignerState.selectedWorkflowStepIndex < 0) {
    formDesignerState.selectedWorkflowStepIndex = index;
  }
  const step = steps[index];
  if (!step) {
    return `<div class="designer-properties-empty"><strong>选择一个流程节点</strong><span>流程人员、节点类型和审批规则会显示在这里</span></div>`;
  }
  const options = designerWorkflowOptions();
  const approverType = step.approverType || (step.approverUserId ? "user" : "role");
  return `<div class="designer-properties-head"><span class="eyebrow">NODE PROPERTIES</span><h2>${escapeHtml(step.name || "流程节点")}</h2></div>
    <label class="designer-property-field"><span>节点名称</span><input data-designer-workflow-property="name" data-index="${index}" value="${escapeHtml(step.name || "")}" /></label>
    <label class="designer-property-field"><span>节点类型</span><select data-designer-workflow-property="nodeType" data-index="${index}">
      <option value="handler" ${step.nodeType === "handler" ? "selected" : ""}>经办节点</option>
      <option value="approval" ${step.nodeType === "approval" || !step.nodeType ? "selected" : ""}>审批节点</option>
      <option value="cc" ${step.nodeType === "cc" ? "selected" : ""}>抄送节点</option>
    </select></label>
    <label class="designer-property-field"><span>人员来源</span><select data-designer-workflow-property="approverType" data-index="${index}">
      <option value="role" ${approverType === "role" ? "selected" : ""}>按角色</option>
      <option value="user" ${approverType === "user" ? "selected" : ""}>指定用户</option>
    </select></label>
    <label class="designer-property-field" ${approverType === "user" ? "hidden" : ""}><span>流程角色</span><select data-designer-workflow-property="approverRoleCode" data-index="${index}">${options.roles.map((item) => `<option value="${escapeHtml(item.value)}" ${item.value === step.approverRoleCode ? "selected" : ""}>${escapeHtml(item.label)}</option>`).join("")}</select></label>
    <label class="designer-property-field" ${approverType !== "user" ? "hidden" : ""}><span>流程人员</span><select data-designer-workflow-property="approverUserId" data-index="${index}">${options.users.map((item) => `<option value="${escapeHtml(item.value)}" ${String(item.value) === String(step.approverUserId) ? "selected" : ""}>${escapeHtml(item.label)}</option>`).join("")}</select></label>
    <label class="designer-switch"><input type="checkbox" data-designer-workflow-property="required" data-index="${index}" ${step.required !== false ? "checked" : ""} /> <span>必须通过</span></label>
    <label class="designer-switch"><input type="checkbox" data-designer-workflow-property="notify" data-index="${index}" ${step.notify !== false ? "checked" : ""} /> <span>进入节点时通知</span></label>
    <button type="button" class="danger-text-button" data-action="designer-delete-workflow-step" data-index="${index}">删除此节点</button>`;
}

function renderDesignerWorkflow() {
  const steps = designerWorkflowSteps();
  return `<div class="designer-workflow-layout">
    <aside class="designer-workflow-palette">
      <div class="designer-palette-group"><h3>节点</h3><button type="button" class="designer-node-tool" data-action="designer-add-workflow-step" data-node-type="handler"><span>↗</span><strong>经办节点</strong><small>指定处理人执行任务</small></button><button type="button" class="designer-node-tool" data-action="designer-add-workflow-step" data-node-type="approval"><span>✓</span><strong>审批节点</strong><small>指定人员或角色审批</small></button><button type="button" class="designer-node-tool" data-action="designer-add-workflow-step" data-node-type="cc"><span>⌁</span><strong>抄送节点</strong><small>流程推进时同步通知</small></button></div>
      <div class="designer-flow-help"><strong>流程人员</strong><span>提交表单后，节点配置的人员会显示在工单详情、审批记录和消息提醒中。</span></div>
    </aside>
    <main class="designer-workflow-canvas"><div class="designer-canvas-head"><div><span class="eyebrow">WORKFLOW CANVAS</span><h2>${escapeHtml(designerForm().name || "未命名表单")}</h2></div><span class="designer-canvas-hint">从上到下依次执行</span></div><div class="designer-flow-start"><span>▶</span><strong>开始</strong><small>提交表单</small></div><div class="designer-flow-list">${steps.length ? steps.map(renderDesignerWorkflowNode).join("") : '<div class="designer-empty-canvas"><strong>从左侧添加流程节点</strong><span>节点人员将在表单详情中显示</span></div>'}</div><div class="designer-flow-end"><span>◉</span><strong>结束</strong></div></main>
    <aside class="designer-properties designer-workflow-properties">${renderDesignerWorkflowProperties()}</aside>
  </div>`;
}

function renderDesignerPermissionRows() {
  const permissions = formDesignerState.permissions || [];
  const roles = settingsState.accessControl?.roles || [];
  const users = settingsState.users || [];
  const rows = permissions.map((item, index) => {
    const subjects = item.subjectType === "role" ? roles : users;
    return `<div class="designer-permission-row" data-permission-index="${index}">
      <select data-designer-permission="subjectType"><option value="role" ${item.subjectType === "role" ? "selected" : ""}>角色</option><option value="user" ${item.subjectType === "user" ? "selected" : ""}>用户</option></select>
      <select data-designer-permission="subjectId">${subjects.map((subject) => `<option value="${escapeHtml(subject.id)}" ${String(subject.id) === String(item.subjectId) ? "selected" : ""}>${escapeHtml(subject.name || subject.displayName || subject.username || subject.code)}</option>`).join("")}</select>
      ${["view", "submit", "update", "delete", "approve", "export"].map((action) => `<label title="${action}"><input type="checkbox" data-designer-permission="${action}" ${item[`can${action.charAt(0).toUpperCase()}${action.slice(1)}`] ? "checked" : ""} />${{ view: "看", submit: "提", update: "改", delete: "删", approve: "审", export: "导" }[action]}</label>`).join("")}
      <select data-designer-permission="dataScope">${[["all", "全部资产"], ["organization", "所属部门"], ["own", "本人资产"], ["submitted", "本人提交"], ["assigned", "负责工单"], ["none", "无数据"]].map(([value, label]) => `<option value="${value}" ${value === (item.dataScope || "all") ? "selected" : ""}>${label}</option>`).join("")}</select>
      <button type="button" class="icon-button" data-action="designer-remove-permission" data-index="${index}" title="删除权限对象">×</button>
    </div>`;
  }).join("");
  return `<div class="designer-permission-list">${rows || '<div class="designer-muted">尚未配置表单级权限，默认沿用模块权限。</div>'}</div><div class="designer-permission-add"><select data-designer-add-subject-type><option value="role">角色</option><option value="user">用户</option></select><select data-designer-add-subject-id>${roles.map((role) => `<option value="${escapeHtml(role.id)}">${escapeHtml(role.name || role.code)}</option>`).join("")}</select><button type="button" class="secondary-button" data-action="designer-add-permission">添加权限对象</button></div>`;
}

function renderServiceFormDesignerPage() {
  const panels = [["form", "表单设计"], ["workflow", "流程设计"], ["settings", "表单设置"]];
  const form = designerForm();
  let content = "";
  if (formDesignerState.activePanel === "settings") content = renderDesignerSettings();
  else if (formDesignerState.activePanel === "workflow") content = renderDesignerWorkflow();
  else content = `<div class="form-designer-layout"><aside class="designer-palette">${renderDesignerPalette()}</aside><main class="designer-workspace">${renderDesignerCanvas()}</main><aside class="designer-properties">${renderDesignerProperties()}</aside></div>`;
  return `<div class="form-designer-page"><header class="form-designer-toolbar"><button type="button" class="icon-button" data-action="designer-back" title="返回服务管理">‹</button><div class="designer-title"><input data-designer-title value="${escapeHtml(form.name || "未命名表单")}" aria-label="表单名称" /><span>${form.id ? `版本 ${escapeHtml(form.version || 1)}` : "新建表单"}</span></div><nav class="designer-tabs">${panels.map(([value, label]) => `<button type="button" class="${formDesignerState.activePanel === value ? "is-active" : ""}" data-action="designer-panel" data-panel="${value}">${label}</button>`).join("")}</nav><div class="designer-toolbar-actions"><span class="${formDesignerState.dirty ? "designer-dirty" : ""}">${formDesignerState.dirty ? "未保存" : "已保存"}</span><button type="button" class="primary-button" data-action="designer-save">保存</button></div></header>${formDesignerState.loading ? '<div class="designer-loading">正在加载表单…</div>' : content}</div>`;
}

async function openFormDesigner(formId = "") {
  const requestId = beginAsyncRequest("form-designer");
  formDesignerState = { formId: String(formId || ""), form: designerNormalizeForm(formId ? null : { recordType: "ticket", fields: [] }), selectedFieldKey: "", selectedWorkflowStepIndex: -1, activePanel: "form", permissions: [], loading: Boolean(formId), dirty: false };
  state.page = "formDesigner";
  render();
  try {
    await loadWorkflowOptions();
    if (!isLatestAsyncRequest("form-designer", requestId)) return;
    if (formId) {
      const [formPayload, permissionPayload] = await Promise.all([
        requestJson(`${API_SERVICE_FORMS_URL}/${encodeURIComponent(formId)}`),
        requestJson(`${API_SERVICE_FORMS_URL}/${encodeURIComponent(formId)}${API_SERVICE_FORM_PERMISSIONS_URL}`),
      ]);
      if (!isLatestAsyncRequest("form-designer", requestId)) return;
      formDesignerState.form = designerNormalizeForm(formPayload.form);
      formDesignerState.permissions = Array.isArray(permissionPayload.permissions) ? permissionPayload.permissions : [];
    }
  } catch (error) {
    if (!isLatestAsyncRequest("form-designer", requestId)) return;
    showToast(`加载表单设计失败：${error.message}`, true);
    if (state.page === "formDesigner") {
      state.page = "serviceManagement";
      serviceState().view = "forms";
      render();
    }
  } finally {
    if (!isLatestAsyncRequest("form-designer", requestId)) return;
    formDesignerState.loading = false;
    renderIfCurrentPage("formDesigner");
  }
}

function designerSyncFieldFromPanel(target) {
  const field = designerSelectedField();
  if (!field) return;
  const property = target.dataset.designerProperty;
  if (!property) return;
  if (property === "required" || property === "readonly") field[property] = Boolean(target.checked);
  else if (property === "options") {
    field.options = target.value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
      const [value, ...labelParts] = line.split("|");
      return { value: value.trim(), label: labelParts.join("|").trim() || value.trim() };
    });
  } else if (property === "systemSource") {
    field.type = "system";
    field.config = { ...(field.config || {}), source: target.value, readonly: true };
    field.readonly = true;
  } else if (property === "type") {
    field.type = target.value;
    if (target.value === "system") {
      field.config = { ...(field.config || {}), source: "current_employee_name", readonly: true };
      field.readonly = true;
    } else if (!["select", "multiselect"].includes(target.value)) field.options = [];
  } else field[property] = target.value;
  formDesignerState.dirty = true;
}

async function saveFormDesigner() {
  const form = designerForm();
  const title = document.querySelector("[data-designer-title]")?.value.trim();
  if (title) form.name = title;
  if (!form.code || !form.name) return showToast("表单编码和名称不能为空。", true);
  const payload = {
    code: form.code,
    name: form.name,
    recordType: form.recordType,
    description: form.description || "",
    fields: form.fields.map((field, index) => ({ ...field, sortOrder: (index + 1) * 10 })),
    layout: form.layout,
    workflow: form.workflow,
    listConfig: form.listConfig,
    settings: form.settings,
  };
  try {
    const endpoint = form.id ? `${API_SERVICE_FORMS_URL}/${encodeURIComponent(form.id)}` : API_SERVICE_FORMS_URL;
    const result = await requestJson(endpoint, { method: form.id ? "PUT" : "POST", body: JSON.stringify(payload) });
    formDesignerState.form = designerNormalizeForm(result.form);
    formDesignerState.formId = String(result.form?.id || form.id || "");
    if (formDesignerState.formId && isAdminUser()) {
      const permissionPayload = await requestJson(`${API_SERVICE_FORMS_URL}/${encodeURIComponent(formDesignerState.formId)}${API_SERVICE_FORM_PERMISSIONS_URL}`, { method: "PUT", body: JSON.stringify({ permissions: formDesignerState.permissions || [] }) });
      formDesignerState.permissions = permissionPayload.permissions || formDesignerState.permissions;
    }
    formDesignerState.dirty = false;
    showToast("表单设计已保存。");
    render();
  } catch (error) {
    showToast(`保存表单设计失败：${error.message}`, true);
  }
}

function renderServiceFormFieldRow(field = {}) {
  const type = field.type || "text";
  return `<section class="service-form-builder-row" data-service-form-field>
    <div class="form-grid">
      ${inputField("字段标识", "fieldKey", field.key || "", true, "小写字母、数字和下划线")}
      ${inputField("字段名称", "fieldLabel", field.label || "", true, "例如：业务影响说明")}
      ${selectField("字段类型", "fieldType", serviceFormFieldTypes, type, true)}
      ${inputField("提示文字", "fieldPlaceholder", field.placeholder || "", false, "填写提示")}
    </div>
    <div class="service-form-builder-options">
      ${textareaField("选项", "fieldOptions", serviceFormOptionsText(field), false, "仅单选/多选使用；每行格式：值|显示名称", 3)}
      <label class="service-form-check"><input type="checkbox" name="fieldRequired" ${field.required ? "checked" : ""} /> 必填</label>
      <label class="service-form-check"><input type="checkbox" name="fieldReadonly" ${field.readonly ? "checked" : ""} /> 只读</label>
      <button type="button" class="text-button" data-action="remove-service-form-field">删除字段</button>
    </div>
  </section>`;
}

function readServiceFormFields(form) {
  return [...form.querySelectorAll("[data-service-form-field]")].map((row, index) => {
    const type = row.querySelector('[name="fieldType"]')?.value || "text";
    const rawOptions = row.querySelector('[name="fieldOptions"]')?.value || "";
    const options = ["select", "multiselect"].includes(type)
      ? rawOptions
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean)
          .map((line) => {
            const [value, ...labelParts] = line.split("|");
            const label = labelParts.join("|").trim() || value.trim();
            return { value: value.trim(), label };
          })
          .filter((option) => option.value)
      : [];
    return {
      key: row.querySelector('[name="fieldKey"]')?.value.trim() || "",
      label: row.querySelector('[name="fieldLabel"]')?.value.trim() || "",
      type,
      placeholder: row.querySelector('[name="fieldPlaceholder"]')?.value.trim() || "",
      options,
      required: Boolean(row.querySelector('[name="fieldRequired"]')?.checked),
      readonly: Boolean(row.querySelector('[name="fieldReadonly"]')?.checked),
      sortOrder: (index + 1) * 10,
    };
  });
}

function openServiceFormModal(formId = "") {
  const existing = (serviceState().forms || []).find((form) => String(form.id) === String(formId));
  const fields = existing?.fields?.length ? existing.fields : [{ type: "text" }];
  const editing = Boolean(existing);
  openModal(`${modalHeader(editing ? "编辑服务表单" : "新建服务表单", "通过可视化字段编辑器定义工单、变更和问题的业务字段。")}
    <form data-form="service-form" data-id="${escapeHtml(existing?.id || "")}">
      <div class="form-grid">
        ${inputField("表单编码", "code", existing?.code || "", true, "例如：new_employee_request")}
        ${inputField("表单名称", "name", existing?.name || "", true, "例如：新员工入职申请")}
        ${selectField("业务类型", "recordType", [{ value: "ticket", label: "工单" }, { value: "change", label: "变更管理" }, { value: "problem", label: "问题管理" }], existing?.recordType || "ticket", true)}
      </div>
      ${textareaField("说明", "description", existing?.description || "", false, "表单用途说明。", 3)}
      <section class="modal-section"><div class="modal-section-title"><h3>表单字段</h3><span>选项字段按“值|显示名称”逐行填写。</span><button type="button" class="secondary-button" data-action="add-service-form-field">添加字段</button></div><div data-service-form-fields>${fields.map((field) => renderServiceFormFieldRow(field)).join("")}</div></section>
      <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">保存表单</button></div>
    </form>`, false);
}

function openSlaPolicyModal(policyId = "") {
  const existing = (serviceState().policies || []).find((policy) => String(policy.id) === String(policyId));
  const editing = Boolean(existing);
  openModal(`${modalHeader(editing ? "编辑 SLA 策略" : "新建 SLA 策略", "按工单优先级设置响应和解决时限。")}
    <form data-form="sla-policy" data-id="${escapeHtml(existing?.id || "")}">
      <div class="form-grid">
        ${inputField("策略编码", "code", existing?.code || "", true, "例如：critical_4h")}
        ${inputField("策略名称", "name", existing?.name || "", true, "例如：关键业务 SLA")}
        ${selectField("优先级", "priority", [{ value: "high", label: "高" }, { value: "medium", label: "中" }, { value: "low", label: "低" }], existing?.priority || "medium", true)}
        ${inputField("响应时限（分钟）", "responseMinutes", existing?.responseMinutes || 60, true, "例如：30")}
        ${inputField("解决时限（分钟）", "resolutionMinutes", existing?.resolutionMinutes || 240, true, "例如：240")}
      </div>
      <label class="service-form-check"><input type="checkbox" name="isActive" ${existing?.isActive === false || existing?.isActive === 0 ? "" : "checked"} /> 启用此策略</label>
      <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">保存策略</button></div>
    </form>`, false);
}

async function loadWorkflowOptions() {
  const service = serviceState();
  if (service.workflowUsers.length && service.workflowRoles.length) return;
  const [usersResult, rolesResult] = await Promise.allSettled([
    requestJson(API_USERS_URL),
    requestJson(API_ROLES_URL),
  ]);
  service.workflowUsers =
    usersResult.status === "fulfilled" && Array.isArray(usersResult.value.users)
      ? usersResult.value.users.filter((user) => user.isActive !== false)
      : [];
  service.workflowRoles =
    rolesResult.status === "fulfilled" && Array.isArray(rolesResult.value.roles)
      ? rolesResult.value.roles.filter((role) => role.isActive !== false)
      : [];
}

function workflowStepRow(step = {}) {
  const service = serviceState();
  const approverType = step.approverUserId ? "user" : "role";
  const roleOptions = [{ value: "", label: "选择角色" }].concat(
    (service.workflowRoles || []).map((role) => ({ value: role.code, label: role.name || role.code })),
  );
  const userOptions = [{ value: "", label: "选择用户" }].concat(
    (service.workflowUsers || []).map((user) => ({ value: user.id, label: user.displayName || user.username })),
  );
  return `<section class="workflow-step-row" data-workflow-step>
    <div class="form-grid">
      ${inputField("步骤名称", "stepName", step.name || "", true, "例如：部门负责人审批")}
      ${selectField("审批人类型", "approverType", [{ value: "role", label: "按角色" }, { value: "user", label: "指定用户" }], approverType, true)}
      <div data-workflow-role ${approverType === "user" ? "hidden" : ""}>${selectField("审批角色", "approverRoleCode", roleOptions, step.approverRoleCode || "", true)}</div>
      <div data-workflow-user ${approverType === "role" ? "hidden" : ""}>${selectField("审批用户", "approverUserId", userOptions, step.approverUserId || "", true)}</div>
    </div>
    <div class="service-form-builder-options">
      <label class="service-form-check"><input type="checkbox" name="stepRequired" ${step.required === false || step.required === 0 ? "" : "checked"} /> 必须通过</label>
      <button type="button" class="text-button" data-action="remove-workflow-step">删除步骤</button>
    </div>
  </section>`;
}

function readWorkflowSteps(form) {
  return [...form.querySelectorAll("[data-workflow-step]")].map((row) => {
    const approverType = row.querySelector('[name="approverType"]')?.value || "role";
    return {
      name: row.querySelector('[name="stepName"]')?.value.trim() || "",
      approverRoleCode: approverType === "role" ? row.querySelector('[name="approverRoleCode"]')?.value || "" : "",
      approverUserId: approverType === "user" ? row.querySelector('[name="approverUserId"]')?.value || "" : "",
      required: Boolean(row.querySelector('[name="stepRequired"]')?.checked),
    };
  });
}

function syncWorkflowStepApprover(row) {
  const approverType = row.querySelector('[name="approverType"]')?.value || "role";
  const roleBox = row.querySelector("[data-workflow-role]");
  const userBox = row.querySelector("[data-workflow-user]");
  if (roleBox) roleBox.hidden = approverType !== "role";
  if (userBox) userBox.hidden = approverType !== "user";
}

async function openApprovalWorkflowModal(workflowId = "") {
  try {
    await loadWorkflowOptions();
  } catch (error) {
    showToast(`读取审批人配置失败：${error.message}`, true);
    return;
  }
  const existing = (serviceState().workflows || []).find((workflow) => String(workflow.id) === String(workflowId));
  const steps = existing?.steps?.length ? existing.steps : [{ name: "一级审批", approverRoleCode: "operator", required: true }];
  const editing = Boolean(existing);
  openModal(`${modalHeader(editing ? "编辑审批流程" : "新建审批流程", "一个步骤可以按角色分派，或指定到单个用户。")}
    <form data-form="approval-workflow" data-id="${escapeHtml(existing?.id || "")}">
      <div class="form-grid">
        ${inputField("流程编码", "code", existing?.code || "", true, "例如：change_department_approval")}
        ${inputField("流程名称", "name", existing?.name || "", true, "例如：部门变更审批")}
        ${selectField("业务类型", "recordType", [{ value: "ticket", label: "工单" }, { value: "change", label: "变更管理" }, { value: "problem", label: "问题管理" }], existing?.recordType || "change", true)}
      </div>
      <label class="service-form-check"><input type="checkbox" name="isActive" ${existing?.isActive === false || existing?.isActive === 0 ? "" : "checked"} /> 启用此流程</label>
      <section class="modal-section"><div class="modal-section-title"><h3>审批步骤</h3><span>从上到下依次执行。</span><button type="button" class="secondary-button" data-action="add-workflow-step">添加步骤</button></div><div data-workflow-steps>${steps.map((step) => workflowStepRow(step)).join("")}</div></section>
      <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">保存流程</button></div>
    </form>`, false);
}

function openServiceTransitionModal(recordType, recordId, currentStatus) {
  const transitions = {
    change: { draft: ["submitted", "cancelled"], submitted: ["assessing", "cancelled"], assessing: ["scheduled", "rejected", "cancelled"], approved: ["scheduled", "cancelled"], scheduled: ["implementing", "cancelled"], implementing: ["verified", "cancelled"], verified: ["closed", "implementing"] },
    problem: { new: ["investigating", "cancelled"], investigating: ["known_error", "resolved", "cancelled"], known_error: ["resolved", "cancelled"], resolved: ["closed", "investigating"] },
    knowledge: { draft: ["review", "archived"], review: ["published", "draft", "archived"], published: ["archived", "draft"], archived: ["draft"] },
  }[recordType] || {};
  const options = transitions[currentStatus] || [];
  if (!options.length) return showToast("当前状态没有可执行的流转。", true);
  openModal(`${modalHeader("更新状态", "状态变更会写入历史并触发相关通知。")}
    <form data-form="service-transition" data-record-type="${escapeHtml(recordType)}" data-id="${escapeHtml(recordId)}">
      ${selectField("下一状态", "status", options.map((value) => ({ value, label: serviceStatusLabels[value] || value })), options[0], true)}
      ${recordType === "problem" ? textareaField("根因", "rootCause", "", false, "可选", 3) : ""}
      ${recordType === "problem" ? textareaField("解决方案", "resolution", "", false, "可选", 3) : ""}
      <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">保存状态</button></div>
    </form>`, false);
}

function openApprovalDecisionModal(approvalId) {
  openModal(`${modalHeader("审批", "请确认本步骤是否同意。")}
    <form data-form="service-approval" data-id="${escapeHtml(approvalId)}">
      ${selectField("审批结果", "decision", [{ value: "approved", label: "同意" }, { value: "rejected", label: "拒绝" }], "approved", true)}
      ${textareaField("审批意见", "comment", "", false, "可选", 4)}
      <div class="modal-footer"><button type="button" class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" type="submit">提交审批</button></div>
    </form>`, false);
}

async function handleServiceFormSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    const formId = form.dataset.id || "";
    const existing = (serviceState().forms || []).find((item) => String(item.id) === String(formId));
    const endpoint = formId ? `${API_SERVICE_FORMS_URL}/${encodeURIComponent(formId)}` : API_SERVICE_FORMS_URL;
    await requestJson(endpoint, {
      method: formId ? "PUT" : "POST",
      body: JSON.stringify({
        code: data.code || existing?.code,
        name: data.name,
        recordType: data.recordType || existing?.recordType,
        description: data.description,
        fields: readServiceFormFields(form),
      }),
    });
    closeModal();
    await loadServiceManagement();
    render();
    showToast("服务表单已保存");
  } catch (error) {
    showToast(`保存服务表单失败：${error.message}`, true);
  }
}

async function handleSlaPolicySubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const policyId = form.dataset.id || "";
  try {
    await requestJson(policyId ? `${API_SLA_POLICIES_URL}/${encodeURIComponent(policyId)}` : API_SLA_POLICIES_URL, {
      method: policyId ? "PUT" : "POST",
      body: JSON.stringify({
        code: data.code,
        name: data.name,
        priority: data.priority,
        responseMinutes: Number(data.responseMinutes),
        resolutionMinutes: Number(data.resolutionMinutes),
        isActive: data.isActive === "on",
      }),
    });
    closeModal();
    await loadServiceManagement();
    render();
    showToast("SLA 策略已保存");
  } catch (error) {
    showToast(`保存 SLA 策略失败：${error.message}`, true);
  }
}

async function handleApprovalWorkflowSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const workflowId = form.dataset.id || "";
  const existing = (serviceState().workflows || []).find((workflow) => String(workflow.id) === String(workflowId));
  try {
    await requestJson(workflowId ? `${API_WORKFLOWS_URL}/${encodeURIComponent(workflowId)}` : API_WORKFLOWS_URL, {
      method: workflowId ? "PUT" : "POST",
      body: JSON.stringify({
        code: data.code || existing?.code,
        name: data.name,
        recordType: data.recordType || existing?.recordType,
        isActive: data.isActive === "on",
        steps: readWorkflowSteps(form),
      }),
    });
    closeModal();
    await loadServiceManagement();
    render();
    showToast("审批流程已保存");
  } catch (error) {
    showToast(`保存审批流程失败：${error.message}`, true);
  }
}

async function handleServiceChangeSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  data.customFields = collectServiceCustomFields(form, "change", data.formCode);
  try {
    await requestJson(API_CHANGES_URL, { method: "POST", body: JSON.stringify(data) });
    closeModal();
    await loadServiceManagement();
    render();
    showToast("变更已创建");
  } catch (error) {
    showToast(`创建变更失败：${error.message}`, true);
  }
}

async function handleServiceProblemSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  data.customFields = collectServiceCustomFields(form, "problem", data.formCode);
  try {
    await requestJson(API_PROBLEMS_URL, { method: "POST", body: JSON.stringify(data) });
    closeModal();
    await loadServiceManagement();
    render();
    showToast("问题已创建");
  } catch (error) {
    showToast(`创建问题失败：${error.message}`, true);
  }
}

async function handleServiceKnowledgeSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    await requestJson(API_KNOWLEDGE_URL, { method: "POST", body: JSON.stringify(data) });
    closeModal();
    await loadServiceManagement();
    render();
    showToast("知识文章已创建");
  } catch (error) {
    showToast(`创建知识文章失败：${error.message}`, true);
  }
}

async function handleServiceTransitionSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const type = form.dataset.recordType;
  const endpoint = type === "change" ? API_CHANGES_URL : type === "problem" ? API_PROBLEMS_URL : API_KNOWLEDGE_URL;
  try {
    await requestJson(`${endpoint}/${encodeURIComponent(form.dataset.id)}/transitions`, { method: "POST", body: JSON.stringify(data) });
    closeModal();
    await loadServiceManagement();
    render();
    showToast("状态已更新");
  } catch (error) {
    showToast(`状态更新失败：${error.message}`, true);
  }
}

async function handleServiceApprovalSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    await requestJson(`${API_APPROVALS_URL}/${encodeURIComponent(form.dataset.id)}/decision`, { method: "POST", body: JSON.stringify(data) });
    closeModal();
    await loadServiceManagement();
    render();
    showToast("审批已提交");
  } catch (error) {
    showToast(`审批提交失败：${error.message}`, true);
  }
}

document.addEventListener("click", (event) => {
  const item = event.target.closest("[data-action]");
  if (!item) return;
  const action = item.dataset.action;
  if (action === "service-view") {
    const service = serviceState();
    const view = item.dataset.view || "tickets";
    if (!canViewServiceView(view)) {
      showToast("当前账号没有查看该服务模块的权限。", true);
      return;
    }
    service.view = view;
    loadServiceManagement()
      .then(() => renderIfCurrentPage("serviceManagement"))
      .catch((error) => showToast(`加载服务管理失败：${error.message}`, true));
    return;
  }
  if (action === "refresh-service") {
    loadServiceManagement()
      .then(() => renderIfCurrentPage("serviceManagement"))
      .catch((error) => showToast(`刷新服务管理失败：${error.message}`, true));
    return;
  }
  if (action === "open-service-change") return openServiceChangeModal();
  if (action === "open-service-problem") return openServiceProblemModal();
  if (action === "open-service-knowledge") return openServiceKnowledgeModal();
  if (action === "open-form-designer") return openFormDesigner(item.dataset.id || "");
  if (action === "open-service-form") return openServiceFormModal(item.dataset.id || "");
  if (action === "designer-back") {
    state.page = "serviceManagement";
    serviceState().view = "forms";
    render();
    return;
  }
  if (action === "designer-panel") {
    formDesignerState.activePanel = item.dataset.panel || "form";
    render();
    return;
  }
  if (action === "designer-add-field") {
    const field = designerNewField(item.dataset.type || "text");
    designerForm().fields.push(field);
    formDesignerState.selectedFieldKey = field.key;
    formDesignerState.dirty = true;
    render();
    return;
  }
  if (action === "designer-delete-field") {
    const key = item.dataset.key || "";
    const form = designerForm();
    form.fields = form.fields.filter((field) => designerFieldKey(field) !== key);
    if (formDesignerState.selectedFieldKey === key) formDesignerState.selectedFieldKey = "";
    formDesignerState.dirty = true;
    render();
    return;
  }
  if (action === "designer-save") {
    saveFormDesigner();
    return;
  }
  if (action === "designer-add-workflow-step") {
    const steps = designerWorkflowSteps();
    const nodeType = item.dataset.nodeType || "approval";
    const index = steps.length + 1;
    steps.push({
      nodeType,
      name: nodeType === "handler" ? `经办节点 ${index}` : nodeType === "cc" ? `抄送节点 ${index}` : `审批节点 ${index}`,
      approverType: "role",
      approverRoleCode: serviceState().workflowRoles?.[0]?.code || "",
      approverUserId: "",
      required: nodeType !== "cc",
      notify: true,
    });
    formDesignerState.selectedWorkflowStepIndex = steps.length - 1;
    formDesignerState.dirty = true;
    render();
    return;
  }
  if (action === "designer-delete-workflow-step") {
    const index = Number(item.dataset.index || -1);
    const steps = designerWorkflowSteps();
    if (index >= 0 && index < steps.length) steps.splice(index, 1);
    formDesignerState.selectedWorkflowStepIndex = Math.min(
      formDesignerState.selectedWorkflowStepIndex,
      steps.length - 1,
    );
    formDesignerState.dirty = true;
    render();
    return;
  }
  if (action === "designer-add-permission") {
    const type = document.querySelector("[data-designer-add-subject-type]")?.value || "role";
    const id = document.querySelector("[data-designer-add-subject-id]")?.value || "";
    if (!id) return showToast("请选择权限对象。", true);
    formDesignerState.permissions.push({
      subjectType: type,
      subjectId: id,
      canView: true,
      canSubmit: true,
      canUpdate: false,
      canDelete: false,
      canApprove: false,
      canExport: false,
      dataScope: "all",
    });
    formDesignerState.dirty = true;
    render();
    return;
  }
  if (action === "designer-remove-permission") {
    formDesignerState.permissions.splice(Number(item.dataset.index || -1), 1);
    formDesignerState.dirty = true;
    render();
    return;
  }
  if (action === "add-service-form-field") {
    const container = item.closest("form")?.querySelector("[data-service-form-fields]");
    if (container) container.insertAdjacentHTML("beforeend", renderServiceFormFieldRow({ type: "text" }));
    return;
  }
  if (action === "remove-service-form-field") {
    item.closest("[data-service-form-field]")?.remove();
    return;
  }
  if (action === "open-sla-policy") return openSlaPolicyModal(item.dataset.id || "");
  if (action === "open-approval-workflow") return openApprovalWorkflowModal(item.dataset.id || "");
  if (action === "add-workflow-step") {
    const container = item.closest("form")?.querySelector("[data-workflow-steps]");
    if (container) container.insertAdjacentHTML("beforeend", workflowStepRow({ approverRoleCode: "operator", required: true }));
    return;
  }
  if (action === "remove-workflow-step") {
    item.closest("[data-workflow-step]")?.remove();
    return;
  }
  if (action === "open-service-transition") return openServiceTransitionModal(item.dataset.recordType, item.dataset.id, item.dataset.status);
  if (action === "open-approval-decision") return openApprovalDecisionModal(item.dataset.id);
  if (action === "read-notification") {
    requestJson(`${API_NOTIFICATIONS_URL}/${encodeURIComponent(item.dataset.id)}/read`, { method: "POST", body: "{}" })
      .then(() => loadServiceManagement())
      .then(() => renderIfCurrentPage("serviceManagement"))
      .catch((error) => showToast(`通知更新失败：${error.message}`, true));
  }
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (target.matches("[data-designer-property]")) {
    designerSyncFieldFromPanel(target);
    render();
    return;
  }
  if (target.matches("[data-designer-form-property]")) {
    const form = designerForm();
    const property = target.dataset.designerFormProperty;
    if (property === "allowDraft") form.settings.allowDraft = Boolean(target.checked);
    else if (property === "formCode") form.code = target.value;
    else if (property === "formName") form.name = target.value;
    else if (property === "submitMessage") form.settings.submitMessage = target.value;
    else form[property] = target.value;
    formDesignerState.dirty = true;
    render();
    return;
  }
  if (target.matches("[data-designer-workflow-property]")) {
    const index = Number(target.dataset.index || -1);
    const step = designerWorkflowSteps()[index];
    if (!step) return;
    const property = target.dataset.designerWorkflowProperty;
    if (property === "required" || property === "notify") step[property] = Boolean(target.checked);
    else if (property === "approverType") {
      step.approverType = target.value;
      if (target.value === "role") step.approverUserId = "";
      else step.approverRoleCode = "";
    } else {
      step[property] = target.value;
    }
    formDesignerState.dirty = true;
    render();
    return;
  }
  if (target.matches("[data-designer-permission]")) {
    const row = target.closest("[data-permission-index]");
    const item = formDesignerState.permissions[Number(row?.dataset.permissionIndex || -1)];
    if (!item) return;
    const key = target.dataset.designerPermission;
    if (key === "subjectType") {
      item.subjectType = target.value;
      const subjects = target.value === "role" ? settingsState.accessControl?.roles || [] : settingsState.users || [];
      item.subjectId = String(subjects[0]?.id || "");
    } else if (key === "subjectId" || key === "dataScope") item[key] = target.value;
    else item[`can${key.charAt(0).toUpperCase()}${key.slice(1)}`] = Boolean(target.checked);
    formDesignerState.dirty = true;
    render();
    return;
  }
  if (target.matches("[data-designer-add-subject-type]")) {
    const targetSelect = document.querySelector("[data-designer-add-subject-id]");
    const subjects = target.value === "role" ? settingsState.accessControl?.roles || [] : settingsState.users || [];
    if (targetSelect) {
      targetSelect.innerHTML = subjects.map((subject) => `<option value="${escapeHtml(subject.id)}">${escapeHtml(subject.name || subject.displayName || subject.username || subject.code)}</option>`).join("");
    }
    return;
  }
  const form = target.closest("form[data-form]");
  if (!form) return;
  if ((form.dataset.form === "service-change" || form.dataset.form === "service-problem") && target.name === "formCode") {
    const recordType = form.dataset.form === "service-change" ? "change" : "problem";
    serviceRecordDraft(recordType).selectedCode = target.value;
    const container = form.querySelector(`[data-service-custom-fields="${recordType}"]`);
    if (container) container.innerHTML = renderServiceRecordCustomFields(recordType, target.value);
  }
  if (form.dataset.form === "approval-workflow" && target.name === "approverType") {
    syncWorkflowStepApprover(target.closest("[data-workflow-step]"));
  }
});

document.addEventListener("click", (event) => {
  const field = event.target.closest("[data-designer-field]");
  if (field) {
    formDesignerState.selectedFieldKey = field.dataset.designerField || "";
    render();
    return;
  }
  const workflowStep = event.target.closest("[data-designer-workflow-step]");
  if (workflowStep) {
    formDesignerState.selectedWorkflowStepIndex = Number(workflowStep.dataset.designerWorkflowStep || -1);
    render();
  }
});

document.addEventListener("dragstart", (event) => {
  const palette = event.target.closest("[data-action='designer-add-field']");
  const field = event.target.closest("[data-designer-field]");
  if (palette) event.dataTransfer?.setData("application/x-form-field-type", palette.dataset.type || "text");
  if (field) event.dataTransfer?.setData("application/x-form-field-key", field.dataset.designerField || "");
});

document.addEventListener("dragover", (event) => {
  if (event.target.closest("[data-designer-dropzone]")) event.preventDefault();
});

document.addEventListener("drop", (event) => {
  const dropzone = event.target.closest("[data-designer-dropzone]");
  if (!dropzone) return;
  event.preventDefault();
  const type = event.dataTransfer?.getData("application/x-form-field-type");
  const draggedKey = event.dataTransfer?.getData("application/x-form-field-key");
  const form = designerForm();
  if (type) {
    const field = designerNewField(type);
    form.fields.push(field);
    formDesignerState.selectedFieldKey = field.key;
  } else if (draggedKey) {
    const sourceIndex = form.fields.findIndex((field) => designerFieldKey(field) === draggedKey);
    const targetCard = event.target.closest("[data-designer-field]");
    const targetIndex = Number(targetCard?.dataset.index || form.fields.length - 1);
    if (sourceIndex >= 0) {
      const [moved] = form.fields.splice(sourceIndex, 1);
      form.fields.splice(Math.max(0, targetIndex), 0, moved);
    }
  }
  formDesignerState.dirty = true;
  render();
});

// ---------------------------------------------------------------- 机房巡检

const API_INSPECTION_SITES = "/api/inspection/sites";
const API_INSPECTION_RACKS = "/api/inspection/racks";
const API_INSPECTION_TEMPLATES = "/api/inspection/templates";
const API_INSPECTION_TASKS = "/api/inspection/tasks";

const inspectionSiteTypeLabels = { server_room: "机房", weak_room: "弱电间", both: "通用" };
const inspectionStatusLabels = { running: "进行中", submitted: "已提交", void: "已作废" };
const inspectionResultLabels = { pending: "未检查", ok: "正常", fail: "异常", na: "不适用" };
const inspectionValueTypeLabels = { ok_fail: "正常/异常", number: "数值", text: "文本", select: "选项" };

let inspectionState = {
  view: "tasks",
  loaded: false,
  loading: false,
  sites: [],
  racks: [],
  templates: [],
  tasks: [],
  task: null,
  statusFilter: "",
};

function inspectionScopeName(record) {
  const parts = [record.siteName || "", record.rackName || ""].filter(Boolean);
  return parts.length ? parts.join(" / ") : "—";
}

function inspectionEmptyState(message) {
  return `<div class="empty-state">${escapeHtml(message)}</div>`;
}

async function loadInspectionData({ force = false } = {}) {
  if (inspectionState.loading) return;
  if (inspectionState.loaded && !force) return;
  inspectionState.loading = true;
  try {
    const statusQuery = inspectionState.statusFilter
      ? `?status=${encodeURIComponent(inspectionState.statusFilter)}`
      : "";
    const [sites, racks, templates, tasks] = await Promise.all([
      requestJson(API_INSPECTION_SITES).catch(() => ({ sites: [] })),
      requestJson(API_INSPECTION_RACKS).catch(() => ({ racks: [] })),
      requestJson(API_INSPECTION_TEMPLATES).catch(() => ({ templates: [] })),
      requestJson(`${API_INSPECTION_TASKS}${statusQuery}`).catch(() => ({ tasks: [] })),
    ]);
    inspectionState.sites = Array.isArray(sites.sites) ? sites.sites : [];
    inspectionState.racks = Array.isArray(racks.racks) ? racks.racks : [];
    inspectionState.templates = Array.isArray(templates.templates) ? templates.templates : [];
    inspectionState.tasks = Array.isArray(tasks.tasks) ? tasks.tasks : [];
    inspectionState.loaded = true;
  } finally {
    inspectionState.loading = false;
  }
}

async function refreshInspectionTasks() {
  const statusQuery = inspectionState.statusFilter
    ? `?status=${encodeURIComponent(inspectionState.statusFilter)}`
    : "";
  const payload = await requestJson(`${API_INSPECTION_TASKS}${statusQuery}`);
  inspectionState.tasks = Array.isArray(payload.tasks) ? payload.tasks : [];
}

async function loadInspectionTask(taskId) {
  const payload = await requestJson(`${API_INSPECTION_TASKS}/${encodeURIComponent(taskId)}`);
  inspectionState.task = payload.task || null;
  if (inspectionState.task) {
    const index = inspectionState.tasks.findIndex((task) => String(task.id) === String(taskId));
    const summary = {
      status: inspectionState.task.status,
      itemTotal: inspectionState.task.itemTotal,
      itemOk: inspectionState.task.itemOk,
      itemFail: inspectionState.task.itemFail,
      itemNa: inspectionState.task.itemNa,
      submittedAt: inspectionState.task.submittedAt,
    };
    if (index >= 0) inspectionState.tasks[index] = { ...inspectionState.tasks[index], ...summary };
  }
  render();
}

function inspectionTemplatesForScope(scopeKind) {
  return (inspectionState.templates || []).filter((template) => {
    if (template.isActive === 0 || template.isActive === false) return false;
    if (!scopeKind) return true;
    return template.siteType === "both" || template.siteType === scopeKind;
  });
}

function openInspectionStartModal(preselected = {}) {
  if (!hasPermission("inspection_management", "create")) {
    showToast("当前账号没有发起巡检的权限。", true);
    return;
  }
  const templates = inspectionTemplatesForScope("site");
  const sites = inspectionState.sites || [];
  const racks = inspectionState.racks || [];
  if (!templates.length) {
    showToast("还没有可用的巡检模板，请先在巡检模板中创建。", true);
    return;
  }
  if (!sites.length && !racks.length) {
    showToast("还没有机房或机柜，请先在“机房与机柜”中维护。", true);
    return;
  }
  const inspector = (authState.user && (authState.user.displayName || authState.user.username)) || "当前账号";
  const selectedRack = racks.find((rack) => String(rack.code || "") === String(preselected.rackCode || ""));
  const initialScopeKind = selectedRack ? "rack" : "site";
  const templateOptions = inspectionTemplatesForScope(initialScopeKind)
    .map(
      (template) =>
        `<option value="${escapeHtml(template.id)}">${escapeHtml(template.name)}（${escapeHtml(
          inspectionSiteTypeLabels[template.siteType] || "通用",
        )}）</option>`,
    )
    .join("");
  const siteOptions = sites
    .map(
      (site) =>
        `<option value="${escapeHtml(site.id)}">${escapeHtml(
          `${inspectionSiteTypeLabels[site.siteType] || "机房"} · ${site.name}`,
        )}</option>`,
    )
    .join("");
  const rackOptions = racks
    .map(
      (rack) =>
        `<option value="${escapeHtml(rack.id)}"${
          selectedRack && String(selectedRack.id) === String(rack.id) ? " selected" : ""
        }>${escapeHtml(`${rack.siteName || ""} / ${rack.name}`)}</option>`,
    )
    .join("");
  openModal(
    `${modalHeader("开始巡检", "执行人默认为开始巡检的账号；开始后按模板输出全部巡检事项。")}
      <form data-form="inspection-start">
        <div class="form-grid">
          ${selectField(
            "巡检对象类型",
            "scopeKind",
            initialScopeKind,
            [
              { value: "site", label: "机房 / 弱电间" },
              { value: "rack", label: "单个机柜" },
            ],
            true,
          )}
          <div class="form-field" data-inspection-scope="site"${initialScopeKind === "site" ? "" : " hidden"}>
            <label for="inspectionSiteId">机房 / 弱电间 *</label>
            <select id="inspectionSiteId" name="siteId">${siteOptions}</select>
          </div>
          <div class="form-field" data-inspection-scope="rack"${initialScopeKind === "rack" ? "" : " hidden"}>
            <label for="inspectionRackId">机柜 *</label>
            <select id="inspectionRackId" name="rackId">${rackOptions}</select>
          </div>
          ${selectField("巡检模板", "templateId", "", templateOptions, true)}
          ${inputField("执行人", "inspectorName", inspector, false, "", "text", "", "readonly")}
        </div>
        ${inputField("备注", "remarks", "", false, "可填写本次巡检的说明")}
        <div class="modal-footer">
          <button type="button" class="secondary-button" data-action="close-modal">取消</button>
          <button type="submit" class="primary-button">开始巡检</button>
        </div>
      </form>`,
    true,
  );
}

async function handleInspectionStartSubmit(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const scopeKind = String(data.scopeKind || "site");
  const payload = {
    templateId: String(data.templateId || ""),
    scopeKind,
    remarks: String(data.remarks || "").slice(0, 200),
  };
  if (scopeKind === "site") {
    payload.siteId = String(data.siteId || "");
    if (!payload.siteId) return showToast("请选择要巡检的机房或弱电间。", true);
  } else {
    payload.rackId = String(data.rackId || "");
    if (!payload.rackId) return showToast("请选择要巡检的机柜。", true);
  }
  if (!payload.templateId) return showToast("请选择巡检模板。", true);
  try {
    const result = await runCommand(API_INSPECTION_TASKS, payload, "inspection-start");
    closeModal();
    showToast(`巡检已开始：${result.taskNo || ""}，共 ${result.itemTotal || 0} 项。`);
    inspectionState.view = "tasks";
    await refreshInspectionTasks();
    await loadInspectionTask(result.id);
  } catch (error) {
    showToast(`开始巡检失败：${error.message}`, true);
  }
}

async function submitInspectionCheck(taskId, itemId, result) {
  const valueInput = document.querySelector(`[data-inspection-value="${itemId}"]`);
  const notesInput = document.querySelector(`[data-inspection-notes="${itemId}"]`);
  const valueText = valueInput ? valueInput.value.trim() : "";
  const notes = notesInput ? notesInput.value.trim() : "";
  if (result === "fail" && !notes) {
    showToast("异常项必须填写说明。", true);
    if (notesInput) notesInput.focus();
    return;
  }
  try {
    await runCommand(
      `${API_INSPECTION_TASKS}/${encodeURIComponent(taskId)}/items/${encodeURIComponent(itemId)}/check`,
      { result, valueText, notes },
      "inspection-check",
    );
    await loadInspectionTask(taskId);
  } catch (error) {
    showToast(`保存巡检结果失败：${error.message}`, true);
  }
}

async function submitInspectionTask() {
  const task = inspectionState.task;
  if (!task) return;
  const summaryInput = document.querySelector('[data-inspection-field="abnormalSummary"]');
  const payload = { abnormalSummary: summaryInput ? summaryInput.value.trim() : "" };
  try {
    const result = await runCommand(
      `${API_INSPECTION_TASKS}/${encodeURIComponent(task.id)}/submit`,
      payload,
      "inspection-submit",
    );
    showToast(
      result.itemFail
        ? `巡检已提交：共 ${result.itemTotal} 项，异常 ${result.itemFail} 项。`
        : `巡检已提交：共 ${result.itemTotal} 项，全部正常。`,
    );
    await refreshInspectionTasks();
    await loadInspectionTask(task.id);
  } catch (error) {
    showToast(`提交巡检失败：${error.message}`, true);
  }
}

async function voidInspectionTask(taskId) {
  const reason = window.prompt("请填写作废原因（会写入操作日志）：", "");
  if (reason === null) return;
  if (!String(reason).trim()) return showToast("作废巡检任务必须填写原因。", true);
  try {
    await runCommand(
      `${API_INSPECTION_TASKS}/${encodeURIComponent(taskId)}/void`,
      { reason: String(reason).trim().slice(0, 200) },
      "inspection-void",
    );
    showToast("巡检任务已作废。");
    inspectionState.task = null;
    await refreshInspectionTasks();
    render();
  } catch (error) {
    showToast(`作废巡检任务失败：${error.message}`, true);
  }
}

async function saveInspectionSite(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const payload = {
    code: String(data.code || "").trim(),
    name: String(data.name || "").trim(),
    siteType: String(data.siteType || "server_room"),
    location: String(data.location || "").trim(),
    remarks: String(data.remarks || "").trim(),
  };
  if (!payload.code || !payload.name) return showToast("机房/弱电间编码和名称不能为空。", true);
  const siteId = form.dataset.id || "";
  try {
    if (siteId) {
      await requestJson(`${API_INSPECTION_SITES}/${encodeURIComponent(siteId)}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    } else {
      await requestJson(API_INSPECTION_SITES, { method: "POST", body: JSON.stringify(payload) });
    }
    closeModal();
    showToast("机房/弱电间已保存。");
    await loadInspectionData({ force: true });
    render();
  } catch (error) {
    showToast(`保存机房/弱电间失败：${error.message}`, true);
  }
}

async function saveInspectionRack(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const payload = {
    code: String(data.code || "").trim(),
    name: String(data.name || "").trim(),
    siteId: String(data.siteId || ""),
    heightU: String(data.heightU || "42").trim(),
    remarks: String(data.remarks || "").trim(),
  };
  if (!payload.code || !payload.name || !payload.siteId) {
    return showToast("机柜编码、名称和所属机房不能为空。", true);
  }
  const rackId = form.dataset.id || "";
  try {
    if (rackId) {
      await requestJson(`${API_INSPECTION_RACKS}/${encodeURIComponent(rackId)}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    } else {
      await requestJson(API_INSPECTION_RACKS, { method: "POST", body: JSON.stringify(payload) });
    }
    closeModal();
    showToast("机柜已保存。");
    await loadInspectionData({ force: true });
    render();
  } catch (error) {
    showToast(`保存机柜失败：${error.message}`, true);
  }
}

function inspectionTemplateItemRow(item = {}) {
  const valueType = item.valueType || "ok_fail";
  const options = Object.entries(inspectionValueTypeLabels)
    .map(
      ([value, label]) =>
        `<option value="${value}"${value === valueType ? " selected" : ""}>${escapeHtml(label)}</option>`,
    )
    .join("");
  return `<tr data-inspection-template-item>
    <td><input type="text" data-item-field="category" value="${escapeHtml(item.category || "")}" placeholder="类别" /></td>
    <td><input type="text" data-item-field="title" value="${escapeHtml(item.title || "")}" placeholder="巡检事项" /></td>
    <td><input type="text" data-item-field="checkMethod" value="${escapeHtml(
      item.checkMethod || "",
    )}" placeholder="检查方法" /></td>
    <td><select data-item-field="valueType">${options}</select></td>
    <td><input type="text" data-item-field="unit" value="${escapeHtml(item.unit || "")}" placeholder="单位" /></td>
    <td><input type="text" data-item-field="normalRange" value="${escapeHtml(
      item.normalRange || "",
    )}" placeholder="正常范围" /></td>
    <td><input type="checkbox" data-item-field="isRequired"${
      item.isRequired === 0 || item.isRequired === false ? "" : " checked"
    } /></td>
    <td><button type="button" class="text-button" data-action="inspection-remove-item">删除</button></td>
  </tr>`;
}

async function openInspectionTemplateModal(templateId = "") {
  if (!hasPermission("inspection_management", "create") && !hasPermission("inspection_management", "update")) {
    showToast("当前账号没有维护巡检模板的权限。", true);
    return;
  }
  let template = { code: "", name: "", siteType: "both", description: "", items: [] };
  if (templateId) {
    try {
      const payload = await requestJson(`${API_INSPECTION_TEMPLATES}/${encodeURIComponent(templateId)}`);
      template = payload.template || template;
    } catch (error) {
      showToast(`加载巡检模板失败：${error.message}`, true);
      return;
    }
  }
  const items = Array.isArray(template.items) && template.items.length ? template.items : [{}];
  openModal(
    `${modalHeader(
      templateId ? "编辑巡检模板" : "新增巡检模板",
      "开始巡检时会把事项快照进当次巡检表，之后再改模板不影响历史记录。",
    )}
      <form data-form="inspection-template" data-id="${escapeHtml(templateId)}">
        <div class="form-grid">
          ${inputField("模板编码", "code", template.code || "", true, "例如 XJ-SERVER-ROOM")}
          ${inputField("模板名称", "name", template.name || "", true, "例如 机房巡检")}
          ${selectField("适用对象", "siteType", template.siteType || "both", [
            { value: "server_room", label: "机房" },
            { value: "weak_room", label: "弱电间" },
            { value: "both", label: "通用" },
          ], true)}
          ${inputField("说明", "description", template.description || "", false, "可选")}
        </div>
        <div class="section-heading">
          <div><h3>巡检事项</h3><span>逐项检查时按这里的顺序输出</span></div>
          <button type="button" class="secondary-button" data-action="inspection-add-item">＋ 添加事项</button>
        </div>
        <div class="table-wrap inspection-template-items">
          <table>
            <thead><tr><th>类别</th><th>巡检事项</th><th>检查方法</th><th>取值类型</th><th>单位</th><th>正常范围</th><th>必填</th><th></th></tr></thead>
            <tbody data-inspection-template-items>${items.map(inspectionTemplateItemRow).join("")}</tbody>
          </table>
        </div>
        <div class="modal-footer">
          <button type="button" class="secondary-button" data-action="close-modal">取消</button>
          <button type="submit" class="primary-button">保存模板</button>
        </div>
      </form>`,
    true,
  );
}

async function saveInspectionTemplate(form) {
  const rows = [...form.querySelectorAll("[data-inspection-template-item]")];
  const items = rows
    .map((row) => {
      const read = (field) => {
        const element = row.querySelector(`[data-item-field="${field}"]`);
        return element ? element.value.trim() : "";
      };
      const checked = (field) => {
        const element = row.querySelector(`[data-item-field="${field}"]`);
        return element ? element.checked : false;
      };
      return {
        category: read("category"),
        title: read("title"),
        checkMethod: read("checkMethod"),
        valueType: read("valueType") || "ok_fail",
        unit: read("unit"),
        normalRange: read("normalRange"),
        isRequired: checked("isRequired"),
      };
    })
    .filter((item) => item.title);
  if (!items.length) return showToast("至少需要一项巡检事项。", true);
  const data = Object.fromEntries(new FormData(form).entries());
  const payload = {
    code: String(data.code || "").trim(),
    name: String(data.name || "").trim(),
    siteType: String(data.siteType || "both"),
    description: String(data.description || "").trim(),
    items,
  };
  if (!payload.code || !payload.name) return showToast("模板编码和名称不能为空。", true);
  const templateId = form.dataset.id || "";
  try {
    if (templateId) {
      await requestJson(`${API_INSPECTION_TEMPLATES}/${encodeURIComponent(templateId)}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    } else {
      await requestJson(API_INSPECTION_TEMPLATES, { method: "POST", body: JSON.stringify(payload) });
    }
    closeModal();
    showToast("巡检模板已保存。");
    await loadInspectionData({ force: true });
    render();
  } catch (error) {
    showToast(`保存巡检模板失败：${error.message}`, true);
  }
}

function openInspectionSiteModal(siteId = "") {
  const site = (inspectionState.sites || []).find((item) => String(item.id) === String(siteId)) || {};
  openModal(
    `${modalHeader(
      siteId ? "编辑机房/弱电间" : "新增机房/弱电间",
      "巡检对象只包含机房、弱电间和其下的机柜。",
    )}
      <form data-form="inspection-site" data-id="${escapeHtml(siteId)}">
        <div class="form-grid">
          ${inputField("编码", "code", site.code || "", true, "例如 SR-01")}
          ${inputField("名称", "name", site.name || "", true, "例如 主机房")}
          ${selectField("类型", "siteType", site.siteType || "server_room", [
            { value: "server_room", label: "机房" },
            { value: "weak_room", label: "弱电间" },
          ], true)}
          ${inputField("位置描述", "location", site.location || "", false, "例如 1 号楼 2 层")}
        </div>
        ${inputField("备注", "remarks", site.remarks || "", false, "可选")}
        <div class="modal-footer">
          <button type="button" class="secondary-button" data-action="close-modal">取消</button>
          <button type="submit" class="primary-button">保存</button>
        </div>
      </form>`,
  );
}

function openInspectionRackModal(rackId = "") {
  const rack = (inspectionState.racks || []).find((item) => String(item.id) === String(rackId)) || {};
  const siteOptions = (inspectionState.sites || []).map((site) => ({
    value: site.id,
    label: `${inspectionSiteTypeLabels[site.siteType] || "机房"} · ${site.name}`,
  }));
  openModal(
    `${modalHeader(rackId ? "编辑机柜" : "新增机柜", "机柜可以单独发起巡检，也可以在巡检整个机房时一并覆盖。")}
      <form data-form="inspection-rack" data-id="${escapeHtml(rackId)}">
        <div class="form-grid">
          ${inputField("机柜编码", "code", rack.code || "", true, "例如 RACK-A01")}
          ${inputField("机柜名称", "name", rack.name || "", true, "例如 A 列 1 号柜")}
          ${selectField("所属机房/弱电间", "siteId", rack.siteId || "", siteOptions, true)}
          ${inputField("高度（U）", "heightU", String(rack.heightU || 42), true, "默认 42", "number", "1")}
        </div>
        ${inputField("备注", "remarks", rack.remarks || "", false, "可选")}
        <div class="modal-footer">
          <button type="button" class="secondary-button" data-action="close-modal">取消</button>
          <button type="submit" class="primary-button">保存</button>
        </div>
      </form>`,
  );
}

function inspectionTaskTable() {
  const tasks = inspectionState.tasks || [];
  if (!tasks.length) return inspectionEmptyState("暂无巡检任务，点击“开始巡检”发起一次。");
  return `<div class="table-wrap"><table>
    <thead><tr><th>任务号</th><th>巡检对象</th><th>模板</th><th>执行人</th><th>开始时间</th><th>进度</th><th>状态</th><th>操作</th></tr></thead>
    <tbody>${tasks
      .map((task) => {
        const progress = `${task.itemTotal || 0} 项 / 正常 ${task.itemOk || 0} / 异常 ${
          task.itemFail || 0
        } / 不适用 ${task.itemNa || 0}`;
        const actions = [
          `<button class="text-button" data-action="inspection-open-task" data-id="${escapeHtml(
            task.id,
          )}">${task.status === "running" ? "继续巡检" : "查看巡检表"}</button>`,
        ];
        if (task.status === "running" && hasPermission("inspection_management", "delete")) {
          actions.push(
            `<button class="text-button" data-action="inspection-void" data-id="${escapeHtml(task.id)}">作废</button>`,
          );
        }
        return `<tr>
          <td class="strong-cell">${escapeHtml(task.taskNo || "")}</td>
          <td>${escapeHtml(inspectionScopeName(task))}</td>
          <td>${escapeHtml(task.templateName || "")}</td>
          <td>${escapeHtml(task.inspectorName || "")}</td>
          <td>${escapeHtml(task.startedAt ? formatDateTime(task.startedAt) : "")}</td>
          <td>${escapeHtml(progress)}</td>
          <td><span class="status-chip">${escapeHtml(inspectionStatusLabels[task.status] || task.status)}</span></td>
          <td>${actions.join(" ")}</td>
        </tr>`;
      })
      .join("")}</tbody>
  </table></div>`;
}

function renderInspectionTasksPanel() {
  const canCreate = hasPermission("inspection_management", "create");
  const statusOptions = [
    ["", "全部状态"],
    ["running", "进行中"],
    ["submitted", "已提交"],
    ["void", "已作废"],
  ]
    .map(
      ([value, label]) =>
        `<option value="${value}"${value === inspectionState.statusFilter ? " selected" : ""}>${escapeHtml(
          label,
        )}</option>`,
    )
    .join("");
  return `<section class="data-panel">
    <div class="section-heading"><div><h2>巡检任务</h2><span>开始巡检后按模板逐项检查，提交即生成完整巡检表</span></div>
      <div class="toolbar-actions">
        <select class="filter-select" data-action="inspection-filter-status">${statusOptions}</select>
        <button class="secondary-button" data-action="inspection-refresh">刷新</button>
        ${canCreate ? '<button class="primary-button" data-action="inspection-start">开始巡检</button>' : ""}
      </div>
    </div>
    ${inspectionTaskTable()}
  </section>`;
}

function renderInspectionTemplatesPanel() {
  const templates = inspectionState.templates || [];
  const canEdit = hasPermission("inspection_management", "update") || hasPermission("inspection_management", "create");
  return `<section class="data-panel">
    <div class="section-heading"><div><h2>巡检模板</h2><span>巡检事项字典，修改后只影响之后开始的巡检</span></div>
      ${canEdit ? '<div class="toolbar-actions"><button class="primary-button" data-action="inspection-new-template">＋ 新增模板</button></div>' : ""}
    </div>
    ${
      templates.length
        ? `<div class="table-wrap"><table>
            <thead><tr><th>模板编码</th><th>模板名称</th><th>适用对象</th><th>事项数</th><th>状态</th><th>说明</th><th>操作</th></tr></thead>
            <tbody>${templates
              .map(
                (template) => `<tr>
                  <td class="strong-cell">${escapeHtml(template.code || "")}</td>
                  <td>${escapeHtml(template.name || "")}</td>
                  <td>${escapeHtml(inspectionSiteTypeLabels[template.siteType] || "通用")}</td>
                  <td>${escapeHtml(String(template.itemCount || 0))}</td>
                  <td>${escapeHtml(template.isActive ? "启用" : "停用")}</td>
                  <td>${escapeHtml(template.description || "—")}</td>
                  <td>${
                    canEdit
                      ? `<button class="text-button" data-action="inspection-edit-template" data-id="${escapeHtml(
                          template.id,
                        )}">编辑</button>`
                      : "—"
                  }</td>
                </tr>`,
              )
              .join("")}</tbody>
          </table></div>`
        : inspectionEmptyState("暂无巡检模板。")
    }
  </section>`;
}

function renderInspectionSitesPanel() {
  const sites = inspectionState.sites || [];
  const racks = inspectionState.racks || [];
  const canCreate = hasPermission("inspection_management", "create");
  return `<section class="data-panel">
      <div class="section-heading"><div><h2>机房与弱电间</h2><span>巡检对象只包含机房、弱电间和其下的机柜</span></div>
        ${canCreate ? '<div class="toolbar-actions"><button class="primary-button" data-action="inspection-new-site">＋ 新增机房/弱电间</button></div>' : ""}
      </div>
      ${
        sites.length
          ? `<div class="table-wrap"><table>
              <thead><tr><th>编码</th><th>名称</th><th>类型</th><th>组织</th><th>位置</th><th>机柜数</th><th>操作</th></tr></thead>
              <tbody>${sites
                .map(
                  (site) => `<tr>
                    <td class="strong-cell">${escapeHtml(site.code || "")}</td>
                    <td>${escapeHtml(site.name || "")}</td>
                    <td>${escapeHtml(inspectionSiteTypeLabels[site.siteType] || "机房")}</td>
                    <td>${escapeHtml(site.orgName || "—")}</td>
                    <td>${escapeHtml(site.location || "—")}</td>
                    <td>${escapeHtml(String(site.rackCount || 0))}</td>
                    <td>${
                      canCreate
                        ? `<button class="text-button" data-action="inspection-edit-site" data-id="${escapeHtml(
                            site.id,
                          )}">编辑</button>`
                        : "—"
                    }</td>
                  </tr>`,
                )
                .join("")}</tbody>
            </table></div>`
          : inspectionEmptyState("还没有机房或弱电间，请先新增。")
      }
    </section>
    <section class="data-panel">
      <div class="section-heading"><div><h2>机柜</h2><span>机柜可单独发起巡检，也可在巡检某个机房时一并覆盖</span></div>
        ${canCreate ? '<div class="toolbar-actions"><button class="primary-button" data-action="inspection-new-rack">＋ 新增机柜</button></div>' : ""}
      </div>
      ${
        racks.length
          ? `<div class="table-wrap"><table>
              <thead><tr><th>机柜编码</th><th>名称</th><th>所属机房/弱电间</th><th>高度</th><th>备注</th><th>操作</th></tr></thead>
              <tbody>${racks
                .map(
                  (rack) => `<tr>
                    <td class="strong-cell">${escapeHtml(rack.code || "")}</td>
                    <td>${escapeHtml(rack.name || "")}</td>
                    <td>${escapeHtml(
                      `${inspectionSiteTypeLabels[rack.siteType] || "机房"} · ${rack.siteName || ""}`,
                    )}</td>
                    <td>${escapeHtml(`${rack.heightU || 0}U`)}</td>
                    <td>${escapeHtml(rack.remarks || "—")}</td>
                    <td>${
                      canCreate
                        ? `<button class="text-button" data-action="inspection-edit-rack" data-id="${escapeHtml(
                            rack.id,
                          )}">编辑</button>`
                        : "—"
                    }</td>
                  </tr>`,
                )
                .join("")}</tbody>
            </table></div>`
          : inspectionEmptyState("还没有机柜。")
      }
    </section>`;
}

function renderInspectionTaskItem(item, editable) {
  const result = item.result || "pending";
  const buttons = ["ok", "fail", "na"]
    .map(
      (value) =>
        `<button type="button" class="inspection-result-button${
          result === value ? " is-active" : ""
        }" data-action="inspection-check" data-result="${value}" data-id="${escapeHtml(
          item.id,
        )}"${editable ? "" : " disabled"}>${escapeHtml(inspectionResultLabels[value])}</button>`,
    )
    .join("");
  const valueField =
    item.valueType === "number" || item.valueType === "text"
      ? `<input type="text" data-inspection-value="${escapeHtml(item.id)}" value="${escapeHtml(
          item.valueText || "",
        )}" placeholder="${item.valueType === "number" ? "实测值" : "记录"}"${editable ? "" : " disabled"} />`
      : "";
  return `<tr class="inspection-item${result === "fail" ? " is-abnormal" : ""}">
    <td>${escapeHtml(String(item.seqNo || ""))}</td>
    <td>${escapeHtml(item.category || "")}</td>
    <td class="strong-cell">${escapeHtml(item.title || "")}${
      item.checkMethod ? `<small class="cell-sub">${escapeHtml(item.checkMethod)}</small>` : ""
    }</td>
    <td>${buttons}</td>
    <td>${valueField}${item.unit ? `<span class="cell-unit">${escapeHtml(item.unit)}</span>` : ""}</td>
    <td><input type="text" data-inspection-notes="${escapeHtml(item.id)}" value="${escapeHtml(
      item.notes || "",
    )}" placeholder="${result === "fail" ? "必填：异常说明" : "说明"}"${editable ? "" : " disabled"} /></td>
    <td>${escapeHtml(item.checkedAt ? formatDateTime(item.checkedAt) : "—")}</td>
  </tr>`;
}

function renderInspectionTaskDetail(task) {
  const items = Array.isArray(task.items) ? task.items : [];
  const editable = task.status === "running";
  const canSubmit = hasPermission("inspection_management", "update");
  const abnormal = items.filter((item) => item.result === "fail");
  return `<section class="data-panel inspection-detail">
    <div class="section-heading">
      <div>
        <h2>${escapeHtml(task.taskNo || "")} · ${escapeHtml(inspectionScopeName(task))}</h2>
        <span>${escapeHtml(task.templateName || "")} ｜ 执行人 ${escapeHtml(
          task.inspectorName || "",
        )} ｜ 开始 ${escapeHtml(task.startedAt ? formatDateTime(task.startedAt) : "")}${
          task.submittedAt ? ` ｜ 提交 ${escapeHtml(formatDateTime(task.submittedAt))}` : ""
        }</span>
      </div>
      <div class="toolbar-actions">
        <button class="secondary-button" data-action="inspection-back">返回列表</button>
        <button class="secondary-button" data-action="inspection-export">导出巡检表</button>
        <button class="secondary-button" data-action="inspection-print">打印</button>
        ${
          editable && canSubmit
            ? '<button class="primary-button" data-action="inspection-submit">提交巡检表</button>'
            : ""
        }
      </div>
    </div>
    <div class="inspection-metrics">
      <span>事项 <strong>${escapeHtml(String(items.length))}</strong></span>
      <span>正常 <strong>${escapeHtml(String(task.itemOk || 0))}</strong></span>
      <span class="${abnormal.length ? "is-abnormal" : ""}">异常 <strong>${escapeHtml(
        String(task.itemFail || 0),
      )}</strong></span>
      <span>不适用 <strong>${escapeHtml(String(task.itemNa || 0))}</strong></span>
      <span>状态 <strong>${escapeHtml(inspectionStatusLabels[task.status] || task.status)}</strong></span>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>序号</th><th>类别</th><th>巡检事项</th><th>结论</th><th>实测值</th><th>说明</th><th>检查时间</th></tr></thead>
        <tbody>${items.map((item) => renderInspectionTaskItem(item, editable)).join("")}</tbody>
      </table>
    </div>
    ${
      abnormal.length
        ? `<div class="inspection-abnormal">
            <h3>异常汇总</h3>
            <ul>${abnormal
              .map(
                (item) =>
                  `<li>${escapeHtml(item.title || "")}${item.valueText ? `：${escapeHtml(item.valueText)}` : ""} — ${escapeHtml(
                    item.notes || "",
                  )}</li>`,
              )
              .join("")}</ul>
          </div>`
        : ""
    }
    ${
      editable
        ? `<label class="form-field form-field-wide"><span>异常情况与处理建议（可留空，提交时会自动汇总异常项说明）</span>
            <textarea data-inspection-field="abnormalSummary" rows="3" maxlength="500">${escapeHtml(
              task.abnormalSummary || "",
            )}</textarea>
          </label>`
        : task.abnormalSummary
          ? `<div class="inspection-summary"><strong>异常情况与处理建议</strong><p>${escapeHtml(
              task.abnormalSummary,
            )}</p></div>`
          : ""
    }
  </section>`;
}

function renderInspectionPage() {
  if (!hasPermission("inspection_management", "view")) {
    return inspectionEmptyState("当前账号没有巡检管理的查看权限。");
  }
  if (inspectionState.task) return renderInspectionTaskDetail(inspectionState.task);
  const tabs = [
    ["tasks", "巡检任务"],
    ["templates", "巡检模板"],
    ["sites", "机房与机柜"],
  ];
  const activeView = ["tasks", "templates", "sites"].includes(inspectionState.view)
    ? inspectionState.view
    : "tasks";
  const panel =
    activeView === "templates"
      ? renderInspectionTemplatesPanel()
      : activeView === "sites"
        ? renderInspectionSitesPanel()
        : renderInspectionTasksPanel();
  return `<section class="page-intro">
      <div><span class="eyebrow">INSPECTION</span><h2>机房巡检</h2>
        <p>按机房、弱电间或单个机柜发起巡检，逐项记录结论并在提交后输出完整巡检表。</p></div>
    </section>
    <div class="settings-tabs">
      ${tabs
        .map(
          ([value, label]) =>
            `<button type="button" class="settings-tab${
              value === activeView ? " is-active" : ""
            }" data-action="inspection-view" data-view="${value}">${escapeHtml(label)}</button>`,
        )
        .join("")}
    </div>
    ${inspectionState.loading ? inspectionEmptyState("正在加载巡检数据…") : panel}`;
}

function inspectionExportSheets(task) {
  const items = Array.isArray(task.items) ? task.items : [];
  return [
    {
      name: "巡检表",
      headers: ["项目", "内容"],
      rows: [
        ["巡检单号", task.taskNo || ""],
        ["巡检对象", inspectionScopeName(task)],
        ["巡检模板", task.templateName || ""],
        ["执行人", task.inspectorName || ""],
        ["开始时间", task.startedAt ? formatDateTime(task.startedAt) : ""],
        ["提交时间", task.submittedAt ? formatDateTime(task.submittedAt) : ""],
        ["事项总数", String(items.length)],
        ["正常", String(task.itemOk || 0)],
        ["异常", String(task.itemFail || 0)],
        ["不适用", String(task.itemNa || 0)],
        ["状态", inspectionStatusLabels[task.status] || task.status || ""],
        ["异常情况与处理建议", task.abnormalSummary || ""],
        ["备注", task.remarks || ""],
      ],
    },
    {
      name: "巡检明细",
      headers: ["序号", "类别", "巡检事项", "检查方法", "结论", "实测值/记录", "单位", "说明", "检查时间", "检查人"],
      rows: items.map((item) => [
        String(item.seqNo || ""),
        item.category || "",
        item.title || "",
        item.checkMethod || "",
        inspectionResultLabels[item.result] || item.result || "",
        item.valueText || "",
        item.unit || "",
        item.notes || "",
        item.checkedAt ? formatDateTime(item.checkedAt) : "",
        item.checkedByName || "",
      ]),
    },
  ];
}

function exportInspectionTask() {
  const task = inspectionState.task;
  if (!task) return showToast("请先打开一张巡检表。", true);
  downloadExcel(`机房巡检-${task.taskNo || exportDateStamp()}.xls`, inspectionExportSheets(task));
}

function printInspectionTask() {
  const task = inspectionState.task;
  if (!task) return showToast("请先打开一张巡检表。", true);
  const items = Array.isArray(task.items) ? task.items : [];
  const rows = items
    .map(
      (item) => `<tr>
        <td>${escapeHtml(String(item.seqNo || ""))}</td>
        <td>${escapeHtml(item.category || "")}</td>
        <td>${escapeHtml(item.title || "")}<br /><small>${escapeHtml(item.checkMethod || "")}</small></td>
        <td>${escapeHtml(inspectionResultLabels[item.result] || "")}</td>
        <td>${escapeHtml(item.valueText || "")}${item.unit ? escapeHtml(item.unit) : ""}</td>
        <td>${escapeHtml(item.notes || "")}</td>
      </tr>`,
    )
    .join("");
  const printWindow = window.open("", "_blank");
  if (!printWindow) return showToast("浏览器拦截了打印窗口，请允许弹出窗口后重试。", true);
  printWindow.document.write(
    `<html><head><meta charset="utf-8" /><title>${escapeHtml(task.taskNo || "巡检表")}</title>
      <style>
        body { font-family: "Microsoft YaHei", Arial, sans-serif; font-size: 12px; margin: 24px; }
        h1 { font-size: 18px; margin: 0 0 4px; }
        p.meta { color: #555; margin: 0 0 12px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #999; padding: 5px 6px; text-align: left; vertical-align: top; }
        th { background: #f0f0f0; }
        tfoot td { border: none; padding-top: 18px; }
      </style></head><body>
      <h1>机房巡检表</h1>
      <p class="meta">巡检单号 ${escapeHtml(task.taskNo || "")} ｜ 巡检对象 ${escapeHtml(
        inspectionScopeName(task),
      )} ｜ 模板 ${escapeHtml(task.templateName || "")} ｜ 执行人 ${escapeHtml(
        task.inspectorName || "",
      )} ｜ 开始 ${escapeHtml(task.startedAt ? formatDateTime(task.startedAt) : "")}${
        task.submittedAt ? ` ｜ 提交 ${escapeHtml(formatDateTime(task.submittedAt))}` : ""
      }</p>
      <table><thead><tr><th>序号</th><th>类别</th><th>巡检事项</th><th>结论</th><th>实测值</th><th>说明</th></tr></thead>
        <tbody>${rows}</tbody></table>
      ${
        task.abnormalSummary
          ? `<p class="meta"><strong>异常情况与处理建议：</strong>${escapeHtml(task.abnormalSummary)}</p>`
          : ""
      }
      <tfoot><table><tr><td>巡检人签字：</td><td>复核人签字：</td><td>日期：</td></tr></table></tfoot>
    </body></html>`,
  );
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
}

function maybeStartInspectionFromHash() {
  const hash = String(window.location.hash || "");
  const match = hash.match(/inspection(?:[/?](?:rack|rackCode)=?)([A-Za-z0-9._-]+)/i);
  if (!match) return;
  const rackCode = match[1];
  const rack = (inspectionState.racks || []).find((item) => String(item.code) === rackCode);
  if (!rack) return;
  openInspectionStartModal({ rackCode });
}

document.addEventListener("click", (event) => {
  const actionElement = event.target.closest("[data-action]");
  if (!actionElement) return;
  const action = actionElement.dataset.action || "";
  if (!action.startsWith("inspection-")) return;

  if (action === "inspection-view") {
    inspectionState.view = actionElement.dataset.view || "tasks";
    inspectionState.task = null;
    render();
    return;
  }
  if (action === "inspection-start") {
    openInspectionStartModal();
    return;
  }
  if (action === "inspection-refresh") {
    loadInspectionData({ force: true })
      .then(() => render())
      .catch((error) => showToast(`巡检数据加载失败：${error.message}`, true));
    return;
  }
  if (action === "inspection-open-task") {
    loadInspectionTask(actionElement.dataset.id || "").catch((error) =>
      showToast(`加载巡检表失败：${error.message}`, true),
    );
    return;
  }
  if (action === "inspection-back") {
    inspectionState.task = null;
    render();
    return;
  }
  if (action === "inspection-check") {
    const task = inspectionState.task;
    if (!task) return;
    submitInspectionCheck(task.id, actionElement.dataset.id || "", actionElement.dataset.result || "");
    return;
  }
  if (action === "inspection-submit") {
    submitInspectionTask();
    return;
  }
  if (action === "inspection-void") {
    voidInspectionTask(actionElement.dataset.id || "");
    return;
  }
  if (action === "inspection-export") {
    exportInspectionTask();
    return;
  }
  if (action === "inspection-print") {
    printInspectionTask();
    return;
  }
  if (action === "inspection-new-template") {
    openInspectionTemplateModal();
    return;
  }
  if (action === "inspection-edit-template") {
    openInspectionTemplateModal(actionElement.dataset.id || "");
    return;
  }
  if (action === "inspection-add-item") {
    const body = document.querySelector("[data-inspection-template-items]");
    if (body) body.insertAdjacentHTML("beforeend", inspectionTemplateItemRow({}));
    return;
  }
  if (action === "inspection-remove-item") {
    const row = actionElement.closest("[data-inspection-template-item]");
    if (row) row.remove();
    return;
  }
  if (action === "inspection-new-site") {
    openInspectionSiteModal();
    return;
  }
  if (action === "inspection-edit-site") {
    openInspectionSiteModal(actionElement.dataset.id || "");
    return;
  }
  if (action === "inspection-new-rack") {
    openInspectionRackModal();
  }
});

document.addEventListener("change", (event) => {
  const element = event.target.closest("[data-action]");
  const scopeSelect = event.target.closest('form[data-form="inspection-start"] select[name="scopeKind"]');
  if (scopeSelect) {
    const scopeKind = scopeSelect.value;
    scopeSelect.closest("form").querySelectorAll("[data-inspection-scope]").forEach((field) => {
      field.hidden = field.dataset.inspectionScope !== scopeKind;
    });
    const templateSelect = scopeSelect.closest("form").querySelector('select[name="templateId"]');
    if (templateSelect) {
      const options = inspectionTemplatesForScope(scopeKind);
      templateSelect.innerHTML = options
        .map(
          (template) =>
            `<option value="${escapeHtml(template.id)}">${escapeHtml(template.name)}（${escapeHtml(
              inspectionSiteTypeLabels[template.siteType] || "通用",
            )}）</option>`,
        )
        .join("");
    }
    return;
  }
  if (!element) return;
  const action = element.dataset.action || "";
  if (action === "inspection-filter-status") {
    inspectionState.statusFilter = element.value || "";
    refreshInspectionTasks()
      .then(() => render())
      .catch((error) => showToast(`巡检任务加载失败：${error.message}`, true));
  }
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-form]");
  if (!form) return;
  const type = form.dataset.form || "";
  if (!type.startsWith("inspection-")) return;
  event.preventDefault();
  if (type === "inspection-start") {
    handleInspectionStartSubmit(form);
    return;
  }
  if (type === "inspection-site") {
    saveInspectionSite(form);
    return;
  }
  if (type === "inspection-rack") {
    saveInspectionRack(form);
    return;
  }
  if (type === "inspection-template") {
    saveInspectionTemplate(form);
  }
});

initializeTheme();
startAuth();
