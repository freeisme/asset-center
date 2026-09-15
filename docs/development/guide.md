# 办公资产管理系统开发指南

本文档面向需要维护、扩展、部署和排查本项目的开发人员及系统管理员。
文档以当前仓库代码为准，适用于 Docker Compose 部署和 Gitea 手动版本更新流程。

本文档不包含任何真实密码、SSH 私钥、Webhook Secret、更新控制令牌、业务数据或
数据库备份。生产运行时配置只保存在服务器上的 `.env` 或 systemd 环境文件中。

## 开发与测试约定

- 后端入口仍为 `server.py`，领域服务、SQL 仓储、鉴权和公共代码位于 `office_asset/`；新增业务优先扩展相应模块，避免恢复全量状态快照写入。
- `GET /api/state` 只能兼容读取。入库、领用、归还、设备分配和设备归还必须使用独立命令、事务、幂等键和审计记录。
- 数据库结构变化必须添加新的 `database/migrations/YYYYMMDD_NNN_description.sql`，不得修改已发布迁移。执行前后运行 `python tools/migration_runner.py --database <测试库> --verify`。
- 测试环境使用独立数据库，例如 `office_asset_mgmt_test`，并用 `127.0.0.1:8011` 启动；不得使用生产库或提交测试数据。
- 发布前运行 Python 编译、`node --check web/app.js`、`tests/integration/qa_security_regression.py` 和浏览器关键路径验证。

## 文档导航

GitHub Wiki 提供适合团队日常查阅的模块化文档：

- [项目 Wiki](https://github.com/freeisme/asset-center/wiki)
- [项目概览](https://github.com/freeisme/asset-center/wiki/Project-Overview)
- [系统架构](https://github.com/freeisme/asset-center/wiki/Architecture)
- [模块说明](https://github.com/freeisme/asset-center/wiki/Modules)
- [本地开发](https://github.com/freeisme/asset-center/wiki/Development)
- [数据库与迁移](https://github.com/freeisme/asset-center/wiki/Database-and-Migrations)
- [测试规范](https://github.com/freeisme/asset-center/wiki/Testing)
- [部署与配置](https://github.com/freeisme/asset-center/wiki/Deployment)
- [版本更新与发布](https://github.com/freeisme/asset-center/wiki/Release-and-Update)
- [安全运维](https://github.com/freeisme/asset-center/wiki/Security-and-Operations)
- [故障排查](https://github.com/freeisme/asset-center/wiki/Troubleshooting)

代码仓库中的本文件保留完整开发参考；Wiki 页面用于按主题快速查阅。两处文档冲突时，
以当前代码、数据库脚本和发布说明为准。

## 1. 项目定位

### 1.1 技术栈

| 层次 | 技术 |
| --- | --- |
| 后端 | Python 3.10+ 标准库，`http.server` 提供 HTTP 服务 |
| 前端 | 原生 HTML、CSS、JavaScript，无前端构建工具 |
| 数据库 | MySQL 8.0+，当前 Docker 镜像为 MySQL 8.4 |
| 容器 | Docker Compose v2 |
| 代码托管 | GitHub 源仓库，私有 Gitea 部署镜像 |
| 反向代理 | 可选 Nginx |
| 运行方式 | `server.py` 直接运行，或使用 Docker 镜像运行 |

项目没有使用 Python 数据库驱动。后端通过 `mysql` 和 `mysqldump` 命令行客户端访问
数据库，并通过环境变量提供连接参数。

### 1.2 当前生产拓扑

```text
浏览器
  |
  +-- HTTP/HTTPS --> Nginx 或 app:8000
                         |
                         +-- Python server.py
                                  |
                                  +-- Docker 网络中的 db:3306
                                         |
                                         +-- MySQL 8.4

开发机 push GitHub main
  |
  +-- GitHub freeisme/asset-center
          |
          +-- Gitea 镜像 OWNER/office-asset-management（每 8 小时）
                  |
                  +-- 签名 Webhook --> 宿主机更新服务:9000
                                           |
                                           +-- 只记录 push，不自动部署

设置页检查并选择版本
  |
  +-- app 容器 --> host.docker.internal:9000/control/status
  +-- 管理员确认 --> host.docker.internal:9000/control/update
                                   |
                                   +-- 按指定提交 git fetch/reset
                                   +-- docker compose build
                                   +-- docker compose up
                                   +-- /api/health
```

当前服务器约定：

| 项目 | 当前值 |
| --- | --- |
| 服务器地址 | `<asset-server-host>` |
| 服务器 SSH | `22` |
| Gitea SSH | `2222` |
| 应用目录 | `/opt/office-asset-mgmt` |
| 应用地址 | `https://asset.example.internal/` |
| Gitea 仓库 | `OWNER/office-asset-management` |
| 发布分支 | `main` |
| 应用数据库服务名 | `db` |

服务器 IP、端口和仓库名称可以写入运维文档，但密码和令牌不能写入 Git。

当前 GitHub 到 Gitea 的发布链路：

```text
GitHub freeisme/asset-center
  -> Gitea 镜像 OWNER/office-asset-mgmt（每 8 小时）
  -> 设置页检查并选择版本
  -> 更新控制服务手动部署
```

Gitea 镜像同步只更新仓库，不会自动部署服务器。更新服务读取私有仓库时，必须为目标
仓库授权 `officeasset-deploy` 只读部署密钥。

## 2. 目录和模块职责

```text
.
├── server.py
├── web/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── database/
│   ├── bootstrap/              # 空库初始化 SQL
│   ├── migrations/             # 受跟踪的增量迁移
│   └── manual/                 # 手工维护 SQL
├── tools/
│   ├── migration_runner.py
│   └── run_mysql_utf8.py
├── scripts/
│   └── windows/deploy.ps1
├── deploy/
│   ├── gitea/
│   ├── docker/
│   ├── nginx/
│   ├── scripts/
│   └── systemd/
├── tests/
│   ├── integration/qa_security_regression.py
│   └── test_regressions.py
├── docs/
│   ├── development/
│   ├── deployment/
│   ├── releases/
│   └── security/
├── compose.yaml
├── Dockerfile
├── .env.example
└── requirements.txt
```

### 2.1 后端 `server.py`

`server.py` 是后端、静态文件服务、数据库访问和后台备份调度器的集中入口。
主要模块按职责可以分为：

| 代码区域/函数族 | 作用 |
| --- | --- |
| 顶部环境变量 | 读取数据库、HTTP、备份、认证和更新服务配置 |
| `run_mysql`、`run_mysql_json_queries` | 统一调用 MySQL 客户端，处理字符集、密码和数据库参数 |
| `password_hash`、`verify_password` | 账号密码哈希和校验 |
| `create_auth_session`、`current_auth_context` | 创建、读取和校验登录会话 |
| `require_auth`、`require_role`、`require_csrf` | API 认证、角色和 CSRF 防护 |
| `build_state_payload` | 将数据库记录组装为前端使用的状态快照 |
| `normalize_*` | 兼容历史数据、清理空值、修正关联和格式 |
| `build_sync_sql`、`sync_state` | 把前端状态快照转换为数据库事务并保存 |
| `build_audit_entries` | 对比旧快照和新数据，生成操作日志 |
| `create_database_backup` | 生成压缩 SQL 备份并写入备份记录 |
| `database_backup_scheduler_loop` | 按系统设置执行每日自动备份 |
| `AppHandler.handle_api` | API 路由分发、请求读取和 JSON 响应 |
| `main` | 启动 HTTP 服务和后台备份调度线程 |

当前后端是单体服务。新增业务功能时，应优先沿用已有的参数校验、事务、审计和
错误处理方法，而不是在文件外部另起一套访问方式。

### 2.2 前端 `web/index.html`

`index.html` 只负责应用外壳：

- 登录/初始化根节点：`#authRoot`
- 主应用壳：`#appShell`
- 左侧导航：`#sidebarNav`
- 顶部标题、用户信息和主题切换按钮
- 页面内容容器：`#appContent`
- 模态框容器：`#modalRoot`
- Toast 消息容器：`#toastRoot`

页面业务内容主要由 `app.js` 动态渲染。修改静态 HTML 时要保持这些 ID 和
`data-action` 属性不变，否则事件委托和页面初始化会失效。

列表型文本筛选使用“输入草稿 + 显式查询”规则。用户输入时只能更新草稿，点击查询按钮
或按 Enter 后才能写入已应用筛选、重绘列表或请求接口；不能在每个 `input` 事件中调用
`render`、刷新远程数据或覆盖输入框。这条规则同时适用于中文输入法组合输入。

### 2.3 前端 `web/app.js`

前端采用单文件状态管理和事件委托：

| 模块 | 作用 |
| --- | --- |
| `state` | 组织、人员、办公终端、库存、日志等业务状态 |
| `settingsState` | 系统设置、用户、备份和版本检查状态 |
| `loadInitialState`、`normalizeState` | 从本地缓存读取并兼容旧状态 |
| `hydrateStateFromServer` | 从 `/api/state` 加载数据库状态 |
| `persistState` | 保存 UI 本地状态，并在需要时同步业务快照到服务器 |
| `render` 及各 `render*` 函数 | 根据当前状态生成页面 HTML |
| `open*Modal` | 打开新增、编辑和详情模态框 |
| `handle*Submit` | 处理表单提交、校验和状态修改 |
| `requestJson`、`requestDownload` | 统一处理 API、CSRF 和错误响应 |
| `document.addEventListener` | 通过 `data-action`、`data-form`、`data-filter` 处理事件 |
| Excel 导出函数 | 生成员工、办公终端、库存、采购和操作日志导出文件 |
| `applyTheme`、`toggleTheme` | 持久化并切换亮色/暗色主题 |

浏览器本地只保存界面偏好和主题：

- `office-asset-center-ui-v1`：当前页面、展开节点、筛选条件和选中项等 UI 状态
- `office-asset-center-theme-v1`：`light` 或 `dark`

业务数据的正式来源是 MySQL，不是浏览器 localStorage。

### 2.4 样式 `web/styles.css`

样式文件包含基础布局、表格、表单、模态框、响应式规则和主题变量。
暗色模式通过 `html[data-theme="dark"]` 覆盖 CSS 变量和关键组件，而不是复制整套
页面结构。新增组件时应同时检查：

1. 亮色主题下的文字和边框对比度。
2. 暗色主题下的背景、输入框、表格、弹窗和 Toast 对比度。
3. `860px`、`640px` 附近的移动布局。
4. 长文本、按钮和表格在小屏幕上是否溢出。

### 2.5 数据库脚本 `database/`

数据库脚本按用途分层。`database/bootstrap/` 按数字顺序存放空库初始化 SQL；
`deploy/scripts/init_database.sh` 先按 `DB_NAME` 创建并选中数据库，再依次执行：

```text
01_schema.sql
02_seed_reference_data.sql
03_views.sql
04_routines.sql
10_audit_log.sql
12_it_inventory.sql
13_hardening_migration.sql
14_computer_configuration.sql
15_inventory_computer_batches.sql
16_inventory_purchase_log.sql
17_data_lineage_and_consistency.sql
18_backfill_computer_inbound_dates.sql
19_auth_and_settings.sql
20_database_backup.sql
21_security_hardening.sql
22_update_repository_setting.sql
```

`database/bootstrap/00_create_database.sql` 是兼容性辅助文件，使用固定默认库名时才单独执行；
它不属于可配置 `DB_NAME` 的初始化顺序。`database/bootstrap/06_smoke_test.sql` 是检查脚本，
不应在生产初始化时误当作迁移执行。`database/bootstrap/01_schema.sql` 会删除并重建核心表，
只适合空库初始化或明确批准的重建操作。

生产升级只新增 `database/migrations/YYYYMMDD_NNN_description.sql`。迁移执行器为
`tools/migration_runner.py`，会登记文件校验和；`database/manual/` 中的 SQL 不会被自动执行。

### 2.6 部署目录 `deploy/`

| 路径 | 作用 |
| --- | --- |
| `deploy/scripts/init_database.sh` | 按顺序初始化数据库 |
| `deploy/docker/init_database.sh` | Docker 空库初始化包装脚本，选择 `MYSQL_DATABASE` 并执行审核过的文件 |
| `deploy/scripts/backup_database.sh` | 使用 `mysqldump` 生成独立备份 |
| `deploy/scripts/update_from_gitea.sh` | 拉取指定分支、构建和重启 Docker 服务 |
| `deploy/gitea/deploy_webhook.py` | 接收签名 Webhook，并提供手动版本更新控制接口 |
| `deploy/gitea/office-asset-gitea-webhook.service` | systemd 托管 Webhook 服务 |
| `deploy/gitea/compose.yaml` | Gitea + PostgreSQL 部署 |
| `deploy/nginx/office-asset-mgmt.conf` | Nginx 反向代理示例 |
| `deploy/systemd/office-asset-mgmt.service` | 非 Docker 运行方式的 systemd 示例 |

## 3. 后端配置和运行方式

### 3.1 环境变量

以 `.env.example` 为模板创建运行时配置。真实 `.env` 不得提交到 Git。

| 变量 | 作用 | Docker 典型值/说明 |
| --- | --- | --- |
| `APP_PORT` | 宿主机映射端口 | `8000` |
| `DB_HOST` | MySQL 主机 | Docker 中由 Compose 覆盖为 `db` |
| `DB_PORT` | MySQL 端口 | `3306` |
| `DB_NAME` | 数据库名 | `office_asset_mgmt` |
| `DB_USER` | 应用数据库账号 | 使用独立账号，不建议使用 root |
| `DB_PASSWORD` | 应用数据库密码 | 只放在服务器 `.env` |
| `MYSQL_ROOT_PASSWORD` | MySQL 管理密码 | 只放在服务器 `.env` |
| `MYSQL_BIN` | `mysql` 客户端路径 | Docker 为 `/usr/bin/mysql` |
| `MYSQLDUMP_BIN` | `mysqldump` 路径 | Docker 为 `/usr/bin/mysqldump` |
| `BACKUP_DIR` | Web 备份目录 | Docker 为 `/app/backups` |
| `SERVER_HOST` | Python 监听地址 | Docker 为 `0.0.0.0` |
| `SERVER_PORT` | Python 监听端口 | `8000` |
| `AUTH_SESSION_HOURS` | 登录会话有效小时数 | 默认 `8`，有效范围 `1-168` |
| `AUTH_COOKIE_SECURE` | 是否给 Cookie 加 Secure | HTTPS 反代后设为 `true` |
| `MAX_REQUEST_BODY_BYTES` | JSON 请求体最大字节数 | 默认 `8388608`，最大支持 `64 MB` |
| `PASSWORD_MAX_LENGTH` | 密码最大长度 | 默认 `256`，最大支持 `1024` |
| `LOGIN_RATE_WINDOW_SECONDS` | 登录限流窗口 | 默认 `300` 秒 |
| `LOGIN_RATE_MAX_ATTEMPTS` | 每个 IP/账号窗口内允许的登录次数 | 默认 `15` |
| `BACKUP_SCHEDULER_POLL_SECONDS` | 自动备份轮询间隔 | 默认 `30` 秒 |
| `BACKUP_SCHEDULER_RETRY_SECONDS` | 自动备份失败后的重试间隔 | 默认 `300` 秒 |
| `UPDATE_SERVICE_URL` | 容器访问宿主机更新服务 | 默认 `https://host.docker.internal:9000` |
| `UPDATE_CONTROL_TOKEN` | 容器到宿主机的更新控制令牌 | 与宿主机配置一致，只放运行时环境 |
| `UPDATE_SERVICE_CA_FILE` | 更新服务 CA 证书路径 | 自签或内部 CA 时指定，不能提交到 Git |
| `UPDATE_SERVICE_CERTS_DIR` | CA 证书目录 | Compose 只读挂载到 app 容器 |
| `UPDATE_SERVICE_ALLOW_HTTP` | 是否允许 HTTP 更新服务 | 仅隔离开发环境显式设为 `true` |
| `UPDATE_REQUEST_TIMEOUT` | 请求更新服务的超时秒数 | 默认 `12` 秒 |

注意：Docker Compose 中 `db` 是服务名。应用容器内的 `127.0.0.1` 指向应用容器
自身，不是 MySQL 容器。修改 `.env` 中的应用密码后需要重新创建 app 容器：

```bash
sudo docker compose \
  -f /opt/office-asset-mgmt/compose.yaml \
  --env-file /opt/office-asset-mgmt/.env \
  up -d --force-recreate app
```

MySQL 官方镜像的初始化环境变量主要只在数据卷第一次创建时生效。数据卷已经存在
时，单纯修改 `MYSQL_ROOT_PASSWORD` 或 `DB_PASSWORD` 不会自动修改数据库用户密码。

### 3.2 本地启动

PowerShell 示例：

```powershell
cd <项目工作目录>
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3306"
$env:DB_NAME = "office_asset_mgmt"
$env:DB_USER = "office_asset_app"
$env:DB_PASSWORD = "从本机安全配置读取"
$env:MYSQL_BIN = "<MySQL 客户端完整路径>"
$env:MYSQLDUMP_BIN = "<mysqldump 完整路径>"
$env:SERVER_HOST = "127.0.0.1"
$env:SERVER_PORT = "8000"
python .\server.py
```

启动前必须确认 MySQL 客户端文件存在、数据库可访问、`DB_PASSWORD` 已设置。
浏览器访问 `http://127.0.0.1:8000/`。

### 3.3 Docker Compose 启动

```bash
cp .env.example .env
chmod 600 .env
docker compose config
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:8000/api/health
```

数据库容器只在空数据卷首次初始化时执行
`/docker-entrypoint-initdb.d` 中的脚本。已有数据卷升级时不会自动重新执行
数据库目录中的脚本。

## 4. 认证、权限和 API 约定

### 4.1 认证模型

认证相关表：

- `user_account`：用户、角色、启停状态、失败次数和锁定时间。
- `auth_session`：数据库中的会话记录，保存会话令牌哈希和 CSRF 令牌哈希。
- `system_setting`：系统名称、登录提示、会话时长和备份配置。

首次访问时，如果 `user_account` 为空，前端显示管理员初始化页面。
初始化成功后不能再次通过 bootstrap 接口创建管理员。

登录使用 HttpOnly、SameSite=Lax 的会话 Cookie；写操作同时要求
`X-CSRF-Token` 请求头和 CSRF Cookie 匹配。密码不会以明文保存。

### 4.2 角色

| 角色 | 权限 |
| --- | --- |
| `admin` | 读写业务数据，管理用户、系统设置、数据库备份和版本更新 |
| `operator` | 读写业务数据，不能管理用户、系统设置、备份和版本更新 |
| `viewer` | 只读业务数据和操作日志 |

后端权限校验是最终边界。前端隐藏按钮只是用户体验，不是安全控制。

### 4.3 API 清单

| 方法 | 路径 | 权限 | 作用 |
| --- | --- | --- | --- |
| `GET` | `/api/health` | 无 | 检查数据库探针和必需表数量 |
| `GET` | `/api/auth/bootstrap-status` | 无 | 检查是否需要初始化管理员 |
| `GET` | `/api/auth/session` | Cookie | 返回当前登录状态 |
| `POST` | `/api/auth/bootstrap` | 未初始化 | 创建第一个管理员 |
| `POST` | `/api/auth/login` | 无 | 登录 |
| `POST` | `/api/auth/logout` | 登录 | 注销当前会话 |
| `POST` | `/api/auth/change-password` | 登录 + CSRF | 修改当前密码 |
| `GET` | `/api/users` | admin | 获取用户列表 |
| `POST` | `/api/users` | admin + CSRF | 创建用户 |
| `PUT` | `/api/users/{id}` | admin + CSRF | 修改用户角色、状态或密码 |
| `GET` | `/api/settings` | 登录 | 获取系统设置 |
| `PUT` | `/api/settings` | admin + CSRF | 保存系统和备份设置 |
| `POST` | `/api/updates/check` | admin + CSRF | 检查 Gitea 并返回可选版本 |
| `POST` | `/api/updates/apply` | admin + CSRF | 按指定提交排队手动更新 |
| `GET` | `/api/backups` | admin | 获取备份记录 |
| `POST` | `/api/backups` | admin + CSRF | 创建手动备份 |
| `POST` | `/api/backups/{id}/download` | admin + CSRF + 当前密码 | 下载备份文件 |
| `GET` | `/api/state` | 登录 | 获取完整业务状态快照 |
| `PUT` | `/api/state` | admin/operator + CSRF | 保存完整业务状态快照 |
| `GET` | `/api/audit-logs` | 登录 | 按筛选条件分页获取操作日志 |

新增 API 时必须同时完成以下事项：

1. 在 `AppHandler.handle_api` 中增加明确的方法和路径判断。
2. 先调用 `require_auth`，再按需要调用 `require_role` 和 `require_csrf`。
3. 对 JSON body 做类型、长度、枚举、唯一性和关联校验。
4. 使用 `send_json` 返回一致的 JSON 响应和 HTTP 状态码。
5. 需要变更业务数据时写入 `audit_log`。
6. 在前端增加请求函数或复用 `requestJson`。
7. 在本文档 API 表中补充接口用途和权限。

### 4.4 错误处理

后端会将常见异常转换为 JSON：

- 未登录：HTTP 401，`code=AUTH_REQUIRED`
- CSRF 失败：HTTP 403，`code=CSRF_INVALID`
- 权限不足：HTTP 403，`code=FORBIDDEN`
- 状态冲突：HTTP 409，`code=STATE_CONFLICT`
- 参数或业务校验失败：HTTP 400
- 请求体超过限制：HTTP 413，`code=PAYLOAD_TOO_LARGE`
- 登录频率超过限制：HTTP 429，`code=LOGIN_RATE_LIMITED`，并返回 `Retry-After`
- 未捕获异常：HTTP 500

前端 `requestJson` 会解析这些错误并在页面显示 Toast。不要在业务函数中重复实现
一套 fetch 错误解析逻辑。

## 5. 业务状态和数据流

### 5.1 状态快照

`GET /api/state` 返回一个聚合对象，主要字段如下：

```text
stateRevision
orgs
nonAssetTypes
inventoryBrands
inventoryModels
inventoryMovementLogs
inventoryPurchaseLogs
employees
leftEmployees
computers
auditLogs
```

前端表单先修改内存中的 `state`，然后由 `persistState(true)` 将状态快照发送到
`PUT /api/state`。后端在数据库锁和事务中执行同步 SQL，并更新
`app_state_revision`。

后端的 `build_state_payload` 负责数据库到前端的映射，`build_sync_sql` 负责前端到
数据库的映射。新增字段时必须同时修改这两个方向，不能只修改其中一边。

`PUT /api/state` 必须提交所有状态数组和正数 `stateRevision`。后端先比较数据库当前
版本，再在事务中同步；不能用 `0` 或缺失字段绕过版本冲突检查。新增状态数组时必须
同步修改 `STATE_ARRAY_KEYS`、前端状态归一化和测试快照。

### 5.2 主要业务模块

#### 组织架构

- `org_unit` 保存树形组织节点。
- `parent_org_unit_id` 指向上级组织。
- `org_code` 在同一父节点下必须唯一。
- 组织用于人员归属、办公终端归属和路径展示。
- 删除组织前需要处理下属组织、人员和办公终端的引用。

前端相关函数包括 `openOrgModal`、`handleOrgSubmit`、组织树渲染和编码生成函数。

#### 使用人员

- `employee` 保存员工编号、姓名、组织、部门、岗位和联系方式。
- `employment_status` 支持 `active`、`inactive`、`left`。
- 离职人员会被归档到 `left_employee_archive`，保留离职信息和设备快照。
- 员工编号必须唯一，新增或调整组织时会根据组织路径生成建议编号。

当前普通人员编辑页只允许维护在职和停用状态，不提供离职日期、离职信息和备注输入。
数据库中的 `left` 仅用于离职档案兼容和受控归档结果，不能通过普通人员编辑接口直接写入。
离职档案页面只读展示归档信息和离职时设备快照。

完整的独立受控离职归档流程应按以下顺序执行：

1. 管理员确认离职申请和离职日期、说明、备注。
2. 锁定人员及其当前设备分配，防止归档期间发生新的领用或转移。
3. 逐项回收显示屏和非资产物资，按独立回收事务回补库存并记录流转日志。
4. 解除办公终端分配，保留设备流转历史和离职时设备快照。
5. 在同一归档事务中写入离职档案、更新人员状态并记录审计日志；任一步骤失败时整体回滚。

`v2.0.13` 已完成普通编辑页与上述流程边界的界面修正，但当前版本尚未开放独立的
“办理离职”操作入口。前端相关函数包括 `openEmployeeModal`、`handleEmployeeSubmit`、
设备回收函数和 `openLeftEmployeeModal`。

#### 办公终端资产

- `computer_asset` 保存设备名称、类型、品牌、型号、配置、固定资产编码、
  采购日期、登记日期、序列号、MAC、位置和 IT 状态。
- `computer_assignment` 表示当前分配关系。
- `computer_assignment_history` 保存分配历史快照。
- 每台办公终端只能存在一条未归还的有效分配记录。
- `it_asset_status` 支持 `in_use`、`idle`、`repair`、`retired`、`lost`。
- Wi-Fi 和网口 MAC 在前端规范化为带短横线格式，并由数据库约束校验。

保存办公终端时还可能联动物资库存型号，产生库存扣减或回收动作。

#### IT 物资库存

库存分为三层：

```text
non_asset_type
  └── it_inventory_brand
        └── it_inventory_model
```

- `non_asset_type`：鼠标、键盘、显示屏、办公终端等类型。
- `it_inventory_brand`：类型下的品牌。
- `it_inventory_model`：品牌下的型号、数量、批次和办公终端配置。
- `inventory_movement_log`：增加/减少库存的流水。
- `inventory_purchase_log`：采购入库记录。
- `employee_monitor_usage`：人员使用的显示屏。
- `employee_non_asset_usage`：人员使用的鼠标、键盘等非资产设备。

库存数量必须保持非负。分配办公终端、保存显示屏或非资产设备、回收设备时，需要同步
处理库存数量和流水日志，不能只修改前端显示。

#### 操作日志

`audit_log` 保存动作类型、实体、旧值、新值、摘要、操作者、来源和时间。
业务变更优先使用现有快照差异逻辑生成日志，避免只记录“保存成功”而丢失具体变化。

#### 数据库备份

`database_backup` 保存备份文件名、路径、大小、SHA-256、类型、请求人和状态。
备份文件存放在 `BACKUP_DIR`，不通过静态文件服务暴露。

管理员可以在设置页：

- 手动创建备份。
- 开关每日自动备份。
- 设置每日时间。
- 设置保留天数。
- 输入当前密码后下载已完成的备份。

## 6. 前端扩展方法

### 6.1 新增页面

按以下顺序修改：

1. 在 `web/index.html` 的侧边栏增加 `data-action="navigate"` 和唯一的
   `data-page`。
2. 在 `pageMeta` 增加标题和说明。
3. 在页面渲染分发逻辑中增加新页面的 render 函数。
4. 为页面增加筛选、表单和操作按钮，并使用已有的 `data-action`、
   `data-form`、`data-filter` 约定。
5. 在全局事件委托中增加动作分支。
6. 如果页面需要数据库数据，补充 `/api/state` 或独立 API。
7. 检查管理员、操作员、只读用户三种权限下的按钮显示和后端拒绝行为。
8. 检查亮色、暗色和移动端布局。

不要为每个页面单独注册大量 DOM 事件。项目使用事件委托，动态渲染后的元素也应
通过 `data-*` 属性接入现有事件系统。

文本搜索框必须复用 `deferredTextFilterNames`、`filterSearchDraftValue` 和
`applyDeferredTextFilters`。输入事件只更新 `filterSearchDrafts`；列表重绘或 API 查询
只能由查询按钮、Enter 或明确的筛选提交动作触发。下拉框和日期字段可以即时应用，但不
得清空未提交的文本草稿。

### 6.2 新增业务字段

以“给办公终端增加一个字段”为例，完整修改链路应包括：

1. 新增编号递增的数据库迁移脚本，使用幂等的列存在检查。
2. 修改 `build_state_payload` 的 SQL JSON 映射。
3. 修改 `normalize_computers` 或相关归一化函数。
4. 修改 `build_sync_sql` 的 INSERT/UPDATE 字段。
5. 修改前端 `normalizeComputerRecord`。
6. 修改办公终端表单渲染函数和 `handleComputerSubmit`。
7. 修改详情展示、筛选和 Excel 导出（如果字段需要导出）。
8. 修改审计字段比较逻辑或字段标签。
9. 增加迁移、保存、刷新、备份恢复测试。

只修改表单而不修改数据库映射，会导致刷新后字段丢失；只修改数据库而不修改
归一化，会导致旧记录出现 `undefined`、空值或类型错误。

### 6.3 新增表单动作

推荐流程：

1. 在 `render*` 中输出 `data-action` 或 `data-form`。
2. 在事件委托中定位元素。
3. 先检查 `canWriteState()` 或 `isAdminUser()`。
4. 读取 `FormData`，规范化文本和数字。
5. 做前端即时校验，减少无效请求。
6. 更新 `state`。
7. 调用 `persistState(true)`。
8. 成功后 `render()`，失败时保留用户输入并显示 Toast。

前端校验不能代替后端校验。唯一键、外键、数量、权限和敏感操作必须在后端再次
验证。

### 6.4 新增系统设置

新增设置项时需要同步修改：

1. `database/bootstrap/19_auth_and_settings.sql` 或新的递增迁移，增加默认值和说明。
2. 后端 `/api/settings` 的 `allowed` 集合。
3. 后端的格式、范围和枚举校验。
4. 前端 `settingsState`、设置页渲染和提交处理。
5. 若影响备份或安全策略，补充审计日志。
6. `.env.example` 只添加部署级配置，不要把数据库设置和环境变量混淆。

设置值目前以字符串保存在 `system_setting.setting_value`，读取时必须显式转换为
布尔值、整数或时间格式。

### 6.5 新增主题样式

主题切换不应改变业务状态。新增颜色时：

1. 优先使用现有 CSS 变量。
2. 在亮色变量和 `html[data-theme="dark"]` 变量中同时定义。
3. 检查输入框、禁用按钮、表格 hover、弹窗和错误 Toast。
4. 修改 `web/index.html` 或 `web/app.js` 的资源查询版本，例如
   `app.js?v=YYYYMMDD-NN`，以便运维和浏览器明确加载新资源。
5. 用浏览器清缓存或无痕窗口验证首次加载和刷新后的主题保持。

## 7. 数据库开发和迁移规范

### 7.1 新增迁移

不要修改已经应用过的旧迁移来“修复历史”。新结构变更使用下一个未使用编号，
例如 `21_add_xxx.sql`。

推荐结构：

```sql
SET NAMES utf8mb4;

SET @column_exists := (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'computer_asset'
    AND column_name = 'new_field'
);

SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE computer_asset ADD COLUMN new_field VARCHAR(128) NULL AFTER model',
  'SELECT 1'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
```

迁移由客户端通过 `--database="$DB_NAME"` 或等效参数选定目标数据库；不要在新迁移
中加入固定的 `USE office_asset_mgmt`。

实际脚本应根据变更类型增加索引、外键、默认值、数据回填和回滚说明。
迁移执行前必须：

1. 备份当前数据库。
2. 在测试库或备份副本上执行。
3. 检查旧数据、空值、唯一键和外键冲突。
4. 记录执行时间、脚本版本和结果。
5. 再部署依赖该字段的新应用代码。

`update_from_gitea.sh` 会在发布应用容器前执行受跟踪迁移，并将迁移标准输出和错误输出
保留在部署服务日志中。旧业务库缺少 `schema_migration` 时，迁移器默认拒绝执行；只有在
已验证备份和历史结构后，管理员临时设置 `MIGRATION_ADOPT_BASELINE=legacy-20260813` 才能
接管基线。迁移失败会回滚应用代码，但不会反向撤销已经成功提交的数据库变更，因此每次
结构发布前仍必须完成备份和测试库验证。

### 7.2 视图和存储过程

当前视图包括：

- `v_org_unit_tree`
- `v_computer_asset_detail`
- `v_employee_office_devices`
- `v_employee_office_device_summary`
- `v_employee_org_tree`

当前存储过程包括：

- `sp_assign_computer`
- `sp_return_computer`
- `sp_set_non_asset_quantity`
- `sp_set_monitor_usage`

修改表结构后，应检查相关视图和存储过程的字段引用。当前应用的主要状态同步
逻辑在 `server.py` 中生成 SQL；不要误以为只更新存储过程就会自动改变 Web 行为。

### 7.3 约束和软删除

重要约束包括：

- 组织编码在同一父节点下唯一。
- 员工编号唯一。
- 办公终端设备名、固定资产编码、序列号唯一。
- 一个办公终端只能有一条有效分配。
- 库存数量不能小于零。
- 办公终端状态、员工状态、用户角色和备份状态使用固定枚举。
- 办公终端登记日期不能早于采购日期。
- 办公终端 MAC 地址必须是规定格式。

对已经被业务引用的组织、人员、库存品牌和型号，优先使用 `is_active=0` 或现有
归档流程，不要直接物理删除。物理删除可能破坏历史日志、分配历史和库存关联。

### 7.4 备份和恢复

命令行备份应包含：

```bash
mysqldump \
  --single-transaction \
  --skip-lock-tables \
  --routines \
  --events \
  --triggers \
  --default-character-set=utf8mb4 \
  --hex-blob \
  --no-tablespaces \
  "$DB_NAME"
```

包含存储过程或函数时，数据库账号可能需要 `SHOW ROUTINE` 权限。若备份出现
`SHOW ROUTINE` 或 routine 相关权限错误，应使用具备相应权限的专用备份账号或
管理员账号，不要直接删除存储过程选项掩盖问题。

恢复前：

1. 确认备份文件来自办公资产数据库，而不是 Gitea PostgreSQL 数据库。
2. 确认文件是纯 SQL 或正确解压后的 SQL。
3. 停止应用写入。
4. 在测试库先试恢复并检查表、视图、过程和数据量。
5. 恢复后检查 `/api/health`、关键表和登录。

恢复 `.sql.gz`：

```bash
gzip -dc /path/to/office_asset_mgmt.sql.gz \
  | sudo docker exec -i office-asset-mgmt-db-1 sh -lc \
    'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --binary-mode=1 --protocol=tcp -uroot'
```

出现以下错误时：

```text
ASCII '\0' appeared in the statement
```

通常说明传入的不是纯文本 SQL，常见原因是：

- 直接把 gzip、zip 或其他二进制文件传给了 `mysql`。
- 使用 PowerShell 重定向生成了 UTF-16 文件。
- 备份文件在传输或解压过程中损坏。
- 把错误的数据库文件交给了 MySQL 客户端。

应先确认文件类型和编码，再用 `gzip -dc` 解压。`--binary-mode=1` 只适用于确实
包含二进制内容的合法导入场景，不能替代解压、编码转换或文件修复。

## 8. Gitea 手动版本发布和更新

### 8.1 正常发布流程

本地修改完成后：

```powershell
cd <项目工作目录>
git status
git diff --check
git add .
git diff --cached --check
git commit -m "Describe the change"
git push origin main
```

当前远程仓库：

```text
ssh://git@code.example.internal:2222/organization/office-asset-mgmt.git
```

服务器 Webhook 服务收到 Gitea 的 `main` 分支 push 后，会校验：

- `X-Gitea-Signature` HMAC 签名。
- 仓库全名是否匹配。
- 分支是否为 `main`。
- commit SHA 是否为有效的 40 位 SHA。

校验通过后只记录事件并返回成功，不会调用部署脚本，也不会重启 Docker
容器。版本更新必须从设置页检查、选择并确认。

### 8.2 手动部署步骤

`deploy/scripts/update_from_gitea.sh` 的流程是：

1. 使用锁文件防止并发部署。
2. 检查部署目录、Git checkout 和运行时 `.env`。
3. `git fetch --prune origin main`。
4. 检查目标提交是否属于所选来源的 `main` 历史且不早于当前部署版本。
5. 清理未跟踪源文件，但保留被忽略的 `.env` 和备份。
6. 将工作树重置到管理员选择的目标提交。
7. 执行 `docker compose config --quiet`。
8. 构建 app 和 migrate 镜像。
9. 启动并等待数据库服务健康，再停止旧 app 容器，避免旧程序与结构迁移并发运行。
10. 使用一次性 `migrate` 容器执行受跟踪迁移；失败时将迁移输出保留在部署服务日志。
11. 仅在迁移成功后启动 app 容器并轮询 `/api/health`。
12. 迁移、构建、启动或健康检查失败时恢复之前的提交并重建旧 app 镜像。
13. 成功后更新控制服务重新加载当前工作目录中的代码，以便新版本筛选规则立即生效。

发布前仍必须完成数据库备份和测试库验证。已有业务库无迁移登记时，管理员必须先确认
旧库满足 `legacy-20260813`，并在 `.env` 临时设置 `MIGRATION_ADOPT_BASELINE=legacy-20260813`；
未设置时更新会安全失败并自动恢复旧应用代码。

### 8.3 设置页检查、选择和更新版本

调用链如下：

```text
设置页选择“发行版”或“Beta 版”，填写项目地址并点击“检查版本”
  -> POST /api/updates/check
  -> 后端校验 admin + CSRF + repositoryUrl + releaseChannel
  -> app 容器请求 host.docker.internal:9000/control/status?repositoryUrl=...&releaseChannel=...
  -> 宿主机服务 fetch 指定 GitHub/Gitea 地址；留空时 fetch origin/main
  -> 返回已发布 SemVer 列表

管理员选择版本号更高的已发布版本并点击“更新到所选版本”
  -> POST /api/updates/apply
  -> 后端校验发布版本 SHA、admin + CSRF + repositoryUrl + releaseChannel
  -> app 容器请求 host.docker.internal:9000/control/update
  -> 宿主机服务重新 fetch 同一项目地址并校验目标标签属于该 main 历史且版本号高于当前版本
  -> 排队执行 update_from_gitea.sh
```

宿主机控制接口使用独立的 `DEPLOY_CONTROL_TOKEN`，应用容器中对应
`UPDATE_CONTROL_TOKEN`。它与 Gitea Webhook Secret 不是同一个令牌，也不能暴露到
前端、Git 或普通日志。

更新状态：

- `up_to_date`：当前部署已经是最新发布版本。
- `update_available`：存在版本号更高的已发布版本，但尚未执行更新。
- `no_releases`：所选项目地址中没有符合 SemVer 的发布标签。
- `no_release_available`：没有高于当前部署版本的已发布版本。
- `queued`：管理员选择的版本已排队。
- `running`：部署正在执行。

部署服务还提供：

- `GET /healthz`：服务存活检查。
- `GET /control/status`：带控制令牌的版本状态查询，可带 `repositoryUrl` 和
  `releaseChannel` 查询参数。
- `POST /control/update`：带控制令牌并提交已发布版本对应的 `targetSha`，可同时提交
  `repositoryUrl` 和 `releaseChannel` 后排队更新。

检查响应中的 `availableVersions` 只包含所选项目地址中已合并到 `main` 的
SemVer 注释标签，并且标签对应提交必须包含匹配的 `VERSION_NOTES.md` 标题。发行版通道
仅显示稳定的 `vMAJOR.MINOR.PATCH` 标签；Beta 通道仅显示
`vMAJOR.MINOR.PATCH-beta.N` 标签，默认使用 Beta 通道。每项包含 `version`、`tag`、
`sha`、提交说明、发布时间、`releaseNotes`、`isCurrent`、`isLatest` 和
`isSelectable`。前端只允许选择 `isSelectable` 为真的版本。

`repositoryUrl` 支持 HTTPS、SSH 和内网 HTTP Git 地址，例如 GitHub HTTPS、Gitea HTTPS、
`ssh://git@host:port/owner/repo.git` 或 `git@host:owner/repo.git`。HTTP 只允许内网、
本机或内部域名；URL 不能包含账号密码、令牌、查询参数、片段、空白或本地文件协议。

更新控制服务必须使用 TLS。应用通过 `UPDATE_SERVICE_CA_FILE` 验证自签或内部 CA；
只有隔离的开发环境可以同时设置 `UPDATE_SERVICE_ALLOW_HTTP=true` 和 HTTP 地址。
控制令牌必须独立于 Gitea Webhook Secret，并只存在于服务器运行时配置中。

### 8.4 版本更新说明要求

每次准备推送到 Gitea 的可部署变更，必须同步修改
`VERSION_NOTES.md`，至少包含：

1. 日期、SemVer 版本标签和对应的提交范围或目标提交。
2. 功能、修复和安全变更摘要。
3. 是否包含数据库迁移。
4. 更新前备份要求、配置变更和回滚注意事项。

发行版本必须使用未占用的注释标签，格式为 `vMAJOR.MINOR.PATCH`；未特别说明的 Beta
版本使用 `vMAJOR.MINOR.PATCH-beta.N`。管理员选择版本前，应先阅读
`VERSION_NOTES.md` 中对应条目。数据库迁移不由
更新脚本自动执行，涉及结构变更时必须先完成评审和备份。

### 8.5 发布后验证

服务器上执行：

```bash
cd /opt/office-asset-mgmt
sudo docker compose \
  --env-file .env \
  -f compose.yaml \
  ps

curl --fail http://127.0.0.1:8000/api/health

sudo docker compose \
  --env-file .env \
  -f compose.yaml \
  logs --tail=100 app db

sudo journalctl \
  -u office-asset-gitea-webhook \
  -n 100 \
  --no-pager
```

如果只是前端资源变化，应同时检查浏览器页面源码中的 `app.js?v=...` 和
`styles.css?v=...` 是否已经更新。

## 9. 测试指南

### 9.1 提交前静态检查

在仓库根目录执行：

```bash
git diff --check
python -m py_compile server.py
```

如果修改了 SQL，至少做文本检查：

```bash
rg -n "CREATE TABLE|ALTER TABLE|CREATE VIEW|CREATE PROCEDURE|DROP TABLE|DROP VIEW" database
git status --short
```

不要把 `.env`、数据库导出、`.sql.gz`、日志、Excel 原始数据或临时文件加入提交。

### 9.2 API 冒烟测试

未登录时：

```bash
curl -i http://127.0.0.1:8000/api/health
curl -i http://127.0.0.1:8000/api/auth/bootstrap-status
```

登录后至少验证：

1. `/api/auth/session` 返回当前用户。
2. `/api/state` 能加载完整状态。
3. 管理员可读取设置和备份列表。
4. 操作员可保存业务状态但不能修改系统设置。
5. 只读用户的写接口返回 403。
6. 缺少或错误 CSRF Token 的写请求返回 403。
7. `/api/health` 返回数据库探针为 `1`，必需表数量为 `19/19`。

### 9.3 业务回归清单

每次涉及业务数据或状态同步的修改，至少测试：

- 新增、编辑、停用组织。
- 新增、编辑、离职归档和恢复员工。
- 新增、编辑、分配、归还办公终端。
- 新增库存类型、品牌、型号和采购入库。
- 库存不足时分配办公终端是否被拒绝。
- 显示屏和非资产设备增加、修改、回收。
- 库存增加/减少流水和采购日志。
- 操作日志旧值、新值、操作者和摘要。
- Excel 导出字段和中文编码。
- 连续输入筛选关键词和中文输入法组合输入时，列表、焦点和输入值不会在查询前变化；
  点击查询或按 Enter 后，结果数量与导出数据一致。
- 页面刷新后数据仍来自数据库。
- 亮色/暗色主题切换及浏览器刷新后的主题保持。

### 9.4 备份回归清单

- 管理员手动创建备份。
- 检查文件存在、大小大于零、SHA-256 记录一致。
- 非管理员不能创建或下载备份。
- 下载时输入错误密码会被拒绝。
- 解压并在测试数据库恢复。
- 恢复后检查表、视图、存储过程、用户登录和 `/api/health`。
- 自动备份开关、时间和保留天数生效。

### 9.5 更新回归清单

- Gitea 中推送一个测试提交。
- 确认 Webhook 日志显示已接收但未自动部署。
- 设置页点击“检查版本”。
- 确认返回 `update_available` 和可选发布版本列表。
- 选择目标版本并点击“更新到所选版本”。
- 确认返回 `queued`，观察更新服务日志。
- 等待 app、db 变为 healthy。
- 检查页面资源版本和新功能。
- 再次检查版本，确认当前版本和目标提交一致。

## 10. 常见问题和排查

### 10.1 应用无法连接数据库

先确认 Compose 状态：

```bash
sudo docker compose \
  -f /opt/office-asset-mgmt/compose.yaml \
  --env-file /opt/office-asset-mgmt/.env \
  ps
```

再确认 app 容器内的 DNS 和连接参数：

```bash
sudo docker exec office-asset-mgmt-app-1 getent hosts db

sudo docker exec office-asset-mgmt-app-1 sh -lc \
  'MYSQL_PWD="$DB_PASSWORD" mysql --protocol=tcp -h"$DB_HOST" \
   -P"$DB_PORT" -u"$DB_USER" "$DB_NAME" -NBe "SELECT 1;"'
```

不要将应用容器的 `DB_HOST` 写成 `127.0.0.1`。

### 10.2 `/api/health` 返回 503

重点检查：

- MySQL 容器是否 healthy。
- `DB_PASSWORD` 是否正确。
- `DB_NAME` 是否正确。
- `app_state_revision` 是否存在。
- 必需的 19 张表是否全部存在。
- 数据库初始化是否中途失败。

查看日志：

```bash
sudo docker compose \
  -f /opt/office-asset-mgmt/compose.yaml \
  --env-file /opt/office-asset-mgmt/.env \
  logs --tail=200 app db
```

### 10.3 数据库初始化脚本没有重新执行

这是 MySQL 官方镜像的正常行为：只有空数据卷才会执行
`/docker-entrypoint-initdb.d`。已有数据卷升级必须单独执行经过审核的迁移。

不要直接执行：

```bash
docker compose down -v
```

该命令会删除 Docker 管理的数据库卷，只有在备份已验证且明确要清空环境时才能用。

### 10.4 Gitea push 后没有自动更新

这是预期行为。当前 push webhook 已取消自动部署。需要：

1. 在设置页点击“检查版本”。
2. 选择版本号更高的已发布版本。
3. 点击“更新到所选版本”。
4. 检查更新服务日志是否出现排队或失败。

如果启用了 push Webhook，仍需检查：

```bash
sudo systemctl status office-asset-gitea-webhook
sudo journalctl -u office-asset-gitea-webhook -n 200 --no-pager
sudo curl --fail \
  --cacert /opt/office-asset-mgmt/secrets/update-service/update-control-ca.pem \
  --resolve host.docker.internal:9000:127.0.0.1 \
  https://host.docker.internal:9000/healthz
```

再确认：

- Gitea Webhook Secret 与宿主机一致。
- Webhook 仓库全名和分支为 `main`。
- 部署用户可以通过 SSH 读取 Gitea 仓库。
- Gitea SSH 端口为 `2222`。
- `/opt/office-asset-mgmt/.env` 存在且权限正确。
- 部署用户具备 Docker Compose 执行权限。

### 10.5 手动版本更新返回未授权或请求失败

检查应用容器的 `UPDATE_SERVICE_URL`、宿主机 Webhook 服务监听地址和
`UPDATE_CONTROL_TOKEN`/`DEPLOY_CONTROL_TOKEN` 是否成对一致。

控制令牌只允许出现在服务器运行时环境文件中。不要把令牌复制到浏览器控制台、
前端 JavaScript、Gitea 仓库或聊天记录。

### 10.6 页面仍显示旧版本

执行以下步骤：

1. 确认 Gitea `main` 已包含最新 commit。
2. 确认部署日志显示该 commit 已发布。
3. 确认 app 容器已重新创建。
4. 检查 `web/index.html` 中 JS/CSS 查询版本。
5. 使用强制刷新或无痕窗口验证。

后端对 HTML、JS 和 CSS 设置了禁止缓存响应头，但资源查询版本仍用于排查和
浏览器/CDN 场景。

## 11. 开发注意事项

### 11.1 安全

- 不提交 `.env`、密码、令牌、私钥、业务 SQL、备份和日志。
- Web 应用使用独立的 MySQL 账号，不使用 root。
- 不把 MySQL 3306 直接暴露到局域网，必要时使用 SSH 隧道。
- 生产环境通过 HTTPS 时启用 `AUTH_COOKIE_SECURE=true`。
- 所有写 API 都要后端校验权限和 CSRF。
- 文件下载必须校验登录账号当前密码，并限制在备份目录内。
- 更新控制接口不应暴露到公网。

### 11.2 数据一致性

- 保存完整状态前使用数据库锁和事务。
- 使用现有 `sql_quote`、`text_value`、`sql_int` 等辅助函数处理值。
- 不直接拼接未经校验的用户输入。
- 新增业务记录时同步考虑软删除、审计日志、历史表、库存流水和外键。
- 关联删除前确认是否会影响历史记录。
- 不把当前 Docker 容器 IP 写入配置，使用 Compose 服务名 `db`。

### 11.3 编码和文件

- SQL 和 Web 源码统一使用 UTF-8。
- 导入 SQL 前先识别 gzip、UTF-16、UTF-8 和纯文本格式。
- PowerShell 不要使用会把命令输出保存为 UTF-16 的重定向方式生成 SQL。
- 备份文件使用严格权限并保存到服务器之外的独立存储。

### 11.4 Git

- 功能修改和数据库迁移尽量拆分为清晰 commit。
- commit 前执行 `git diff --check`。
- 不要把生成文件、临时测试文件和运行时配置加入提交。
  - 以后统一推送到当前 GitHub 远程主仓库。
- 生产服务器工作树由部署脚本管理，不要在服务器直接编辑源代码。

## 12. 新功能发布检查表

### 代码

- [ ] 明确修改了后端、前端、数据库或部署中的哪些层。
- [ ] 新字段已完成数据库到前端、前端到数据库的双向映射。
- [ ] 写操作有角色和 CSRF 校验。
- [ ] 业务变更有审计日志。
- [ ] 旧数据和空值有兼容处理。
- [ ] 亮色、暗色和移动端界面已检查。

### 数据库

- [ ] 使用新编号迁移，没有修改历史迁移。
- [ ] 迁移脚本具备幂等性或有明确的一次性执行说明。
- [ ] 已备份并在测试库验证。
- [ ] 已检查视图、存储过程、索引和外键。
- [ ] 已准备回滚或恢复方案。

### 测试

- [ ] `git diff --check`
- [ ] `python -m py_compile server.py`
- [ ] `python -m unittest discover -s tests -v`
- [ ] `/api/health` 正常
- [ ] 登录、角色、CSRF 正常
- [ ] 主要业务流程正常
- [ ] 备份创建和恢复验证
- [ ] Gitea 手动版本更新验证

### 发布

- [ ] `.env` 和运行时令牌没有进入 commit。
- [ ] 已推送 Gitea `main`。
- [ ] 已创建未占用的 SemVer 注释标签并推送到 Gitea。
- [ ] Gitea Releases 已补充对应版本说明和附件。
- [ ] 已确认 Webhook 不会自动部署，并完成手动版本更新验证。
- [ ] app、db 均 healthy。
- [ ] 页面已加载新资源版本。
- [ ] 数据库迁移已按顺序手动执行。
- [ ] 已记录发布 commit、迁移脚本和验证结果。

## 14. 认证页面显示问题修复记录

### 14.1 问题现象

当登录会话过期后，系统会自动切换回登录页。如果此时登录页上方出现了较大的
空白区域，继续向下滚动还可以看到之前的系统主页，说明登录页和已退出的主应用
同时参与了页面布局。

该问题不会删除或修改数据库业务数据，但会造成页面显示混乱，也可能让用户误以为
旧会话仍然有效。

### 14.2 根因

认证流程在 `renderAuthScreen` 和 `updateAuthenticatedChrome` 中通过
`element.hidden = true/false` 切换 `#authRoot` 与 `#appShell`。原有样式同时为
`.app-shell` 设置了 `display: flex`。

浏览器默认样式通常会隐藏带有 `hidden` 属性的元素，但组件样式的 `display` 规则
可能覆盖这个默认行为。于是，虽然 DOM 中的 `appShell.hidden` 已经是 `true`，
旧主页仍然显示在登录页后面。

### 14.3 修复内容

本次修复包括：

1. 在 `web/styles.css` 增加全局 `[hidden] { display: none !important; }`。
2. 保留认证代码对 `hidden` 属性的统一管理，不在各个页面中重复设置内联显示样式。
3. 将 `web/index.html` 中的 JS/CSS 资源版本更新为 `20260807-01`，避免浏览器继续
   使用旧样式。
4. 认证失败、会话过期、主动退出和重新登录仍然使用同一套显示状态切换流程。

### 14.4 修改隐藏状态时的注意事项

- 需要隐藏元素时使用 `element.hidden = true`，需要显示时先设置
  `element.hidden = false`。
- 不要只依赖组件自身的 `display` 样式判断认证状态。
- 新增页面或弹窗如果使用 `hidden`，必须确认全局 `[hidden]` 规则不会被后续 CSS
  覆盖。
- 认证状态切换后应检查页面滚动高度，未显示的主应用不应继续占用文档高度。

### 14.5 回归测试

至少验证以下流程：

1. 未登录直接打开页面，只显示登录面板，页面不应出现主应用导航。
2. 登录成功后只显示主应用，不应保留登录面板。
3. 会话过期或模拟 API 返回 401 后，只显示登录面板，页面不应出现旧主页。
4. 退出登录后刷新页面，只显示登录面板。
5. 重新登录后恢复主应用，页面顶部和滚动高度正常。
6. 亮色、暗色、桌面端和移动端均检查。

## 15. 参考文件

- [项目简介和快速启动](../../README.md)
- [Docker Compose 部署](../deployment/docker.md)
- [Gitea 和手动版本更新](../deployment/gitea.md)
- [MySQL 连接、备份和恢复](../deployment/mysql-connection.md)
- [Ubuntu 原生部署](../deployment/ubuntu.md)
- [应用和 MySQL 编排](../../compose.yaml)
- [后端、API 和备份实现](../../server.py)
- [前端状态、渲染和交互](../../web/app.js)
- [核心表结构](../../database/bootstrap/01_schema.sql)
- [按指定版本发布脚本](../../deploy/scripts/update_from_gitea.sh)
- [Webhook 和手动版本更新控制服务](../../deploy/gitea/deploy_webhook.py)
- [网络安全检查和生产运维注意事项](../security/review.md)
- [每次版本发布的更新说明](../../VERSION_NOTES.md)
