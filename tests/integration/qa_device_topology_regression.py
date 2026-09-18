"""End-to-end regression for the device panel and topology module.

Covers phases 1 and 2: device type import with port templates, port
initialisation for a placed device, cable creation with port-conflict rules,
the topology payload, saved node positions, audit trail and permissions.

Run with::

    $env:DB_PASSWORD = "<password>"
    $env:DB_NAME = "office_asset_mgmt_codex_device_topology_20260918"
    python .\\tests\\integration\\qa_device_topology_regression.py
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
DB_NAME = os.environ.get("DB_NAME", "office_asset_mgmt_codex_device_topology_20260918")
SERVER_PORT = int(os.environ.get("QA_DEVICE_TOPOLOGY_PORT", "8026"))
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"
PASSWORD = os.environ.get("QA_DEVICE_TOPOLOGY_PASSWORD") or f"Qa{secrets.token_urlsafe(12)}!"
PREFIX = "qadt"

SAMPLE_YAML = """---
manufacturer: {prefix}Vendor
model: {prefix}Switch 24
slug: {prefix}-switch-24
part_number: TS-24
u_height: 1
is_full_depth: false
front_image: false
rear_image: true
interfaces:
  - name: GE1
    type: 1000base-t
  - name: GE2
    type: 1000base-t
  - name: XGE1
    type: 10gbase-x-sfpp
power-ports:
  - name: PSU1
    type: iec-60320-c14
"""


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
    return Path(tempfile.gettempdir()) / f"qa_device_topology_server_{SERVER_PORT}.log"


def _test_rack_ids() -> str:
    return f"SELECT rack_id FROM asset_rack WHERE rack_code LIKE '{PREFIX.upper()}%'"


def _test_placement_ids() -> str:
    return f"SELECT placement_id FROM rack_device_placement WHERE rack_id IN ({_test_rack_ids()})"


def cleanup() -> None:
    statements = [
        f"DELETE FROM topology_node_position WHERE node_id IN ({_test_placement_ids()})",
        f"DELETE FROM rack_cable_run WHERE a_port_id IN (SELECT port_id FROM rack_device_port WHERE placement_id IN ({_test_placement_ids()}))",
        f"DELETE FROM rack_device_port WHERE placement_id IN ({_test_placement_ids()})",
        f"DELETE FROM rack_device_placement WHERE rack_id IN ({_test_rack_ids()})",
        f"DELETE FROM asset_rack WHERE rack_code LIKE '{PREFIX.upper()}%'",
        f"DELETE FROM asset_site WHERE site_code LIKE '{PREFIX.upper()}%'",
        f"DELETE FROM device_type_port_template WHERE catalog_id IN (SELECT catalog_id FROM device_type_catalog WHERE slug LIKE '{PREFIX}%')",
        f"DELETE FROM device_type_catalog WHERE slug LIKE '{PREFIX}%'",
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
        VALUES ('{PREFIX.upper()}-{suffix}', '{PREFIX}拓扑组织', 930, 1);
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
          device_name, org_unit_id, device_type, brand, model, fixed_asset_code, sn_st,
          location, it_asset_status, is_active
        )
        VALUES (
          '{PREFIX}-SRV-{suffix}', {org_id}, 'server', '{PREFIX}Vendor', 'Rack Server',
          '{PREFIX.upper()}-FA-{suffix}', '{PREFIX.upper()}-SN-{suffix}', '机房待上架', 'idle', 1
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
        "/api/device-types/import",
        {"source": "inline", "yamlText": SAMPLE_YAML.format(prefix=PREFIX)},
        expected=201,
    )
    catalog_id = payload["catalogId"]
    assert payload["portCount"] == 4, payload
    status, payload = admin.request("GET", f"/api/device-types/{catalog_id}", expected=200)
    kinds = sorted(item["kind"] for item in payload["deviceType"]["ports"])
    assert kinds == ["fiber", "network", "network", "power"], kinds
    print("device type import ok:", catalog_id, kinds)

    status, payload = admin.request(
        "POST",
        "/api/inspection/sites",
        {"code": f"{PREFIX.upper()}-SR-{suffix}", "name": f"{PREFIX}机房", "siteType": "server_room"},
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

    status, payload = admin.request("GET", "/api/rack-layout/available", expected=200)
    computer = next(item for item in payload["computers"] if item["name"] == f"{PREFIX}-SRV-{suffix}")

    status, switch = admin.request(
        "POST",
        f"/api/rack-layout/racks/{rack_id}/placements",
        {
            "sourceKind": "custom",
            "displayName": f"{PREFIX} 交换机",
            "brandModel": f"{PREFIX}Switch 24",
            "category": "network",
            "positionU": 40,
            "uHeight": 1,
            "face": "front",
        },
        expected=201,
        extra_headers={"Idempotency-Key": f"{PREFIX}-sw-{suffix}"},
    )
    status, server = admin.request(
        "POST",
        f"/api/rack-layout/racks/{rack_id}/placements",
        {
            "sourceKind": "computer",
            "computerId": computer["computerId"],
            "displayName": computer["name"],
            "brandModel": computer["brandModel"],
            "category": "server",
            "positionU": 30,
            "uHeight": 2,
            "face": "front",
        },
        expected=201,
        extra_headers={"Idempotency-Key": f"{PREFIX}-srv-{suffix}"},
    )
    print("placements ok:", switch["id"], server["id"])

    status, payload = admin.request(
        "POST",
        f"/api/rack-layout/placements/{switch['id']}/ports/import",
        {"catalogId": catalog_id, "applyHeight": True, "uHeight": 1},
        expected=201,
    )
    assert payload["created"] == 4, payload
    status, again = admin.request(
        "POST",
        f"/api/rack-layout/placements/{switch['id']}/ports/import",
        {"catalogId": catalog_id},
        expected=201,
    )
    assert again["created"] == 0 and again["skipped"] == 4, again
    print("port template import ok:", payload, again)

    status, payload = admin.request(
        "POST",
        f"/api/rack-layout/placements/{server['id']}/ports",
        {"name": "NIC1", "type": "1000base-t", "kind": "network", "face": "rear", "rowIndex": 1, "positionIndex": 1},
        expected=201,
    )
    server_port_id = payload["id"]

    status, payload = admin.request("GET", f"/api/rack-layout/racks/{rack_id}/ports", expected=200)
    rack_ports = payload["rack"]
    assert rack_ports["portCount"] == 5, rack_ports["portCount"]
    switch_ports = next(item for item in rack_ports["placements"] if item["placementId"] == switch["id"])["ports"]
    ge1 = next(item for item in switch_ports if item["name"] == "GE1")
    print("rack ports ok:", rack_ports["portCount"])

    cable_payload = {
        "aPortId": ge1["id"],
        "bPortId": server_port_id,
        "medium": "cat6",
        "lengthM": 5,
        "label": f"{PREFIX} 测试链路",
    }
    status, payload = admin.request(
        "POST",
        "/api/rack-layout/cables",
        cable_payload,
        expected=201,
        extra_headers={"Idempotency-Key": f"{PREFIX}-cable-{suffix}"},
    )
    cable_id = payload["id"]
    status, repeat = admin.request(
        "POST",
        "/api/rack-layout/cables",
        cable_payload,
        expected=201,
        extra_headers={"Idempotency-Key": f"{PREFIX}-cable-{suffix}"},
    )
    assert repeat["id"] == cable_id, (repeat, cable_id)
    admin.request(
        "POST",
        "/api/rack-layout/cables",
        {"aPortId": ge1["id"], "bPortId": next(item for item in switch_ports if item["name"] == "GE2")["id"], "medium": "cat6"},
        expected=409,
    )
    print("cable create + conflict ok:", cable_id)

    status, payload = admin.request(
        "GET",
        f"/api/rack-layout/topology?siteId={site_id}&onlyLinked=1",
        expected=200,
    )
    assert len(payload["nodes"]) == 2, payload["nodes"]
    assert len(payload["links"]) == 1, payload["links"]
    node_ids = [item["id"] for item in payload["nodes"]]
    status, saved = admin.request(
        "POST",
        "/api/rack-layout/topology/positions",
        {"nodes": [{"nodeId": node_ids[0], "x": 120, "y": 80}, {"nodeId": node_ids[1], "x": 320, "y": 180}]},
        expected=200,
    )
    assert saved["saved"] == 2, saved
    status, payload = admin.request("GET", f"/api/rack-layout/topology?siteId={site_id}", expected=200)
    assert len(payload["positions"]) == 2, payload["positions"]
    print("topology ok:", len(payload["nodes"]), "节点", len(payload["links"]), "链路")

    admin.request(
        "POST",
        f"/api/rack-layout/cables/{cable_id}/remove",
        {"reason": f"{PREFIX} 测试拆除"},
        expected=200,
    )
    status, payload = admin.request("GET", f"/api/rack-layout/cables?rackId={rack_id}", expected=200)
    assert payload["cables"] == [], payload["cables"]
    admin.request(
        "POST",
        f"/api/rack-layout/ports/{server_port_id}/remove",
        {"reason": f"{PREFIX} 测试移除"},
        expected=200,
    )
    print("cable and port removal ok")

    audit_rows = sql_rows(
        "SELECT action_type FROM audit_log WHERE entity_type IN "
        "('device_type_catalog', 'rack_device_port', 'rack_cable_run', 'topology_node_position', "
        "'rack_device_placement') "
        "GROUP BY action_type;"
    )
    for expected_action in (
        "device_type_imported",
        "rack_port_created",
        "placement_ports_initialized",
        "rack_cable_created",
        "rack_cable_removed",
        "topology_positions_saved",
    ):
        assert expected_action in audit_rows, (expected_action, audit_rows)
    print("audit ok:", sorted(audit_rows))

    viewer = login(fixture["viewer"])
    viewer.request("GET", "/api/device-types", expected=403)
    viewer.request("GET", f"/api/rack-layout/racks/{rack_id}/ports", expected=403)
    viewer.request("GET", "/api/rack-layout/topology", expected=403)
    viewer.request(
        "POST",
        "/api/rack-layout/cables",
        {"aPortId": ge1["id"], "bPortId": server_port_id, "medium": "cat6"},
        expected=403,
    )
    print("permission checks ok")

    print("DEVICE TOPOLOGY REGRESSION OK")
    return 0


if __name__ == "__main__":
    server_process = None
    try:
        server_process = start_server()
        raise SystemExit(main())
    finally:
        if server_process is not None:
            server_process.terminate()
