# Ubuntu 部署文档

本文档适用于将本项目部署到 Ubuntu 局域网服务器，并通过 Nginx 提供访问。

> v2.0.0 迁移要求：`database/bootstrap/01_schema.sql` 只用于空库。已有业务库升级前先备份，并使用 `tools/migration_runner.py` 执行已登记基线之后的增量迁移；不要对生产库重放历史初始化 SQL。

## 1. 部署架构

```text
局域网浏览器
      │
      ▼
Nginx :80 / :443
      │ 反向代理
      ▼
Python server.py :127.0.0.1:8000
      │
      ▼
MySQL :127.0.0.1:3306
```

Python 服务不直接暴露到局域网，Nginx 是唯一对外入口。

## 2. 服务器准备

在 Ubuntu 服务器执行：

```bash
sudo apt update
sudo apt install -y git mysql-server nginx python3
python3 --version
mysql --version
```

建议使用 Ubuntu 22.04 或 24.04，并确保 Python 版本不低于 3.10。

创建运行用户和目录：

```bash
sudo useradd --system --home /opt/office-asset-mgmt --shell /usr/sbin/nologin officeasset
sudo mkdir -p /opt/office-asset-mgmt
sudo mkdir -p /etc/office-asset-mgmt
sudo mkdir -p /var/backups/office-asset-mgmt
```

## 3. 上传项目

### 方式 A：从 GitHub 克隆

```bash
sudo git clone <你的GitHub仓库地址> /opt/office-asset-mgmt
```

### 方式 B：上传压缩包

在本地项目目录执行：

```bash
tar --exclude='.git' --exclude='.env' -czf office-asset-management.tar.gz .
```

将压缩包上传服务器后：

```bash
sudo tar -xzf office-asset-management.tar.gz -C /opt/office-asset-mgmt
```

设置权限：

```bash
sudo chown -R officeasset:officeasset /opt/office-asset-mgmt
sudo chmod 750 /opt/office-asset-mgmt
sudo chmod +x /opt/office-asset-mgmt/deploy/scripts/*.sh
```

## 4. 创建 MySQL 数据库

先登录 MySQL：

```bash
sudo mysql
```

创建独立应用账号：

```sql
CREATE DATABASE IF NOT EXISTS office_asset_mgmt
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'office_asset_app'@'127.0.0.1'
  IDENTIFIED BY '请替换为随机强密码';

GRANT ALL PRIVILEGES ON office_asset_mgmt.*
  TO 'office_asset_app'@'127.0.0.1';

FLUSH PRIVILEGES;
EXIT;
```

初始化空库：

```bash
cd /opt/office-asset-mgmt
sudo env \
  DB_USER=root \
  DB_NAME=office_asset_mgmt \
  bash deploy/scripts/init_database.sh
```

脚本会按 `DB_NAME` 创建并选中数据库，然后执行：

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

其中 `00_create_database.sql` 是固定默认库名的兼容辅助文件，不在以上可配置初始化
顺序中。`02_seed_reference_data.sql` 只包含通用物资类型，不包含组织架构、人员、
办公终端或库存业务数据。组织架构请在系统中按实际情况创建或通过独立的内部初始化
脚本导入。

空库初始化完成后，登记历史基线并应用增量迁移：

```bash
cd /opt/office-asset-mgmt
sudo -u officeasset env \
  DB_HOST=127.0.0.1 DB_PORT=3306 DB_USER=office_asset_app \
  DB_NAME=office_asset_mgmt DB_PASSWORD='<从安全环境文件读取>' \
  MYSQL_BIN=/usr/bin/mysql \
  python3 tools/migration_runner.py --database office_asset_mgmt --mark-baseline legacy-20260813
```

## 5. 配置服务环境变量

创建配置文件：

```bash
sudo nano /etc/office-asset-mgmt/office-asset-mgmt.env
```

内容示例：

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=office_asset_mgmt
DB_USER=office_asset_app
DB_PASSWORD=替换为MySQL应用账号密码
MYSQL_BIN=/usr/bin/mysql
SERVER_HOST=127.0.0.1
SERVER_PORT=8000
AUTH_COOKIE_SECURE=true
PASSWORD_MAX_LENGTH=256
LOGIN_RATE_WINDOW_SECONDS=300
LOGIN_RATE_MAX_ATTEMPTS=15
```

保护配置文件：

```bash
sudo chown root:officeasset /etc/office-asset-mgmt/office-asset-mgmt.env
sudo chmod 640 /etc/office-asset-mgmt/office-asset-mgmt.env
```

密码只写入服务器配置文件，不要写入 GitHub。

## 6. 配置 systemd

```bash
sudo cp /opt/office-asset-mgmt/deploy/systemd/office-asset-mgmt.service \
  /etc/systemd/system/office-asset-mgmt.service

sudo systemctl daemon-reload
sudo systemctl enable --now office-asset-mgmt
sudo systemctl status office-asset-mgmt
```

查看日志：

```bash
sudo journalctl -u office-asset-mgmt -f
```

检查后端：

```bash
curl http://127.0.0.1:8000/api/health
```

正常应返回 HTTP 200。

## 7. 配置 Nginx

```bash
sudo cp /opt/office-asset-mgmt/deploy/nginx/office-asset-mgmt.conf \
  /etc/nginx/sites-available/office-asset-mgmt

sudo ln -sfn /etc/nginx/sites-available/office-asset-mgmt \
  /etc/nginx/sites-enabled/office-asset-mgmt

sudo nginx -t
sudo systemctl reload nginx
```

完成 HTTPS 配置后，局域网用户访问服务器 IP 或域名：

```text
https://服务器局域网IP/
```

例如：

```text
https://asset.example.internal/
```

## 8. 防火墙

如果启用了 UFW，只开放 SSH 和 Nginx：

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

不要将 3306 和 8000 直接开放给局域网，除非有明确运维需求。

## 9. HTTPS

如果有域名，建议使用 Certbot：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d asset.example.com
```

没有域名时，使用受办公终端信任的内部 CA 证书配置 Nginx。当前 Nginx 示例中的
HTTP 监听仅用于初始配置或申请证书，不能作为生产登录入口。生产环境保持
`AUTH_COOKIE_SECURE=true`；不要为了长期使用 HTTP 而关闭 Secure Cookie。

## 10. 备份

手动备份：

```bash
sudo -u officeasset env \
  DB_USER=office_asset_app \
  DB_NAME=office_asset_mgmt \
  BACKUP_DIR=/var/backups/office-asset-mgmt \
  bash /opt/office-asset-mgmt/deploy/scripts/backup_database.sh
```

设置定时任务：

```bash
sudo crontab -e
```

加入：

```cron
0 2 * * * DB_USER=office_asset_app DB_NAME=office_asset_mgmt BACKUP_DIR=/var/backups/office-asset-mgmt MYSQL_PWD='替换为密码' /opt/office-asset-mgmt/deploy/scripts/backup_database.sh >> /var/log/office-asset-mgmt-backup.log 2>&1
```

生产环境不建议把密码直接写入 crontab，可以改用只允许 root 读取的环境文件。

## 11. 更新版本

```bash
cd /opt/office-asset-mgmt
sudo git pull
sudo chown -R officeasset:officeasset /opt/office-asset-mgmt
sudo systemctl restart office-asset-mgmt
sudo systemctl status office-asset-mgmt
```

如果数据库结构有变化，先备份数据库，再按版本说明执行对应 SQL。

v2.0.0 及以后使用迁移执行器校验并执行增量迁移：

```bash
cd /opt/office-asset-mgmt
sudo -u officeasset env \
  DB_HOST=127.0.0.1 DB_PORT=3306 DB_USER=office_asset_app \
  DB_NAME=office_asset_mgmt DB_PASSWORD='<从安全环境文件读取>' \
  MYSQL_BIN=/usr/bin/mysql \
  python3 tools/migration_runner.py --database office_asset_mgmt --verify
```

如果已有库没有 `schema_migration`，不要自动补表后直接升级。完成备份并确认历史基线后，显式加上 `--mark-baseline legacy-20260813` 执行一次。

恢复文本 SQL 时，先停止服务并确认目标数据库名，再启用 MySQL 二进制模式：

```bash
sudo systemctl stop office-asset-mgmt
sudo env MYSQL_PWD='从安全环境文件读取' \
  mysql --binary-mode=1 -h 127.0.0.1 -u root office_asset_mgmt \
  < /path/to/office_asset_mgmt.sql
sudo systemctl start office-asset-mgmt
```

如果数据库名不是 `office_asset_mgmt`，必须将命令中的名称替换为实际 `DB_NAME`；
不要依赖脚本中的固定数据库选择。

## 12. 故障排查

查看服务状态：

```bash
sudo systemctl status office-asset-mgmt
sudo journalctl -u office-asset-mgmt -n 100 --no-pager
```

查看 Nginx：

```bash
sudo nginx -t
sudo tail -n 100 /var/log/nginx/error.log
```

检查端口：

```bash
sudo ss -lntp | grep -E ':80|:8000|:3306'
```

检查数据库：

```bash
mysql -h 127.0.0.1 -u office_asset_app -p office_asset_mgmt \
  -e "SELECT COUNT(*) FROM computer_asset;"
```

## 13. GitHub 发布前检查

在提交前确认：

```bash
git status
git diff --check
find . -type f \( -name '*.xlsx' -o -name '*.xls' -o -name '*.log' -o -name '*.sql.gz' \)
```

必须确认以下内容没有提交：

- `.env`
- MySQL 密码
- `tmp_state.json`
- `backups/`
- Excel 原始数据
- 服务器日志
- 业务数据库导出文件

## 14. 创建 GitHub 仓库并首次提交

在本地发布目录执行。请确认当前目录是 `<发布工作目录>`，不要在原始项目根目录执行提交。

```bash
cd <发布工作目录>
git init
git add .
git diff --cached --check
git commit -m "Initial release"
git branch -M main
git remote add origin <你的GitHub仓库地址>
git push -u origin main
```

建议将 GitHub 仓库设置为 Private。首次推送前可以再次检查待提交文件：

```bash
git status --short
git ls-files
```

后续更新：

```bash
git add .
git diff --cached --check
git commit -m "Update office asset management"
git push
```
