"""End-to-end regression for inspection management (v2.8.0).

The script runs against a disposable database that already has every tracked
migration applied. It seeds its own organization and two accounts, then checks
the full inspection flow over the public API:

* sites, racks and templates can be maintained through resource endpoints;
* starting an inspection snapshots the template items into the task;
* starting twice with the same Idempotency-Key returns the same task;
* an abnormal item cannot be saved or submitted without a note;
* submitting requires every item to be answered and produces the counts;
* a submitted sheet is read-only, and mismatched templates are rejected;
* the viewer account is refused by the inspection permission module.

Run with::

    $env:DB_PASSWORD = "<password>"
    $env:DB_NAME = "office_asset_mgmt_codex_inspection_20260918"
    python .\\tests\\integration\\qa_inspection_regression.py
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
DB_NAME = os.environ.get("DB_NAME", "office_asset_mgmt_codex_inspection_20260918")
SERVER_PORT = int(os.environ.get("QA_INSPECTION_PORT", "8021"))
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"
# Never store a fixed credential in the repository: the fixture users are
# created by this script, so a per-run random password is enough.
PASSWORD = os.environ.get("QA_INSPECTION_PASSWORD") or f"Qa{secrets.token_urlsafe(12)}!"
PREFIX = "qaxj"


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
    return Path(tempfile.gettempdir()) / f"qa_inspection_server_{SERVER_PORT}.log"


def cleanup() -> None:
    statements = [
        f"DELETE FROM inspection_task_item WHERE task_id IN (SELECT task_id FROM inspection_task WHERE task_no LIKE 'XJ-%' AND (site_name LIKE '%{PREFIX}%' OR rack_name LIKE '%{PREFIX}%'))",
        f"DELETE FROM inspection_task WHERE site_name LIKE '%{PREFIX}%' OR rack_name LIKE '%{PREFIX}%'",
        f"DELETE FROM inspection_template WHERE template_code LIKE '{PREFIX.upper()}%'",
        f"DELETE FROM asset_rack WHERE rack_code LIKE '{PREFIX.upper()}%'",
        f"DELETE FROM asset_site WHERE site_code LIKE '{PREFIX.upper()}%'",
        f"DELETE FROM audit_log WHERE actor LIKE '{PREFIX}%'",
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
        VALUES ('{PREFIX.upper()}-{suffix}', '{PREFIX}巡检组织', 910, 1);
        """
    )
    org_id = sql_scalar(f"SELECT org_unit_id FROM org_unit WHERE org_code = '{PREFIX.upper()}-{suffix}';")
    sql_run(
        f"""
        INSERT INTO employee (employee_no, employee_name, org_unit_id, employment_status, is_active)
        VALUES ('{PREFIX.upper()}-EMP-{suffix}', '{PREFIX}员工', {org_id}, 'active', 1);
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

    status, payload = admin.request("GET", "/api/inspection/templates", expected=200)
    templates = payload.get("templates") or []
    assert templates, "seeded inspection templates are missing"
    server_template = next((item for item in templates if item["siteType"] == "server_room"), None)
    weak_template = next((item for item in templates if item["siteType"] == "weak_room"), None)
    assert server_template and weak_template, templates
    print("templates ok:", server_template["name"], server_template["itemCount"], "项")

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
        {
            "code": f"{PREFIX.upper()}-RK-{suffix}",
            "name": f"{PREFIX}A01 机柜",
            "siteId": site_id,
            "heightU": 42,
        },
        expected=201,
    )
    rack_id = payload["id"]

    status, payload = admin.request(
        "GET",
        f"/api/inspection/racks?siteId={site_id}",
        expected=200,
    )
    assert len(payload.get("racks") or []) == 1, payload
    print("site and rack ok:", site_id, rack_id)

    start_payload = {
        "templateId": server_template["id"],
        "scopeKind": "site",
        "siteId": site_id,
        "remarks": f"{PREFIX} 首次巡检",
    }
    idempotency_key = f"{PREFIX}-start-{suffix}"
    status, payload = admin.request(
        "POST",
        "/api/inspection/tasks",
        start_payload,
        expected=201,
        extra_headers={"Idempotency-Key": idempotency_key},
    )
    task_id = payload["id"]
    assert payload["itemTotal"] == int(server_template["itemCount"]), payload
    status, repeat = admin.request(
        "POST",
        "/api/inspection/tasks",
        start_payload,
        expected=201,
        extra_headers={"Idempotency-Key": idempotency_key},
    )
    assert repeat["id"] == task_id, (repeat, task_id)
    print("start inspection ok:", payload["taskNo"], payload["itemTotal"], "项")

    status, payload = admin.request("GET", f"/api/inspection/tasks/{task_id}", expected=200)
    task = payload["task"]
    items = task["items"]
    assert len(items) == int(server_template["itemCount"]), len(items)
    assert all(item["result"] == "pending" for item in items)

    first_item = items[0]
    admin.request(
        "POST",
        f"/api/inspection/tasks/{task_id}/items/{first_item['id']}/check",
        {"result": "fail", "valueText": "32", "notes": ""},
        expected=400,
    )
    admin.request(
        "POST",
        f"/api/inspection/tasks/{task_id}/items/{first_item['id']}/check",
        {"result": "fail", "valueText": "32", "notes": f"{PREFIX} 温度偏高"},
        expected=200,
    )
    print("abnormal note enforcement ok")

    status, payload = admin.request("POST", f"/api/inspection/tasks/{task_id}/submit", {}, expected=409)
    assert "未检查" in str(payload.get("error", "")), payload
    for item in items[1:]:
        admin.request(
            "POST",
            f"/api/inspection/tasks/{task_id}/items/{item['id']}/check",
            {"result": "ok", "valueText": "", "notes": ""},
            expected=200,
        )
    status, submitted = admin.request(
        "POST",
        f"/api/inspection/tasks/{task_id}/submit",
        {"abnormalSummary": f"{PREFIX} 需要更换空调滤网"},
        expected=200,
    )
    assert submitted["itemTotal"] == len(items), submitted
    assert submitted["itemFail"] == 1, submitted
    assert submitted["itemOk"] == len(items) - 1, submitted
    print("submit ok:", submitted)

    status, payload = admin.request("GET", f"/api/inspection/tasks/{task_id}", expected=200)
    task = payload["task"]
    assert task["status"] == "submitted", task
    assert task["itemFail"] == 1 and task["itemNa"] == 0, task
    admin.request(
        "POST",
        f"/api/inspection/tasks/{task_id}/items/{first_item['id']}/check",
        {"result": "ok", "valueText": "", "notes": ""},
        expected=409,
    )
    admin.request("POST", f"/api/inspection/tasks/{task_id}/void", {"reason": "test"}, expected=409)
    print("submitted sheet is read-only")

    admin.request(
        "POST",
        "/api/inspection/tasks",
        {"templateId": weak_template["id"], "scopeKind": "site", "siteId": site_id},
        expected=400,
        extra_headers={"Idempotency-Key": f"{PREFIX}-mismatch-{suffix}"},
    )
    print("template mismatch rejected")

    status, payload = admin.request("GET", "/api/inspection/tasks?status=submitted", expected=200)
    assert any(str(item["id"]) == str(task_id) for item in payload.get("tasks") or []), payload

    audit_rows = sql_rows(
        "SELECT action_type FROM audit_log "
        f"WHERE entity_type IN ('inspection_task', 'asset_site', 'asset_rack') "
        f"AND action_type IN ('inspection_started', 'inspection_submitted') "
        f"ORDER BY audit_log_id DESC LIMIT 4;"
    )
    assert "inspection_started" in audit_rows, audit_rows
    assert "inspection_submitted" in audit_rows, audit_rows
    print("audit trail ok:", audit_rows)

    viewer = login(fixture["viewer"])
    viewer.request("GET", "/api/inspection/tasks", expected=403)
    viewer.request("GET", "/api/inspection/templates", expected=403)
    viewer.request(
        "POST",
        "/api/inspection/sites",
        {"code": f"{PREFIX.upper()}-DENY-{suffix}", "name": f"{PREFIX}越权机房"},
        expected=403,
    )
    print("permission checks ok")

    print("INSPECTION REGRESSION OK")
    return 0


if __name__ == "__main__":
    server_process = None
    try:
        server_process = start_server()
        raise SystemExit(main())
    finally:
        if server_process is not None:
            server_process.terminate()
