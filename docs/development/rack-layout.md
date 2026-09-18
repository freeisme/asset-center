# 机柜视图

机柜视图是独立模块（权限模块 `rack_layout`）：把台账里的设备放到机柜的具体 U 位，
用于机柜正面/背面布局的查看与编辑。它和「机房巡检」共用 `asset_site`、`asset_rack` 两个对象，
但职责分开——巡检管"检查什么"，机柜视图管"设备装在哪"。

## 数据模型

迁移文件：`database/migrations/20260918_002_rack_layout.sql`（只新增表与权限）。

| 字段 | 说明 |
| --- | --- |
| `rack_id` | 归属机柜（`asset_rack`，删除机柜级联删除位置记录） |
| `source_kind` | `computer`＝办公终端台账设备；`custom`＝手工登记（可来自 IT 物资型号） |
| `computer_id` | 办公终端 ID，唯一索引保证一台设备只在一个机柜上架 |
| `inventory_model_id` | 来自 IT 物资型号时记录型号 ID，仅作追溯，不扣库存 |
| `display_name` / `brand_model` | 图上显示的名称与品牌型号 |
| `category` | 机柜内设备类型（server、network、patch-panel、power、storage、kvm 等 12 类） |
| `position_u` / `u_height` | 起始 U 位（从下往上编号）与占用高度（整数 U，1-50） |
| `face` | `front`、`rear` 或 `both`（整机深度） |
| `status_snapshot` / `asset_code` / `serial_number` / `owner_label` | 上架时的台账快照；读取时优先显示台账实时值 |
| `is_active` | 下架为软删除，保留审计痕迹 |

### 位置规则

1. 前后面板各自成层：同一 U 位上，前后面板设备可以共存；`both`（整机深度）独占该 U 位；
2. 越界拒绝：`position_u + u_height - 1` 必须落在机柜高度内；
3. 重复上架拒绝：同一台办公终端只能出现在一个机柜位置；
4. 已报废归档的办公终端不能上架；
5. 占用统计按**物理 U 行**去重计算，前后面板重叠不会重复计数。

服务的写操作都在事务内完成，并写入 `audit_log`：`rack_placement_created`、
`rack_placement_updated`、`rack_placement_removed`。上架与下架都不会改变库存和资产状态。

## 接口

```text
GET  /api/rack-layout/racks                          机柜列表（含占用与设备数）
GET  /api/rack-layout/racks/{rackId}                 机柜详情与全部位置
GET  /api/rack-layout/available?keyword=             未上架设备（办公终端 + IT 物资型号）
POST /api/rack-layout/racks/{rackId}/placements      上架（支持 Idempotency-Key）
PUT  /api/rack-layout/placements/{id}                移动 / 改高度 / 改面板 / 改名
POST /api/rack-layout/placements/{id}/remove         下架（软删除，写原因）
```

权限：`view`、`create`、`update`、`delete`、`export`；管理员角色默认全开。
读接口按组织数据范围过滤机柜，写接口校验机柜与设备所属组织。

## 前端

v2.11.0 起「机柜视图」由 **Vue 页面**渲染（`frontend/src/views/RackLayoutView.vue`，
路由 `/rack-layout`，在 `frontend/src/navigation.ts` 的 `NAV_ITEMS` 与
`frontend/src/router/index.ts` 的 `MIGRATED_VIEWS` 中登记）；旧前端里的同名实现已删除，
避免两套代码并存。左侧是机柜图，右侧是属性面板与未上架设备池：

- 点设备选中，右侧改名称、起始 U 位、占用高度、设备类型、安装面板与备注；
- 直接拖动设备换 U 位，吸附到整数 U，冲突时红框提示并拒绝保存；
- 点右侧未上架设备后再点机柜空位上架，默认 1U；
- 前面板 / 后面板切换：整机深度设备照常显示，非当前面板设备置灰；
- 导出设备清单（Excel）与打印机柜图（逐 U 打印视图）；
- 「发起巡检」按当前机柜跳到巡检模块并预选该机柜。

端口、线缆与拓扑图见[设备面板与网络拓扑](device-panel-and-topology.md)。

## 验证

```powershell
python -m unittest tests.test_regressions

$env:DB_PASSWORD = "<password>"
$env:DB_NAME = "office_asset_mgmt_codex_rack_layout_20260918"
$env:MYSQL_BIN = "mysql"
python .\tests\integration\qa_rack_layout_regression.py
```

端到端脚本覆盖：机柜列表占用统计、未上架设备来源、上架与幂等重复提交、同面重叠拒绝、
前后面板同位共存、越界拒绝、移动与改高度的二次校验、下架后重新出现在未上架列表、
审计留痕、只读账号被拒绝。

健康检查 `/api/health` 的必需表数量为 64。

## 本版不做的事

- 不做 0.5U 与半宽设备（当前按整数 U 建模）；
- 不生成 PNG/SVG 图片，只提供打印机柜图与设备清单导出；
- 不绘制设备面板图片与端口/连线（Rackula 的 `cables`、`interfaces` 属于后续阶段）；
- IT 物资按"型号"登记，不按序列号追踪，也不在上架时扣减库存；
- 多机柜并排与整列视图属于后续阶段。
