# 前端与接口

前端是无构建步骤的原生 HTML、CSS、JavaScript 应用，由根目录 `server.py` 提供静态文件和 API。

## 页面模块

- 资产总览、办公终端、人员、组织与资产关系。
- IT 物资、入库、领用、归还与物资流转记录。
- 工单、服务管理、表单设计、审批、SLA、变更、问题和知识库。
- 同步与质量、审计日志、备份、账户、角色和权限设置。

导航会根据当前用户的模块权限隐藏不可用入口，但所有写入和读取范围都由 API 再次校验。

## 常用接口

| 接口 | 说明 |
| --- | --- |
| `GET /api/health` | 服务与数据库健康检查。 |
| `GET /api/state` | 兼容性只读状态快照。 |
| `PUT /api/state` | 已退役，返回 `405 STATE_WRITE_RETIRED`。 |
| `POST /api/inventory/receipts` | IT 物资入库命令。 |
| `POST /api/inventory/allocations` | IT 物资领用命令。 |
| `POST /api/inventory/allocations/{id}/return` | IT 物资归还命令。 |
| `POST /api/computers/{id}/assignments` | 办公终端分配命令。 |
| `POST /api/computers/{id}/assignments/return` | 办公终端归还命令。 |
| `GET /api/computers/{id}/movement-history` | 当前用户数据范围内的设备流转时间线。 |
| `GET/POST /api/tickets` | 工单查询与创建。 |
| `GET/POST /api/service-forms` | 服务表单设计和发布。 |
| `GET/POST /api/sync-runs` | 同步暂存任务和结果。 |
| `POST /api/data-quality/run` | 数据质量审计。 |

## 前端约束

- 业务数据以 MySQL 为唯一来源；浏览器本地存储只保存主题和界面偏好。
- 列表筛选使用“输入草稿 + 明确查询”，不能在每次输入时触发全量重绘或远程请求。
- 静态资源缓存版本在 `index.html` 中维护；发布新前端时更新版本参数。
- 所有破坏性或状态变更操作必须显示服务端错误，不得仅依赖前端禁用按钮。
