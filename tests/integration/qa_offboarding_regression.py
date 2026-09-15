"""End-to-end regression for offboarding recovery warehouse selection.

Verifies the release requirement "选择回收时必须选择回收到哪个仓库":

* the offboarding command rejects a recovery item without a target warehouse;
* a deducted item is returned to the selected warehouse and the stock quantity
  is restored there;
* an item registered without stock deduction keeps stock untouched but still
  records the destination warehouse;
* the archive snapshot keeps the selected warehouse.

Run with::

    $env:DB_PASSWORD = "<password>"
    $env:DB_NAME = "office_asset_mgmt_codex_offboard_20260915"
    python .\\tests\\integration\\qa_offboarding_regression.py
"""

from __future__ import annotations

import base64
import hashlib
import http.cookiejar
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MYSQL = Path(os.environ.get("MYSQL_BIN", "mysql"))
DB_NAME = os.environ.get("DB_NAME", "office_asset_mgmt_codex_offboard_20260915")
SERVER_PORT = int(os.environ.get("QA_OFFBOARD_PORT", "8015"))
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"
PASSWORD = os.environ.get("QA_OFFBOARD_PASSWORD") or f"Qa{secrets.token_urlsafe(12)}!"
PREFIX = "qaoff"
MONITOR_TYPE_ID = 1


def password_hash(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=32768,
        r=8,
        p=1,
        dklen=64,
        maxmem=64 * 1024 * 1024,
    )
    return "scrypt$N=32768,r=8,p=1${}${}".format(
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(derived).decode("ascii"),
    )


def _mysql_args(sql: str, database: str) -> list[str]:
    return [
        str(MYSQL),
        "--protocol=tcp",
        "--host=127.0.0.1",
        "--port=3306",
        "--user=root",
        f"--database={database}",
        "--default-character-set=utf8mb4",
        "--batch",
        "--raw",
        "--skip-column-names",
        "--silent",
        "-e",
        sql,
    ]


def sql_rows(sql: str, database: str | None = None) -> list[str]:
    env = os.environ.copy()
    env["MYSQL_PWD"] = os.environ.get("DB_PASSWORD", "")
    result = subprocess.run(
        _mysql_args(sql, database or DB_NAME),
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def sql_scalar(sql: str, database: str | None = None) -> str:
    rows = sql_rows(sql, database)
    return rows[0] if rows else ""


def sql_run(sql: str, database: str | None = None) -> None:
    sql_rows(sql, database)


def server_log_path() -> Path:
    return Path(tempfile.gettempdir()) / f"qa_offboard_server_{SERVER_PORT}.log"


def cleanup() -> None:
    statements = [
        f"DELETE FROM inventory_movement_log WHERE related_employee_name LIKE '{PREFIX}%'",
        f"DELETE FROM left_employee_archive WHERE employee_name LIKE '{PREFIX}%'",
        f"DELETE FROM inventory_allocation_history WHERE employee_id IN (SELECT employee_id FROM employee WHERE employee_name LIKE '{PREFIX}%')",
        f"DELETE FROM computer_assignment_history WHERE employee_name LIKE '{PREFIX}%'",
        f"DELETE FROM computer_assignment WHERE employee_id IN (SELECT employee_id FROM employee WHERE employee_name LIKE '{PREFIX}%')",
        f"DELETE FROM employee_monitor_usage WHERE employee_id IN (SELECT employee_id FROM employee WHERE employee_name LIKE '{PREFIX}%')",
        f"DELETE FROM employee_non_asset_usage WHERE employee_id IN (SELECT employee_id FROM employee WHERE employee_name LIKE '{PREFIX}%')",
        f"DELETE FROM computer_asset WHERE device_name LIKE '{PREFIX}%'",
        f"DELETE FROM employee WHERE employee_name LIKE '{PREFIX}%'",
        f"DELETE FROM inventory_warehouse_stock WHERE model_id IN (SELECT model_id FROM it_inventory_model WHERE model_name LIKE '{PREFIX}%')",
        f"DELETE FROM it_inventory_model WHERE model_name LIKE '{PREFIX}%'",
        f"DELETE FROM it_inventory_brand WHERE brand_name LIKE '{PREFIX}%'",
        f"DELETE FROM inventory_warehouse WHERE warehouse_code LIKE '{PREFIX.upper()}%'",
        f"DELETE FROM org_unit WHERE org_code LIKE '{PREFIX.upper()}%'",
        f"DELETE FROM user_account WHERE username LIKE '{PREFIX}%'",
    ]
    for statement in statements:
        try:
            sql_run(statement)
        except RuntimeError:
            pass


class Client:
    def __init__(self) -> None:
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def csrf(self) -> str:
        return next((item.value for item in self.jar if item.name == "oa_csrf"), "")

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        expected: int | None = None,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if method not in {"GET", "HEAD", "OPTIONS"}:
            headers["X-CSRF-Token"] = self.csrf()
        if extra_headers:
            headers.update(extra_headers)
        request = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=15) as response:
                status = response.status
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            status = error.code
            raw = error.read().decode("utf-8")
        result = json.loads(raw) if raw else {}
        if expected is not None and status != expected:
            raise AssertionError(f"{method} {path}: expected {expected}, got {status}: {result}")
        return status, result


def login(username: str) -> Client:
    last_error: object | None = None
    for _ in range(30):
        client = Client()
        status, payload = client.request(
            "POST",
            "/api/auth/login",
            {"username": username, "password": PASSWORD},
        )
        if status == 200:
            return client
        last_error = (status, payload)
        time.sleep(0.4)
    raise AssertionError(f"login failed for {username}: {last_error}")


def start_server() -> "subprocess.Popen[str]":
    env = os.environ.copy()
    env.update(
        {
            "DB_USER": "root",
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "3306",
            "DB_NAME": DB_NAME,
            "MYSQL_BIN": str(MYSQL),
            "MYSQLDUMP_BIN": os.environ.get("MYSQLDUMP_BIN", "mysqldump"),
            "SERVER_HOST": "127.0.0.1",
            "SERVER_PORT": str(SERVER_PORT),
            "PYTHONUNBUFFERED": "1",
        }
    )
    process = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=str(ROOT),
        env=env,
        stdout=open(server_log_path(), "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        text=True,
    )
    for _ in range(40):
        try:
            status, payload = Client().request("GET", "/api/health")
            if status == 200 and payload.get("ok"):
                return process
        except Exception:
            pass
        if process.poll() is not None:
            raise AssertionError("server process exited before becoming healthy")
        time.sleep(0.5)
    process.terminate()
    raise AssertionError("service did not become healthy")


def seed(suffix: str) -> dict[str, str]:
    admin_hash = password_hash(PASSWORD)
    sql_run(
        f"""
        INSERT INTO user_account (username, display_name, password_hash, user_role, role_code, is_active)
        VALUES ('{PREFIX}_admin_{suffix}', '{PREFIX}管理员', '{admin_hash}', 'admin', 'admin', 1);
        """
    )
    sql_run(
        f"""
        INSERT INTO org_unit (org_code, org_name, sort_order, is_active)
        VALUES ('{PREFIX.upper()}-{suffix}', '{PREFIX}回收组织', 901, 1);
        """
    )
    org_id = sql_scalar(f"SELECT org_unit_id FROM org_unit WHERE org_code = '{PREFIX.upper()}-{suffix}';")
    sql_run(
        f"""
        INSERT INTO employee (employee_no, employee_name, org_unit_id, employment_status, is_active)
        VALUES ('{PREFIX.upper()}-EMP-{suffix}', '{PREFIX}员工', {org_id}, 'active', 1);
        """
    )
    employee_id = sql_scalar(
        f"SELECT employee_id FROM employee WHERE employee_no = '{PREFIX.upper()}-EMP-{suffix}';"
    )
    sql_run(
        f"""
        INSERT INTO it_inventory_brand (non_asset_type_id, brand_name, is_active)
        VALUES ({MONITOR_TYPE_ID}, '{PREFIX}品牌-{suffix}', 1);
        """
    )
    brand_id = sql_scalar(f"SELECT brand_id FROM it_inventory_brand WHERE brand_name = '{PREFIX}品牌-{suffix}';")
    sql_run(
        f"""
        INSERT INTO it_inventory_model (non_asset_type_id, brand_id, model_name, batch_key, quantity, is_active)
        VALUES ({MONITOR_TYPE_ID}, {brand_id}, '{PREFIX}型号-{suffix}', 'qaoff-{suffix}', 5, 1);
        """
    )
    model_id = sql_scalar(f"SELECT model_id FROM it_inventory_model WHERE model_name = '{PREFIX}型号-{suffix}';")
    warehouse_ids: list[str] = []
    for index, name in enumerate(("A", "B"), start=1):
        code = f"{PREFIX.upper()}-WH{index}-{suffix}"
        sql_run(
            f"""
            INSERT INTO inventory_warehouse (warehouse_code, warehouse_name, org_unit_id, is_active)
            VALUES ('{code}', '{PREFIX}仓库{name}', {org_id}, 1);
            """
        )
        warehouse_ids.append(
            sql_scalar(f"SELECT warehouse_id FROM inventory_warehouse WHERE warehouse_code = '{code}';")
        )
    sql_run(
        f"""
        INSERT INTO inventory_warehouse_stock (warehouse_id, model_id, quantity)
        VALUES ({warehouse_ids[0]}, {model_id}, 3), ({warehouse_ids[1]}, {model_id}, 0);
        """
    )
    sql_run(
        f"""
        INSERT INTO computer_asset (
          device_name, org_unit_id, device_type, brand, model, it_asset_status, is_active
        )
        VALUES ('{PREFIX}-PC-{suffix}', {org_id}, 'laptop', '联想', 'ThinkPad', 'in_use', 1);
        """
    )
    computer_id = sql_scalar(f"SELECT computer_id FROM computer_asset WHERE device_name = '{PREFIX}-PC-{suffix}';")
    return {
        "org_id": org_id,
        "employee_id": employee_id,
        "model_id": model_id,
        "warehouse_a": warehouse_ids[0],
        "warehouse_b": warehouse_ids[1],
        "computer_id": computer_id,
        "suffix": suffix,
        "admin": f"{PREFIX}_admin_{suffix}",
    }


def main() -> int:
    if not os.environ.get("DB_PASSWORD"):
        raise RuntimeError("DB_PASSWORD environment variable is required.")
    cleanup()
    suffix = str(int(time.time()))
    fixture = seed(suffix)
    employee_id = fixture["employee_id"]
    model_id = fixture["model_id"]
    warehouse_a = fixture["warehouse_a"]
    warehouse_b = fixture["warehouse_b"]
    computer_id = fixture["computer_id"]
    admin = login(fixture["admin"])

    # 1. 发放一台扣减库存的显示屏，并登记一条不扣库存的物资。
    model_before = sql_scalar(f"SELECT quantity FROM it_inventory_model WHERE model_id = {model_id};")
    _, allocation = admin.request(
        "POST",
        "/api/inventory/allocations",
        {
            "allocationType": "monitor",
            "employeeId": employee_id,
            "modelId": model_id,
            "warehouseId": warehouse_a,
            "quantity": 1,
            "notes": f"{PREFIX} 发放",
        },
        expected=201,
        extra_headers={"Idempotency-Key": f"{PREFIX}-alloc-{suffix}"},
    )
    usage_record_id = str(allocation["usageRecordId"])
    stock_after_issue = sql_scalar(
        f"SELECT quantity FROM inventory_warehouse_stock WHERE warehouse_id = {warehouse_a} AND model_id = {model_id};"
    )
    sql_run(
        f"""
        INSERT INTO employee_non_asset_usage (
          employee_id, non_asset_type_id, inventory_brand_id, inventory_model_id,
          brand, model, quantity, stock_adjusted, notes, is_active
        )
        VALUES ({employee_id}, 2, NULL, NULL, '{PREFIX}自定义品牌', '{PREFIX}定制物资', 2, 0, '{PREFIX} 登记不扣库存', 1);
        """
    )
    legacy_usage_id = sql_scalar(
        f"SELECT non_asset_usage_id FROM employee_non_asset_usage WHERE employee_id = {employee_id} AND notes = '{PREFIX} 登记不扣库存';"
    )
    sql_run(
        f"""
        INSERT INTO computer_assignment (computer_id, employee_id, assignment_status, notes)
        VALUES ({computer_id}, {employee_id}, 'active', '{PREFIX} 分配');
        """
    )

    # 2. 离职预览必须列出全部项目。
    _, preview = admin.request(
        "GET",
        f"/api/employees/{employee_id}/offboarding-preview",
        expected=200,
    )
    preview_items = preview.get("items") or []
    assert len(preview_items) == 3, preview_items
    items_by_key = {str(item.get("key") or ""): item for item in preview_items}
    monitor_key = f"monitor:{usage_record_id}"
    non_asset_key = f"non_asset:{legacy_usage_id}"
    computer_key = f"computer:{computer_id}"
    assert monitor_key in items_by_key and non_asset_key in items_by_key and computer_key in items_by_key

    def plan(recovery_warehouse: str, include_non_asset_warehouse: bool = True) -> list[dict]:
        return [
            {
                "itemType": "monitor",
                "itemId": usage_record_id,
                "action": "recover",
                "recoveryWarehouseId": recovery_warehouse,
            },
            {
                "itemType": "non_asset",
                "itemId": legacy_usage_id,
                "action": "recover",
                "recoveryWarehouseId": recovery_warehouse if include_non_asset_warehouse else "",
            },
            {
                "itemType": "computer",
                "itemId": computer_id,
                "action": "recover",
                "recoveryWarehouseId": recovery_warehouse,
            },
        ]

    offboard_payload = {
        "leaveDate": "2026-09-15",
        "leaveReason": f"{PREFIX} 回归测试",
        "leaveRemark": f"{PREFIX} 回归测试",
    }

    # 3. 缺少仓库必须被拒绝（含未扣库存的物资）。
    status, error = admin.request(
        "POST",
        f"/api/employees/{employee_id}/offboard",
        {**offboard_payload, "items": plan(warehouse_a, include_non_asset_warehouse=False)},
        extra_headers={"Idempotency-Key": f"{PREFIX}-offboard-missing-{suffix}"},
    )
    assert status == 400, (status, error)
    assert "回收目标仓库" in json.dumps(error, ensure_ascii=False), error
    assert sql_scalar(f"SELECT employment_status FROM employee WHERE employee_id = {employee_id};") == "active"
    print("missing recovery warehouse rejected ok")

    # 4. 指定另一个仓库后办理成功，库存必须回到该仓库。
    status, result = admin.request(
        "POST",
        f"/api/employees/{employee_id}/offboard",
        {**offboard_payload, "items": plan(warehouse_b)},
        expected=200,
        extra_headers={"Idempotency-Key": f"{PREFIX}-offboard-{suffix}"},
    )
    assert result.get("archiveId"), result
    assert sql_scalar(f"SELECT employment_status FROM employee WHERE employee_id = {employee_id};") == "left"
    assert (
        sql_scalar(
            f"SELECT quantity FROM inventory_warehouse_stock WHERE warehouse_id = {warehouse_a} AND model_id = {model_id};"
        )
        == stock_after_issue
    ), "回收不应回到原发放仓库"
    assert (
        sql_scalar(
            f"SELECT quantity FROM inventory_warehouse_stock WHERE warehouse_id = {warehouse_b} AND model_id = {model_id};"
        )
        == "1"
    ), "库存必须回到选择的回收仓库"
    assert sql_scalar(f"SELECT quantity FROM it_inventory_model WHERE model_id = {model_id};") == model_before
    assert (
        sql_scalar(
            "SELECT status FROM inventory_allocation_history WHERE allocation_type = 'monitor' "
            f"AND usage_record_id = {usage_record_id};"
        )
        == "returned"
    )
    assert (
        sql_scalar(
            "SELECT warehouse_id FROM inventory_allocation_history WHERE allocation_type = 'monitor' "
            f"AND usage_record_id = {usage_record_id};"
        )
        == warehouse_b
    )
    assert (
        sql_scalar(
            "SELECT warehouse_id FROM inventory_allocation_history WHERE allocation_type = 'non_asset' "
            f"AND usage_record_id = {legacy_usage_id};"
        )
        == warehouse_b
    ), "未扣库存的物资也要记录回收仓库"
    # 登记物资（未扣库存）现在同样回收入库，因此会产生第二条离职回收流转记录。
    assert (
        sql_scalar(
            f"SELECT COUNT(*) FROM inventory_movement_log WHERE trigger_action = 'leave_recovery' AND target_warehouse_id = {warehouse_b};"
        )
        == "2"
    ), "显示屏与登记物资都应产生离职回收流转记录"
    assert len(result.get("recoveryRecords") or []) == 2, result.get("recoveryRecords")
    new_model_id = sql_scalar(
        "SELECT model_id FROM it_inventory_model WHERE model_name = '"
        f"{PREFIX}定制物资' ORDER BY model_id DESC LIMIT 1;"
    )
    assert new_model_id, "缺少品牌型号的登记物资应自动创建库存型号"
    assert sql_scalar(f"SELECT quantity FROM it_inventory_model WHERE model_id = {new_model_id};") == "2"
    assert (
        sql_scalar(
            f"SELECT quantity FROM inventory_warehouse_stock WHERE warehouse_id = {warehouse_b} AND model_id = {new_model_id};"
        )
        == "2"
    ), "自动创建的型号必须回收到指定仓库"
    snapshot = sql_scalar(
        f"SELECT CAST(device_snapshot AS CHAR) FROM left_employee_archive WHERE employee_no = '{PREFIX.upper()}-EMP-{suffix}' ORDER BY archive_id DESC LIMIT 1;"
    )
    assert snapshot, "离职档案缺少设备快照"
    recorded_warehouses = snapshot.count(
        f'"recoveryWarehouseId":"{warehouse_b}"'
    ) + snapshot.count(f'"recoveryWarehouseId": "{warehouse_b}"')
    assert recorded_warehouses == 3, f"归档快照必须记录三件物资的回收仓库: {snapshot[:400]}"
    print("offboarding recovery warehouse enforced:", result.get("archiveId"))
    print("OFFBOARDING REGRESSION OK")
    return 0


if __name__ == "__main__":
    process = None
    try:
        process = start_server()
        raise SystemExit(main())
    finally:
        if process is not None:
            process.terminate()
