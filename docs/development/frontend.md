# 前端结构与迁移说明

## 结论速览

| 项目 | 现状 |
| --- | --- |
| 技术栈 | Vue 3 + TypeScript + Vite + Element Plus + Vue Router |
| 源码 | `frontend/`（`src/` 下按 api / router / layouts / views / components 分层） |
| 构建产物 | `web/app/`，由 `server.py` 在 `/` 与前端路由上回落该入口 |
| 路由 | 真实路径（History API）：`/dashboard`、`/computers`、`/settings`… |
| 旧前端 | 完整保留在 `web/`，由 `/legacy/` 提供，迁移期用 iframe 承载未迁移页面 |
| 版本号 | 仓库根目录 `VERSION`，后端 `GET /api/meta` 暴露，前端构建时注入 |

## 开发与构建

```bash
cd frontend
pnpm install          # 首次或依赖变更后
pnpm dev              # 本地开发服务器（Vite，默认 5173，需自行代理 /api 到后端）
pnpm build            # 类型检查 + 生产构建，产物写入 ../web/app
pnpm typecheck        # 只做类型检查
```

后端仍然是一个进程：`python server.py` 同时提供 `/api/*` 与前端静态资源。
本地调试时先 `pnpm build`，再启动 `server.py`，访问 `http://127.0.0.1:8000/` 即可。
没有构建产物时，`/` 会自动回落到旧版入口，功能不受影响。

`Dockerfile` 使用多阶段构建，镜像里已经包含 `web/app/`，部署时无需在服务器上装 Node。

## 路由与权限

路由表由 `frontend/src/navigation.ts` 的 `NAV_ITEMS` 同时驱动：侧边栏菜单、路径映射、
页面标题和权限规则都来自这一处，新增页面只需要在这里加一条并在 `router/index.ts` 注册组件。

权限判定与旧前端 `canViewPage` 保持一致（见 `frontend/src/session.ts`）：

- 超级管理员直接放行；
- 其他账号按 `/api/auth/permissions` 返回的 `{resource, action}` 判断，`view` 权限决定菜单可见性；
- 无权限访问某页时，路由守卫会跳到第一个有权限的页面，避免出现空白页。

## 版本号

`VERSION` 是唯一来源：

- 后端启动时读取，`GET /api/meta` 返回 `version` / `serverTime` / `timeZone`；
- 前端构建时由 `vite.config.ts` 注入 `__APP_VERSION__`，设置页与顶栏显示；
- `tests/test_regressions.py` 会校验 `VERSION` 与 `VERSION_NOTES.md` 的最新版本标题一致。

发布新版本时先更新 `VERSION` 与 `VERSION_NOTES.md` 的同名条目，再打标签。

## 渐进迁移：旧前端桥接

15 个页面仍在旧前端里。为了让新旧界面共用一套导航与顶栏，同时不动旧代码：

1. 旧前端整体挂在 `/legacy/`（`server.py` 的 `serve_frontend_route` 负责前缀重写，
   旧的 `app.js` / `styles.css` 仍按 `web/` 根目录的相对路径加载）；
2. 新外壳用同源 iframe 承载它，并注入样式隐藏旧侧边栏与顶栏；
3. 旧前端新增 `window.oaLegacy` 桥接接口：

   ```js
   oaLegacy.getPage()          // 当前页面 key
   oaLegacy.setPage(page)      // 切换页面（复用旧渲染）
   oaLegacy.isAuthenticated()  // 旧前端是否已完成会话校验
   oaLegacy.getTheme() / setTheme(theme)
   ```

4. 顶栏按钮通过点击旧前端里隐藏的按钮来复用其逻辑（主题、消息提醒、重新加载），
   不重复实现第二套；
5. 旧前端内部跳页时，新外壳通过 `MutationObserver` 监听 `#appContent`，把路由同步回去。

**为什么用 iframe 而不是直接挂载 DOM**：旧样式表里有
`*, *::before, *::after { border-radius: 0 !important; box-shadow: none !important }`
这类全局强制规则，直接在同一个文档里混用会把 Element Plus 的组件外观压平；
旧脚本还注册了文档级点击监听。iframe 提供彻底的样式与脚本隔离，代价只是多一个文档。

### 迁移单个页面的步骤

1. 在 `frontend/src/views/` 写新的 Vue 页面，数据仍走既有 `/api/*` 接口；
2. 在 `router/index.ts` 把该路径从 `LegacyPage` 换成新组件（`navigation.ts` 不用改）；
3. 跑 `pnpm build` 与回归测试；
4. 14 个页面全部迁完后再做收尾：删除 `LegacyPage.vue`、`LegacyFrame.vue`、`legacyBridge.ts`、
   `web/app.js`、`web/styles.css`、`/legacy/` 路由与 `window.oaLegacy` 桥接，
   并把 `X-Frame-Options` 的 `SAMEORIGIN` 分支去掉。

## 已知待办

- Element Plus 目前是全量引入，首屏 JS 约 1 MB（gzip 330 KB）；后续可改为按需引入
  （`unplugin-vue-components` + `unplugin-auto-import`）压缩到约三分之一。
- 消息提醒、主题等仍经由旧前端实现；随页面迁移一并搬到 Vue 侧。
- 旧前端的 `pageMeta` 缺少 `inspection`、`rackLayout` 两个标题，新外壳已用
  `navigation.ts` 里的标题覆盖，迁移完成后该问题自然消失。
