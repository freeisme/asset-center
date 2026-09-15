# 工具

- `migration_runner.py`：发现、校验并执行 `database/migrations/` 中的受跟踪迁移。
- `run_mysql_utf8.py`：通过 MySQL 客户端以 UTF-8 执行 SQL 文件，供 Windows 部署脚本使用。

根目录保留同名兼容入口，避免影响既有自动化。新脚本应引用本目录中的实现文件。
