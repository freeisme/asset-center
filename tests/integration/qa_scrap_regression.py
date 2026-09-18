"""End-to-end regression for direct scrap handling (v2.3.0).

The script runs against a disposable database that already has every tracked
migration applied. It seeds its own organization, employee, inventory batch,
warehouse stock and computer asset, then verifies:

* issued IT supplies can be scrapped without returning stock;
* items registered without stock deduction never change stock when scrapped;
* computer scrap retires and soft archives the asset, keeping a snapshot;
* scrap commands are permission checked, auditable and idempotent;
* scrap records can be listed and read back.

Run with::

    $env:DB_PASSWORD = "<password>"
    $env:DB_NAME = "office_asset_mgmt_codex_scrap_20260915"
    python .\\tests\\integration\\qa_scrap_regression.py
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
DB_NAME = os.environ.get("DB_NAME", "office_asset_mgmt_codex_scrap_20260915")
SERVER_PORT = int(os.environ.get("QA_SCRAP_PORT", "8013"))
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"
# Never store a fixed credential in the repository: the fixture users are
# created by this script, so a per-run random password is enough.
PASSWORD = os.environ.get("QA_SCRAP_PASSWORD") or f"Qa{secrets.token_urlsafe(12)}!"
PREFIX = "qasc"
MONITOR_TYPE_ID = 1
MOUSE_TYPE_ID = 2


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
    return Path(tempfile.gettempdir()) / f"qa_scrap_server_{SERVER_PORT}.log"


def cleanup() -> None:
    statements = [
        f"DELETE FROM inventory_scrap_record WHERE operated_by_name LIKE '{PREFIX}%'",
        f"DELETE FROM asset_scrap_record WHERE operated_by_name LIKE '{PREFIX}%'",
        f"DELETE FROM inventory_scrap_record WHERE employee_name LIKE '{PREFIX}%'",
        f"DELETE FROM asset_scrap_record WHERE employee_name LIKE '{PREFIX}%'",
        f"DELETE FROM inventory_allocation_history WHERE notes LIKE '%{PREFIX}%'",
        f"DELETE FROM inventory_movement_log WHERE related_employee_name LIKE '{PREFIX}%'",
        f"DELETE FROM computer_assignment_history WHERE employee_name LIKE '{PREFIX}%'",
        f"DELETE FROM computer_assignment WHERE employee_id IN (SELECT employee_id FROM employee WHERE employee_name LIKE '{PREFIX}%')",
        f"DELETE FROM employee_monitor_usage WHERE employee_id IN (SELECT employee_id FROM employee WHERE employee_name LIKE '{PREFIX}%')",
        f"DELETE FROM employee_non_asset_usage WHERE employee_id IN (SELECT employee_id FROM employee WHERE employee_name LIKE '{PREFIX}%')",
        f"DELETE FROM asset_status_history WHERE computer_id IN (SELECT computer_id FROM computer_asset WHERE device_name LIKE '{PREFIX}%')",
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
        except RuntimeError as error:
            print(f"cleanup skipped: {statement.splitlines()[0][:80]} :: {error}", flush=True)


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


def seed(suffix: str) -> dict[str, str]:
    admin_hash = password_hash(PASSWORD)
    sql_run(
        f"""
        INSERT INTO user_account (username, display_name, password_hash, user_role, role_code, is_active)
        VALUES
          ('{PREFIX}_admin_{suffix}', '{PREFIX}管理员', '{admin_hash}', 'admin', 'admin', 1),
          ('{PREFIX}_viewer_{suffix}', '{PREFIX}只读', '{admin_hash}', 'viewer', 'viewer', 1);
        """
    )
    sql_run(
        f"""
        INSERT INTO org_unit (org_code, org_name, sort_order, is_active)
        VALUES ('{PREFIX.upper()}-{suffix}', '{PREFIX}报废组织', 900, 1);
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
        VALUES ({MONITOR_TYPE_ID}, {brand_id}, '{PREFIX}型号-{suffix}', 'qasc-{suffix}', 5, 1);
        """
    )
    model_id = sql_scalar(f"SELECT model_id FROM it_inventory_model WHERE model_name = '{PREFIX}型号-{suffix}';")
    sql_run(
        f"""
        INSERT INTO inventory_warehouse (warehouse_code, warehouse_name, org_unit_id, is_active)
        VALUES ('{PREFIX.upper()}-WH-{suffix}', '{PREFIX}报废仓库', {org_id}, 1);
        """
    )
    warehouse_id = sql_scalar(
        f"SELECT warehouse_id FROM inventory_warehouse WHERE warehouse_code = '{PREFIX.upper()}-WH-{suffix}';"
    )
    sql_run(
        f"""
        INSERT INTO inventory_warehouse_stock (warehouse_id, model_id, quantity)
        VALUES ({warehouse_id}, {model_id}, 5);
        """
    )
    sql_run(
        f"""
        INSERT INTO computer_asset (
          device_name, org_unit_id, device_type, brand, model, cpu, memory, storage, gpu,
          fixed_asset_code, sn_st, location, it_asset_status, is_active
        )
        VALUES (
          '{PREFIX}-PC-{suffix}', {org_id}, 'laptop', '联想', 'ThinkPad-X1', 'i7-1360P',
          '32G', '1T SSD', '集显', '{PREFIX.upper()}-FA-{suffix}', '{PREFIX.upper()}-SN-{suffix}',
          'IT 仓库', 'idle', 1
        );
        """
    )
    computer_id = sql_scalar(f"SELECT computer_id FROM computer_asset WHERE device_name = '{PREFIX}-PC-{suffix}';")
    return {
        "org_id": org_id,
        "employee_id": employee_id,
        "brand_id": brand_id,
        "model_id": model_id,
        "warehouse_id": warehouse_id,
        "computer_id": computer_id,
        "suffix": suffix,
        "admin": f"{PREFIX}_admin_{suffix}",
        "viewer": f"{PREFIX}_viewer_{suffix}",
    }


def start_server() -> "subprocess.Popen[str]":
    """Start the application against the disposable database."""
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


def main() -> int:
    if not os.environ.get("DB_PASSWORD"):
        raise RuntimeError("DB_PASSWORD environment variable is required.")
    cleanup()
    suffix = str(int(time.time()))
    fixture = seed(suffix)
    employee_id = fixture["employee_id"]
    model_id = fixture["model_id"]
    warehouse_id = fixture["warehouse_id"]
    computer_id = fixture["computer_id"]
    admin = login(fixture["admin"])

    status, health = admin.request("GET", "/api/health", expected=200)
    assert health.get("requiredTableCount") == 69, health
    print("health ok:", status, health.get("requiredTables"), "/", health.get("requiredTableCount"))

    status, payload = admin.request("GET", "/api/scrap-reasons", expected=200)
    reasons = payload.get("reasons") or []
    assert len(reasons) >= 5 and any(item["code"] == "damaged_unrepairable" for item in reasons), reasons
    print("scrap reasons:", [item["code"] for item in reasons])

    # 1. Issued monitor with stock deduction: scrap must not restore stock.
    model_before = sql_scalar(f"SELECT quantity FROM it_inventory_model WHERE model_id = {model_id};")
    stock_before = sql_scalar(
        f"SELECT quantity FROM inventory_warehouse_stock WHERE warehouse_id = {warehouse_id} AND model_id = {model_id};"
    )
    status, allocation = admin.request(
        "POST",
        "/api/inventory/allocations",
        {
            "allocationType": "monitor",
            "employeeId": employee_id,
            "modelId": model_id,
            "warehouseId": warehouse_id,
            "quantity": 1,
            "notes": f"{PREFIX} issue",
        },
        expected=201,
        extra_headers={"Idempotency-Key": f"{PREFIX}-alloc-{suffix}"},
    )
    usage_record_id = str(allocation["usageRecordId"])
    model_after_issue = sql_scalar(f"SELECT quantity FROM it_inventory_model WHERE model_id = {model_id};")
    assert model_before != model_after_issue, (model_before, model_after_issue)

    scrap_key = f"{PREFIX}-scrap-monitor-{suffix}"
    status, scrap = admin.request(
        "POST",
        f"/api/inventory/usage/monitor/{usage_record_id}/scrap",
        {"reasonCode": "damaged_unrepairable", "notes": f"{PREFIX} 屏幕损坏报废"},
        expected=201,
        extra_headers={"Idempotency-Key": scrap_key},
    )
    assert scrap["stockRestored"] is False, scrap
    assert scrap["status"] == "scrapped", scrap
    assert sql_scalar(f"SELECT quantity FROM it_inventory_model WHERE model_id = {model_id};") == model_after_issue
    assert (
        sql_scalar(
            f"SELECT quantity FROM inventory_warehouse_stock WHERE warehouse_id = {warehouse_id} AND model_id = {model_id};"
        )
        == str(int(stock_before) - 1)
    )
    assert sql_scalar(f"SELECT is_active FROM employee_monitor_usage WHERE monitor_usage_id = {usage_record_id};") == "0"
    assert (
        sql_scalar(
            f"SELECT COUNT(*) FROM employee_monitor_usage WHERE monitor_usage_id = {usage_record_id};"
        )
        == "1"
    ), "scrapped usage row must be retained"
    assert (
        sql_scalar(
            "SELECT status FROM inventory_allocation_history WHERE usage_record_id = "
            f"{usage_record_id} AND allocation_type = 'monitor';"
        )
        == "scrapped"
    )
    scrap_id = sql_scalar(
        f"SELECT scrap_id FROM inventory_scrap_record WHERE usage_record_id = {usage_record_id};"
    )
    assert scrap_id, "inventory scrap record missing"
    assert (
        sql_scalar(
            f"SELECT stock_adjusted FROM inventory_scrap_record WHERE scrap_id = {scrap_id};"
        )
        == "1"
    )
    assert (
        sql_scalar(f"SELECT COUNT(*) FROM audit_log WHERE action_type = 'inventory_scrapped' AND entity_id = '{scrap_id}';")
        == "1"
    ), "scrap must be audited"
    print("issued monitor scrapped without stock restore:", scrap_id)

    # Idempotent retry returns the cached result and writes no second record.
    status, retry = admin.request(
        "POST",
        f"/api/inventory/usage/monitor/{usage_record_id}/scrap",
        {"reasonCode": "damaged_unrepairable", "notes": f"{PREFIX} 屏幕损坏报废"},
        expected=201,
        extra_headers={"Idempotency-Key": scrap_key},
    )
    assert retry["scrapId"] == scrap["scrapId"], (retry, scrap)
    assert sql_scalar(f"SELECT COUNT(*) FROM inventory_scrap_record WHERE usage_record_id = {usage_record_id};") == "1"

    # 2. Legacy registration without stock deduction keeps stock untouched.
    sql_run(
        f"""
        INSERT INTO employee_non_asset_usage (
          employee_id, non_asset_type_id, inventory_brand_id, inventory_model_id,
          brand, model, quantity, stock_adjusted, notes, is_active
        )
        VALUES ({employee_id}, {MOUSE_TYPE_ID}, NULL, NULL, '{PREFIX}自定义品牌', '{PREFIX}鼠标', 2, 0, '{PREFIX} 登记不扣库存', 1);
        """
    )
    legacy_usage_id = sql_scalar(
        f"SELECT non_asset_usage_id FROM employee_non_asset_usage WHERE employee_id = {employee_id} AND notes = '{PREFIX} 登记不扣库存';"
    )
    status, legacy_scrap = admin.request(
        "POST",
        f"/api/inventory/usage/non_asset/{legacy_usage_id}/scrap",
        {"reasonCode": "lost_offsite", "notes": f"{PREFIX} 丢失报废"},
        expected=201,
        extra_headers={"Idempotency-Key": f"{PREFIX}-scrap-legacy-{suffix}"},
    )
    assert legacy_scrap["stockAdjusted"] is False, legacy_scrap
    assert sql_scalar(f"SELECT quantity FROM it_inventory_model WHERE model_id = {model_id};") == model_after_issue
    assert sql_scalar(f"SELECT is_active FROM employee_non_asset_usage WHERE non_asset_usage_id = {legacy_usage_id};") == "0"
    assert (
        sql_scalar(
            f"SELECT stock_adjusted FROM inventory_scrap_record WHERE usage_record_id = {legacy_usage_id} AND allocation_type = 'non_asset';"
        )
        == "0"
    )
    print("legacy non-deducted supply scrapped without stock change:", legacy_usage_id)

    # 3. Computer scrap retires and soft archives the asset with a snapshot.
    admin.request(
        "POST",
        f"/api/computers/{computer_id}/assignments",
        {"employeeId": employee_id, "notes": f"{PREFIX} assign"},
        expected=201,
        extra_headers={"Idempotency-Key": f"{PREFIX}-assign-{suffix}"},
    )
    status, computer_scrap = admin.request(
        "POST",
        f"/api/computers/{computer_id}/scrap",
        {"reasonCode": "worn_out", "notes": f"{PREFIX} 主板损坏报废", "attachmentRef": "附件单号 QASC-001"},
        expected=201,
        extra_headers={"Idempotency-Key": f"{PREFIX}-scrap-computer-{suffix}"},
    )
    assert computer_scrap["archived"] is True and computer_scrap["status"] == "retired", computer_scrap
    assert computer_scrap["holderAssignmentClosed"] is True, computer_scrap
    assert sql_scalar(f"SELECT is_archived FROM computer_asset WHERE computer_id = {computer_id};") == "1"
    assert sql_scalar(f"SELECT it_asset_status FROM computer_asset WHERE computer_id = {computer_id};") == "retired"
    assert (
        sql_scalar(
            f"SELECT COUNT(*) FROM computer_assignment WHERE computer_id = {computer_id} AND returned_at IS NULL;"
        )
        == "0"
    ), "scrap must close the active assignment"
    assert (
        sql_scalar(
            f"SELECT CONCAT_WS('|', cpu, memory, storage, gpu) FROM asset_scrap_record WHERE computer_id = {computer_id};"
        )
        == "i7-1360P|32G|1T SSD|集显"
    ), "scrap record must snapshot the device configuration"
    assert (
        sql_scalar(
            f"SELECT COUNT(*) FROM asset_status_history WHERE computer_id = {computer_id} AND reason = 'Computer scrap';"
        )
        == "1"
    )
    _, state = admin.request("GET", "/api/state", expected=200)
    assert all(str(item.get("id")) != str(computer_id) for item in state.get("computers") or []), (
        "archived computer must not stay in the ledger"
    )
    # A different idempotency key must not archive twice.
    status, conflict = admin.request(
        "POST",
        f"/api/computers/{computer_id}/scrap",
        {"reasonCode": "worn_out", "notes": f"{PREFIX} 重复报废"},
        extra_headers={"Idempotency-Key": f"{PREFIX}-scrap-computer-again-{suffix}"},
    )
    assert status == 409, (status, conflict)
    assert sql_scalar(f"SELECT COUNT(*) FROM asset_scrap_record WHERE computer_id = {computer_id};") == "1"
    print("computer scrapped and archived:", computer_id)

    # 4. Scrap records are listable and readable.
    status, listing = admin.request("GET", "/api/scrap-records?limit=200", expected=200)
    records = listing.get("records") or []
    inventory_record = next(item for item in records if item["kind"] == "inventory" and item["id"] == scrap_id)
    assert inventory_record["reason"], inventory_record
    assert any(item["kind"] == "asset" and item["computerId"] == str(computer_id) for item in records)
    status, detail = admin.request("GET", f"/api/scrap-records/inventory:{scrap_id}", expected=200)
    assert detail["record"]["modelName"], detail
    status, asset_only = admin.request("GET", "/api/scrap-records?kind=asset", expected=200)
    assert all(item["kind"] == "asset" for item in asset_only.get("records") or [])
    print("scrap records readable:", len(records), "records")

    # 5. Users without scrap permission are rejected on every entry point.
    viewer = login(fixture["viewer"])
    status, _ = viewer.request("GET", "/api/scrap-records")
    assert status == 403, status
    status, _ = viewer.request(
        "POST",
        f"/api/computers/{computer_id}/scrap",
        {"reasonCode": "worn_out"},
        extra_headers={"Idempotency-Key": f"{PREFIX}-viewer-{suffix}"},
    )
    assert status == 403, status
    status, _ = viewer.request(
        "POST",
        f"/api/inventory/usage/non_asset/{legacy_usage_id}/scrap",
        {"reasonCode": "lost_offsite"},
        extra_headers={"Idempotency-Key": f"{PREFIX}-viewer2-{suffix}"},
    )
    assert status == 403, status
    print("permission checks ok")

    print("SCRAP REGRESSION OK")
    return 0


if __name__ == "__main__":
    server_process = None
    try:
        server_process = start_server()
        raise SystemExit(main())
    finally:
        if server_process is not None:
            server_process.terminate()
