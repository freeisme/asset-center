import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

const versionPath = fileURLToPath(new URL("../VERSION", import.meta.url));
const appVersion = readFileSync(versionPath, "utf8").trim();

// 构建到 web/app/，由 server.py 在 / 与前端路由上回落这个入口；
// base 用 /app/ 保证深层路由（如 /settings）刷新时静态资源仍然可解析。
export default defineConfig({
  base: "/app/",
  plugins: [vue()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
    __APP_BUILD_TIME__: JSON.stringify(new Date().toISOString()),
  },
  build: {
    outDir: "../web/app",
    emptyOutDir: true,
    target: "es2020",
    sourcemap: false,
  },
});
