# 生产扫描整改说明：Nginx 加固、端口收敛与 CSRF 复测

本文档记录一次外部安全扫描（扫描目标填的是服务器地址，即默认 HTTP 端口）的复核过程，
以及三项整改结论：端口仅本机访问、Nginx 层补齐安全响应头并隐藏 Server 头、CSRF 项复测。

文中一律使用占位符，不在文档里写真实主机、网段、账号和证书路径。

## 一、扫描到底命中了哪一层

只读探测结果（`<主机>` 替换为实际服务器地址）：

| 探测 | 结果 |
| --- | --- |
| `curl -I http://<主机>/` | `200` + `Server: openresty`，响应头里没有任何安全头 |
| `curl -I http://<主机>:8000/` | `200` + 应用下发的 CSP、X-Content-Type-Options、X-Frame-Options、Referrer-Policy、Permissions-Policy、COOP、CORP |
| `curl -kI https://<主机>/` | TLS 握手被拒绝（curl 返回 `000`），代理默认站点配置里是 `ssl_reject_handshake on` |
| `curl -X POST http://<主机>/api/tickets` | `404`（代理层是静态占位站点，没有该路径） |
| 代理层 `nginx.conf` | 已设置 `server_tokens off`，所以 `Server` 头只去掉了版本号，保留了 `openresty` |
| 代理层 `nginx -V` | 已编译 `--add-module=../headers-more-nginx-module-0.39` |

结论：**80/443 上跑的是 1Panel OpenResty 自带的静态占位站点**（`root /usr/share/nginx/html`），
应用容器实际监听 `:8000` 并直接对局域网提供服务。扫描器因此没有扫到应用本身。

这解释了报告里的大部分条目：

- “未使用 HTTPS / 内容安全策略 CSP 缺失 / X-Content-Type-Options / Referrer-Policy /
  Permissions-Policy / X-XSS-Protection / COOP / CORP / X-Frame-Options 缺失”命中的是代理层占位站点。
  这些头**应用本身已经下发**（见 `server.py` 的 `end_headers`），业务端口并不缺。
- “敏感信息泄露 Server=openresty”来自 OpenResty，应用端口返回的是 `SimpleHTTP` 版本号，
  两者都应该在代理层统一隐藏。
- “CSRF 漏洞”命中的是静态占位页面里返回的 `200`，不是应用接口（见第四节）。

## 二、端口收敛：只允许本机访问

目标状态（应用只通过代理对外提供服务）：

| 端口 | 服务 | 目标 |
| --- | --- | --- |
| 80 / 443 | OpenResty 反向代理 | 保留，作为唯一对外入口 |
| 8000 | 应用容器 | 只绑 `127.0.0.1` |
| 9000 | Gitea 部署 Webhook | 只绑 `127.0.0.1` |
| 3306 | 1Panel MySQL | 只绑 `127.0.0.1` |
| 9100 | node-exporter | 只绑 `127.0.0.1`，或不再对外发布 |
| 3001 / 2222 | Gitea Web / SSH | 按实际需要收敛到本机或指定管理网段 |
| 22 | SSH | 保留，用防火墙限制来源网段 |

操作步骤：

1. 应用端口。把生产 `compose.yaml` 里的应用端口映射改成只绑回环地址，然后只重建应用服务：

   ```yaml
   ports:
     - "127.0.0.1:${APP_PORT:-8000}:8000"
   ```

   ```bash
   docker compose up -d --no-deps app
   ```

   仓库内的 `compose.yaml` 保持 `"${APP_PORT:-8000}:8000"`，是为了让没有反向代理的
   单机部署可以直接访问；只在有代理的生产实例上改成回环绑定。

2. Webhook 端口。在服务器的 webhook 环境文件（`EnvironmentFile` 指向的那个文件）里加入
   或改成仅本机监听，然后重启服务：

   ```text
   WEBHOOK_BIND=127.0.0.1
   WEBHOOK_PORT=9000
   ```

   ```bash
   sudo systemctl restart office-asset-gitea-webhook.service
   ```

   注意：Webhook 只允许 Gitea 本机调用；即使需要跨主机调用，也应该走代理并按来源网段限制。

3. 1Panel 组件。MySQL 和 node-exporter 由 1Panel 管理，在 1Panel 的容器详情里把端口发布改成
   `127.0.0.1:3306:3306`，node-exporter 直接不要对外发布端口（1Panel 自身即可抓取）。
   只在 1Panel 界面改，不要手工改它的 compose 文件。

4. 防火墙兜底（ufw 已启用）。只放通必要来源：

   ```bash
   sudo ufw allow from <办公网段> to any port 80,443 proto tcp
   sudo ufw allow from <管理网段> to any port 22 proto tcp
   sudo ufw deny 3306/tcp
   sudo ufw deny 9100/tcp
   sudo ufw deny 9000/tcp
   sudo ufw status numbered
   ```

   规则顺序会影响结果，`deny` 之前不要留下更宽松的 `allow <端口>`。

5. 验证。从另一台机器执行，除 80/443/22 外都应连接失败：

   ```bash
   for p in 8000 9000 9100 3306; do
     timeout 3 bash -c "echo > /dev/tcp/<主机>/$p" 2>/dev/null \
       && echo "$p 仍然可访问" || echo "$p 已收敛"
   done
   ```

## 三、Nginx 层补齐响应头并隐藏 Server 头

**可修复，且已在生产实际的 OpenResty 版本上验证过。**

- `server_tokens off` 已经开启，但它只去掉版本号，`Server: openresty` 仍然会返回；
  彻底隐藏需要 headers-more 模块的 `more_clear_headers`，生产 OpenResty 已编译该模块。
- 用生产容器和一份临时配置执行 `nginx -t`，返回
  `configuration file ... syntax is ok / test is successful`，说明该写法在本版本可直接生效。
  校验用的临时文件已删除，线上配置没有被改动。

落地步骤：

1. 站点配置使用仓库内的 [deploy/nginx/office-asset-mgmt.conf](../../deploy/nginx/office-asset-mgmt.conf)，
   它包含 `server_tokens off`、`more_clear_headers Server` 和应用同一套安全响应头。
2. 1Panel OpenResty 的站点配置目录是 `/opt/1panel/www/conf.d/`（容器内挂载为
   `/usr/local/openresty/nginx/conf/conf.d/`）。把文件放成
   `/opt/1panel/www/conf.d/office-asset-mgmt.conf`。
3. 把 `server_name` 改成实际访问用的域名或服务器 IP。**不要写 `_`**：OpenResty 自带的
   `00.default.conf` 已经用 `_` 占了 default_server，用 `_` 的站点不会生效，请求会继续落到静态占位页。
4. 校验并热加载：

   ```bash
   docker exec <openresty 容器名> nginx -t
   docker exec <openresty 容器名> nginx -s reload
   ```

5. 验证：

   ```bash
   curl -sI http://<主机>/ | grep -iE 'server:|content-security-policy|x-frame-options|x-content-type|referrer-policy|permissions-policy|cross-origin|x-xss'
   ```

   期望：没有 `Server` 头，并且上面这些安全头都出现。

补充说明：

- 使用 HTTPS 时再补 `Strict-Transport-Security`，并把 `AUTH_COOKIE_SECURE=true` 打开
  （此时 Cookie 才会带上 `Secure`）。
- 如果目标环境的 Nginx 没有 headers-more 模块，删掉 `more_*` 指令并改用配置文件中注释的
  `add_header ... always` 写法；该写法无法隐藏 `Server` 头。
- 反向代理上线后应把 `compose.yaml` 的应用端口改成第二节的 `127.0.0.1` 绑定，
  否则 `:8000` 仍可直接访问，代理层的响应头会被绕过。

## 四、CSRF 复测：结论是误报

复测按扫描器的方式构造请求：伪造外部 `Referer`/`Origin`，观察响应是否变化。

### 4.1 生产只读探测

请求都不带会话与令牌，因此只会被拒绝或落到静态页面，不会修改数据。

| 请求 | 结果 | 说明 |
| --- | --- | --- |
| `POST http://<主机>:8000/api/tickets`（伪造外部 Referer、无会话） | `401` | 应用先做登录校验，未登录写请求直接拒绝 |
| `GET http://<主机>:8000/api/state`（伪造外部 Referer、无会话） | `401` | 未登录不能读状态 |
| `POST http://<主机>/api/tickets`（伪造外部 Referer） | `404` | 代理层是静态站点，没有该接口 |
| `GET http://<主机>/`（伪造外部 Referer） | `200` | **扫描器看到的 `200` 就是这个静态页面** |

### 4.2 带有效会话的完整矩阵

在本地测试实例上以登录会话执行，覆盖扫描器未构造的场景：

| 用例 | 结果 |
| --- | --- |
| 写接口 POST，伪造外部 Referer/Origin，**不带** CSRF 令牌 | `403 CSRF_INVALID` |
| 写接口 POST，伪造外部 Referer/Origin，**带错误** CSRF 令牌 | `403 CSRF_INVALID` |
| 写接口 POST，伪造外部 Referer/Origin，**带正确** CSRF 令牌 | 正常受理（业务校验结果） |
| 只读 GET，伪造外部 Referer | `200`（只读接口，符合预期） |

结论：

- 服务端 CSRF 判定只看 `X-CSRF-Token` 与数据库中会话的 `csrfHash` 是否匹配
  （`server.py` 的 `require_csrf`），**不读 `Referer`**；伪造 `Referer` 不会让写请求通过。
- 只读接口对伪造 `Referer` 返回 `200` 属于预期行为，不构成 CSRF 漏洞。
- 会话 Cookie 使用 `HttpOnly; SameSite=Lax`，CSRF Cookie 使用 `SameSite=Lax`，
  浏览器跨站场景下不会自动携带会话。
- 扫描报告里的“修改 Referer 后响应仍为 200”来自静态占位页面的 `200`，
  既没有有效会话也没有业务动作，**属于误报**。

该复测已固化为 `tests/integration/qa_security_regression.py` 中的 `csrf_scanner_referer`
检查项，回归通过时会在输出里列出，后续扫描或改动可以直接复跑。

## 五、验证清单

```text
[ ] 应用端口、Webhook 端口、MySQL、node-exporter 不再对局域网开放
[ ] http://<主机>/ 返回应用页面，且不再落到 OpenResty 静态占位页
[ ] 响应头没有 Server，且带 CSP / X-Content-Type-Options / X-Frame-Options /
    X-XSS-Protection / Referrer-Policy / Permissions-Policy / COOP / CORP
[ ] 启用 HTTPS 后补充 HSTS，并设置 AUTH_COOKIE_SECURE=true
[ ] 伪造 Referer 的写请求仍然返回 403（无令牌或令牌错误）
[ ] tests/integration/qa_security_regression.py 输出 QA_REGRESSION_PASS
```
