from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a UTF-8 SQL file through mysql.exe.")
    parser.add_argument("--mysql", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--user", default="root")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--database", default="")
    parser.add_argument("--strip-use", action="store_true")
    args = parser.parse_args()

    sql_path = Path(args.file).resolve()
    if not sql_path.exists():
        raise SystemExit(f"SQL file not found: {sql_path}")
    mysql_path = Path(args.mysql)
    if mysql_path.exists():
        mysql_executable = str(mysql_path)
    else:
        mysql_executable = shutil.which(args.mysql)
        if not mysql_executable:
            raise SystemExit(f"MySQL client not found: {args.mysql}")

    command = [
        mysql_executable,
        "--protocol=tcp",
        f"--host={args.host}",
        f"--port={args.port}",
        f"--user={args.user}",
        "--default-character-set=utf8mb4",
    ]
    if args.database:
        command.append(f"--database={args.database}")

    sql_bytes = sql_path.read_bytes()
    if args.strip_use:
        sql_text = sql_bytes.decode("utf-8-sig")
        sql_text = re.sub(
            r"(?im)^\s*USE\s+[^;]+;\s*(?:\r?\n)?",
            "",
            sql_text,
        )
        sql_bytes = sql_text.encode("utf-8")

    completed = subprocess.run(
        command,
        input=sql_bytes,
        capture_output=True,
        env=os.environ.copy(),
    )
    if completed.returncode:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise SystemExit(message or f"MySQL failed with exit code {completed.returncode}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
