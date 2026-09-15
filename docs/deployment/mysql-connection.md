# 办公资产管理系统 MySQL 连接指南

本文档对应当前服务器部署：

- 服务器：`<asset-server-host>`
- 应用目录：`/opt/office-asset-mgmt`
- Compose 文件：`/opt/office-asset-mgmt/compose.yaml`
- 环境文件：`/opt/office-asset-mgmt/.env`
- 应用地址：`https://asset.example.internal/`
- 应用容器：`office-asset-mgmt-app-1`
- MySQL 容器：`office-asset-mgmt-db-1`

## 1. 实际连接参数

应用容器使用以下参数连接 MySQL：

| 参数 | 值 |
| --- | --- |
| 主机 | `db` |
| 端口 | `3306` |
| 数据库 | `office_asset_mgmt` |
| 用户 | `office_asset_app` |
| 密码 | `/opt/office-asset-mgmt/.env` 中的 `DB_PASSWORD` |

这里的主机必须写 `db`，不能写 `127.0.0.1`。`db` 是
`office-asset-mgmt_default` Docker 网络中的服务名。

应用代码从环境变量读取这些值：

```text
DB_HOST=db
DB_PORT=3306
DB_NAME=office_asset_mgmt
DB_USER=office_asset_app
DB_PASSWORD=...
```

MySQL root 密码在同一个 `.env` 文件的 `MYSQL_ROOT_PASSWORD` 中。
不要把密码写进 Git、命令行参数或聊天记录。

## 2. 当前端口和网络边界

办公资产 MySQL 当前只在 Docker 网络内监听，没有发布到宿主机：

```text
office-asset-mgmt-db-1   3306/tcp
```

宿主机的 `<asset-server-host>:3306` 可能属于另一套 MySQL 服务
容器 `1Panel-mysql-Xwiv`，不是办公资产管理系统数据库。

当前应用网络：

```text
office-asset-mgmt_default
```

应用容器可以通过 `db:3306` 访问数据库。数据库容器的 IP 可能变化，
不要把当前 Docker IP 写死到配置中。

## 3. 登录服务器

Windows PowerShell：

```powershell
ssh <deployment-user>@<asset-server-host> -p 22
```

进入服务器后：

```bash
cd /opt/office-asset-mgmt
```

部署账号当前没有 Docker Socket 权限，因此 Docker 命令使用 `sudo`。

## 4. 检查应用和数据库状态

```bash
sudo docker compose \
  -f /opt/office-asset-mgmt/compose.yaml \
  --env-file /opt/office-asset-mgmt/.env \
  ps
```

正常结果应包含：

```text
office-asset-mgmt-app-1   Up ... (healthy)
office-asset-mgmt-db-1    Up ... (healthy)
```

检查应用到数据库的实际健康状态：

```bash
curl --fail http://127.0.0.1:8000/api/health
```

正常响应类似：

```json
{
  "ok": true,
  "databaseProbe": 1,
  "requiredTables": 19,
  "requiredTableCount": 19
}
```

检查 Docker 内部 DNS：

```bash
sudo docker exec office-asset-mgmt-app-1 getent hosts db
```

检查日志：

```bash
sudo docker compose \
  -f /opt/office-asset-mgmt/compose.yaml \
  --env-file /opt/office-asset-mgmt/.env \
  logs --tail=100 app db
```

## 5. 在服务器上登录 MySQL

### 5.1 使用应用账号

```bash
sudo docker exec -it office-asset-mgmt-db-1 \
  mysql --protocol=tcp -uoffice_asset_app -p office_asset_mgmt
```

按提示输入 `/opt/office-asset-mgmt/.env` 中的 `DB_PASSWORD`。

### 5.2 使用 root 账号

```bash
sudo docker exec -it office-asset-mgmt-db-1 \
  mysql --protocol=tcp -uroot -p
```

按提示输入 `.env` 中的 `MYSQL_ROOT_PASSWORD`。

登录后常用检查：

```sql
SELECT DATABASE();
SHOW TABLES;
SELECT COUNT(*) FROM employee;
SELECT COUNT(*) FROM computer_asset;
SELECT COUNT(*) FROM audit_log;
```

### 5.3 非交互查询

使用容器内已经存在的环境变量，不要把密码放在命令参数中：

```bash
sudo docker exec office-asset-mgmt-db-1 sh -lc \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=tcp -uroot office_asset_mgmt -NBe "SELECT 1;"'
```

查询业务表数量：

```bash
sudo docker exec office-asset-mgmt-db-1 sh -lc \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=tcp -uroot office_asset_mgmt -NBe "SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema = DATABASE() ORDER BY table_name;"'
```

## 6. 应用容器内测试连接

应用容器已经包含 MySQL 客户端，可以直接测试：

```bash
sudo docker exec office-asset-mgmt-app-1 sh -lc \
  'MYSQL_PWD="$DB_PASSWORD" mysql --protocol=tcp -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" "$DB_NAME" -NBe "SELECT 1;"'
```

如果返回 `1`，说明应用容器到 MySQL 的网络、账号和密码均正常。

## 7. 修改数据库连接参数

先备份环境文件：

```bash
sudo cp /opt/office-asset-mgmt/.env \
  /opt/office-asset-mgmt/.env.backup.$(date +%Y%m%d_%H%M%S)
sudo chmod 600 /opt/office-asset-mgmt/.env
```

编辑：

```bash
sudo nano /opt/office-asset-mgmt/.env
```

重点参数：

```dotenv
DB_NAME=office_asset_mgmt
DB_USER=office_asset_app
DB_PASSWORD=change-me
MYSQL_ROOT_PASSWORD=change-me-too
APP_PORT=8000
```

修改后检查 Compose 配置并重建应用容器：

```bash
sudo docker compose \
  -f /opt/office-asset-mgmt/compose.yaml \
  --env-file /opt/office-asset-mgmt/.env \
  config --quiet

sudo docker compose \
  -f /opt/office-asset-mgmt/compose.yaml \
  --env-file /opt/office-asset-mgmt/.env \
  up -d --force-recreate app
```

注意：MySQL 官方镜像的 `MYSQL_USER`、`MYSQL_PASSWORD` 和
`MYSQL_ROOT_PASSWORD` 主要只在数据卷第一次初始化时生效。
如果 `mysql-data` 已经存在，仅修改 `.env` 不会自动修改 MySQL
用户密码。此时应在 MySQL 内执行 `ALTER USER`，或将应用配置改回
数据库中实际存在的密码。

## 8. 备份数据库

先确认备份目录，再生成压缩 SQL：

```bash
sudo install -d -m 700 /var/backups/office-asset-mgmt
sudo -v

sudo docker exec office-asset-mgmt-db-1 sh -lc \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump \
   --protocol=tcp \
   -uroot \
   --single-transaction \
   --routines \
   --events \
   --triggers \
   --hex-blob \
   --no-tablespaces \
   --databases "$MYSQL_DATABASE"' \
  | sudo gzip > "/var/backups/office-asset-mgmt/office_asset_mgmt_$(date +%Y%m%d_%H%M%S).sql.gz"

sudo chmod 600 /var/backups/office-asset-mgmt/*.sql.gz
```

查看备份：

```bash
sudo ls -lh /var/backups/office-asset-mgmt/
```

备份文件包含业务数据，必须限制权限并复制到另一台存储设备。

## 9. 恢复 SQL 备份

恢复前先停止应用，避免应用在恢复期间读写不完整的数据：

```bash
sudo docker compose \
  -f /opt/office-asset-mgmt/compose.yaml \
  --env-file /opt/office-asset-mgmt/.env \
  stop app
```

如果是包含 `CREATE DATABASE` 和 `USE office_asset_mgmt` 的完整 SQL：

```bash
sudo docker exec -i office-asset-mgmt-db-1 sh -lc \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --binary-mode=1 --protocol=tcp -uroot' \
  < /path/to/office_asset_mgmt.sql
```

如果备份是 gzip：

```bash
gzip -dc /path/to/office_asset_mgmt.sql.gz \
  | sudo docker exec -i office-asset-mgmt-db-1 sh -lc \
    'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --binary-mode=1 --protocol=tcp -uroot'
```

如果备份不包含 `CREATE DATABASE` 或 `USE`，必须把当前 Compose 配置中的数据库名
显式传给客户端：

```bash
sudo docker exec -i office-asset-mgmt-db-1 sh -lc \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --binary-mode=1 --protocol=tcp -uroot "$MYSQL_DATABASE"' \
  < /path/to/office_asset_mgmt.sql
```

恢复完成后启动应用：

```bash
sudo docker compose \
  -f /opt/office-asset-mgmt/compose.yaml \
  --env-file /opt/office-asset-mgmt/.env \
  up -d app

curl --fail http://127.0.0.1:8000/api/health
```

不要把办公资产数据库 SQL 恢复到 Gitea 数据库。当前 Gitea 使用
PostgreSQL 容器 `gitea-db`，不是 `office-asset-mgmt-db-1`。

## 10. 从远程办公终端使用 GUI 客户端

当前办公资产 MySQL 没有发布到宿主机，因此不能直接在本地 GUI
中连接 `<asset-server-host>:3306`。确认该地址对应当前目标 MySQL 实例。

推荐做法是临时只绑定到服务器本机回环地址：

在 `/opt/office-asset-mgmt/compose.yaml` 的 `db` 服务中增加：

```yaml
ports:
  - "127.0.0.1:13306:3306"
```

应用仍然使用 `db:3306`，不需要修改应用配置。重新创建数据库容器：

```bash
sudo docker compose \
  -f /opt/office-asset-mgmt/compose.yaml \
  --env-file /opt/office-asset-mgmt/.env \
  up -d db
```

在 Windows 本地建立 SSH 隧道：

```powershell
ssh -L 13306:127.0.0.1:13306 <deployment-user>@<asset-server-host> -p 22
```

GUI 客户端连接参数：

```text
Host: 127.0.0.1
Port: 13306
Database: office_asset_mgmt
User: office_asset_app
Password: .env 中的 DB_PASSWORD
```

不建议把办公资产 MySQL 绑定为 `0.0.0.0:3306` 或直接开放到局域网。
服务器当前已有另一个服务占用宿主机 `3306`。

## 11. 常见错误

### `Can't connect to MySQL server on '127.0.0.1'`

应用容器内的 `127.0.0.1` 指向应用容器自身，不是数据库容器。
将 `DB_HOST` 设置为 `db`。

### `Connection refused` 或 `db:3306`

检查：

```bash
sudo docker compose -f /opt/office-asset-mgmt/compose.yaml \
  --env-file /opt/office-asset-mgmt/.env ps
sudo docker exec office-asset-mgmt-app-1 getent hosts db
sudo docker compose -f /opt/office-asset-mgmt/compose.yaml \
  --env-file /opt/office-asset-mgmt/.env logs --tail=100 db app
```

### `Access denied for user`

确认 `.env` 中的 `DB_USER` 和 `DB_PASSWORD` 与 MySQL 现有用户一致。
修改 `.env` 后必须重建应用容器：

```bash
sudo docker compose -f /opt/office-asset-mgmt/compose.yaml \
  --env-file /opt/office-asset-mgmt/.env up -d --force-recreate app
```

如果 MySQL 数据卷已存在，单纯修改 `.env` 不会改变数据库用户密码。

### `Unknown database 'office_asset_mgmt'`

确认数据库容器状态和数据库名称：

```bash
sudo docker exec office-asset-mgmt-db-1 \
  printenv MYSQL_DATABASE MYSQL_USER
```

### `ASCII '\0' appeared in the statement`

通常是把 UTF-16、gzip、zip 或其他二进制文件直接交给 `mysql`。
纯 SQL 文件应该以类似下面的文本开头：

```text
-- MySQL dump
```

如果文件是 gzip，先使用 `gzip -dc` 解压；如果是 PowerShell
生成的文件，不要使用 `*>` 保存原始 `mysqldump` 输出，避免被转换为
UTF-16。必要时使用：

```bash
mysql --binary-mode=1
```

但 `--binary-mode=1` 不能替代解压或修复错误的文件编码。

## 12. 当前验证结果

2026-08-04 已验证：

- 应用容器：`healthy`
- MySQL 容器：`healthy`
- Docker DNS：应用容器通过服务名 `db` 解析到 MySQL 容器，容器内网地址随环境变化，不应写死
- 应用健康接口：HTTP `200`
- 数据库探针：`databaseProbe = 1`
- 必需表数量：以当前 `server.py` 的健康检查为准（随版本变化）
- 应用实际连接：`db:3306/office_asset_mgmt`
