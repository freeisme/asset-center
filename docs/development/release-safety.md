# 发布前脱敏检查

本仓库可能被公开访问，任何提交到远程或打包发布的内容都必须先通过脱敏检查。

## 检查命令

```bash
python tools/scan_release_safety.py --rev HEAD
```

脚本从 git 对象库读取指定版本的受跟踪文件，命中任意规则时返回退出码 `1` 并列出文件、行号和规则名。
CI 的 `Verify source` 工作流已包含该步骤，未通过时不会执行后续检查。

## 检查规则

| 规则 | 说明 |
| --- | --- |
| `cloud-or-personal-access-token` | 常见云平台与个人访问令牌前缀 |
| `private-key-material` | 私钥文件正文 |
| `ssh-key-material` | SSH 公钥正文 |
| `internal-hostname` | 内网域名与内部主机名（`host.docker.internal` 等容器内通用名称除外） |
| `internal-ipv4` | 内网 IPv4 网段 |
| `local-machine-path` | 本机用户目录、盘符路径和项目工作目录 |
| `local-mysql-path` | 本机 MySQL 客户端安装路径 |
| `hardcoded-credential` | 直接写在代码或文档中的口令、令牌与密钥赋值 |
| `business-employee-number` | 企业工号等业务编号格式 |
| `internal-account-name` | 内网服务器账号、部署密钥文件名等标识 |

另外禁止提交 `.env`、数据库导出、压缩备份、业务表格、运行日志和内部交接文档。

## 编写规则

- 文档、示例和测试数据统一使用保留地址或占位符，不写真实主机、账号、口令和路径；
- 需要真实取值时，通过环境变量或服务器上的受保护配置文件提供，并在文档里写成 `<占位符>`；
- 不要为了通过扫描而把敏感内容改写成分散拼接的字符串；应直接删除。
- 扫描规则本身在 `tools/scan_release_safety.py`，新增生产环境标识时同步补充规则。

## 本地预检查（可选）

把下面内容保存为 `.git/hooks/pre-push` 并赋予执行权限，可以在本机推送前自动运行检查：

```bash
#!/usr/bin/env bash
set -e
python tools/scan_release_safety.py --rev HEAD
```
