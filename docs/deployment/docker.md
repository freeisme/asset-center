# Docker Compose 部署

本部署方式包含 MySQL、一次性迁移服务和应用服务：

```text
Browser -> app:8000 -> db:3306
                    ^
                 migrate
```

`migrate` 仅在数据库健康后执行。它应用已登记基线之后的增量迁移；失败时 `app` 不会启动。

## 1. 配置

```bash
cp .env.example .env
chmod 600 .env
```

至少设置以下值：

```dotenv
APP_PORT=8000
DB_NAME=office_asset_mgmt
DB_USER=office_asset_app
DB_PASSWORD=replace-with-a-long-random-password
MYSQL_ROOT_PASSWORD=replace-with-a-different-long-random-password
AUTH_COOKIE_SECURE=true
```

不要提交 `.env`。生产环境必须通过 HTTPS 访问并保持 `AUTH_COOKIE_SECURE=true`。

## 2. 首次启动

```bash
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=200 migrate
docker compose logs --tail=200 app
```

空数据卷会由 `deploy/docker/init_database.sh` 初始化 `database/bootstrap/` 中的历史结构和参考数据，同时登记 `legacy-20260813`。之后 `migrate` 应用 `database/migrations/` 中的全部未登记版本。

验证：

```bash
curl http://127.0.0.1:8000/api/health
docker compose exec db sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -e "SELECT version, applied_at FROM schema_migration ORDER BY version;"'
```

首次浏览器访问会进入管理员初始化流程，系统没有固定默认密码。

## 3. 已有数据卷升级

1. 先创建并验证数据库备份。
2. 拉取已验证版本并查看 [版本说明](../../VERSION_NOTES.md) 和[数据库迁移说明](../development/migrations.md)。
3. 构建并启动：

```bash
git pull --ff-only
docker compose build --pull
docker compose up -d
docker compose ps
```

如果已有库没有 `schema_migration`，`migrate` 会停止。这是保护机制，不会重放
`database/bootstrap/01_schema.sql`。确认数据库已达到历史基线后，在 `.env` 中临时设置：

```dotenv
MIGRATION_ADOPT_BASELINE=legacy-20260813
```

下一次受控更新会先验证关键历史表，再登记基线并执行增量迁移。也可以显式登记一次：

```bash
docker compose run --rm --entrypoint python migrate \
  tools/migration_runner.py --database office_asset_mgmt --mark-baseline legacy-20260813
docker compose up -d
```

将命令中的数据库名替换为实际 `DB_NAME`。不要用删除 `mysql-data` 卷来绕过迁移问题。
成功后删除 `.env` 中的 `MIGRATION_ADOPT_BASELINE`，并运行 `docker compose run --rm migrate
--entrypoint python migrate tools/migration_runner.py --database office_asset_mgmt --verify`
确认没有待执行迁移。

## 4. 备份与恢复

管理员可以在系统设置中创建受控备份。部署账户执行 Docker 数据库备份时使用项目脚本：

```bash
sudo -u officeasset-deploy -H bash \
  /opt/office-asset-mgmt/deploy/scripts/backup_compose_database.sh
```

备份默认写入 `/home/officeasset-deploy/backups/office-asset-mgmt/`，生成 `.sql.gz` 文件和
同名 `.sha256` 校验文件，并通过临时文件和原子移动避免将部分导出文件当成可恢复备份。

恢复前停止应用并确认目标数据库，恢复后重新运行迁移校验和关键业务验证。

## 5. 运维

```bash
docker compose ps
docker compose logs --tail=200 app
docker compose logs --tail=200 migrate
docker compose logs --tail=200 db
docker compose down
```

`docker compose down -v` 会永久删除 Docker 管理的数据库卷，只能在已验证备份可恢复时执行。
