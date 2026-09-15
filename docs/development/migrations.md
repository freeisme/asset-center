# MySQL 迁移策略

## 基本规则

1. `database/bootstrap/` 中的 SQL 是空库初始化材料，可能重建对象，不能用于生产库的原地升级。
2. 每个生产结构变化都必须在 `database/migrations/` 新增一个不可变文件，命名为 `YYYYMMDD_NNN_description.sql`。
3. `tools/migration_runner.py` 在 `schema_migration` 中记录迁移版本、SHA-256 校验和、文件名和执行时间。
4. 已登记迁移不得修改。任何修复必须创建新的迁移文件。
5. 迁移文件不得固定 `USE database_name`。两个历史 `20260814_*` 迁移在执行时会去除旧的 `USE` 行，但校验和仍基于原文件。
6. `/api/state` 仅保留只读兼容用途；所有业务写操作使用资源接口或命令接口和独立事务。
7. 对已有业务库的基线接管只能显式指定 `legacy-20260813`。迁移器会检查旧库的组织、人员、资产、审计、认证、库存和备份关键表；校验失败时不会创建迁移登记表。
8. 如果已发布迁移在特定 MySQL 版本上不兼容，新增迁移必须按实际执行顺序放在问题迁移之前；不得修改问题迁移或复用其版本号。

## 迁移清单

| 文件 | 内容 |
| --- | --- |
| `20260814_001_itil_governance.sql` | ITIL 治理基础：工单、审批、SLA、变更、问题和知识库结构。 |
| `20260814_002_command_atomicity.sql` | 入库、领用、归还、分配等命令的原子性和幂等支撑。 |
| `20260817_001_access_control.sql` | 角色、模块、操作权限、用户覆盖权限和数据范围。 |
| `20260818_001_access_control_collation.sql` | 角色代码与历史账户表的排序规则兼容。 |
| `20260818_002_service_management.sql` | 服务表单、流程、通知、审批、SLA、变更、问题和知识库。 |
| `20260818_003_permission_chinese.sql` | 内置角色和权限模块名称中文化，不改变内部权限代码。 |
| `20260818_004_role_category.sql` | 管理员、普通用户和自定义角色类别。 |
| `20260819_001_form_designer_and_identity.sql` | 表单设计器与账号绑定组织人员后的自动预填。 |
| `20260819_002_access_control_hardening.sql` | 权限和数据范围边界加固。 |
| `20260819_003_form_workflow_binding.sql` | 表单与流程、审批节点绑定。 |
| `20260819_004_workflow_role_collation.sql` | 工作流角色关联的排序规则兼容。 |
| `20260820_001_computer_movement_history.sql` | 办公终端设备流转记录和详情时间线。 |
| `20260902_001_inventory_warehouses.sql` | 组织归属仓库、仓库库存、库存调拨及历史库存向默认仓库的兼容迁移。 |
| `20260907_000_usage_inventory_model_identity_compatibility.sql` | MySQL 8.4 兼容：为带级联外键的人员物资表先创建 `VIRTUAL` 库存型号键和新唯一索引。 |
| `20260907_001_usage_inventory_model_identity.sql` | 按库存型号/购买批次区分人员物资记录，兼容自定义物资的唯一性。 |
| `20260909_001_individual_inventory_usage_records.sql` | 取消人员同型号领用记录的唯一约束，让每次领用保留独立使用记录和审计链。 |

## 新数据库

```powershell
.\scripts\windows\deploy.ps1 -User root -Database office_asset_mgmt
```

部署脚本只在确认空库时执行 `database/bootstrap/`，登记 `legacy-20260813`，再执行所有未登记的 `database/migrations/` 文件。Docker 的空库初始化也登记相同基线。

## 已有数据库接入

对于已有业务表但没有 `schema_migration` 的实例：

1. 创建且验证备份。
2. 确认实例已达到 `legacy-20260813` 历史结构和安全基线。
3. 显式采用基线：

```powershell
.\scripts\windows\deploy.ps1 -User root -Database office_asset_mgmt -AdoptExistingBaseline
```

脚本不会重放历史重建 SQL。基线检查失败时应恢复备份或先补齐历史版本，而不是绕过校验。

Docker 已有数据卷缺少登记表时会使 `migrate` 失败。确认备份和基线后，可以临时在
部署目录 `.env` 设置：

```dotenv
MIGRATION_ADOPT_BASELINE=legacy-20260813
```

下一次受控更新会校验基线、登记 `schema_migration` 并执行增量迁移。也可以在已检出的
v2.0.2 或更高版本中手动执行：

```bash
docker compose run --rm --entrypoint python migrate \
  tools/migration_runner.py --database office_asset_mgmt --mark-baseline legacy-20260813
docker compose up -d
```

成功后必须从 `.env` 删除 `MIGRATION_ADOPT_BASELINE`，避免以后升级误用基线接管模式。

## 校验

```powershell
$env:DB_PASSWORD = "<本机数据库密码>"
python .\tools\migration_runner.py --database office_asset_mgmt --verify
```

校验失败的含义：

- `Pending migrations`：存在尚未应用的版本。
- `checksum mismatch`：已应用文件被修改，必须恢复原文件并另建迁移。
- `missing required tables`：旧库不符合 `legacy-20260813`，不得采用基线；应从备份恢复或先完成历史升级。
- MySQL 错误：立即停止升级，从备份和 SQL 兼容性开始排查。

### MySQL 8.4 生成列兼容说明

`employee_non_asset_usage.inventory_model_id` 和
`employee_monitor_usage.inventory_model_id` 已由历史结构声明为带级联行为的外键。
MySQL 8.4 拒绝在这些列上直接添加 `STORED` 生成列，可能返回
`ERROR 1215 (HY000): Cannot add foreign key constraint`。兼容迁移
`20260907_000_usage_inventory_model_identity_compatibility.sql` 使用
`VIRTUAL` 生成列建立相同的唯一性约束；`VIRTUAL` 列仍会被唯一索引实时计算，
不会改变库存型号区分规则，也不会修改或删除历史外键。

该迁移必须按文件名排在 `20260907_001_usage_inventory_model_identity.sql` 之前。
如果 `20260907_001` 已经登记，迁移器仍可安全登记此兼容迁移：对象已存在时各步骤均为
无操作。升级前仍应检查两张表的 `inventory_model_key`、`uq_non_asset_usage_item_model`
和 `uq_employee_monitor_model`，并在异常时从升级前备份恢复。

### 同型号多次领用

`20260909_001_individual_inventory_usage_records.sql` 会删除
`uq_non_asset_usage_item_model` 和 `uq_employee_monitor_model`，并建立同字段顺序的
普通索引。该变化是为了让同一人员多次领取相同库存型号时，每次操作都生成新的使用记录；
`inventory_allocation_history.usage_record_id` 因此可以一对一关联对应的领用操作。

一次领用请求中的 `quantity > 1` 仍保持为一条使用记录。迁移不会拆分既有合并行，也不会
重写历史分配记录；回收服务继续按分配历史的 `allocationId` 和 `usageRecordId` 兼容处理。

## 回滚

数据库迁移不提供自动反向执行。升级前必须备份；出现不可接受的业务或结构问题时，停止应用并使用已验证的备份恢复。代码回退到旧标签不会自动撤销数据库结构。
