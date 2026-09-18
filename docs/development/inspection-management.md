# 机房巡检管理

巡检模块只覆盖**机房、弱电间和它们下面的机柜**，不包含办公区终端和 IT 物资仓库。
一次巡检的完整流程是：选择模板与对象 → 开始巡检 → 逐项记录结论 → 提交 → 输出整张巡检表。

## 数据模型

迁移文件：`database/migrations/20260918_001_inspection_management.sql`（只新增对象，不改历史数据）。

| 表 | 用途 |
| --- | --- |
| `asset_site` | 机房 / 弱电间，`site_type` 取 `server_room` 或 `weak_room` |
| `asset_rack` | 机柜，归属某个 `asset_site`，含高度（1-100U）与上下方向 |
| `inspection_template` | 巡检模板，`site_type` 取 `server_room`、`weak_room` 或 `both` |
| `inspection_template_item` | 模板事项：类别、事项、检查方法、取值类型、单位、正常范围、是否必填 |
| `inspection_task` | 一次巡检：任务号、模板快照、对象快照、执行人、状态与统计 |
| `inspection_task_item` | 逐项记录：事项快照、结论、实测值、说明、检查人与检查时间 |

关键规则：

1. **快照**：开始巡检时把模板事项复制进 `inspection_task_item`，之后修改模板不影响已开始的巡检表；
2. **对象二选一**：任务要么指向一个机房/弱电间（覆盖其下机柜），要么指向单个机柜；
   该约束由服务层校验，因为 MySQL 不允许在 `ON DELETE SET NULL` 外键引用的列上再建 `CHECK`；
3. **模板匹配**：模板适用对象与巡检对象类型不一致时拒绝开始巡检；
4. **异常必须说明**：结论为异常时，填写与提交两个环节都会校验说明非空；
5. **提交即定稿**：提交后任务与明细只读，不能继续修改，也不能作废；
6. **手动发起**：没有周期计划、没有自动派单，只能由有权限的账号点击“开始巡检”。

迁移会写入两张标准模板：`XJ-SERVER-ROOM`（机房巡检，16 项）与 `XJ-WEAK-ROOM`（弱电间巡检，14 项）。

## 权限与审计

权限模块 `inspection_management`，动作 `view`、`create`、`update`、`delete`、`export`。
管理员角色在迁移中默认获得 `view`、`create`、`update`、`export`。后端逐项校验权限，
前端隐藏按钮不构成安全边界。

审计动作写入 `audit_log`：

| 动作 | 触发点 |
| --- | --- |
| `inspection_site_created` / `inspection_site_updated` | 维护机房、弱电间 |
| `inspection_rack_created` / `inspection_rack_updated` | 维护机柜 |
| `inspection_template_created` / `inspection_template_updated` | 维护模板与事项 |
| `inspection_started` | 开始巡检 |
| `inspection_submitted` | 提交巡检表 |
| `inspection_voided` | 作废未提交的巡检任务 |

## 接口

```text
GET    /api/inspection/sites                 POST   /api/inspection/sites
PUT    /api/inspection/sites/{id}
GET    /api/inspection/racks                 POST   /api/inspection/racks
PUT    /api/inspection/racks/{id}
GET    /api/inspection/templates             POST   /api/inspection/templates
GET    /api/inspection/templates/{id}        PUT    /api/inspection/templates/{id}
GET    /api/inspection/tasks?status=         POST   /api/inspection/tasks
GET    /api/inspection/tasks/{id}
POST   /api/inspection/tasks/{id}/items/{itemId}/check
POST   /api/inspection/tasks/{id}/submit
POST   /api/inspection/tasks/{id}/void
```

`POST /api/inspection/tasks` 支持 `Idempotency-Key`：同一键与同一请求体重复提交返回同一个任务，
键与请求体不一致时返回冲突。所有写接口都需要 CSRF 令牌。

## 前端

侧栏“机房巡检”对应 `data-page="inspection"`，页面分三个分区：

| 分区 | 内容 |
| --- | --- |
| 巡检任务 | 任务列表、状态筛选、开始巡检、继续巡检、查看巡检表、作废 |
| 巡检模板 | 模板与事项维护（类别、检查方法、取值类型、单位、正常范围、是否必填） |
| 机房与机柜 | 机房/弱电间与机柜的维护 |

执行页按事项逐行输出：每行三个结论按钮（正常 / 异常 / 不适用）、实测值输入、说明输入。
点击结论按钮即保存，异常项缺少说明时前端提示并阻止保存，后端同样拒绝。
底部提供“异常情况与处理建议”，留空时提交会自动汇总异常项说明。

提交后可“导出巡检表”（Excel 两个页签：巡检表摘要 + 巡检明细）或“打印”（浏览器打印视图，
带巡检人 / 复核人签字栏）。

### 扫码开检

打开形如 `/#inspection?rack=<机柜编码>` 的链接会自动切到巡检页并预选该机柜，
配合机柜上的二维码即可扫码开检。预选只在编码存在时生效，不存在时不弹窗。

## 验证

```powershell
# 结构回归
python -m unittest tests.test_regressions

# 端到端回归（需要一个已应用全部迁移的一次性数据库）
$env:DB_PASSWORD = "<password>"
$env:DB_NAME = "office_asset_mgmt_codex_inspection_20260918"
$env:MYSQL_BIN = "mysql"
python .\tests\integration\qa_inspection_regression.py
```

端到端脚本覆盖：模板读取、机房与机柜创建、开始巡检快照、幂等重复提交、异常项必须填说明、
未完成不可提交、提交后只读、模板与对象不匹配被拒绝、审计留痕、只读账号被拒绝。

健康检查 `/api/health` 的表数量门槛已从 57 提升为 63，包含巡检相关表。

## 本版不做的事

- 不生成周期巡检计划，也不自动派单；
- 不上传照片，`inspection_task_item` 不保存附件；
- 异常项不自动创建工单，需人工在工单模块登记；
- 巡检对象不包含办公区设备与仓库；
- 机房与机柜暂不参与资产范围（组织数据范围）过滤，统一按巡检权限控制。
