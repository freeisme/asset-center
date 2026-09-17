# 时区迁移：从 UTC 切到 UTC+8

## 背景

系统长期部署在 UTC：宿主机、应用容器、MySQL 都是 UTC。数据库里 **123 个时间列全部是
`DATETIME`，没有一个 `TIMESTAMP`**，MySQL 不会做时区换算；前端 `formatDateTime` 也只做
字符串裁剪。因此用户看到的时间比北京时间少 8 小时（例如北京时间 15:50 的操作记录成 07:50）。

本迁移把运行环境切到 `Asia/Shanghai`，并把历史数据整体后移 8 小时。

## 迁移前必须判定的两件事

### 1. 表里到底是 DATETIME 还是 TIMESTAMP

`TIMESTAMP` 在 MySQL 内部按 UTC 存储、按会话时区换算，切换时区会自动正确；
`DATETIME` 存的是字面值，必须显式平移。用下面的查询确认：

```sql
SELECT data_type, COUNT(*) FROM information_schema.columns
WHERE table_schema = DATABASE() AND data_type IN ('datetime', 'timestamp')
GROUP BY data_type;
```

### 2. 有没有「浏览器本地时间」写入的列

前端 `currentTimestampText()` 会按浏览器本地时间生成字符串，随整体状态同步写进库；
这类值本来就是本地时间，再 +8 小时就错了。判定方法是把候选列与同一行的 `created_at`
（由服务器时钟写入）比较：

```sql
SELECT COUNT(*) AS n,
       SUM(ABS(TIMESTAMPDIFF(MINUTE, created_at, occurred_at)) <= 5) AS same_as_server_clock,
       SUM(ABS(TIMESTAMPDIFF(MINUTE, created_at, occurred_at) - 480) <= 5) AS browser_local
FROM inventory_movement_log WHERE occurred_at IS NOT NULL;
```

已知的两列属于这种情况：`inventory_movement_log.occurred_at`、
`left_employee_archive.archived_at`。`itil_change.planned_start_at/planned_end_at`
由用户手填，语义就是本地时间，也不平移。

## 执行步骤

1. **备份**（必须，且确认可恢复）

   ```bash
   docker exec <db 容器> sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot \
     --single-transaction --routines --triggers --events --hex-blob \
     --databases <数据库名>' | gzip -9 > before_tz.sql.gz
   ```

   同时留一份逐表行数基线（`information_schema.tables.table_rows`）用于迁移后比对。

2. **本地演练**：把备份还原到两个临时库，其中一个执行迁移脚本，然后逐表逐列比对
   （迁移后 = 迁移前 + 8 小时；例外列中浏览器本地时间行保持不变；其余列必须完全一致）。

3. **切换容器时区**：`compose.yaml` 的 `db`、`migrate`、`app` 三个服务都加
   `TZ: ${TZ:-Asia/Shanghai}`，然后先只重建数据库：

   ```bash
   docker compose stop app
   docker compose up -d --no-deps db
   docker exec <db 容器> sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot \
     -e "SELECT NOW(), @@system_time_zone"'   # 期望 CST / +08:00
   ```

4. **执行数据迁移**（手工脚本，不在自动迁移流程里）：

   ```bash
   docker exec -i <db 容器> sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot \
     --default-character-set=utf8mb4 -D <数据库名>' < database/manual/20260917_001_timezone_utc_to_asia_shanghai.sql
   ```

5. **恢复应用**：`docker compose up -d --no-deps app`，确认 `/api/health` 正常。

6. **校验**：

   ```sql
   SELECT NOW();                                     -- 应为北京时间
   SELECT COUNT(*) FROM audit_log WHERE created_at > NOW() + INTERVAL 1 HOUR;  -- 应为 0
   SELECT COUNT(*) FROM inventory_movement_log WHERE updated_at > NOW();       -- 应为 0
   SELECT COUNT(*) FROM auth_session WHERE revoked_at IS NULL AND expires_at > NOW();
   ```

## 演练中踩到的两个坑

1. **不能逐列平移**。`computer_assignment` 有行内约束
   `ck_assignment_dates (returned_at IS NULL OR returned_at >= assigned_at)`：
   先平移 `assigned_at` 再平移 `returned_at`，中间状态下约束必然被违反。
   脚本改为**按表一次性平移该行所有时间列**。
2. **`ON UPDATE CURRENT_TIMESTAMP` 会污染 `updated_at`**。对例外列做条件平移时，
   该语句改动了行而 `updated_at` 未被显式赋值，MySQL 会把它刷成当前时间，
   随后整表平移再多加 8 小时。解决办法是在这两条条件 UPDATE 里显式写上
   `updated_at = updated_at`。

## 回滚

- 删除 `data_migration_marker` 中 `20260917_timezone_utc_to_utc8` 这一行，
  把脚本里的 `INTERVAL 8 HOUR` 改成 `INTERVAL -8 HOUR` 重跑
  （例外列的判定条件是对称的，仍然成立）；或
- 直接恢复迁移前的备份，并把 `TZ` 改回 UTC 后重建容器。

## 不在本仓库范围内的部分

以下由服务器运维或面板管理，需要单独处理：

- **宿主机**：`sudo timedatectl set-timezone Asia/Shanghai`（影响系统日志、cron、面板显示）。
  注意 `timedatectl` 只改 `/etc/localtime`（符号链接），`/etc/timezone` 可能仍是旧值，
  需要单独补一致（有些容器会把这个文件挂进去）：

  ```bash
  sudo sh -c 'echo Asia/Shanghai > /etc/timezone'
  ```

- **Gitea / Gitea 数据库**：在各自的 compose 服务上加 `TZ=Asia/Shanghai` 后重建；
  Gitea 用 PostgreSQL `timestamptz`，内部按 UTC 存储，切换时区**不需要迁移数据**。
- **1Panel 组件**（OpenResty、MySQL、node-exporter）：在 1Panel 的容器设置里加
  `TZ=Asia/Shanghai` 并重启；这些组件不存业务时间。

### Alpine 镜像下 `TZ` 不会自动生效

Gitea 官方镜像基于 **Alpine（musl libc）**且不带 tzdata：容器里没有
`/usr/share/zoneinfo/Asia/Shanghai` 时，只设 `TZ=Asia/Shanghai` 会让 musl 解析失败并
**退回 UTC**，此时连挂载进来的 `/etc/localtime` 都不会被采用。必须把宿主机的 zoneinfo
挂进容器：

```yaml
    volumes:
      - /usr/share/zoneinfo:/usr/share/zoneinfo:ro
```

已运行的容器只会保留启动时解析到的时区，宿主机改完时区后必须重建或重启容器才会生效
（`docker compose up -d` 在 compose 内容没变化时不会重建，会显示 `Running` 而不是
`Recreated`，那是空操作）。

### 不要改 Gitea 数据库的 PostgreSQL 会话时区

Gitea 的时间字段绝大多数是 `bigint`（epoch 秒，与时区无关），只有 `created`、
`expires_at` 这类 `timestamp without time zone` 字段按会话时区写入和比较。
PostgreSQL 会话时区保持 `Etc/UTC` 时写入与过期判断自洽；改成 UTC+8 会让令牌过期判断
整体偏移 8 小时。容器 `TZ` 只影响日志时间，不影响这个 GUC。
