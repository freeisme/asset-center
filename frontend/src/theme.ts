import { applyLegacyAccent } from "./legacyBridge";

export interface ThemeColorPreset {
  key: string;
  label: string;
  color: string;
}

export const THEME_COLOR_KEY = "oa-theme-color";
export const DEFAULT_THEME_COLOR = "#409eff";

/** 预设主题色：默认蓝保持 Element Plus 观感，其余与旧前端的强调色习惯接近。 */
export const THEME_COLOR_PRESETS: ThemeColorPreset[] = [
  { key: "blue", label: "商务蓝", color: "#409eff" },
  { key: "indigo", label: "靛蓝", color: "#4f46e5" },
  { key: "teal", label: "青色", color: "#0f766e" },
  { key: "green", label: "松绿", color: "#15803d" },
  { key: "orange", label: "暖橙", color: "#c2410c" },
  { key: "red", label: "标准红", color: "#c9002b" },
  { key: "purple", label: "紫罗兰", color: "#7c3aed" },
  { key: "slate", label: "石墨", color: "#334155" },
];

const HEX_PATTERN = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i;

function normalizeHex(input: string): string {
  const value = String(input ?? "").trim();
  const match = HEX_PATTERN.exec(value);
  if (!match) return DEFAULT_THEME_COLOR;
  const hex = match[1];
  if (hex.length === 3) {
    return `#${hex[0]}${hex[0]}${hex[1]}${hex[1]}${hex[2]}${hex[2]}`.toLowerCase();
  }
  return `#${hex}`.toLowerCase();
}

function hexToRgb(color: string): { r: number; g: number; b: number } {
  const hex = normalizeHex(color).slice(1);
  return {
    r: parseInt(hex.slice(0, 2), 16),
    g: parseInt(hex.slice(2, 4), 16),
    b: parseInt(hex.slice(4, 6), 16),
  };
}

function toHex(value: number): string {
  return Math.max(0, Math.min(255, Math.round(value))).toString(16).padStart(2, "0");
}

/** weight 表示目标色占比：0 为原色，1 为目标色。 */
export function mixColor(color: string, target: string, weight: number): string {
  const from = hexToRgb(color);
  const to = hexToRgb(target);
  const ratio = Math.max(0, Math.min(1, weight));
  return `#${toHex(from.r + (to.r - from.r) * ratio)}${toHex(
    from.g + (to.g - from.g) * ratio,
  )}${toHex(from.b + (to.b - from.b) * ratio)}`;
}

export function themeColorContrast(color: string): string {
  const { r, g, b } = hexToRgb(color);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.65 ? "#1f1f1f" : "#ffffff";
}

export function currentThemeColor(): string {
  return normalizeHex(window.localStorage.getItem(THEME_COLOR_KEY) ?? DEFAULT_THEME_COLOR);
}

/** 把主题色写入 Element Plus 的 CSS 变量，并同步给旧前端 iframe 的强调色。 */
export function applyThemeColor(color: string, options: { persist?: boolean } = {}): string {
  const value = normalizeHex(color);
  const root = document.documentElement;
  root.style.setProperty("--el-color-primary", value);
  for (const level of [3, 5, 7, 8, 9]) {
    root.style.setProperty(
      `--el-color-primary-light-${level}`,
      mixColor(value, "#ffffff", level / 10),
    );
  }
  root.style.setProperty("--el-color-primary-dark-2", mixColor(value, "#000000", 0.2));
  root.style.setProperty("--oa-accent", value);
  root.style.setProperty("--oa-accent-contrast", themeColorContrast(value));
  if (options.persist !== false) {
    window.localStorage.setItem(THEME_COLOR_KEY, value);
  }
  // 旧前端用 --teal / --teal-soft 作为强调色，迁移期一并跟随。
  applyLegacyAccent(value, mixColor(value, "#ffffff", 0.9));
  return value;
}

export function resetThemeColor(): string {
  return applyThemeColor(DEFAULT_THEME_COLOR);
}
