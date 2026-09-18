/** 迁移期：与 /legacy/ 里的旧前端通信。页面逐页迁移完成后整个模块可以删除。 */

let legacyWindow: Window | null = null;

export function registerLegacyFrame(target: Window | null): void {
  legacyWindow = target;
}

export function hasLegacyFrame(): boolean {
  return Boolean(legacyWindow && !legacyWindow.closed);
}

function legacyApi(): Record<string, (...args: unknown[]) => unknown> | null {
  if (!legacyWindow || legacyWindow.closed) return null;
  const api = (legacyWindow as unknown as { oaLegacy?: Record<string, (...args: unknown[]) => unknown> })
    .oaLegacy;
  return api ?? null;
}

/** 通过点击旧前端里隐藏的按钮，复用它已经实现好的逻辑（主题、通知、重新加载等）。 */
export function clickLegacyAction(action: string): boolean {
  if (!legacyWindow || legacyWindow.closed) return false;
  const doc = legacyWindow.document;
  const element = doc.querySelector<HTMLElement>(`[data-action="${action}"]`);
  if (!element) return false;
  element.click();
  return true;
}

export function legacyNotificationCount(): string {
  if (!legacyWindow || legacyWindow.closed) return "";
  const badge = legacyWindow.document.querySelector<HTMLElement>("[data-notification-count]");
  if (!badge || badge.hidden) return "";
  return String(badge.textContent ?? "").trim();
}

export function legacyPage(): string {
  const api = legacyApi();
  const value = api?.getPage?.();
  return typeof value === "string" ? value : "";
}

export function legacyAuthenticated(): boolean {
  const api = legacyApi();
  const value = api?.isAuthenticated?.();
  return value === true;
}

export function legacyTheme(): string {
  const api = legacyApi();
  const value = api?.getTheme?.();
  return typeof value === "string" && value ? value : "";
}

export function pushLegacyPage(page: string): boolean {
  const api = legacyApi();
  if (!api?.setPage) return false;
  api.setPage(page);
  return true;
}

export function applyLegacyTheme(theme: string): void {
  const api = legacyApi();
  api?.setTheme?.(theme);
}
