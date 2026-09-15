# 办公资产与 IT 服务管理

本仓库是面向内部 IT 资产运营和 ITIL 服务管理的单体 Web 系统。当前稳定版说明见 `VERSION_NOTES.md`。仓库不包含业务数据、数据库备份、账户密码、令牌或证书。

## 模块

- 办公终端、IT 物资、人员、组织和资产关系。
- 入库、领用、归还、设备分配与设备归还的独立命令和独立事务。
- 细粒度中文权限、数据范围、审计日志和数据库备份。
- 工单、服务表单、工作流、多级审批、SLA、变更、问题和知识库。
- 同步暂存、中文数据质量审计和设备流转时间线。
- 物资流转备注采用追加式更正，原始事务记录保留，更正原因和操作审计可追溯。
- 多仓库库存：仓库绑定组织，可配置负责人、联系方式、地址、启停和备注；入库、调整、领用、归还及回收均按仓库独立记账，仓库间调拨使用独立事务、幂等键和审计日志。

`GET /api/state` 仅保留为兼容读取接口。`PUT /api/state` 已退役并返回 `405 STATE_WRITE_RETIRED`；业务写入必须调用资源接口或命令接口。

## 仓库结构

```text
.
├── server.py                    # HTTP 应用入口
├── office_asset/                # 领域服务、仓储、权限和范围控制
├── web/                         # 原生 HTML、CSS 和 JavaScript 前端
├── database/
│   ├── bootstrap/               # 仅用于空库初始化的历史 SQL
│   ├── migrations/              # 可追踪、不可修改的增量迁移
│   └── manual/                  # 不由部署流程自动执行的维护 SQL
├── tools/                       # 迁移与 MySQL 辅助工具
├── scripts/windows/             # Windows 部署脚本
├── tests/
│   ├── integration/             # 接口安全与权限回归
│   └── test_regressions.py      # 单元和结构回归
├── deploy/                      # Docker、Nginx、systemd、备份和更新脚本
├── docs/                        # 开发、部署、安全和发布文档
├── compose.yaml                 # MySQL、迁移器和应用编排
└── VERSION_NOTES.md             # 版本说明，供更新服务读取
```

根目录的 `deploy.ps1`、`migration_runner.py`、`run_mysql_utf8.py` 和 `qa_security_regression.py` 是兼容入口。现有脚本和自动化命令可以继续使用；新脚本和文档应优先引用归类后的目录。

## 快速开始

### Windows

```powershell
.\scripts\windows\deploy.ps1 -User root -Database office_asset_mgmt
```

为兼容旧命令，也可使用：

```powershell
.\deploy.ps1 -User root -Database office_asset_mgmt
```

部署脚本只对空库执行 `database/bootstrap/` 的历史初始化文件，随后登记 `legacy-20260813` 基线并执行 `database/migrations/`。数据库名只能包含字母、数字和下划线。

### Docker Compose

```bash
cp .env.example .env
# 设置 DB_PASSWORD 和 MYSQL_ROOT_PASSWORD；生产环境保留 AUTH_COOKIE_SECURE=true
docker compose up -d --build
```

Compose 会在数据库健康后运行一次迁移器；迁移成功后才启动应用。

## 已有数据库升级

1. 先使用部署账户创建并验证数据库备份：

```bash
sudo -u officeasset-deploy -H bash \
  /opt/office-asset-mgmt/deploy/scripts/backup_compose_database.sh
```

备份默认写入 `/home/officeasset-deploy/backups/office-asset-mgmt/`，不写入可能由
root 管理的应用目录。脚本会生成 `.sql.gz` 备份及同名 `.sha256` 校验文件。

2. 确认数据库已经包含 `legacy-20260813` 的核心业务与认证结构。`v2.0.3` 及以后版本会以首条增量迁移补齐旧版缺少的认证启动保护表和会话来源字段，无需手工执行历史重建 SQL。
3. 仅当旧库没有 `schema_migration` 时，在部署服务器 `.env` 中临时设置：

```dotenv
MIGRATION_ADOPT_BASELINE=legacy-20260813
```

迁移器会先检查旧库关键表，再登记基线并执行 `database/migrations/`。未设置该值时，
已有业务库会拒绝更新，避免自动重放历史初始化 SQL。

4. 从设置页更新到已验证版本，或按部署文档执行受控更新。升级成功后删除
`MIGRATION_ADOPT_BASELINE`，再执行一次迁移校验。

Windows 环境可在已备份且确认基线后使用：

```powershell
.\scripts\windows\deploy.ps1 -User root -Database office_asset_mgmt -AdoptExistingBaseline
```

以后版本只执行 `database/migrations/*.sql`。不要对已有业务库直接运行 `database/bootstrap/01_schema.sql`，该文件含有重建对象的逻辑。

`v2.0.17` 首次升级会创建 `根组织 / 仓库1`（仅在系统不存在根组织或默认仓库时创建），
并将原有汇总库存迁入该默认仓库。历史物资流转记录不回写来源仓库，因此历史记录保持原样；
之后所有新增入库、领用、归还、回收、调整和调拨都会记录仓库。默认仓库可修改或停用，但不能删除。
回退此版本前需先确认没有依赖仓库字段的新业务记录；数据库迁移本身不自动回滚。

`v2.1.0` 不新增数据库迁移。办公终端新增“自定义品牌型号”和“从仓库库存登记”两种模式：
自定义模式不读取或扣减库存；仓库模式按所选仓库的库存电脑批次登记，并在同一事务中扣减库存。
仓库登记时设备资料仍可编辑，库存扣减只以选定库存型号为准；库存不足时不会创建设备。
分配、回收和离职回收会按组织层级选择可访问的启用仓库，设备分配完成后不再绑定仓库，
但流转记录会保留来源或目标仓库。编辑办公终端只更新设备资料，不会重复调整库存。
同型号不同购置日期的库存批次会在选择项中分别显示。

完整规则见 [数据库迁移说明](docs/development/migrations.md)。

## 本地测试沙盒

```powershell
git clone https://github.com/freeisme/asset-center.git <项目目录>
cd <项目目录>
.\scripts\windows\deploy.ps1 -User root -Database office_asset_mgmt_test

$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3306"
$env:DB_NAME = "office_asset_mgmt_test"
$env:DB_USER = "root"
$env:DB_PASSWORD = "<仅保存在本机环境变量中的密码>"
$env:MYSQL_BIN = "<MySQL 客户端完整路径>"
$env:SERVER_HOST = "127.0.0.1"
$env:SERVER_PORT = "8011"
python .\server.py
```

测试结束后停止服务并仅删除测试数据库，不要删除生产数据库或提交测试数据。

## 验证

```powershell
python -m compileall -q server.py office_asset tools tests migration_runner.py run_mysql_utf8.py qa_security_regression.py
python -m unittest discover -s tests -v
python .\tools\migration_runner.py --database office_asset_mgmt_test --verify
python .\tests\integration\qa_security_regression.py
node --check web\app.js
```

## 文档

- [文档索引](docs/README.md)
- [开发指南](docs/development/guide.md)
- [数据库迁移](docs/development/migrations.md)
- [Docker 部署](docs/deployment/docker.md)
- [Ubuntu 原生部署](docs/deployment/ubuntu.md)
- [Gitea 和更新服务](docs/deployment/gitea.md)
- [GitHub 发布流程](docs/releases/github-release.md)
- [安全检查](docs/security/review.md)
- [前端和接口说明](web/README.md)
- [GitHub Wiki](https://github.com/freeisme/asset-center/wiki)

## 安全要求

- 不提交 `.env`、数据库导出、备份、日志、Excel/CSV 业务数据、账户、密码、访问令牌或私钥。
- 生产环境通过 HTTPS 访问并保持 `AUTH_COOKIE_SECURE=true`。
- 所有权限和数据范围必须由服务端验证；隐藏前端菜单不是授权控制。
- 升级前备份，迁移后执行校验和权限回归测试。
