# Private Gitea and Docker Deployment

This setup uses:

```text
Gitea + PostgreSQL
        |
        +-- private Git repositories and project management
        |
        +-- signed push webhook for main
                    |
                    +-- validate and acknowledge only
                    +-- no automatic deployment
```

The webhook receiver runs as a dedicated host service. It does not mount the Docker
socket into the Gitea container and it only accepts a valid HMAC-signed push event for
the configured repository and branch.

## 1. Server prerequisites

On an Ubuntu server, install Docker Compose v2, Git, Python, and curl:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git python3
```

Install Docker Engine and the Compose plugin using the official Docker instructions.
Then verify:

```bash
docker --version
docker compose version
```

Create the application deployment account and grant it Docker access:

```bash
sudo useradd --create-home --shell /bin/bash officeasset-deploy || true
sudo usermod -aG docker officeasset-deploy
sudo mkdir -p /opt/office-asset-mgmt /opt/gitea /etc/office-asset-mgmt
sudo chown -R officeasset-deploy:officeasset-deploy /opt/office-asset-mgmt
```

Log in again after changing the Docker group membership.

## 2. Start Gitea

Copy `deploy/gitea/compose.yaml` and `deploy/gitea/.env.example` to `/opt/gitea`:

```bash
sudo cp deploy/gitea/compose.yaml /opt/gitea/compose.yaml
sudo cp deploy/gitea/.env.example /opt/gitea/.env
sudo chown -R root:root /opt/gitea
sudo chmod 600 /opt/gitea/.env
sudo nano /opt/gitea/.env
```

Set at least:

```dotenv
GITEA_DB_PASSWORD=use-a-long-random-password
GITEA_DOMAIN=git.example.com
GITEA_ROOT_URL=https://git.example.com/
GITEA_SSH_DOMAIN=git.example.com
```

For a first LAN-only installation, `GITEA_ROOT_URL` can be
`http://SERVER_IP:3000/`. Start the stack:

```bash
cd /opt/gitea
docker compose config
docker compose up -d
docker compose ps
```

Open the configured HTTP URL, create the first administrator, and create a private
repository such as `office-asset-management`. Keep registration disabled unless the
server is intentionally open to self-registration.

After the first administrator has been created, set `GITEA_INSTALL_LOCK=true` in
`/opt/gitea/.env` and restart the stack:

```bash
cd /opt/gitea
docker compose up -d
```

Expose Gitea through HTTPS when it is reachable outside a trusted LAN. Keep PostgreSQL
unpublished and allow only the Gitea HTTP/HTTPS and SSH ports through the firewall.

## 3. Push the project to Gitea

On the development machine:

```powershell
cd <项目工作目录>
git init
git branch -M main
git add .
git diff --cached --check
git commit -m "Initial private repository"
git remote add origin ssh://git@GITEA_HOST:2222/OWNER/office-asset-management.git
git push -u origin main
```

Replace `GITEA_HOST`, `OWNER`, and the SSH port with the values used in
`/opt/gitea/.env`.

On the application server, clone the same repository into the deployment path:

```bash
sudo -u officeasset-deploy git clone \
  ssh://git@GITEA_HOST:2222/OWNER/office-asset-management.git \
  /opt/office-asset-mgmt
```

Create `/opt/office-asset-mgmt/.env` from the existing `env.example`, set production
database passwords, and verify the application once with:

```bash
cd /opt/office-asset-mgmt
docker compose --env-file .env up -d --build
curl --fail http://127.0.0.1:8000/api/health
```

## 4. Give the deployment account read access

Generate a key on the application server:

```bash
sudo -u officeasset-deploy mkdir -p /home/officeasset-deploy/.ssh
sudo -u officeasset-deploy ssh-keygen -t ed25519 \
  -f /home/officeasset-deploy/.ssh/id_ed25519 \
  -N "" \
  -C "officeasset-deploy"
sudo cat /home/officeasset-deploy/.ssh/id_ed25519.pub
```

Add this public key to the Gitea repository as a read-only Deploy Key. Then record the
Gitea host key and test the fetch as the deployment account:

```bash
sudo -u officeasset-deploy ssh-keyscan -p 2222 GITEA_HOST \
  >> /home/officeasset-deploy/.ssh/known_hosts
sudo chmod 700 /home/officeasset-deploy/.ssh
sudo chmod 600 /home/officeasset-deploy/.ssh/id_ed25519
sudo chmod 644 /home/officeasset-deploy/.ssh/known_hosts
sudo -u officeasset-deploy git -C /opt/office-asset-mgmt fetch origin main
```

Verify the repository's `origin` URL uses the same Gitea host and port.

## 5. Enable manual Docker deployment controls

Manual deployment control does not require a push webhook. It reads the configured
Gitea repository directly when an administrator checks for versions. Create a dedicated
control token:

```bash
openssl rand -hex 32
```

Configure a TLS certificate whose subject alternative name matches the hostname used by
the application container, for example `host.docker.internal` or an internal DNS name.
Store the certificate and key outside the repository:

```bash
sudo install -d -m 750 -o root -g officeasset-deploy /etc/office-asset-mgmt/tls
sudo install -m 640 -o root -g officeasset-deploy update-control.crt \
  /etc/office-asset-mgmt/tls/update-control.crt
sudo install -m 640 -o root -g officeasset-deploy update-control.key \
  /etc/office-asset-mgmt/tls/update-control.key
sudo install -d -m 700 -o officeasset-deploy -g officeasset-deploy \
  /opt/office-asset-mgmt/secrets/update-service
sudo install -m 600 -o officeasset-deploy -g officeasset-deploy update-control-ca.pem \
  /opt/office-asset-mgmt/secrets/update-service/update-control-ca.pem
```

Create `/etc/office-asset-mgmt/gitea-webhook.env` with mode `600`:

```dotenv
DEPLOY_CONTROL_TOKEN=replace-with-a-different-generated-secret
WEBHOOK_BIND=0.0.0.0
WEBHOOK_PORT=9000
DEPLOY_REPO=OWNER/office-asset-management
DEPLOY_BRANCH=main
DEPLOY_VERSION_LIST_LIMIT=30
APP_DIR=/opt/office-asset-mgmt
DEPLOY_TLS_CERT_FILE=/etc/office-asset-mgmt/tls/update-control.crt
DEPLOY_TLS_KEY_FILE=/etc/office-asset-mgmt/tls/update-control.key
DEPLOY_ALLOW_INSECURE_HTTP=false
# Optional: map this exact private Gitea HTTP origin to the deployment account's SSH read URL.
# Configure both values together. Do not include user names, passwords, access tokens, paths, or a trailing slash.
DEPLOY_LOCAL_GITEA_HTTP_ORIGIN=http://<Gitea 服务器地址>:3001
DEPLOY_LOCAL_GITEA_SSH_ORIGIN=ssh://git@<Gitea 服务器地址>:2222
```

Set the same `DEPLOY_CONTROL_TOKEN` in `/opt/office-asset-mgmt/.env` as
`UPDATE_CONTROL_TOKEN`, then configure:

```dotenv
UPDATE_SERVICE_URL=https://host.docker.internal:9000
UPDATE_SERVICE_CA_FILE=/run/office-asset-mgmt/update-service/update-control-ca.pem
UPDATE_SERVICE_CERTS_DIR=./secrets/update-service
UPDATE_SERVICE_ALLOW_HTTP=false
```

The application uses the token only to read available release tags and queue a manually
selected version. It is never sent to browsers. The CA file is mounted read-only into
the app container by `compose.yaml` and must remain outside Git.

Install and start the receiver:

```bash
sudo cp deploy/gitea/office-asset-gitea-webhook.service \
  /etc/systemd/system/office-asset-gitea-webhook.service
sudo chmod 600 /etc/office-asset-mgmt/gitea-webhook.env
sudo systemctl daemon-reload
sudo systemctl enable --now office-asset-gitea-webhook
sudo systemctl status office-asset-gitea-webhook
curl --fail --cacert /opt/office-asset-mgmt/secrets/update-service/update-control-ca.pem \
  --resolve host.docker.internal:9000:127.0.0.1 \
  https://host.docker.internal:9000/healthz
```

Push webhooks are optional. When enabled, they only record a signed push and return
`204`; they never trigger a deployment. Set `GITEA_WEBHOOK_SECRET` and `WEBHOOK_PATH`
in the service environment, then configure a Gitea webhook with an HTTPS URL trusted by
Gitea. Do not enable an HTTP webhook merely to receive log events.

The update-control port must be restricted by the host firewall to the Docker bridge and
required administration sources. Do not expose TCP `9000` to the public Internet.
The certificate SAN must match the hostname used by the app container, such as
`host.docker.internal`; the `--resolve` option above keeps TLS hostname validation while
testing from the host.

Administrators use **Settings > 版本更新** to choose either **发行版** or **Beta 版**,
then check published SemVer tags, select a higher version, and confirm the update.
发行版仅显示稳定的 `vMAJOR.MINOR.PATCH` 标签；Beta 版仅显示
`vMAJOR.MINOR.PATCH-beta.N` 等预发布标签，未特别说明时默认 Beta 版。项目地址字段
可留空以使用部署工作目录的 `origin`，也可以填写 GitHub/Gitea Git URL。更新控制服务在
成功部署后会重新加载当前工作目录中的新代码，以加载所选版本中的版本筛选逻辑。服务验证
所选标签为注释标签、属于目标仓库 `main` 历史、包含匹配的 `VERSION_NOTES.md` 条目，并且
版本号高于当前版本。HTTP 项目地址只接受内网、本机或私有网络主机，且不能包含账号、密码或
令牌。对 GitHub 等 HTTPS 仓库，更新控制服务与部署脚本固定使用 HTTP/1.1，并在连接重置、
TLS 对端提前关闭等短暂传输失败时自动重试三次。可在服务环境中按需设置
`DEPLOY_GIT_FETCH_ATTEMPTS=1-5` 和 `DEPLOY_GIT_FETCH_RETRY_SECONDS=1-30`；最终失败会向
界面返回明确的仓库读取失败提示，不会误报为更新服务 HTTP 502。

对于启用了登录认证的私有 Gitea，如果管理员在页面填写的项目地址与
`DEPLOY_LOCAL_GITEA_HTTP_ORIGIN` 精确匹配，更新控制服务和实际部署脚本会仅在服务器内部
改用 `DEPLOY_LOCAL_GITEA_SSH_ORIGIN` 读取同一路径。浏览器、数据库、审计日志和项目地址中
仍保留原始 HTTP 地址，不会保存 Gitea 用户名、密码或访问令牌。两个变量必须同时设置；任何
其他 HTTP/HTTPS/SSH 地址不会被转换。优先在
`/etc/office-asset-mgmt/gitea-webhook.env` 配置这两个变量；若该服务环境文件由系统管理员
集中管理，也可将同样的两个非敏感地址写入 `/opt/office-asset-mgmt/.env`，更新服务会在未设置
对应系统环境变量时读取它们。`.env` 中不得写入 Gitea 账号、密码或访问令牌。

Each release must add a corresponding entry to `VERSION_NOTES.md`, including database
migrations, backup requirements, configuration changes, and rollback notes.

Create and push an annotated release tag from the development machine:

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

Use the next unused SemVer tag for later releases. The tag must be annotated and the
matching version notes must already exist in the tagged commit.

Watch deployment logs:

```bash
sudo journalctl -u office-asset-gitea-webhook -f
docker compose -f /opt/office-asset-mgmt/compose.yaml ps
docker compose -f /opt/office-asset-mgmt/compose.yaml logs --tail=100 app
```

Before a schema-changing release, create a compressed backup and SHA-256 checksum with
the deployment user:

```bash
sudo -u officeasset-deploy -H bash \
  /opt/office-asset-mgmt/deploy/scripts/backup_compose_database.sh
```

The update script runs tracked migrations as a deployment gate before it replaces the
application container. For an existing database without `schema_migration`, set
`MIGRATION_ADOPT_BASELINE=legacy-20260813` temporarily in `/opt/office-asset-mgmt/.env`
only after the backup and legacy baseline have been verified. The migration runner
validates required legacy tables before recording the baseline. Remove the setting after
a successful deployment. The script restores the prior Git commit and starts the prior
app without rerunning its migration dependency if the migration, build, startup, or
health check fails.

## 6. Backup Gitea

Back up both the Gitea data volume and PostgreSQL volume. At minimum, stop writes before
copying them, or use a database-aware backup for PostgreSQL:

```bash
cd /opt/gitea
docker compose exec -T gitea-db pg_dump -U gitea gitea > gitea.sql
docker compose exec -T gitea-db pg_dumpall -U gitea --globals-only > gitea-globals.sql
```

Store these backups outside the server and protect them as sensitive data.
