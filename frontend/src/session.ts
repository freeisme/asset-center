import { reactive } from "vue";
import { api } from "./api/client";
import { NAV_BY_PAGE } from "./navigation";

export interface Permission {
  resource: string;
  action: string;
  scope?: string;
}

export interface SessionUser {
  id?: string;
  username: string;
  displayName: string;
  role: string;
  isSuperAdmin: boolean;
  employeeId?: string;
  orgId?: string;
}

export interface AppMeta {
  version: string;
  buildTime: string;
  serverTime: string;
  timeZone: string;
}

interface SessionState {
  ready: boolean;
  user: SessionUser | null;
  permissions: Permission[];
  isSuperAdmin: boolean;
  meta: AppMeta | null;
}

export const session = reactive<SessionState>({
  ready: false,
  user: null,
  permissions: [],
  isSuperAdmin: false,
  meta: null,
});

export function hasPermission(resource: string, action = "view"): boolean {
  if (session.isSuperAdmin) return true;
  return session.permissions.some((item) => item.resource === resource && item.action === action);
}

/** 与旧前端 canViewPage 保持一致的可见性规则。 */
export function canViewPage(page: string): boolean {
  const item = NAV_BY_PAGE[page];
  if (!item) return true;
  return item.modules.some((resource) => hasPermission(resource, "view"));
}

export function firstVisiblePath(): string {
  const first = Object.values(NAV_BY_PAGE).find((item) => canViewPage(item.page));
  return first ? first.path : "/settings";
}

function clearSession(): void {
  session.user = null;
  session.permissions = [];
  session.isSuperAdmin = false;
}

export async function refreshSession(): Promise<boolean> {
  try {
    const payload = await api<{ authenticated: boolean; user: SessionUser }>("/api/auth/session");
    session.user = payload.user;
    const granted = await api<{ isSuperAdmin: boolean; permissions: Permission[] }>(
      "/api/auth/permissions",
    );
    session.isSuperAdmin = Boolean(granted.isSuperAdmin);
    session.permissions = Array.isArray(granted.permissions) ? granted.permissions : [];
    return true;
  } catch {
    clearSession();
    return false;
  } finally {
    session.ready = true;
  }
}

export async function loadMeta(): Promise<AppMeta | null> {
  try {
    session.meta = await api<AppMeta>("/api/meta");
  } catch {
    session.meta = session.meta ?? {
      version: __APP_VERSION__,
      buildTime: __APP_BUILD_TIME__,
      serverTime: "",
      timeZone: "",
    };
  }
  return session.meta;
}

export async function login(username: string, password: string): Promise<void> {
  await api("/api/auth/login", { method: "POST", body: { username, password } });
  const ok = await refreshSession();
  if (!ok) throw new Error("登录状态校验失败，请重试。");
}

export async function logout(): Promise<void> {
  try {
    await api("/api/auth/logout", { method: "POST", body: {} });
  } finally {
    clearSession();
  }
}
