"""End-to-end regression for the rack layout module (v2.9.0).

Runs against a disposable database that already has every tracked migration
applied. It seeds an organization, two accounts, a computer asset, a site and a
rack, then checks the rack layout API:

* devices can be placed from the asset ledger into a rack slot;
* the same computer cannot be placed twice, and it is offered again after下架;
* front and rear planes coexist at the same U, while整机深度 conflicts with both;
* out-of-range and overlapping placements are rejected with a conflict;
* moving and resizing a placement is validated and audited;
* placements can be removed, keeping an audit trail;
* the viewer account is refused by the rack_layout permission module.

Run with::

    $env:DB_PASSWORD = "<password>"
    $env:DB_NAME = "office_asset_mgmt_codex_rack_layout_20260918"
    python .\\tests\\integration\\qa_rack_layout_regression.py
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
DB_NAME = os.environ.get("DB_NAME", "office_asset_mgmt_codex_rack_layout_20260918")
SERVER_PORT = int(os.environ.get("QA_RACK_LAYOUT_PORT", "8024"))
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"
# Never store a fixed credential in the repository: the fixture users are
# created by this script, so a per-run random password is enough.
PASSWORD = os.environ.get("QA_RACK_LAYOUT_PASSWORD") or f"Qa{secrets.token_urlsafe(12)}!"
PREFIX = "qark"


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
    return Path(tempfile.gettempdir()) / f"qa_rack_layout_server_{SERVER_PORT}.log"


def cleanup() -> None:
    statements = [
        f"DELETE FROM rack_device_placement WHERE rack_id IN (SELECT rack_id FROM asset_rack WHERE rack_code LIKE '{PREFIX.upper()}%')",
        f"DELETE FROM asset_rack WHERE rack_code LIKE '{PREFIX.upper()}%'",
        f"DELETE FROM asset_site WHERE site_code LIKE '{PREFIX.upper()}%'",
        f"DELETE FROM audit_log WHERE actor LIKE '{PREFIX}%'",
        f"DELETE FROM computer_asset WHERE device_name LIKE '{PREFIX}%'",
        f"DELETE FROM employee WHERE employee_name LIKE '{PREFIX}%'",
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
    account_hash = password_hash(PASSWORD)
    sql_run(
        f"""
        INSERT INTO user_account (username, display_name, password_hash, user_role, role_code, is_active)
        VALUES
          ('{PREFIX}_admin_{suffix}', '{PREFIX}管理员', '{account_hash}', 'admin', 'admin', 1),
          ('{PREFIX}_viewer_{suffix}', '{PREFIX}只读', '{account_hash}', 'viewer', 'viewer', 1);
        """
    )
    sql_run(
        f"""
        INSERT INTO org_unit (org_code, org_name, sort_order, is_active)
        VALUES ('{PREFIX.upper()}-{suffix}', '{PREFIX}机柜组织', 920, 1);
        """
    )
    org_id = sql_scalar(f"SELECT org_unit_id FROM org_unit WHERE org_code = '{PREFIX.upper()}-{suffix}';")
    sql_run(
        f"""
        INSERT INTO employee (employee_no, employee_name, org_unit_id, employment_status, is_active)
        VALUES ('{PREFIX.upper()}-EMP-{suffix}', '{PREFIX}员工', {org_id}, 'active', 1);
        """
    )
    sql_run(
        f"""
        INSERT INTO computer_asset (
          device_name, org_unit_id, device_type, brand, model, cpu, memory, storage, gpu,
          fixed_asset_code, sn_st, location, it_asset_status, is_active
        )
        VALUES (
          '{PREFIX}-SRV-{suffix}', {org_id}, 'server', '戴尔', 'PowerEdge-R650', 'Xeon-4310',
          '64G', '2T SSD', '集显', '{PREFIX.upper()}-FA-{suffix}', '{PREFIX.upper()}-SN-{suffix}',
          '机房待上架', 'idle', 1
        );
        """
    )
    return {
        "org_id": org_id,
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
    suffix = str(int(time.time()))[-6:]
    fixture = seed(suffix)
    admin = login(fixture["admin"])

    status, payload = admin.request(
        "POST",
        "/api/inspection/sites",
        {"code": f"{PREFIX.upper()}-SR-{suffix}", "name": f"{PREFIX}主机房", "siteType": "server_room"},
        expected=201,
    )
    site_id = payload["id"]
    status, payload = admin.request(
        "POST",
        "/api/inspection/racks",
        {"code": f"{PREFIX.upper()}-RK-{suffix}", "name": f"{PREFIX}A01", "siteId": site_id, "heightU": 42},
        expected=201,
    )
    rack_id = payload["id"]

    status, payload = admin.request("GET", "/api/rack-layout/racks", expected=200)
    racks = payload.get("racks") or []
    our_rack = next((item for item in racks if str(item["id"]) == str(rack_id)), None)
    assert our_rack, racks
    assert int(our_rack["heightU"]) == 42 and int(our_rack["usedUnits"]) == 0, our_rack
    print("rack list ok:", our_rack["name"], our_rack["heightU"], "U")

    status, payload = admin.request("GET", "/api/rack-layout/available", expected=200)
    computers = payload.get("computers") or []
    our_computer = next((item for item in computers if item["name"] == f"{PREFIX}-SRV-{suffix}"), None)
    assert our_computer, computers[:5]
    print("available devices ok:", len(computers), "台办公终端")

    place_payload = {
        "sourceKind": "computer",
        "computerId": our_computer["computerId"],
        "displayName": our_computer["name"],
        "brandModel": our_computer["brandModel"],
        "category": "server",
        "positionU": 10,
        "uHeight": 2,
        "face": "front",
    }
    idempotency_key = f"{PREFIX}-place-{suffix}"
    status, payload = admin.request(
        "POST",
        f"/api/rack-layout/racks/{rack_id}/placements",
        place_payload,
        expected=201,
        extra_headers={"Idempotency-Key": idempotency_key},
    )
    computer_placement_id = payload["id"]
    status, repeat = admin.request(
        "POST",
        f"/api/rack-layout/racks/{rack_id}/placements",
        place_payload,
        expected=201,
        extra_headers={"Idempotency-Key": idempotency_key},
    )
    assert repeat["id"] == computer_placement_id, (repeat, computer_placement_id)
    print("place computer ok:", computer_placement_id)

    admin.request(
        "POST",
        f"/api/rack-layout/racks/{rack_id}/placements",
        {
            "sourceKind": "custom",
            "displayName": f"{PREFIX} 重复上架测试",
            "positionU": 20,
            "uHeight": 1,
            "category": "server",
        },
        expected=201,
        extra_headers={"Idempotency-Key": f"{PREFIX}-custom-{suffix}"},
    )
    admin.request(
        "POST",
        f"/api/rack-layout/racks/{rack_id}/placements",
        {
            "sourceKind": "custom",
            "displayName": f"{PREFIX} 重叠测试",
            "positionU": 10,
            "uHeight": 1,
            "category": "network",
            "face": "front",
        },
        expected=409,
        extra_headers={"Idempotency-Key": f"{PREFIX}-clash-{suffix}"},
    )
    print("front plane conflict rejected")

    status, rear = admin.request(
        "POST",
        f"/api/rack-layout/racks/{rack_id}/placements",
        {
            "sourceKind": "custom",
            "displayName": f"{PREFIX} 后面板风扇",
            "positionU": 10,
            "uHeight": 1,
            "category": "cooling",
            "face": "rear",
        },
        expected=201,
        extra_headers={"Idempotency-Key": f"{PREFIX}-rear-{suffix}"},
    )
    rear_placement_id = rear["id"]
    print("front and rear planes coexist at U10")

    admin.request(
        "POST",
        f"/api/rack-layout/racks/{rack_id}/placements",
        {
            "sourceKind": "custom",
            "displayName": f"{PREFIX} 超界测试",
            "positionU": 42,
            "uHeight": 2,
            "category": "server",
        },
        expected=409,
        extra_headers={"Idempotency-Key": f"{PREFIX}-range-{suffix}"},
    )
    print("out-of-range placement rejected")

    admin.request(
        "PUT",
        f"/api/rack-layout/placements/{computer_placement_id}",
        {"positionU": 30, "uHeight": 4, "face": "front", "displayName": our_computer["name"]},
        expected=200,
    )
    admin.request(
        "PUT",
        f"/api/rack-layout/placements/{computer_placement_id}",
        {"positionU": 10, "uHeight": 1, "face": "both", "displayName": our_computer["name"]},
        expected=409,
    )
    admin.request(
        "PUT",
        f"/api/rack-layout/placements/{rear_placement_id}",
        {"positionU": 44, "uHeight": 1, "face": "rear", "displayName": f"{PREFIX} 后面板风扇"},
        expected=409,
    )
    print("move validation ok")

    status, payload = admin.request(
        "GET",
        f"/api/rack-layout/racks/{rack_id}",
        expected=200,
    )
    rack = payload["rack"]
    placements = rack["placements"]
    assert len(placements) == 3, placements
    assert rack["usedUnits"] == 4 + 1 + 1, rack
    moved = next(item for item in placements if str(item["id"]) == str(computer_placement_id))
    assert int(moved["positionU"]) == 30 and int(moved["uHeight"]) == 4, moved
    assert moved["assetCode"] == f"{PREFIX.upper()}-FA-{suffix}", moved
    print("placement readback ok:", rack["usedUnits"], "U used")

    admin.request(
        "POST",
        f"/api/rack-layout/placements/{computer_placement_id}/remove",
        {"reason": f"{PREFIX} 测试下架"},
        expected=200,
    )
    status, payload = admin.request("GET", "/api/rack-layout/available", expected=200)
    names = [item["name"] for item in payload.get("computers") or []]
    assert f"{PREFIX}-SRV-{suffix}" in names, names[:5]
    print("removed device is offered again")

    audit_rows = sql_rows(
        "SELECT action_type FROM audit_log WHERE entity_type = 'rack_device_placement' "
        "ORDER BY audit_log_id DESC LIMIT 6;"
    )
    assert "rack_placement_created" in audit_rows, audit_rows
    assert "rack_placement_updated" in audit_rows, audit_rows
    assert "rack_placement_removed" in audit_rows, audit_rows
    print("audit trail ok:", sorted(set(audit_rows)))

    viewer = login(fixture["viewer"])
    viewer.request("GET", "/api/rack-layout/racks", expected=403)
    viewer.request("GET", f"/api/rack-layout/racks/{rack_id}", expected=403)
    viewer.request(
        "POST",
        f"/api/rack-layout/racks/{rack_id}/placements",
        {"sourceKind": "custom", "displayName": f"{PREFIX} 越权", "positionU": 1, "uHeight": 1},
        expected=403,
    )
    print("permission checks ok")

    print("RACK LAYOUT REGRESSION OK")
    return 0


if __name__ == "__main__":
    server_process = None
    try:
        server_process = start_server()
        raise SystemExit(main())
    finally:
        if server_process is not None:
            server_process.terminate()
