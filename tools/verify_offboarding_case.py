"""Read-only verification report for one offboarding / asset recovery case.

The report never writes to the database. It prints the evidence needed before
any manual repair: employee state, offboarding archive, computers, issued IT
supplies, allocation history, inventory movement logs and audit entries.

Example::

    $env:DB_PASSWORD = "<password>"
    python .\\tools\\verify_offboarding_case.py --employee-no <员工工号>

The report only prints database rows; pass the real employee id, employee number
or name on the command line instead of storing case details in this file.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MYSQL = "mysql"


def mysql_command(database: str) -> list[str]:
    return [
        os.environ.get("MYSQL_BIN", DEFAULT_MYSQL),
        "--protocol=tcp",
        f"--host={os.environ.get('DB_HOST', '127.0.0.1')}",
        f"--port={os.environ.get('DB_PORT', '3306')}",
        f"--user={os.environ.get('DB_USER', 'root')}",
        f"--database={database}",
        "--default-character-set=utf8mb4",
        "--batch",
        "--raw",
    ]


def run_sql(sql: str, database: str) -> str:
    password = os.environ.get("DB_PASSWORD", "")
    if not password:
        raise RuntimeError("DB_PASSWORD environment variable is required.")
    env = os.environ.copy()
    env["MYSQL_PWD"] = password
    completed = subprocess.run(
        mysql_command(database),
        input=sql,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(ROOT_DIR),
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def section(title: str, sql: str, database: str) -> None:
    print()
    print(f"=== {title} ===")
    try:
        output = run_sql(sql, database)
    except RuntimeError as error:
        print(f"（无法读取：{error}）")
        return
    print(output if output else "（无记录）")


def table_exists(table: str, database: str) -> bool:
    return sql_scalar(
        f"""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = {quote(database)} AND table_name = {quote(table)};
        """,
        "information_schema",
    ) not in {"", "0"}


def column_exists(table: str, column: str, database: str) -> bool:
    return sql_scalar(
        f"""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = {quote(database)}
          AND table_name = {quote(table)}
          AND column_name = {quote(column)};
        """,
        "information_schema",
    ) not in {"", "0"}


def sql_scalar(sql: str, database: str) -> str:
    lines = [line for line in run_sql(sql, database).splitlines() if line.strip()]
    return lines[-1].strip() if lines else ""


def qualified(alias: str, table: str, column: str, database: str) -> str:
    """Return a qualified column, or NULL when the column is missing."""
    return f"{alias}.{column}" if column_exists(table, column, database) else f"NULL AS {column}"


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only offboarding case verification.")
    parser.add_argument("--database", default=os.environ.get("DB_NAME", "office_asset_mgmt"))
    parser.add_argument("--employee-no", default="")
    parser.add_argument("--employee-id", default="")
    parser.add_argument("--name", default="")
    return parser.parse_args()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    args = build_args()
    if not (args.employee_id or args.employee_no or args.name):
        print("Provide --employee-id, --employee-no or --name.", file=sys.stderr)
        return 2

    filters: list[str] = []
    if args.employee_id:
        filters.append(f"employee_id = {int(args.employee_id)}")
    if args.employee_no:
        filters.append(f"employee_no = {quote(args.employee_no)}")
    if args.name:
        filters.append(f"employee_name = {quote(args.name)}")
    employee_where = " OR ".join(filters)
    database = args.database

    print(f"离线离职个案核验报告 · 数据库 {database}")
    print("只读检查，不会修改任何数据。")

    section(
        "1. 员工主记录",
        f"""
        SELECT employee_id, employee_no, employee_name, org_unit_id, department,
               position_name, employment_status, is_active, updated_at
        FROM employee
        WHERE {employee_where};
        """,
        database,
    )

    section(
        "2. 离职档案",
        f"""
        SELECT archive_id, source_employee_ref, employee_no, employee_name, org_path,
               leave_date, leave_info, leave_remark, archived_at,
               JSON_LENGTH(device_snapshot) AS snapshot_items
        FROM left_employee_archive
        WHERE employee_no IN (SELECT employee_no FROM employee WHERE {employee_where})
           OR employee_name IN (SELECT employee_name FROM employee WHERE {employee_where});
        """,
        database,
    )

    section(
        "3. 名下办公终端（当前领用）",
        f"""
        SELECT assignment.assignment_id, asset.computer_id, asset.device_name,
               asset.brand, asset.model, asset.fixed_asset_code, asset.it_asset_status,
               {qualified('asset', 'computer_asset', 'is_archived', database)},
               assignment.assigned_at, assignment.returned_at,
               assignment.assignment_status
        FROM computer_assignment assignment
        JOIN computer_asset asset ON asset.computer_id = assignment.computer_id
        WHERE assignment.employee_id IN (SELECT employee_id FROM employee WHERE {employee_where})
        ORDER BY assignment.assignment_id DESC;
        """,
        database,
    )

    section(
        "4. 名下办公终端（历史快照）",
        f"""
        SELECT history_id, computer_id, device_name, assigned_at, returned_at,
               assignment_status, notes
        FROM computer_assignment_history
        WHERE employee_id IN (SELECT employee_id FROM employee WHERE {employee_where})
        ORDER BY history_id DESC;
        """,
        database,
    )

    section(
        "5. 显示屏使用记录（含已关闭行）",
        f"""
        SELECT u.monitor_usage_id, u.display_name, u.model,
               u.quantity, u.stock_adjusted, u.inventory_model_id,
               u.is_active, u.notes, u.created_at, u.updated_at
        FROM employee_monitor_usage u
        WHERE u.employee_id IN (SELECT employee_id FROM employee WHERE {employee_where})
        ORDER BY u.monitor_usage_id;
        """,
        database,
    )

    section(
        "6. 非资产物资使用记录（含已关闭行）",
        f"""
        SELECT u.non_asset_usage_id, u.non_asset_type_id, u.brand, u.model,
               u.quantity, u.stock_adjusted, u.inventory_model_id,
               u.is_active, u.notes, u.created_at, u.updated_at
        FROM employee_non_asset_usage u
        WHERE u.employee_id IN (SELECT employee_id FROM employee WHERE {employee_where})
        ORDER BY u.non_asset_usage_id;
        """,
        database,
    )

    section(
        "7. 库存领用/归还历史",
        f"""
        SELECT allocation_id, allocation_type, inventory_model_id,
               {qualified('inventory_allocation_history', 'inventory_allocation_history', 'warehouse_id', database)},
               usage_record_id, quantity, stock_adjusted, status, issued_at, returned_at,
               notes, issued_by, returned_by
        FROM inventory_allocation_history
        WHERE employee_id IN (SELECT employee_id FROM employee WHERE {employee_where})
        ORDER BY allocation_id;
        """,
        database,
    )

    section(
        "8. 物资流转记录",
        f"""
        SELECT movement_log_id, movement_direction, type_name, brand_name, model_name,
               quantity, source_label, target_label, note, trigger_action, occurred_at
        FROM inventory_movement_log
        WHERE related_employee_no IN (SELECT employee_no FROM employee WHERE {employee_where})
           OR related_employee_name IN (SELECT employee_name FROM employee WHERE {employee_where})
        ORDER BY movement_log_id;
        """,
        database,
    )

    section(
        "9. 审计日志",
        f"""
        SELECT audit_log_id, action_type, entity_type, entity_id, entity_name,
               device_name, summary, actor, source, created_at
        FROM audit_log
        WHERE employee_name IN (SELECT employee_name FROM employee WHERE {employee_where})
           OR entity_name LIKE CONCAT('%', (SELECT employee_name FROM employee WHERE {employee_where} LIMIT 1), '%')
           OR summary LIKE CONCAT('%', (SELECT employee_name FROM employee WHERE {employee_where} LIMIT 1), '%')
        ORDER BY audit_log_id DESC
        LIMIT 50;
        """,
        database,
    )

    section(
        "10. 待核查提示",
        f"""
        SELECT '员工仍在职但已有回收记录' AS finding, COUNT(*) AS rows_found
        FROM employee e
        JOIN inventory_movement_log m ON m.related_employee_no = e.employee_no
        WHERE ({employee_where.replace('employee_id', 'e.employee_id').replace('employee_no', 'e.employee_no').replace('employee_name', 'e.employee_name')})
          AND e.employment_status <> 'left'
        UNION ALL
        SELECT '存在在用设备但无离职档案', COUNT(*)
        FROM employee e
        JOIN computer_assignment a ON a.employee_id = e.employee_id AND a.returned_at IS NULL
        WHERE ({employee_where.replace('employee_id', 'e.employee_id').replace('employee_no', 'e.employee_no').replace('employee_name', 'e.employee_name')})
          AND NOT EXISTS (
            SELECT 1 FROM left_employee_archive l WHERE l.employee_no = e.employee_no
          )
        UNION ALL
        SELECT '已关闭物资记录中标记为未扣库存', COUNT(*)
        FROM employee_monitor_usage u
        JOIN employee e ON e.employee_id = u.employee_id
        WHERE ({employee_where.replace('employee_id', 'e.employee_id').replace('employee_no', 'e.employee_no').replace('employee_name', 'e.employee_name')})
          AND u.is_active = 0 AND u.stock_adjusted = 0;
        """,
        database,
    )

    print()
    print("核验提示：以上数据只用于判断，不要在无备份、无来源证据的情况下调整库存或员工状态。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
