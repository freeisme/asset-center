from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import ssl
import shutil
import subprocess
import threading
import traceback
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from office_asset.api_router import ApiDependencies, DomainApiRouter
from office_asset.jobs import finish_job_execution, job_run_key, run_periodic_job, start_job_execution
from office_asset.permissions import PermissionService
from office_asset.sql import SqlGateway, parse_bool


ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"

MYSQL_BIN = os.environ.get("MYSQL_BIN", "mysql")
MYSQLDUMP_BIN = os.environ.get(
    "MYSQLDUMP_BIN",
    str(Path(MYSQL_BIN).with_name(f"mysqldump{Path(MYSQL_BIN).suffix}")),
)
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_NAME = os.environ.get("DB_NAME", "office_asset_mgmt")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
SERVER_HOST = os.environ.get("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "8011"))
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", str(ROOT_DIR / "backups"))).expanduser().resolve()
UPDATE_SERVICE_URL = os.environ.get("UPDATE_SERVICE_URL", "https://host.docker.internal:9000").rstrip("/")
UPDATE_CONTROL_TOKEN = os.environ.get("UPDATE_CONTROL_TOKEN", "").strip()
UPDATE_REQUEST_TIMEOUT = max(3, int(os.environ.get("UPDATE_REQUEST_TIMEOUT", "12")))
UPDATE_SERVICE_CA_FILE = os.environ.get("UPDATE_SERVICE_CA_FILE", "").strip()
UPDATE_SERVICE_ALLOW_HTTP = (
    os.environ.get("UPDATE_SERVICE_ALLOW_HTTP", "").lower() in {"1", "true", "yes"}
)
AUTH_COOKIE_NAME = "oa_session"
CSRF_COOKIE_NAME = "oa_csrf"
AUTH_SESSION_HOURS = max(1, int(os.environ.get("AUTH_SESSION_HOURS", "8")))
AUTH_COOKIE_SECURE = os.environ.get("AUTH_COOKIE_SECURE", "").lower() in {"1", "true", "yes"}

DB_LOCK = threading.Lock()
BACKUP_LOCK = threading.Lock()
LOGIN_RATE_LOCK = threading.Lock()
AUDIT_LOG_LIMIT = 300
AUDIT_QUERY_LIMIT = 5000
BACKUP_LIST_LIMIT = 500
BACKUP_SCHEDULER_POLL_SECONDS = max(
    15,
    int(os.environ.get("BACKUP_SCHEDULER_POLL_SECONDS", "30")),
)
BACKUP_SCHEDULER_RETRY_SECONDS = max(
    60,
    int(os.environ.get("BACKUP_SCHEDULER_RETRY_SECONDS", "300")),
)
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = min(
    1024,
    max(32, int(os.environ.get("PASSWORD_MAX_LENGTH", "256"))),
)
LOGIN_RATE_WINDOW_SECONDS = max(
    60,
    int(os.environ.get("LOGIN_RATE_WINDOW_SECONDS", "300")),
)
LOGIN_RATE_MAX_ATTEMPTS = min(
    100,
    max(5, int(os.environ.get("LOGIN_RATE_MAX_ATTEMPTS", "15"))),
)
LOGIN_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
MAX_REQUEST_BODY_BYTES = min(
    64 * 1024 * 1024,
    max(64 * 1024, int(os.environ.get("MAX_REQUEST_BODY_BYTES", str(8 * 1024 * 1024)))),
)

SECURITY_CSP = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "object-src 'none'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "font-src 'self' data:"
)

AUDIT_STATUS_LABELS = {
    "in_use": "在用",
    "idle": "闲置",
    "repair": "维修",
    "retired": "报废",
    "lost": "丢失",
}

AUDIT_EMPLOYEE_STATUS_LABELS = {
    "active": "在职",
    "inactive": "停用",
    "left": "离职",
}


AUDIT_CATEGORY_ENTITY_TYPES = {
    "inventory": ("inventory_type", "inventory_brand", "inventory_model"),
    "employee": ("employee", "monitor", "non_asset"),
    "computer": ("computer",),
    "organization": ("org_unit",),
}

AUDIT_CATEGORY_LABELS = {
    "inventory": "物资变动",
    "employee": "人员变动",
    "computer": "办公终端信息变动",
    "organization": "组织架构变动",
    "other": "其他变动",
}

AUDIT_CHANGE_LABELS = {
    "employee_added": "新增人员",
    "employee_removed": "删除人员",
    "employee_archived": "人员离职归档",
    "employee_offboarded": "办理离职",
    "employee_status_changed": "人员状态变更",
    "employee_info_changed": "人员信息变更",
    "monitor_added": "人员增加显示屏",
    "monitor_removed": "人员减少显示屏",
    "monitor_changed": "人员显示屏信息变更",
    "non_asset_added": "人员增加非资产物资",
    "non_asset_removed": "人员减少非资产物资",
    "non_asset_changed": "人员非资产物资信息变更",
    "non_asset_quantity_changed": "人员物资数量变更",
    "computer_added": "新增办公终端",
    "computer_removed": "删除办公终端",
    "computer_status_changed": "办公终端状态变更",
    "computer_assignment_changed": "办公终端使用人变更",
    "computer_info_changed": "办公终端信息变更",
    "inventory_group_added": "物资分组新增",
    "inventory_group_changed": "物资分组变更",
    "inventory_group_removed": "物资分组删除",
    "inventory_type_changed": "物资类型变更",
    "inventory_brand_changed": "物资品牌变更",
    "inventory_model_changed": "物资型号变更",
    "inventory_stock_changed": "物资库存数量变更",
    "database_backup_created": "手动创建数据库备份",
    "database_backup_scheduled": "定时创建数据库备份",
    "database_backup_schedule_changed": "数据库自动备份设置变更",
    "database_backup_downloaded": "下载数据库备份",
}


class ApiError(RuntimeError):
    pass


class InternalServerError(ApiError):
    pass


class ConflictError(ApiError):
    pass


class PayloadTooLargeError(ApiError):
    pass


SCP_REPOSITORY_URL_RE = re.compile(
    r"^(?P<user>[A-Za-z0-9._-]+)@(?P<host>[A-Za-z0-9.-]+|\[[0-9A-Fa-f:.]+\]):(?P<path>[A-Za-z0-9._~/%+-]+(?:\.git)?)$"
)


def repository_host_allows_http(host: str) -> bool:
    host_value = (host or "").strip().strip("[]").lower()
    if not host_value:
        return False
    if host_value in {"localhost"} or "." not in host_value:
        return True
    if host_value.endswith((".local", ".lan", ".internal")):
        return True
    try:
        address = ipaddress.ip_address(host_value)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local


def validate_repository_host(host: str) -> None:
    host_value = (host or "").strip().strip("[]")
    if not host_value or len(host_value) > 253:
        raise ApiError("更新项目地址主机无效。")
    try:
        ipaddress.ip_address(host_value)
        return
    except ValueError:
        pass
    if not re.fullmatch(r"[A-Za-z0-9.-]+", host_value):
        raise ApiError("更新项目地址主机无效。")
    if any(not label or label.startswith("-") or label.endswith("-") for label in host_value.split(".")):
        raise ApiError("更新项目地址主机无效。")


def normalize_update_repository_url(value: object | None) -> str:
    repository_url = "" if value is None else str(value).strip()
    if not repository_url:
        return ""
    if len(repository_url) > 512:
        raise ApiError("更新项目地址过长。")
    if any(ord(char) < 32 for char in repository_url) or any(char.isspace() for char in repository_url):
        raise ApiError("更新项目地址不能包含空白或控制字符。")

    scp_match = SCP_REPOSITORY_URL_RE.fullmatch(repository_url)
    if scp_match:
        validate_repository_host(scp_match.group("host"))
        return repository_url

    parsed = urlparse(repository_url)
    if parsed.scheme not in {"https", "http", "ssh"} or not parsed.netloc:
        raise ApiError("更新项目地址必须是 HTTPS、SSH 或内网 HTTP 的 Git 仓库地址。")
    if parsed.username and parsed.scheme != "ssh":
        raise ApiError("HTTPS/HTTP 更新项目地址不能包含账号或令牌。")
    if parsed.password:
        raise ApiError("更新项目地址不能包含密码或令牌。")
    if parsed.params or parsed.query or parsed.fragment:
        raise ApiError("更新项目地址不能包含查询参数或片段。")
    validate_repository_host(parsed.hostname or "")
    if parsed.scheme == "http" and not repository_host_allows_http(parsed.hostname or ""):
        raise ApiError("HTTP 更新项目地址仅允许内网、本机或内部域名。")
    if parsed.scheme == "ssh" and parsed.username and not re.fullmatch(r"[A-Za-z0-9._-]+", parsed.username):
        raise ApiError("SSH 更新项目地址用户名无效。")
    if not re.fullmatch(r"/[A-Za-z0-9._~/%+-]+(?:\.git)?", parsed.path or ""):
        raise ApiError("更新项目地址路径无效。")
    return repository_url


UPDATE_RELEASE_CHANNELS = {"release", "beta"}
DEFAULT_UPDATE_RELEASE_CHANNEL = "beta"


def normalize_update_release_channel(value: object | None) -> str:
    channel = "" if value is None else str(value).strip().lower()
    if channel not in UPDATE_RELEASE_CHANNELS:
        raise ApiError("更新通道必须是 release 或 beta。")
    return channel


class RateLimitError(ApiError):
    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = max(1, retry_after)


class UnauthorizedError(ApiError):
    pass


class ForbiddenError(ApiError):
    pass


class CsrfError(ForbiddenError):
    pass


def json_query_one(sql: str, default: object | None = None) -> object | None:
    output = run_mysql(sql, database=DB_NAME)
    line = next((item for item in output.splitlines() if item.strip()), "")
    if not line:
        return default
    try:
        return json.loads(line)
    except json.JSONDecodeError as exc:
        raise InternalServerError("数据库返回的 JSON 无效。") from exc


def encode_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_password(value: object | None, *, allow_empty: bool = False) -> str:
    password = "" if value is None else str(value)
    if allow_empty and not password:
        return ""
    if not password:
        raise ApiError("密码不能为空。")
    if password != password.strip():
        raise ApiError("密码首尾不能包含空格。")
    if any(ord(char) < 32 or ord(char) == 127 for char in password):
        raise ApiError("密码不能包含控制字符。")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ApiError(f"密码长度不能少于 {PASSWORD_MIN_LENGTH} 位。")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ApiError(f"密码长度不能超过 {PASSWORD_MAX_LENGTH} 位。")
    return password


def password_hash(password: str) -> str:
    password = validate_password(password)
    salt = secrets.token_bytes(16)
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


def verify_password(password: str, stored_hash: str) -> bool:
    if len(password) > PASSWORD_MAX_LENGTH:
        return False
    try:
        scheme, params, encoded_salt, encoded_digest = stored_hash.split("$", 3)
        if scheme != "scrypt":
            return False
        values = dict(item.split("=", 1) for item in params.split(","))
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(encoded_salt),
            n=int(values.get("N", "32768")),
            r=int(values.get("r", "8")),
            p=int(values.get("p", "1")),
            dklen=len(base64.b64decode(encoded_digest)),
            maxmem=64 * 1024 * 1024,
        )
        return hmac.compare_digest(derived, base64.b64decode(encoded_digest))
    except (ValueError, KeyError, TypeError):
        return False


def validate_username(value: object | None) -> str:
    username = text_value(value)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,63}", username):
        raise ApiError("账号需使用 3-64 位字母、数字、点、下划线或短横线。")
    return username


def client_ip(handler: SimpleHTTPRequestHandler) -> str:
    address = getattr(handler, "client_address", None)
    if isinstance(address, tuple) and address:
        return text_value(address[0]) or "unknown"
    return "unknown"


def _login_rate_keys(handler: SimpleHTTPRequestHandler, username: str) -> tuple[str, str]:
    return (
        f"ip:{client_ip(handler)}",
        f"user:{username.lower()}",
    )


def enforce_login_rate_limit(handler: SimpleHTTPRequestHandler, username: str) -> None:
    now = time.monotonic()
    keys = _login_rate_keys(handler, username)
    with LOGIN_RATE_LOCK:
        retry_after = 0
        for key in keys:
            bucket = LOGIN_RATE_BUCKETS[key]
            while bucket and now - bucket[0] >= LOGIN_RATE_WINDOW_SECONDS:
                bucket.popleft()
            if len(bucket) >= LOGIN_RATE_MAX_ATTEMPTS:
                retry_after = max(
                    retry_after,
                    int(LOGIN_RATE_WINDOW_SECONDS - (now - bucket[0])) + 1,
                )
        if retry_after:
            raise RateLimitError("登录请求过于频繁，请稍后再试。", retry_after)
        for key in keys:
            LOGIN_RATE_BUCKETS[key].append(now)
        if len(LOGIN_RATE_BUCKETS) > 4096:
            stale_keys = [
                key
                for key, bucket in LOGIN_RATE_BUCKETS.items()
                if not bucket or now - bucket[-1] >= LOGIN_RATE_WINDOW_SECONDS
            ]
            for key in stale_keys:
                LOGIN_RATE_BUCKETS.pop(key, None)


def clear_login_rate_limit(handler: SimpleHTTPRequestHandler, username: str) -> None:
    with LOGIN_RATE_LOCK:
        for key in _login_rate_keys(handler, username):
            LOGIN_RATE_BUCKETS.pop(key, None)


def auth_user_public(user: dict) -> dict:
    employee = user.get("employee") if isinstance(user.get("employee"), dict) else {}
    return {
        "id": text_value(user.get("id") or user.get("userId")),
        "username": text_value(user.get("username")),
        "displayName": text_value(user.get("displayName") or user.get("display_name")),
        "role": text_value(user.get("role")) or "operator",
        "roleCode": text_value(user.get("roleCode") or user.get("role")) or "operator",
        "isSuperAdmin": parse_bool(user.get("isSuperAdmin"), False),
        "isActive": parse_bool(user.get("isActive", user.get("is_active", True)), True),
        "lastLoginAt": text_value(user.get("lastLoginAt") or user.get("last_login_at")),
        "employeeId": text_value(user.get("employeeId") or user.get("employee_id") or employee.get("employeeId")),
        "employeeNo": text_value(user.get("employeeNo") or user.get("employee_no") or employee.get("employeeNo")),
        "employeeName": text_value(user.get("employeeName") or user.get("employee_name") or employee.get("employeeName")),
        "department": text_value(user.get("department") or employee.get("department")),
        "positionName": text_value(user.get("positionName") or user.get("position_name") or employee.get("positionName")),
        "orgId": text_value(user.get("orgId") or user.get("org_id") or employee.get("orgId")),
        "orgName": text_value(user.get("orgName") or user.get("org_name") or employee.get("orgName")),
        "email": text_value(user.get("email") or employee.get("email")),
        "mobile": text_value(user.get("mobile") or employee.get("mobile")),
    }


def auth_user_count() -> int:
    return sql_int(run_mysql("SELECT COUNT(*) FROM user_account;", database=DB_NAME).strip(), 0)


def validate_employee_binding(value: object | None, current_user_id: str = "") -> int:
    employee_id = sql_int(value, 0)
    if employee_id <= 0:
        return 0
    employee_exists = sql_int(
        run_mysql(
            f"""
            SELECT COUNT(*)
            FROM employee
            WHERE employee_id = {employee_id}
              AND is_active = 1
              AND employment_status <> 'left'
              AND employment_status <> 'shared';
            """,
            database=DB_NAME,
        ).strip(),
        0,
    )
    if employee_exists != 1:
        raise ApiError("绑定人员不存在、已停用、已离职，或为不可绑定账号的公用人员。")
    assigned = sql_int(
        run_mysql(
            f"""
            SELECT COUNT(*)
            FROM user_account
            WHERE employee_id = {employee_id}
              AND user_id <> {sql_quote(current_user_id or '0')};
            """,
            database=DB_NAME,
        ).strip(),
        0,
    )
    if assigned:
        raise ConflictError("该人员已绑定其他账号。")
    return employee_id


def create_first_admin(username: str, display_name: str, stored_hash: str) -> dict:
    output = run_mysql(
        f"""
        START TRANSACTION;
        INSERT INTO auth_bootstrap_guard (guard_id)
        VALUES (1)
        ON DUPLICATE KEY UPDATE guard_id = VALUES(guard_id);
        INSERT INTO user_account (username, display_name, password_hash, user_role, role_code)
        SELECT {sql_quote(username)}, {sql_quote(display_name)}, {sql_quote(stored_hash)}, 'admin', 'admin'
        WHERE NOT EXISTS (SELECT 1 FROM user_account LIMIT 1);
        SELECT ROW_COUNT();
        COMMIT;
        """,
        database=DB_NAME,
    )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines or sql_int(lines[-1], 0) != 1:
        raise ConflictError("系统管理员已经初始化，不能重复初始化。")
    user = find_user_by_username(username)
    if not user:
        raise InternalServerError("管理员账号创建后无法读取。")
    return user


def configured_session_hours() -> int:
    try:
        value = sql_int(
            run_mysql(
                "SELECT setting_value FROM system_setting "
                "WHERE setting_key = 'session_hours' AND is_active = 1 LIMIT 1;",
                database=DB_NAME,
            ).strip(),
            AUTH_SESSION_HOURS,
        )
        return min(168, max(1, value))
    except ApiError:
        return AUTH_SESSION_HOURS


def find_user_by_username(username: str) -> dict | None:
    return json_query_one(
        f"""
        SELECT JSON_OBJECT(
          'id', CAST(user_id AS CHAR),
          'username', username,
          'displayName', display_name,
          'passwordHash', password_hash,
          'role', COALESCE(role_code, user_role),
          'roleCode', COALESCE(role_code, user_role),
          'isSuperAdmin', EXISTS(
            SELECT 1 FROM auth_role role_row
            WHERE role_row.role_code = COALESCE(user_account.role_code, user_account.user_role)
              AND role_row.is_active = 1
              AND role_row.is_super_admin = 1
          ),
          'isActive', user_account.is_active,
          'failedAttempts', user_account.failed_attempts,
          'locked', IF(user_account.locked_until IS NOT NULL AND user_account.locked_until > NOW(), TRUE, FALSE)
          ,'employeeId', COALESCE(CAST(user_account.employee_id AS CHAR), '')
          ,'employeeNo', COALESCE(employee.employee_no, '')
          ,'employeeName', COALESCE(employee.employee_name, '')
          ,'department', COALESCE(employee.department, '')
          ,'positionName', COALESCE(employee.position_name, '')
          ,'orgId', COALESCE(CAST(employee.org_unit_id AS CHAR), '')
          ,'orgName', COALESCE(org.org_name, '')
          ,'email', COALESCE(employee.email, '')
          ,'mobile', COALESCE(employee.mobile, '')
        )
        FROM user_account
        LEFT JOIN employee ON employee.employee_id = user_account.employee_id
        LEFT JOIN org_unit org ON org.org_unit_id = employee.org_unit_id
        WHERE username = {sql_quote(username)}
        LIMIT 1
        """,
        None,
    )


def find_user_by_id(user_id: str) -> dict | None:
    if not user_id:
        return None
    return json_query_one(
        f"""
        SELECT JSON_OBJECT(
          'id', CAST(user_id AS CHAR),
          'username', username,
          'displayName', display_name,
          'passwordHash', password_hash,
          'role', COALESCE(role_code, user_role),
          'roleCode', COALESCE(role_code, user_role),
          'isSuperAdmin', EXISTS(
            SELECT 1 FROM auth_role role_row
            WHERE role_row.role_code = COALESCE(user_account.role_code, user_account.user_role)
              AND role_row.is_active = 1
              AND role_row.is_super_admin = 1
          ),
          'isActive', user_account.is_active,
          'lastLoginAt', COALESCE(DATE_FORMAT(user_account.last_login_at, '%Y-%m-%d %H:%i:%s'), '')
          ,'employeeId', COALESCE(CAST(user_account.employee_id AS CHAR), '')
          ,'employeeNo', COALESCE(employee.employee_no, '')
          ,'employeeName', COALESCE(employee.employee_name, '')
          ,'department', COALESCE(employee.department, '')
          ,'positionName', COALESCE(employee.position_name, '')
          ,'orgId', COALESCE(CAST(employee.org_unit_id AS CHAR), '')
          ,'orgName', COALESCE(org.org_name, '')
          ,'email', COALESCE(employee.email, '')
          ,'mobile', COALESCE(employee.mobile, '')
        )
        FROM user_account
        LEFT JOIN employee ON employee.employee_id = user_account.employee_id
        LEFT JOIN org_unit org ON org.org_unit_id = employee.org_unit_id
        WHERE user_id = {sql_quote(user_id)}
        LIMIT 1
        """,
        None,
    )


def list_users() -> list[dict]:
    rows = json_query_one(
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(user_id AS CHAR),
          'username', username,
          'displayName', display_name,
          'role', role_code,
          'roleCode', role_code,
          'isSuperAdmin', is_super_admin,
          'isActive', is_active,
          'lastLoginAt', COALESCE(DATE_FORMAT(last_login_at, '%Y-%m-%d %H:%i:%s'), ''),
          'createdAt', DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s')
          ,'employeeId', COALESCE(CAST(ordered_users.employee_id AS CHAR), '')
          ,'employeeNo', COALESCE(ordered_users.employee_no, '')
          ,'employeeName', COALESCE(ordered_users.employee_name, '')
          ,'department', COALESCE(ordered_users.department, '')
          ,'positionName', COALESCE(ordered_users.position_name, '')
          ,'orgId', COALESCE(CAST(ordered_users.org_id AS CHAR), '')
          ,'orgName', COALESCE(ordered_users.org_name, '')
        )), JSON_ARRAY())
        FROM (
          SELECT
            user_account.user_id,
            user_account.username,
            user_account.display_name,
            COALESCE(user_account.role_code, user_account.user_role) AS role_code,
            EXISTS(
              SELECT 1 FROM auth_role role_row
              WHERE role_row.role_code = COALESCE(user_account.role_code, user_account.user_role)
                AND role_row.is_active = 1
                AND role_row.is_super_admin = 1
            ) AS is_super_admin,
            user_account.is_active,
            user_account.last_login_at,
            user_account.created_at
            ,user_account.employee_id
            ,employee.employee_no
            ,employee.employee_name
            ,employee.department
            ,employee.position_name
            ,employee.org_unit_id AS org_id
            ,org_unit.org_name AS org_name
          FROM user_account
          LEFT JOIN employee ON employee.employee_id = user_account.employee_id
          LEFT JOIN org_unit ON org_unit.org_unit_id = employee.org_unit_id
          ORDER BY is_active DESC, username
        ) AS ordered_users
        """,
        [],
    )
    return rows if isinstance(rows, list) else []


def create_auth_session(
    user_id: str,
    handler: SimpleHTTPRequestHandler | None = None,
) -> tuple[str, str]:
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(24)
    session_hours = configured_session_hours()
    ip_address = client_ip(handler) if handler else ""
    user_agent = text_value(handler.headers.get("User-Agent", ""))[:500] if handler else ""
    run_mysql(
        f"""
        INSERT INTO auth_session (
          session_token_hash, csrf_token_hash, user_id, expires_at, ip_address, user_agent
        ) VALUES (
          {sql_quote(encode_token(session_token))},
          {sql_quote(encode_token(csrf_token))},
          {sql_quote(user_id)},
          DATE_ADD(NOW(), INTERVAL {session_hours} HOUR),
           {sql_quote(ip_address)},
           {sql_quote(user_agent)}
        );
        """,
        database=DB_NAME,
    )
    return session_token, csrf_token


def revoke_user_sessions(user_id: str, except_session_token: str = "") -> None:
    except_clause = ""
    if except_session_token:
        except_clause = f"""
          AND session_token_hash <> {sql_quote(encode_token(except_session_token))}
        """
    run_mysql(
        f"""
        UPDATE auth_session
        SET revoked_at = NOW()
        WHERE user_id = {sql_quote(user_id)}
          AND revoked_at IS NULL
          {except_clause};
        """,
        database=DB_NAME,
    )


def cookie_value(handler: SimpleHTTPRequestHandler, name: str) -> str:
    raw = handler.headers.get("Cookie", "")
    for item in raw.split(";"):
        key, separator, value = item.strip().partition("=")
        if separator and key == name:
            return value
    return ""


def current_auth_context(handler: SimpleHTTPRequestHandler) -> dict | None:
    token = cookie_value(handler, AUTH_COOKIE_NAME)
    if not token:
        return None
    return json_query_one(
        f"""
        SELECT JSON_OBJECT(
          'id', CAST(user.user_id AS CHAR),
          'username', user.username,
          'displayName', user.display_name,
          'role', COALESCE(user.role_code, user.user_role),
          'roleCode', COALESCE(user.role_code, user.user_role),
          'isSuperAdmin', EXISTS(
            SELECT 1 FROM auth_role role_row
            WHERE role_row.role_code = COALESCE(user.role_code, user.user_role)
              AND role_row.is_active = 1
              AND role_row.is_super_admin = 1
          ),
          'isActive', user.is_active,
          'csrfHash', session.csrf_token_hash,
          'employee', JSON_OBJECT(
            'employeeId', COALESCE(CAST(employee.employee_id AS CHAR), ''),
            'employeeNo', COALESCE(employee.employee_no, ''),
            'employeeName', COALESCE(employee.employee_name, ''),
            'department', COALESCE(employee.department, ''),
            'positionName', COALESCE(employee.position_name, ''),
            'orgId', COALESCE(CAST(employee.org_unit_id AS CHAR), ''),
            'orgName', COALESCE(org.org_name, ''),
            'email', COALESCE(employee.email, ''),
            'mobile', COALESCE(employee.mobile, '')
          )
        )
        FROM auth_session session
        JOIN user_account user ON user.user_id = session.user_id
        LEFT JOIN employee ON employee.employee_id = user.employee_id
        LEFT JOIN org_unit org ON org.org_unit_id = employee.org_unit_id
        WHERE session.session_token_hash = {sql_quote(encode_token(token))}
          AND session.revoked_at IS NULL
          AND session.expires_at > NOW()
          AND user.is_active = 1
        LIMIT 1
        """,
        None,
    )


def require_auth(handler: SimpleHTTPRequestHandler) -> dict:
    context = current_auth_context(handler)
    if not context:
        raise UnauthorizedError("请先登录。")
    return context


def require_role(context: dict, *roles: str) -> None:
    if text_value(context.get("role")) not in roles:
        raise ForbiddenError("当前账号没有执行此操作的权限。")


def legacy_role_value(role_code: str) -> str:
    return role_code if role_code in {"admin", "operator", "viewer"} else "viewer"


def require_csrf(handler: SimpleHTTPRequestHandler, context: dict) -> None:
    provided = handler.headers.get("X-CSRF-Token", "")
    expected = text_value(context.get("csrfHash"))
    if not provided or not expected or not hmac.compare_digest(encode_token(provided), expected):
        raise CsrfError("请求校验已失效，请刷新页面后重试。")


def cookie_headers(session_token: str, csrf_token: str) -> list[tuple[str, str]]:
    secure = "; Secure" if AUTH_COOKIE_SECURE else ""
    session_hours = configured_session_hours()
    return [
        (
            "Set-Cookie",
            f"{AUTH_COOKIE_NAME}={session_token}; Max-Age={session_hours * 3600}; Path=/; HttpOnly; SameSite=Lax{secure}",
        ),
        (
            "Set-Cookie",
            f"{CSRF_COOKIE_NAME}={csrf_token}; Max-Age={session_hours * 3600}; Path=/; SameSite=Lax{secure}",
        ),
    ]


def clear_auth_cookie_headers() -> list[tuple[str, str]]:
    secure = "; Secure" if AUTH_COOKIE_SECURE else ""
    return [
        ("Set-Cookie", f"{AUTH_COOKIE_NAME}=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax{secure}"),
        ("Set-Cookie", f"{CSRF_COOKIE_NAME}=; Max-Age=0; Path=/; SameSite=Lax{secure}"),
    ]


def write_auth_audit(actor: str, action_type: str, entity_id: str, entity_name: str, summary: str) -> None:
    run_mysql(
        f"""
        INSERT INTO audit_log (
          action_type, entity_type, entity_id, entity_name, summary, actor, source
        ) VALUES (
          {sql_quote(action_type)},
          'user_account',
          {sql_quote(entity_id)},
          {sql_quote(entity_name)},
          {sql_quote(summary)},
          {sql_quote(actor)},
          'web'
        );
        """,
        database=DB_NAME,
    )


def settings_payload() -> dict:
    value = json_query_one(
        """
        SELECT COALESCE(JSON_OBJECTAGG(setting_key, setting_value), JSON_OBJECT())
        FROM system_setting
        WHERE is_active = 1
        """,
        {},
    )
    return value if isinstance(value, dict) else {}


def request_update_service(
    target_sha: str = "",
    repository_url: str = "",
    release_channel: str = DEFAULT_UPDATE_RELEASE_CHANNEL,
) -> dict:
    if not UPDATE_SERVICE_URL or not UPDATE_CONTROL_TOKEN:
        raise ApiError("服务器更新服务尚未配置，请联系系统管理员。")

    parsed_url = urlparse(UPDATE_SERVICE_URL)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ApiError("服务器更新服务地址配置无效。")
    if parsed_url.scheme == "http" and not UPDATE_SERVICE_ALLOW_HTTP:
        raise ApiError("更新服务必须使用 HTTPS；仅可在隔离的本地开发环境显式允许 HTTP。")

    repository_url = normalize_update_repository_url(repository_url)
    release_channel = normalize_update_release_channel(release_channel)
    endpoint = "/control/update" if target_sha else "/control/status"
    method = "POST" if target_sha else "GET"
    data = (
        json.dumps(
            {
                "targetSha": target_sha,
                "repositoryUrl": repository_url,
                "releaseChannel": release_channel,
            }
        ).encode("utf-8")
        if target_sha
        else None
    )
    request_url = f"{UPDATE_SERVICE_URL}{endpoint}"
    if not target_sha:
        request_url = f"{request_url}?{urlencode({'repositoryUrl': repository_url, 'releaseChannel': release_channel})}"
    request = Request(
        request_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Deploy-Control-Token": UPDATE_CONTROL_TOKEN,
        },
        method=method,
    )
    try:
        ssl_context = None
        if parsed_url.scheme == "https":
            if UPDATE_SERVICE_CA_FILE:
                try:
                    ssl_context = ssl.create_default_context(cafile=UPDATE_SERVICE_CA_FILE)
                except (OSError, ssl.SSLError) as exc:
                    raise ApiError("更新服务 CA 证书配置无效。") from exc
            else:
                ssl_context = ssl.create_default_context()
        with urlopen(request, timeout=UPDATE_REQUEST_TIMEOUT, context=ssl_context) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}
        print(f"Update service returned HTTP {exc.code}: {payload.get('error') or raw[:256]}")
        if payload.get("error") == "repository_fetch_failed":
            raise ApiError(
                "更新项目无法获取，请检查项目地址、GitHub 网络或本机 Gitea 的部署读取权限。"
            ) from exc
        raise ApiError(f"服务器更新服务返回 HTTP {exc.code}。") from exc
    except (URLError, TimeoutError) as exc:
        print(f"Unable to connect to update service: {exc}")
        raise ApiError("无法连接服务器更新服务。") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError("服务器更新服务返回了无效响应。") from exc
    if not isinstance(payload, dict):
        raise ApiError("服务器更新服务返回了无效数据。")
    return payload


STATE_ARRAY_KEYS = (
    "orgs",
    "nonAssetTypes",
    "inventoryBrands",
    "inventoryModels",
    "inventoryMovementLogs",
    "inventoryPurchaseLogs",
    "employees",
    "leftEmployees",
    "computers",
)


def validate_state_payload(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ApiError("请求数据格式必须是 JSON 对象。")
    missing = [key for key in (*STATE_ARRAY_KEYS, "stateRevision") if key not in payload]
    if missing:
        raise ApiError("数据同步必须提交完整状态快照，请刷新页面后重试。")
    invalid_arrays = [key for key in STATE_ARRAY_KEYS if not isinstance(payload.get(key), list)]
    if invalid_arrays:
        raise ApiError("数据同步状态快照格式无效，请刷新页面后重试。")
    revision = payload.get("stateRevision")
    if isinstance(revision, bool) or not re.fullmatch(r"[1-9]\d*", text_value(revision)):
        raise ApiError("数据版本号无效，请刷新页面后重试。")


def validate_payload(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ApiError("请求数据格式必须是 JSON 对象。")

    org_ids = {text_value(item.get("id")) for item in payload.get("orgs") or []}
    type_ids = {text_value(item.get("id")) for item in payload.get("nonAssetTypes") or []}
    brand_ids = {text_value(item.get("id")) for item in payload.get("inventoryBrands") or []}
    model_ids = {text_value(item.get("id")) for item in payload.get("inventoryModels") or []}
    employee_ids = {text_value(item.get("id")) for item in payload.get("employees") or []}

    def ensure_unique(values: list[str], label: str) -> None:
        filtered = [value for value in values if value]
        if len(filtered) != len(set(filtered)):
            raise ApiError(f"{label}存在重复编号。")

    ensure_unique([text_value(item.get("id")) for item in payload.get("orgs") or []], "组织")
    ensure_unique([text_value(item.get("employeeNo")) for item in payload.get("employees") or []], "人员编号")
    ensure_unique([text_value(item.get("deviceName")) for item in payload.get("computers") or []], "办公终端设备名")
    ensure_unique([text_value(item.get("fixedAssetCode")) for item in payload.get("computers") or []], "固资编码")
    ensure_unique([text_value(item.get("snSt")) for item in payload.get("computers") or []], "SN/ST")

    type_codes: set[str] = set()
    type_names: set[str] = set()
    for item in payload.get("nonAssetTypes") or []:
        code = text_value(item.get("code"))
        name = text_value(item.get("name"))
        if code and code.lower() in type_codes:
            raise ApiError(f"物资类型编码 {code} 重复。")
        if name and name.lower() in type_names:
            raise ApiError(f"物资类型名称 {name} 重复。")
        if code:
            type_codes.add(code.lower())
        if name:
            type_names.add(name.lower())

    brand_keys: set[tuple[str, str]] = set()
    for brand in payload.get("inventoryBrands") or []:
        type_id = text_value(brand.get("typeId"))
        name = text_value(brand.get("name") or brand.get("brandName"))
        key = (type_id, name.lower())
        if name and key in brand_keys:
            raise ApiError(f"物资品牌 {name} 在同一类型下重复。")
        if name:
            brand_keys.add(key)

    model_keys: set[tuple[str, str, str]] = set()
    brands_by_id = {
        text_value(item.get("id")): item
        for item in payload.get("inventoryBrands") or []
        if text_value(item.get("id"))
    }
    for model in payload.get("inventoryModels") or []:
        type_id = text_value(model.get("typeId"))
        brand_id = text_value(model.get("brandId"))
        name = text_value(model.get("name") or model.get("modelName"))
        brand = brands_by_id.get(brand_id)
        if brand and text_value(brand.get("typeId")) != type_id:
            raise ApiError(f"库存型号 {name} 的类型与品牌不匹配。")
        key = (brand_id, name.lower(), text_value(model.get("batchKey")))
        if name and key in model_keys:
            raise ApiError(f"库存型号 {name} 在同一品牌下重复。")
        if name:
            model_keys.add(key)

    org_by_id = {
        text_value(item.get("id")): item
        for item in payload.get("orgs") or []
        if text_value(item.get("id"))
    }
    for org in payload.get("orgs") or []:
        parent_id = text_value(org.get("parentId"))
        if parent_id and parent_id not in org_ids:
            raise ApiError(f"组织 {text_value(org.get('name'))} 的上级组织不存在。")
        if parent_id and parent_id == text_value(org.get("id")):
            raise ApiError(f"组织 {text_value(org.get('name'))} 不能将自身设为上级组织。")
    for org in payload.get("orgs") or []:
        current_id = text_value(org.get("id"))
        visited: set[str] = set()
        while current_id:
            if current_id in visited:
                raise ApiError("组织架构存在循环引用，请检查上级组织设置。")
            visited.add(current_id)
            current = org_by_id.get(current_id)
            current_id = text_value(current.get("parentId")) if current else ""
    for brand in payload.get("inventoryBrands") or []:
        if text_value(brand.get("typeId")) not in type_ids:
            raise ApiError(f"库存品牌 {text_value(brand.get('name'))} 关联的物资类型不存在。")
    for model in payload.get("inventoryModels") or []:
        if text_value(model.get("typeId")) not in type_ids or text_value(model.get("brandId")) not in brand_ids:
            raise ApiError(f"库存型号 {text_value(model.get('name'))} 的类型或品牌不存在。")
        if sql_int(model.get("quantity"), 0) < 0:
            raise ApiError(f"库存型号 {text_value(model.get('name'))} 的数量不能为负数。")
    for employee in payload.get("employees") or []:
        org_id = text_value(employee.get("orgId"))
        if org_id and org_id not in org_ids:
            raise ApiError(f"人员 {text_value(employee.get('name'))} 关联的组织不存在。")
    for computer in payload.get("computers") or []:
        org_id = text_value(computer.get("orgId"))
        user_id = text_value(computer.get("userId"))
        inventory_model_id = text_value(computer.get("inventoryModelId"))
        if inventory_model_id and inventory_model_id not in model_ids:
            raise ApiError("办公终端关联的库存型号不存在。")
        if org_id and org_id not in org_ids:
            raise ApiError(f"办公终端 {text_value(computer.get('deviceName'))} 关联的组织不存在。")
        if user_id and user_id not in employee_ids:
            raise ApiError(f"办公终端 {text_value(computer.get('deviceName'))} 的使用人不存在。")
        if user_id and text_value(computer.get("status")) in {"retired", "lost"}:
            raise ApiError(f"办公终端 {text_value(computer.get('deviceName'))} 已报废或遗失，不能继续分配。")
        purchase_date = text_value(computer.get("purchaseDate"))
        registered_date = text_value(computer.get("registeredDate"))
        if purchase_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", purchase_date):
            raise ApiError(f"办公终端 {text_value(computer.get('deviceName'))} 的购置日期格式无效。")
        if registered_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", registered_date):
            raise ApiError(f"办公终端 {text_value(computer.get('deviceName'))} 的注册日期格式无效。")
        if purchase_date and registered_date and registered_date < purchase_date:
            raise ApiError(f"办公终端 {text_value(computer.get('deviceName'))} 的注册日期不能早于购置日期。")
        for field, label in (("wifiMac", "Wifi MAC"), ("ethernetMac", "网口 MAC")):
            mac = normalize_mac_address(computer.get(field))
            if not valid_mac_address(mac):
                raise ApiError(f"办公终端 {text_value(computer.get('deviceName'))} 的{label}格式无效。")

    for employee in payload.get("employees") or []:
        for monitor in employee.get("monitors") or []:
            inventory_brand_id = text_value(monitor.get("inventoryBrandId"))
            inventory_model_id = text_value(monitor.get("inventoryModelId"))
            if inventory_brand_id and inventory_brand_id not in brand_ids:
                raise ApiError("人员显示屏关联的库存品牌不存在。")
            if inventory_model_id and inventory_model_id not in model_ids:
                raise ApiError("人员显示屏关联的库存型号不存在。")
        for item in employee.get("nonAssetItems") or []:
            quantity = sql_int(item.get("quantity"), 1)
            inventory_brand_id = text_value(item.get("inventoryBrandId"))
            inventory_model_id = text_value(item.get("inventoryModelId"))
            if inventory_brand_id and inventory_brand_id not in brand_ids:
                raise ApiError("人员非资产设备关联的库存品牌不存在。")
            if inventory_model_id and inventory_model_id not in model_ids:
                raise ApiError("人员非资产设备关联的库存型号不存在。")
            if quantity <= 0:
                raise ApiError(f"人员 {text_value(employee.get('name'))} 的非资产设备数量必须大于 0。")
    for log in payload.get("inventoryMovementLogs") or []:
        if text_value(log.get("direction")) not in {"increase", "decrease"}:
            raise ApiError("物资变动日志的增减方向无效。")
        if sql_int(log.get("quantity"), 0) <= 0:
            raise ApiError("物资变动日志数量必须大于 0。")
    for log in payload.get("inventoryPurchaseLogs") or []:
        if sql_int(log.get("quantity"), 0) <= 0:
            raise ApiError("采购入库记录数量必须大于 0。")
        for field, valid_ids, label in (
            ("typeId", type_ids, "type"),
            ("brandId", brand_ids, "brand"),
            ("modelId", model_ids, "model"),
        ):
            ref_id = text_value(log.get(field))
            if ref_id and ref_id not in valid_ids:
                raise ApiError(f"采购入库记录关联的 {label} 编号不存在。")
        inbound_date = text_value(log.get("inboundDate"))
        if inbound_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", inbound_date):
            raise ApiError(f"采购入库记录 {text_value(log.get('modelName'))} 的入库日期格式无效。")
def sql_quote(value: object | None) -> str:
    if value is None:
        return "NULL"
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace("\0", "\\0")
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "\\r")
    text = text.replace("\x1a", "\\Z")
    return f"'{text}'"


def sql_int(value: object | None, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def sql_nullable_text(value: object | None) -> str:
    return sql_quote(value) if text_value(value) else "NULL"


def is_numeric_id(value: object | None) -> bool:
    return bool(re.fullmatch(r"\d+", str(value or "").strip()))


def allocate_ids(records: list[dict], key: str = "id", start_id: int = 0) -> dict[str, int]:
    used = [int(str(record.get(key)).strip()) for record in records if is_numeric_id(record.get(key))]
    next_id = max(max(used, default=0), start_id) + 1
    mapping: dict[str, int] = {}
    for record in records:
        raw = str(record.get(key) or "").strip()
        if is_numeric_id(raw):
            mapping[raw] = int(raw)
        else:
            if not raw:
                raw = f"tmp-{next_id}"
            if raw not in mapping:
                mapping[raw] = next_id
                next_id += 1
    return mapping


def run_mysql(sql: str, *, database: str | None = None) -> str:
    if not DB_PASSWORD:
        raise InternalServerError("数据库连接未配置。")
    args = [
        MYSQL_BIN,
        "--protocol=tcp",
        f"--host={DB_HOST}",
        f"--port={DB_PORT}",
        f"--user={DB_USER}",
        "--default-character-set=utf8mb4",
        "--batch",
        "--raw",
        "--skip-column-names",
        "--silent",
    ]
    if database:
        args.append(f"--database={database}")

    env = os.environ.copy()
    env["MYSQL_PWD"] = DB_PASSWORD
    completed = subprocess.run(
        args,
        input=sql,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(ROOT_DIR),
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "Unknown MySQL error"
        print(f"MySQL command failed: {message[:512]}")
        if "Duplicate entry" in message:
            raise ConflictError("数据唯一标识已存在，请检查重复的名称、编码或编号。")
        raise InternalServerError("数据库操作失败。")
    return completed.stdout.strip()


def backup_setting_enabled(value: object | None) -> bool:
    return str(value if value is not None else "").strip().lower() in {"1", "true", "yes", "on"}


def validate_backup_time(value: object | None) -> str:
    raw_value = text_value(value)
    match = re.fullmatch(r"(\d{2}):(\d{2})", raw_value)
    if not match:
        raise ApiError("每日备份时间必须使用 HH:MM 格式。")
    hour, minute = (int(part) for part in match.groups())
    if hour > 23 or minute > 59:
        raise ApiError("每日备份时间无效。")
    return f"{hour:02d}:{minute:02d}"


def validate_backup_retention_days(value: object | None) -> int:
    raw_value = text_value(value)
    if not re.fullmatch(r"\d+", raw_value):
        raise ApiError("备份保留天数必须是 0-3650 的整数。")
    days = int(raw_value)
    if days < 0 or days > 3650:
        raise ApiError("备份保留天数必须在 0-3650 天之间。")
    return days


def resolve_mysqldump_binary() -> str:
    configured = text_value(MYSQLDUMP_BIN)
    configured_path = Path(configured).expanduser()
    if configured_path.is_file():
        return str(configured_path)
    discovered = shutil.which(configured)
    if discovered:
        return discovered
    raise InternalServerError("数据库备份工具未配置。")


def resolve_backup_file_path(value: object | None) -> Path:
    raw_path = text_value(value)
    if not raw_path:
        raise ApiError("备份文件记录不完整。")
    file_path = Path(raw_path).expanduser().resolve()
    try:
        file_path.relative_to(BACKUP_DIR)
    except ValueError as exc:
        raise ApiError("备份文件路径无效。") from exc
    return file_path


def file_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def database_backup_record(backup_id: str) -> dict | None:
    if not re.fullmatch(r"\d+", text_value(backup_id)):
        return None
    value = json_query_one(
        f"""
        SELECT JSON_OBJECT(
          'id', CAST(backup_id AS CHAR),
          'fileName', file_name,
          'filePath', file_path,
          'fileSize', file_size,
          'checksumSha256', checksum_sha256,
          'backupType', backup_type,
          'requestedBy', COALESCE(CAST(requested_by AS CHAR), ''),
          'requestedByName', requested_by_name,
          'status', status,
          'createdAt', DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s')
        )
        FROM database_backup
        WHERE backup_id = {sql_quote(backup_id)}
        LIMIT 1
        """,
        None,
    )
    return value if isinstance(value, dict) else None


def serialize_database_backup(record: dict) -> dict:
    file_available = False
    try:
        file_path = resolve_backup_file_path(record.get("filePath"))
        file_available = (
            text_value(record.get("status")) == "completed"
            and file_path.is_file()
            and file_path.stat().st_size > 0
        )
    except (ApiError, OSError):
        file_available = False
    return {
        "id": text_value(record.get("id")),
        "fileName": text_value(record.get("fileName")),
        "fileSize": max(0, sql_int(record.get("fileSize"), 0)),
        "checksumSha256": text_value(record.get("checksumSha256")),
        "backupType": text_value(record.get("backupType")) or "manual",
        "requestedByName": text_value(record.get("requestedByName")),
        "status": text_value(record.get("status")) or "completed",
        "createdAt": text_value(record.get("createdAt")),
        "fileAvailable": file_available,
    }


def list_database_backups() -> list[dict]:
    records = json_query_one(
        f"""
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(backup_id AS CHAR),
          'fileName', file_name,
          'filePath', file_path,
          'fileSize', file_size,
          'checksumSha256', checksum_sha256,
          'backupType', backup_type,
          'requestedBy', COALESCE(CAST(requested_by AS CHAR), ''),
          'requestedByName', requested_by_name,
          'status', status,
          'createdAt', DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s')
        )), JSON_ARRAY())
        FROM (
          SELECT backup_id, file_name, file_path, file_size, checksum_sha256,
                 backup_type, requested_by, requested_by_name, status, created_at
          FROM database_backup
          ORDER BY created_at DESC, backup_id DESC
          LIMIT {BACKUP_LIST_LIMIT}
        ) AS ordered_backups
        """,
        [],
    )
    if not isinstance(records, list):
        return []
    return [serialize_database_backup(record) for record in records if isinstance(record, dict)]


def write_database_backup_audit(
    actor: str,
    action_type: str,
    entity_id: str,
    entity_name: str,
    summary: str,
) -> None:
    run_mysql(
        f"""
        INSERT INTO audit_log (
          action_type, entity_type, entity_id, entity_name, summary, actor, source
        ) VALUES (
          {sql_quote(action_type)},
          'database_backup',
          {sql_quote(entity_id)},
          {sql_quote(entity_name)},
          {sql_quote(summary)},
          {sql_quote(actor)},
          'web'
        );
        """,
        database=DB_NAME,
    )


def cleanup_expired_database_backups(retention_days: int) -> int:
    if retention_days <= 0:
        return 0
    candidates = json_query_one(
        f"""
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(backup_id AS CHAR),
          'filePath', file_path
        )), JSON_ARRAY())
        FROM database_backup
        WHERE status = 'completed'
          AND created_at < DATE_SUB(NOW(), INTERVAL {retention_days} DAY)
        """,
        [],
    )
    expired_ids: list[str] = []
    for record in candidates if isinstance(candidates, list) else []:
        if not isinstance(record, dict):
            continue
        try:
            file_path = resolve_backup_file_path(record.get("filePath"))
            if file_path.exists():
                file_path.unlink()
            expired_ids.append(text_value(record.get("id")))
        except (ApiError, OSError):
            continue
    if not expired_ids:
        return 0
    id_list = ", ".join(sql_quote(value) for value in expired_ids)
    run_mysql(
        f"UPDATE database_backup SET status = 'expired' WHERE backup_id IN ({id_list});",
        database=DB_NAME,
    )
    return len(expired_ids)


def create_database_backup(backup_type: str, context: dict | None = None) -> dict:
    if backup_type not in {"manual", "scheduled"}:
        raise ApiError("备份类型无效。")
    if not DB_PASSWORD:
        raise InternalServerError("数据库连接未配置。")

    mysqldump_bin = resolve_mysqldump_binary()
    actor_id = text_value(context.get("id")) if context else ""
    actor_name = text_value(context.get("username")) if context else "system"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{DB_NAME}_{timestamp}_{backup_type}_{secrets.token_hex(4)}.sql.gz"

    with BACKUP_LOCK:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        final_path = BACKUP_DIR / file_name
        temporary_path = BACKUP_DIR / f".{file_name}.tmp"
        error_path = BACKUP_DIR / f".{file_name}.stderr"
        command = [
            mysqldump_bin,
            "--protocol=tcp",
            f"--host={DB_HOST}",
            f"--port={DB_PORT}",
            f"--user={DB_USER}",
            "--default-character-set=utf8mb4",
            "--single-transaction",
            "--skip-lock-tables",
            "--no-tablespaces",
            "--routines",
            "--events",
            "--triggers",
            "--hex-blob",
            DB_NAME,
        ]
        env = os.environ.copy()
        env["MYSQL_PWD"] = DB_PASSWORD
        process: subprocess.Popen[bytes] | None = None
        return_code = -1
        try:
            with error_path.open("wb") as error_file:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=error_file,
                    env=env,
                    cwd=str(ROOT_DIR),
                )
                if process.stdout is None:
                    raise InternalServerError("无法读取数据库备份输出。")
                with gzip.open(temporary_path, "wb", compresslevel=6) as compressed_output:
                    shutil.copyfileobj(process.stdout, compressed_output, length=1024 * 1024)
                process.stdout.close()
                return_code = process.wait()
        except OSError as exc:
            print(f"Unable to start mysqldump: {exc}")
            raise InternalServerError("无法启动数据库备份。") from exc
        finally:
            if process and process.poll() is None:
                process.kill()
                process.wait()

        error_message = ""
        if error_path.exists():
            error_message = error_path.read_text(encoding="utf-8", errors="replace").strip()
            error_path.unlink(missing_ok=True)
        if return_code != 0:
            temporary_path.unlink(missing_ok=True)
            print(f"mysqldump failed with exit code {return_code}: {error_message[:512]}")
            raise InternalServerError("数据库备份失败。")
        if not temporary_path.exists() or temporary_path.stat().st_size < 256:
            temporary_path.unlink(missing_ok=True)
            raise InternalServerError("数据库备份文件异常为空。")

        checksum = file_sha256(temporary_path)
        temporary_path.replace(final_path)
        file_size = final_path.stat().st_size
        try:
            run_mysql(
                f"""
                INSERT INTO database_backup (
                  file_name, file_path, file_size, checksum_sha256, backup_type,
                  requested_by, requested_by_name, status
                ) VALUES (
                  {sql_quote(file_name)},
                  {sql_quote(str(final_path))},
                  {file_size},
                  {sql_quote(checksum)},
                  {sql_quote(backup_type)},
                  {sql_quote(actor_id) if actor_id else 'NULL'},
                  {sql_quote(actor_name)},
                  'completed'
                );
                """,
                database=DB_NAME,
            )
        except ApiError:
            final_path.unlink(missing_ok=True)
            raise

        backup_id = run_mysql(
            f"""
            SELECT CAST(backup_id AS CHAR)
            FROM database_backup
            WHERE file_name = {sql_quote(file_name)}
            ORDER BY backup_id DESC
            LIMIT 1;
            """,
            database=DB_NAME,
        ).strip()
        record = database_backup_record(backup_id)
        if not record:
            raise InternalServerError("备份已生成，但无法读取备份记录。")

        try:
            cleanup_expired_database_backups(
                validate_backup_retention_days(settings_payload().get("backup_retention_days", "30"))
            )
        except ApiError as exc:
            print(f"Backup cleanup skipped: {exc}")
        return record


def scheduled_backup_already_completed_today() -> bool:
    return (
        sql_int(
            run_mysql(
                """
                SELECT COUNT(*)
                FROM database_backup
                WHERE backup_type = 'scheduled'
                  AND status = 'completed'
                  AND created_at >= CURDATE();
                """,
                database=DB_NAME,
            ).strip(),
            0,
        )
        > 0
    )


def run_scheduled_database_backup(now: datetime | None = None) -> dict | None:
    settings = settings_payload()
    if not backup_setting_enabled(settings.get("backup_enabled", "0")):
        return None
    scheduled_time = validate_backup_time(settings.get("backup_time", "02:00"))
    current_time = now or datetime.now()
    scheduled_hour, scheduled_minute = (int(part) for part in scheduled_time.split(":"))
    if (current_time.hour, current_time.minute) < (scheduled_hour, scheduled_minute):
        return None
    if scheduled_backup_already_completed_today():
        return None
    record = create_database_backup("scheduled")
    write_database_backup_audit(
        "system",
        "database_backup_scheduled",
        text_value(record.get("id")),
        text_value(record.get("fileName")),
        f"按每日计划创建数据库备份 {text_value(record.get('fileName'))}",
    )
    return record


def database_backup_scheduler_loop() -> None:
    def is_due(current_time: datetime) -> bool:
        settings = settings_payload()
        if not backup_setting_enabled(settings.get("backup_enabled", "0")):
            return False
        scheduled_time = validate_backup_time(settings.get("backup_time", "02:00"))
        scheduled_hour, scheduled_minute = (int(part) for part in scheduled_time.split(":"))
        return (current_time.hour, current_time.minute) >= (scheduled_hour, scheduled_minute)

    def execute(current_time: datetime) -> None:
        run_key = job_run_key("database_backup", current_time)
        start_job_execution(DOMAIN_DB, "database_backup", run_key)
        try:
            record = run_scheduled_database_backup(current_time)
            finish_job_execution(
                DOMAIN_DB,
                "database_backup",
                run_key,
                True,
                {
                    "outcome": "created" if record else "already_completed",
                    "backupId": text_value(record.get("id")) if record else "",
                },
            )
        except Exception as exc:
            finish_job_execution(
                DOMAIN_DB,
                "database_backup",
                run_key,
                False,
                error_message=str(exc),
            )
            raise

    run_periodic_job(
        poll_seconds=BACKUP_SCHEDULER_POLL_SECONDS,
        retry_seconds=BACKUP_SCHEDULER_RETRY_SECONDS,
        is_due=is_due,
        execute=execute,
        report_error=lambda exc: print(f"Database backup scheduler error: {exc}"),
    )


def run_mysql_json_queries(*queries: str) -> list[object]:
    sql = "\n".join(query.rstrip(";") + ";" for query in queries)
    output = run_mysql(sql, database=DB_NAME)
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) != len(queries):
        raise InternalServerError("数据库返回结果数量异常。")
    try:
        return [json.loads(line) for line in lines]
    except json.JSONDecodeError as exc:
        raise InternalServerError("数据库返回结果格式异常。") from exc


def load_current_max_ids() -> dict[str, int]:
    definitions = {
        "orgs": "org_unit_id",
        "types": "non_asset_type_id",
        "brands": "brand_id",
        "models": "model_id",
        "employees": "employee_id",
        "leftEmployees": "archive_id",
        "computers": "computer_id",
        "monitors": "monitor_usage_id",
        "nonAssetItems": "non_asset_usage_id",
        "inventoryMovementLogs": "movement_log_id",
        "inventoryPurchaseLogs": "purchase_log_id",
    }
    queries = [
        f"SELECT COALESCE(MAX({column}), 0) FROM {table}"
        for table, column in (
            ("org_unit", definitions["orgs"]),
            ("non_asset_type", definitions["types"]),
            ("it_inventory_brand", definitions["brands"]),
            ("it_inventory_model", definitions["models"]),
            ("employee", definitions["employees"]),
            ("left_employee_archive", definitions["leftEmployees"]),
            ("computer_asset", definitions["computers"]),
            ("employee_monitor_usage", definitions["monitors"]),
            ("employee_non_asset_usage", definitions["nonAssetItems"]),
            ("inventory_movement_log", definitions["inventoryMovementLogs"]),
            ("inventory_purchase_log", definitions["inventoryPurchaseLogs"]),
        )
    ]
    values = run_mysql_json_queries(*queries)
    return {
        key: max(0, sql_int(value, 0))
        for key, value in zip(definitions, values)
    }


def normalize_left_employee_devices(devices: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for device in devices or []:
        normalized.append(
            {
                "category": text_value(device.get("category")) or "other",
                "label": text_value(device.get("label")),
                "detail": text_value(device.get("detail")),
                "quantity": max(1, sql_int(device.get("quantity"), 1)),
                "typeId": text_value(device.get("typeId")),
                "typeName": text_value(device.get("typeName")),
                "brandId": text_value(device.get("brandId")),
                "modelId": text_value(device.get("modelId")),
                "brand": text_value(device.get("brand")),
                "model": text_value(device.get("model")),
                "action": text_value(device.get("action")),
                "actionLabel": text_value(device.get("actionLabel")),
                "targetEmployeeId": text_value(device.get("targetEmployeeId")),
                "targetEmployeeNo": text_value(device.get("targetEmployeeNo")),
                "targetEmployeeName": text_value(device.get("targetEmployeeName")),
                "handlingNote": text_value(device.get("handlingNote")),
            }
        )
    return normalized


def normalize_left_employees(left_employees: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in left_employees or []:
        normalized.append(
            {
                "id": text_value(item.get("id")),
                "sourceEmployeeId": text_value(item.get("sourceEmployeeId")),
                "employeeNo": text_value(item.get("employeeNo")),
                "name": text_value(item.get("name")),
                "orgId": text_value(item.get("orgId")),
                "orgPath": text_value(item.get("orgPath")),
                "department": text_value(item.get("department")),
                "position": text_value(item.get("position")),
                "email": text_value(item.get("email")),
                "mobile": text_value(item.get("mobile")),
                "leaveDate": text_value(item.get("leaveDate")),
                "leaveInfo": text_value(item.get("leaveInfo")),
                "leaveRemark": text_value(item.get("leaveRemark")),
                "archivedAt": text_value(item.get("archivedAt")),
                "devices": normalize_left_employee_devices(item.get("devices") or []),
            }
        )
    return normalized


def normalize_computers(computers: list[dict], employee_ids: set[str]) -> list[dict]:
    normalized: list[dict] = []
    for computer in computers or []:
        status = text_value(computer.get("status")) or "idle"
        user_id = text_value(computer.get("userId"))
        if user_id and user_id not in employee_ids:
            user_id = ""
        if status in {"repair", "retired", "lost"}:
            user_id = ""
        if user_id:
            status = "in_use"
        elif status == "in_use":
            status = "idle"
        normalized.append(
            {
                "id": text_value(computer.get("id")),
                "deviceName": text_value(computer.get("deviceName")),
                "orgId": text_value(computer.get("orgId")),
                "deviceType": text_value(computer.get("deviceType")),
                "brand": text_value(computer.get("brand")),
                "model": text_value(computer.get("model")),
                "inventoryModelId": text_value(computer.get("inventoryModelId")),
                "inventoryStockAdjusted": bool(computer.get("inventoryStockAdjusted")),
                "cpu": text_value(computer.get("cpu")),
                "memory": text_value(computer.get("memory")),
                "storage": text_value(computer.get("storage")),
                "gpu": text_value(computer.get("gpu")),
                "fixedAssetCode": text_value(computer.get("fixedAssetCode")),
                "purchaseDate": text_value(computer.get("purchaseDate")),
                "registeredDate": text_value(computer.get("registeredDate")),
                "snSt": text_value(computer.get("snSt")),
                "wifiMac": normalize_mac_address(computer.get("wifiMac")),
                "ethernetMac": normalize_mac_address(computer.get("ethernetMac")),
                "location": text_value(computer.get("location")),
                "department": text_value(computer.get("department")),
                "status": status,
                "remarks": text_value(computer.get("remarks")),
                "userId": user_id or None,
            }
        )
    return normalized


def normalize_inventory_brands(brands: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for brand in brands or []:
        normalized.append(
            {
                "id": text_value(brand.get("id")),
                "typeId": text_value(brand.get("typeId")),
                "name": text_value(brand.get("name") or brand.get("brandName")),
                "sortOrder": max(0, sql_int(brand.get("sortOrder"), 1000)),
            }
        )
    return normalized


def is_computer_inventory_type_name(value: object | None) -> bool:
    text = text_value(value).lower()
    return text in {"电脑", "办公终端", "办公设备终端", "computer", "pc"}


def normalize_inventory_models(
    models: list[dict],
    computer_type_ids: set[str] | None = None,
) -> list[dict]:
    normalized: list[dict] = []
    for model in models or []:
        type_id = text_value(model.get("typeId"))
        computer_model = type_id in (computer_type_ids or set())
        normalized.append(
            {
                "id": text_value(model.get("id")),
                "typeId": type_id,
                "brandId": text_value(model.get("brandId")),
                "name": text_value(model.get("name") or model.get("modelName")),
                "batchKey": text_value(model.get("batchKey")),
                "quantity": max(0, sql_int(model.get("quantity"), 0)),
                "inboundDate": text_value(model.get("inboundDate")) if computer_model else "",
                "cpu": text_value(model.get("cpu")) if computer_model else "",
                "memory": text_value(model.get("memory")) if computer_model else "",
                "storage": text_value(model.get("storage")) if computer_model else "",
                "gpu": text_value(model.get("gpu")) if computer_model else "",
                "sortOrder": max(0, sql_int(model.get("sortOrder"), 1000)),
            }
        )
    return normalized


def normalize_inventory_movement_logs(logs: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for log in logs or []:
        occurred_at = text_value(log.get("occurredAt")).replace("T", " ")
        if len(occurred_at) == 10:
            occurred_at = f"{occurred_at} 00:00:00"
        normalized.append(
            {
                "id": text_value(log.get("id")),
                "direction": "decrease" if text_value(log.get("direction")) == "decrease" else "increase",
                "typeName": text_value(log.get("typeName")),
                "brandName": text_value(log.get("brandName")),
                "modelName": text_value(log.get("modelName")),
                "quantity": max(1, sql_int(log.get("quantity"), 1)),
                "sourceLabel": text_value(log.get("sourceLabel")),
                "sourceWarehouseId": text_value(log.get("sourceWarehouseId")),
                "targetLabel": text_value(log.get("targetLabel")),
                "targetWarehouseId": text_value(log.get("targetWarehouseId")),
                "note": text_value(log.get("effectiveNote")) or text_value(log.get("note")),
                "originalNote": text_value(log.get("originalNote")) or text_value(log.get("note")),
                "effectiveNote": text_value(log.get("effectiveNote")) or text_value(log.get("note")),
                "noteCorrections": list(log.get("noteCorrections") or []),
                "relatedEmployeeNo": text_value(log.get("relatedEmployeeNo")),
                "relatedEmployeeName": text_value(log.get("relatedEmployeeName")),
                "triggerAction": text_value(log.get("triggerAction")) or "manual",
                "occurredAt": occurred_at[:19],
            }
        )
    return normalized


def normalize_inventory_purchase_logs(logs: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for log in logs or []:
        inbound_date = text_value(log.get("inboundDate"))
        normalized.append(
            {
                "id": text_value(log.get("id")),
                "typeName": text_value(log.get("typeName")),
                "brandName": text_value(log.get("brandName")),
                "modelName": text_value(log.get("modelName")),
                "typeId": text_value(log.get("typeId")),
                "brandId": text_value(log.get("brandId")),
                "modelId": text_value(log.get("modelId")),
                "warehouseId": text_value(log.get("warehouseId")),
                "quantity": max(1, sql_int(log.get("quantity"), 1)),
                "inboundDate": inbound_date,
                "cpu": text_value(log.get("cpu")) if is_computer_inventory_type_name(log.get("typeName")) else "",
                "memory": text_value(log.get("memory")) if is_computer_inventory_type_name(log.get("typeName")) else "",
                "storage": text_value(log.get("storage")) if is_computer_inventory_type_name(log.get("typeName")) else "",
                "gpu": text_value(log.get("gpu")) if is_computer_inventory_type_name(log.get("typeName")) else "",
                "sourceLabel": text_value(log.get("sourceLabel")),
                "note": text_value(log.get("note")),
                "sourceMovementLogId": text_value(log.get("sourceMovementLogId")),
                "createdAt": text_value(log.get("createdAt")),
            }
        )
    return normalized


def remap_existing_inventory_ids(payload: dict) -> None:
    type_rows, brand_rows, model_rows = run_mysql_json_queries(
        """
        SELECT COALESCE(
          JSON_ARRAYAGG(
            JSON_OBJECT(
              'id', CAST(non_asset_type_id AS CHAR),
              'code', type_code,
              'name', type_name
            )
          ),
          JSON_ARRAY()
        )
        FROM non_asset_type
        """,
        """
        SELECT COALESCE(
          JSON_ARRAYAGG(
            JSON_OBJECT(
              'id', CAST(brand_id AS CHAR),
              'typeId', CAST(non_asset_type_id AS CHAR),
              'name', brand_name
            )
          ),
          JSON_ARRAY()
        )
        FROM it_inventory_brand
        """,
        """
        SELECT COALESCE(
          JSON_ARRAYAGG(
            JSON_OBJECT(
              'id', CAST(model_id AS CHAR),
              'brandId', CAST(brand_id AS CHAR),
              'name', model_name,
              'batchKey', COALESCE(batch_key, '')
            )
          ),
          JSON_ARRAY()
        )
        FROM it_inventory_model
        """,
    )
    type_rows = type_rows or []
    brand_rows = brand_rows or []
    model_rows = model_rows or []

    type_by_code = {
        text_value(item.get("code")).lower(): text_value(item.get("id"))
        for item in type_rows
        if text_value(item.get("code")) and text_value(item.get("id"))
    }
    type_by_name = {
        text_value(item.get("name")).lower(): text_value(item.get("id"))
        for item in type_rows
        if text_value(item.get("name")) and text_value(item.get("id"))
    }

    type_remap: dict[str, str] = {}
    for item in payload.get("nonAssetTypes") or []:
        raw_id = text_value(item.get("id"))
        if not raw_id or is_numeric_id(raw_id):
            continue
        code = text_value(item.get("code")).lower()
        name = text_value(item.get("name")).lower()
        existing_id = type_by_code.get(code) or type_by_name.get(name)
        if existing_id:
            item["id"] = existing_id
            type_remap[raw_id] = existing_id

    def remap_type_ref(value: object | None) -> str:
        raw = text_value(value)
        return type_remap.get(raw, raw)

    for item in payload.get("inventoryBrands") or []:
        item["typeId"] = remap_type_ref(item.get("typeId"))
    for item in payload.get("inventoryModels") or []:
        item["typeId"] = remap_type_ref(item.get("typeId"))
    for employee in payload.get("employees") or []:
        for monitor in employee.get("monitors") or []:
            monitor["typeId"] = remap_type_ref(monitor.get("typeId"))
        for item in employee.get("nonAssetItems") or []:
            item["typeId"] = remap_type_ref(item.get("typeId"))
    for item in payload.get("leftEmployees") or []:
        for device in item.get("devices") or []:
            device["typeId"] = remap_type_ref(device.get("typeId"))

    brand_by_key = {
        (text_value(item.get("typeId")), text_value(item.get("name")).lower()): text_value(item.get("id"))
        for item in brand_rows
        if text_value(item.get("typeId")) and text_value(item.get("name")) and text_value(item.get("id"))
    }
    brand_remap: dict[str, str] = {}
    for item in payload.get("inventoryBrands") or []:
        raw_id = text_value(item.get("id"))
        if not raw_id or is_numeric_id(raw_id):
            continue
        key = (text_value(item.get("typeId")), text_value(item.get("name")).lower())
        existing_id = brand_by_key.get(key)
        if existing_id:
            item["id"] = existing_id
            brand_remap[raw_id] = existing_id

    def remap_brand_ref(value: object | None) -> str:
        raw = text_value(value)
        return brand_remap.get(raw, raw)

    for item in payload.get("inventoryModels") or []:
        item["brandId"] = remap_brand_ref(item.get("brandId"))
    for employee in payload.get("employees") or []:
        for monitor in employee.get("monitors") or []:
            monitor["inventoryBrandId"] = remap_brand_ref(monitor.get("inventoryBrandId"))
        for item in employee.get("nonAssetItems") or []:
            item["inventoryBrandId"] = remap_brand_ref(item.get("inventoryBrandId"))
    for item in payload.get("leftEmployees") or []:
        for device in item.get("devices") or []:
            device["brandId"] = remap_brand_ref(device.get("brandId"))

    model_by_key = {
        (
            text_value(item.get("brandId")),
            text_value(item.get("name")).lower(),
            text_value(item.get("batchKey")),
        ): text_value(item.get("id"))
        for item in model_rows
        if text_value(item.get("brandId")) and text_value(item.get("name")) and text_value(item.get("id"))
    }
    model_remap: dict[str, str] = {}
    for item in payload.get("inventoryModels") or []:
        raw_id = text_value(item.get("id"))
        if not raw_id or is_numeric_id(raw_id):
            continue
        key = (
            text_value(item.get("brandId")),
            text_value(item.get("name")).lower(),
            text_value(item.get("batchKey")),
        )
        existing_id = model_by_key.get(key)
        if existing_id:
            item["id"] = existing_id
            model_remap[raw_id] = existing_id

    def remap_model_ref(value: object | None) -> str:
        raw = text_value(value)
        return model_remap.get(raw, raw)

    for employee in payload.get("employees") or []:
        for monitor in employee.get("monitors") or []:
            monitor["inventoryModelId"] = remap_model_ref(monitor.get("inventoryModelId"))
        for item in employee.get("nonAssetItems") or []:
            item["inventoryModelId"] = remap_model_ref(item.get("inventoryModelId"))
    for item in payload.get("leftEmployees") or []:
        for device in item.get("devices") or []:
            device["modelId"] = remap_model_ref(device.get("modelId"))


def normalize_payload(payload: dict) -> dict:
    remap_existing_inventory_ids(payload)
    validate_payload(payload)
    orgs = normalize_org_codes(payload.get("orgs") or [])
    employees = normalize_employee_numbers(payload.get("employees") or [], orgs)
    employee_ids = {text_value(employee.get("id")) for employee in employees if text_value(employee.get("id"))}
    computer_type_ids = {
        text_value(item.get("id"))
        for item in payload.get("nonAssetTypes") or []
        if is_computer_inventory_type_name(item.get("code")) or is_computer_inventory_type_name(item.get("name"))
    }
    inventory_model_inbound_dates = {
        text_value(item.get("id")): text_value(item.get("inboundDate"))
        for item in payload.get("inventoryModels") or []
        if text_value(item.get("id"))
        and text_value(item.get("typeId")) in computer_type_ids
        and text_value(item.get("inboundDate"))
    }
    for computer in payload.get("computers") or []:
        if text_value(computer.get("purchaseDate")):
            continue
        inbound_date = inventory_model_inbound_dates.get(text_value(computer.get("inventoryModelId")))
        if inbound_date:
            computer["purchaseDate"] = inbound_date
    return {
        "orgs": orgs,
        "nonAssetTypes": payload.get("nonAssetTypes") or [],
        "inventoryBrands": normalize_inventory_brands(payload.get("inventoryBrands") or []),
        "inventoryModels": normalize_inventory_models(payload.get("inventoryModels") or [], computer_type_ids),
        "inventoryMovementLogs": normalize_inventory_movement_logs(payload.get("inventoryMovementLogs") or []),
        "inventoryPurchaseLogs": normalize_inventory_purchase_logs(payload.get("inventoryPurchaseLogs") or []),
        "stateRevision": max(0, sql_int(payload.get("stateRevision"), 0)),
        "employees": employees,
        "leftEmployees": normalize_left_employees(payload.get("leftEmployees") or []),
        "computers": normalize_computers(payload.get("computers") or [], employee_ids),
    }


ORG_CODE_OVERRIDES: dict[str, str] = {}

ORG_INITIALS = {
    "产": "C", "品": "P", "流": "L", "程": "C", "质": "Z", "量": "L", "稽": "J", "核": "H", "审": "S",
    "改": "G", "善": "S", "人": "R", "事": "S", "行": "X", "政": "Z", "财": "C", "务": "W", "研": "Y", "发": "F",
    "光": "G", "敏": "M", "树": "S", "脂": "Z", "工": "G", "技": "J", "术": "S", "供": "G", "应": "Y", "链": "L",
    "管": "G", "理": "L", "计": "J", "划": "H", "控": "K", "制": "Z", "营": "Y", "销": "X", "心": "X", "苏": "S",
    "州": "Z", "南": "N", "通": "T", "科": "K", "德": "D", "仓": "C", "储": "C", "物": "W", "公": "G", "共": "G",
    "其": "Q", "他": "T", "包": "B", "装": "Z", "成": "C", "部": "B", "课": "K", "生": "S", "设": "S", "备": "B",
    "采": "C", "购": "G", "基": "J", "础": "C", "材": "C", "料": "L", "型": "X", "及": "J", "高": "G", "性": "X",
    "能": "N", "创": "C", "新": "X", "医": "Y", "用": "Y", "实": "S", "验": "Y", "室": "S", "艺": "Y", "测": "C",
    "试": "S", "颜": "Y", "色": "S", "海": "H", "外": "W", "国": "G", "内": "N", "大": "D", "客": "K", "户": "H",
    "媒": "M", "体": "T", "运": "Y", "项": "X", "目": "M", "组": "Z", "一": "Y", "二": "E", "班": "B",
}


def generated_org_code(name: object | None) -> str:
    text = text_value(name)
    if text in ORG_CODE_OVERRIDES:
        return ORG_CODE_OVERRIDES[text]
    ascii_text = "".join(char for char in text if char.isascii() and char.isalnum()).upper()
    if ascii_text:
        return ascii_text[:8]
    return "".join(ORG_INITIALS.get(char, "") for char in text)[:8] or "ORG"


def normalize_org_codes(orgs: list[dict]) -> list[dict]:
    normalized = [dict(org) for org in orgs]
    used_by_parent: dict[str, set[str]] = {}
    for org in normalized:
        org_id = text_value(org.get("id"))
        parent_id = text_value(org.get("parentId"))
        code = text_value(org.get("code")) or generated_org_code(org.get("name"))
        sibling_codes = used_by_parent.setdefault(parent_id, set())
        if code.upper() in sibling_codes:
            base = code
            suffix = 2
            while f"{base}{suffix}".upper() in sibling_codes:
                suffix += 1
            code = f"{base}{suffix}"
        sibling_codes.add(code.upper())
        org["id"] = org_id or org.get("id")
        org["parentId"] = parent_id
        org["code"] = code.upper()
    return normalized


def employee_prefix_for_org(org_id: object | None, orgs_by_id: dict[str, dict]) -> str:
    path: list[str] = []
    current = orgs_by_id.get(text_value(org_id))
    visited: set[str] = set()
    while current and text_value(current.get("id")) not in visited:
        current_id = text_value(current.get("id"))
        visited.add(current_id)
        path.append(text_value(current.get("code")) or generated_org_code(current.get("name")))
        current = orgs_by_id.get(text_value(current.get("parentId")))
    path.reverse()
    if len(path) > 1:
        path.pop(0)
    return "-".join(path) or "ORG"


def normalize_employee_numbers(employees: list[dict], orgs: list[dict]) -> list[dict]:
    normalized = [dict(employee) for employee in employees]
    orgs_by_id = {text_value(org.get("id")): org for org in orgs}
    used_by_org: dict[str, set[int]] = {}
    for employee in normalized:
        org_id = text_value(employee.get("orgId"))
        match = re.search(r"-(\d+)$", text_value(employee.get("employeeNo")))
        if match:
            used_by_org.setdefault(org_id, set()).add(int(match.group(1)))
    for employee in normalized:
        if text_value(employee.get("employeeNo")):
            continue
        org_id = text_value(employee.get("orgId"))
        used = used_by_org.setdefault(org_id, set())
        sequence = 1
        while sequence in used:
            sequence += 1
        employee["employeeNo"] = f"{employee_prefix_for_org(org_id, orgs_by_id)}-{sequence:03d}"
        used.add(sequence)
    return normalized


def json_sql_value(value: object | None) -> str:
    if value is None:
        return "NULL"
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return f"CAST({sql_quote(encoded)} AS JSON)"


def text_value(value: object | None) -> str:
    return str(value or "").strip()


def normalize_mac_address(value: object | None) -> str:
    raw = text_value(value)
    if not raw:
        return ""
    colon_format = re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", raw)
    hyphen_format = re.fullmatch(r"(?:[0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}", raw)
    if not colon_format and not hyphen_format:
        return raw
    compact = raw.replace(":", "").replace("-", "").upper()
    return "-".join(compact[index : index + 2] for index in range(0, 12, 2))


def valid_mac_address(value: object | None) -> bool:
    raw = text_value(value)
    return not raw or bool(re.fullmatch(r"(?:[0-9A-F]{2}-){5}[0-9A-F]{2}", raw))


def org_path_from_map(org_id: object | None, orgs_by_id: dict[str, dict]) -> str:
    path: list[str] = []
    current = orgs_by_id.get(text_value(org_id))
    visited: set[str] = set()
    while current and text_value(current.get("id")) not in visited:
        current_id = text_value(current.get("id"))
        visited.add(current_id)
        path.append(text_value(current.get("name")))
        current = orgs_by_id.get(text_value(current.get("parentId")))
    path.reverse()
    return " / ".join(part for part in path if part)


def left_employee_source_key(item: dict) -> str:
    return (
        text_value(item.get("sourceEmployeeId"))
        or text_value(item.get("employeeNo"))
        or text_value(item.get("id"))
    )


def left_employee_indexes(snapshot: dict) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for item in snapshot.get("leftEmployees") or []:
        key = left_employee_source_key(item)
        if key:
            indexed[key] = item
        employee_no = text_value(item.get("employeeNo"))
        if employee_no:
            indexed.setdefault(employee_no, item)
    return indexed


def employee_device_snapshot(
    employee: dict,
    computers: list[dict],
    type_names: dict[str, str],
) -> list[dict]:
    snapshot: list[dict] = []
    employee_id = text_value(employee.get("id"))
    for computer in computers:
        if text_value(computer.get("assignmentEmployeeId")) != employee_id:
            continue
        snapshot.append(
            {
                "category": "computer",
                "label": text_value(computer.get("deviceName")),
                "detail": " ".join(
                    part
                    for part in (
                        text_value(computer.get("brand")),
                        text_value(computer.get("model")),
                    )
                    if part
                )
                or text_value(computer.get("deviceType")),
                "quantity": 1,
            }
        )

    for monitor in employee.get("monitors") or []:
        monitor_type_id = text_value(monitor.get("typeId"))
        snapshot.append(
            {
                "category": "monitor",
                "label": "\u663e\u793a\u5c4f",
                "detail": " ".join(
                    part
                    for part in (
                        text_value(monitor.get("brand")),
                        text_value(monitor.get("model")),
                    )
                    if part
                )
                or "\u672a\u586b\u5199\u54c1\u724c\u578b\u53f7",
                "quantity": 1,
                "typeId": monitor_type_id,
                "typeName": type_names.get(monitor_type_id) or "\u663e\u793a\u5c4f",
                "brandId": text_value(monitor.get("inventoryBrandId")),
                "modelId": text_value(monitor.get("inventoryModelId")),
                "brand": text_value(monitor.get("brand")),
                "model": text_value(monitor.get("model")),
            }
        )

    for item in employee.get("nonAssetItems") or []:
        quantity = max(0, sql_int(item.get("quantity"), 1))
        if quantity <= 0:
            continue
        type_id = text_value(item.get("typeId"))
        snapshot.append(
            {
                "category": "non-asset",
                "label": type_names.get(type_id) or type_id or "\u5176\u4ed6\u914d\u4ef6",
                "detail": " ".join(
                    part
                    for part in (
                        text_value(item.get("brand")),
                        text_value(item.get("model")),
                    )
                    if part
                )
                or "\u672a\u586b\u5199\u54c1\u724c\u578b\u53f7",
                "quantity": quantity,
                "typeId": type_id,
                "typeName": type_names.get(type_id) or type_id,
                "brandId": text_value(item.get("inventoryBrandId")),
                "modelId": text_value(item.get("inventoryModelId")),
                "brand": text_value(item.get("brand")),
                "model": text_value(item.get("model")),
            }
        )
    return snapshot


def legacy_left_employee_record(
    employee: dict,
    computers: list[dict],
    type_names: dict[str, str],
    orgs_by_id: dict[str, dict],
) -> dict:
    return {
        "id": f"legacy-{text_value(employee.get('id'))}",
        "sourceEmployeeId": text_value(employee.get("id")),
        "employeeNo": text_value(employee.get("employeeNo")),
        "name": text_value(employee.get("name")),
        "orgId": text_value(employee.get("orgId")),
        "orgPath": org_path_from_map(employee.get("orgId"), orgs_by_id),
        "department": text_value(employee.get("department")),
        "position": text_value(employee.get("position")),
        "email": text_value(employee.get("email")),
        "mobile": text_value(employee.get("mobile")),
        "leaveDate": "",
        "leaveInfo": "",
        "leaveRemark": "",
        "archivedAt": "",
        "devices": employee_device_snapshot(employee, computers, type_names),
    }


def employee_indexes(snapshot: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    by_id: dict[str, dict] = {}
    by_no: dict[str, dict] = {}
    for employee in snapshot.get("employees") or []:
        employee_id = text_value(employee.get("id"))
        employee_no = text_value(employee.get("employeeNo"))
        if employee_id:
            by_id[employee_id] = employee
        if employee_no:
            by_no[employee_no] = employee
    return by_id, by_no


def employee_info(employee: dict | None) -> dict:
    if not employee:
        return {"employeeNo": "", "employeeName": ""}
    return {
        "employeeNo": text_value(employee.get("employeeNo")),
        "employeeName": text_value(employee.get("name")),
    }


def employee_key(employee: dict) -> str:
    return text_value(employee.get("employeeNo")) or f"id:{text_value(employee.get('id'))}"


def computer_assignment_info(computer: dict | None, employees_by_id: dict[str, dict]) -> dict:
    if not computer:
        return {"employeeNo": "", "employeeName": ""}
    employee = employees_by_id.get(text_value(computer.get("userId")))
    return employee_info(employee)


def audit_category_key(action_type: str, entity_type: str) -> str:
    for category, entity_types in AUDIT_CATEGORY_ENTITY_TYPES.items():
        if entity_type in entity_types:
            return category
    return "other"


def audit_change_label(action_type: str, item: dict | None = None) -> str:
    old_value = (item or {}).get("oldValue") or {}
    new_value = (item or {}).get("newValue") or {}
    if action_type == "inventory_stock_changed":
        old_quantity = sql_int(old_value.get("quantity"), 0) if isinstance(old_value, dict) else 0
        new_quantity = sql_int(new_value.get("quantity"), 0) if isinstance(new_value, dict) else 0
        if new_quantity > old_quantity:
            return "物资库存增加"
        if new_quantity < old_quantity:
            return "物资库存减少"
    if action_type == "non_asset_quantity_changed":
        old_quantity = sql_int(old_value.get("quantity"), 0) if isinstance(old_value, dict) else 0
        new_quantity = sql_int(new_value.get("quantity"), 0) if isinstance(new_value, dict) else 0
        if new_quantity > old_quantity:
            return "人员物资增加"
        if new_quantity < old_quantity:
            return "人员物资减少"
    return AUDIT_CHANGE_LABELS.get(action_type) or action_type or "其他变动"


def audit_category_where_condition(category: str) -> str:
    entity_types = AUDIT_CATEGORY_ENTITY_TYPES.get(category)
    if entity_types:
        quoted = ", ".join(sql_quote(item) for item in entity_types)
        return f"entity_type IN ({quoted})"
    if category == "other":
        known_types = tuple(
            entity_type
            for values in AUDIT_CATEGORY_ENTITY_TYPES.values()
            for entity_type in values
        )
        quoted = ", ".join(sql_quote(item) for item in known_types)
        return f"entity_type NOT IN ({quoted})"
    return ""


def audit_entry(
    action_type: str,
    entity_type: str,
    entity_id: object | None,
    entity_name: str,
    employee_no: str = "",
    employee_name: str = "",
    device_name: str = "",
    old_value: object | None = None,
    new_value: object | None = None,
    summary: str = "",
) -> dict:
    return {
        "actionType": action_type,
        "entityType": entity_type,
        "entityId": text_value(entity_id),
        "entityName": entity_name,
        "employeeId": employee_no,
        "employeeName": employee_name,
        "deviceName": device_name,
        "oldValue": old_value,
        "newValue": new_value,
        "summary": summary,
        "actor": "web",
        "source": "web",
    }


def computer_key(computer: dict) -> str:
    return text_value(computer.get("id")) or text_value(computer.get("deviceName")) or "unknown-computer"


def computer_snapshot(snapshot: dict) -> dict[str, dict]:
    return {
        computer_key(computer): computer
        for computer in snapshot.get("computers") or []
    }


def employee_info_snapshot(employee: dict) -> dict:
    return {
        "employeeNo": text_value(employee.get("employeeNo")),
        "name": text_value(employee.get("name")),
        "orgId": text_value(employee.get("orgId")),
        "department": text_value(employee.get("department")),
        "position": text_value(employee.get("position")),
        "email": text_value(employee.get("email")),
        "mobile": text_value(employee.get("mobile")),
    }


def computer_info_snapshot(computer: dict) -> dict:
    return {
        "deviceName": text_value(computer.get("deviceName")),
        "orgId": text_value(computer.get("orgId")),
        "deviceType": text_value(computer.get("deviceType")),
                "brand": text_value(computer.get("brand")),
                "model": text_value(computer.get("model")),
                "inventoryModelId": text_value(computer.get("inventoryModelId")),
                "cpu": text_value(computer.get("cpu")),
        "memory": text_value(computer.get("memory")),
        "storage": text_value(computer.get("storage")),
        "gpu": text_value(computer.get("gpu")),
        "fixedAssetCode": text_value(computer.get("fixedAssetCode")),
        "purchaseDate": text_value(computer.get("purchaseDate")),
        "registeredDate": text_value(computer.get("registeredDate")),
        "snSt": text_value(computer.get("snSt")),
        "wifiMac": text_value(computer.get("wifiMac")),
        "ethernetMac": text_value(computer.get("ethernetMac")),
        "location": text_value(computer.get("location")),
        "department": text_value(computer.get("department")),
        "remarks": text_value(computer.get("remarks")),
    }


def changed_field_summary(old_value: dict, new_value: dict, labels: dict[str, str]) -> str:
    changes = []
    for key, label in labels.items():
        old_item = old_value.get(key) or "未填写"
        new_item = new_value.get(key) or "未填写"
        if old_value.get(key) != new_value.get(key):
            changes.append(f"{label}: {old_item} -> {new_item}")
    return "；".join(changes)


def assignment_label(info: dict) -> str:
    return info.get("employeeName") or "未分配"


def monitor_counts(snapshot: dict) -> dict[tuple[str, str, str], dict]:
    counts: dict[tuple[str, str, str], dict] = {}
    for employee in snapshot.get("employees") or []:
        employee_no = text_value(employee.get("employeeNo"))
        employee_name = text_value(employee.get("name"))
        for monitor in employee.get("monitors") or []:
            brand = text_value(monitor.get("brand"))
            model = text_value(monitor.get("model"))
            monitor_id = text_value(monitor.get("id")) or f"legacy:{employee_no}:{brand}:{model}"
            key = (monitor_id, "", "")
            item = counts.setdefault(
                key,
                {
                    "monitorId": monitor_id,
                    "employeeNo": employee_no,
                    "employeeName": employee_name,
                    "brand": brand,
                    "model": model,
                    "quantity": 0,
                },
            )
            item["quantity"] += 1
    return counts


def non_asset_counts(snapshot: dict) -> dict[tuple[str, str, str, str], dict]:
    types_by_id = {
        text_value(item.get("id")): text_value(item.get("name"))
        for item in snapshot.get("nonAssetTypes") or []
    }
    counts: dict[tuple[str, str, str, str], dict] = {}
    for employee in snapshot.get("employees") or []:
        employee_no = text_value(employee.get("employeeNo"))
        employee_name = text_value(employee.get("name"))
        for item in employee.get("nonAssetItems") or []:
            type_id = text_value(item.get("typeId"))
            type_name = types_by_id.get(type_id) or type_id or "非资产设备"
            brand = text_value(item.get("brand"))
            model = text_value(item.get("model"))
            item_id = text_value(item.get("id")) or f"legacy:{employee_no}:{type_name}:{brand}:{model}"
            key = (item_id, "", "", "")
            record = counts.setdefault(
                key,
                {
                    "itemId": item_id,
                    "employeeNo": employee_no,
                    "employeeName": employee_name,
                    "typeName": type_name,
                    "brand": brand,
                    "model": model,
                    "quantity": 0,
                },
            )
            record["quantity"] += max(0, sql_int(item.get("quantity"), 1))
    return counts


def inventory_type_indexes(snapshot: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    types = {
        text_value(item.get("id")): item
        for item in snapshot.get("nonAssetTypes") or []
        if text_value(item.get("id"))
    }
    brands = {
        text_value(item.get("id")): item
        for item in snapshot.get("inventoryBrands") or []
        if text_value(item.get("id"))
    }
    return types, brands


def inventory_model_key(
    model: dict,
    brands_by_id: dict[str, dict],
    types_by_id: dict[str, dict],
) -> tuple[str, str, str]:
    type_id = text_value(model.get("typeId"))
    brand = brands_by_id.get(text_value(model.get("brandId"))) or {}
    return (
        text_value(types_by_id.get(type_id, {}).get("name")) or type_id,
        text_value(brand.get("name")),
        text_value(model.get("name")),
    )


def build_inventory_audit_entries_v2(old_snapshot: dict, new_snapshot: dict) -> list[dict]:
    old_types, old_brands_by_id = inventory_type_indexes(old_snapshot)
    new_types, new_brands_by_id = inventory_type_indexes(new_snapshot)
    entries: list[dict] = []

    def type_value(item: dict) -> dict:
        return {
            "code": text_value(item.get("code")),
            "name": text_value(item.get("name")),
            "unit": text_value(item.get("unit")),
        }

    def brand_value(item: dict, types_by_id: dict[str, dict]) -> dict:
        type_id = text_value(item.get("typeId"))
        return {
            "typeId": type_id,
            "typeName": text_value(types_by_id.get(type_id, {}).get("name")) or type_id,
            "brand": text_value(item.get("name")),
        }

    def model_value(
        item: dict,
        types_by_id: dict[str, dict],
        brands_by_id: dict[str, dict],
    ) -> dict:
        type_id = text_value(item.get("typeId"))
        brand_id = text_value(item.get("brandId"))
        return {
            "typeId": type_id,
            "brandId": brand_id,
            "typeName": text_value(types_by_id.get(type_id, {}).get("name")) or type_id,
            "brand": text_value(brands_by_id.get(brand_id, {}).get("name")) or brand_id,
            "model": text_value(item.get("name")),
            "batchKey": text_value(item.get("batchKey")),
            "quantity": max(0, sql_int(item.get("quantity"), 0)),
            "inboundDate": text_value(item.get("inboundDate")),
            "cpu": text_value(item.get("cpu")),
            "memory": text_value(item.get("memory")),
            "storage": text_value(item.get("storage")),
            "gpu": text_value(item.get("gpu")),
        }

    def inventory_path(value: dict) -> str:
        return " / ".join(
            part
            for part in (
                value.get("typeName"),
                value.get("brand"),
                value.get("model"),
            )
            if part
        )

    for type_id in sorted(set(old_types) | set(new_types)):
        previous = old_types.get(type_id)
        current = new_types.get(type_id)
        if previous and current:
            old_value = type_value(previous)
            new_value = type_value(current)
            if old_value == new_value:
                continue
            entries.append(
                audit_entry(
                    "inventory_type_changed",
                    "inventory_type",
                    type_id,
                    new_value["name"] or old_value["name"] or type_id,
                    old_value=old_value,
                    new_value=new_value,
                    summary=(
                        f"IT物资类型已变更：{old_value['name'] or type_id} -> "
                        f"{new_value['name'] or type_id}"
                    ),
                )
            )
            continue

        item = current or previous or {}
        action = "inventory_group_added" if current else "inventory_group_removed"
        value = type_value(item)
        entries.append(
            audit_entry(
                action,
                "inventory_type",
                type_id,
                value["name"] or type_id,
                old_value=None if current else value,
                new_value=value if current else None,
                summary=f"IT物资类型已{'新增' if current else '删除'}：{value['name'] or type_id}",
            )
        )

    old_brands = {
        text_value(item.get("id")): item
        for item in old_snapshot.get("inventoryBrands") or []
        if text_value(item.get("id"))
    }
    new_brands = {
        text_value(item.get("id")): item
        for item in new_snapshot.get("inventoryBrands") or []
        if text_value(item.get("id"))
    }
    for brand_id in sorted(set(old_brands) | set(new_brands)):
        previous = old_brands.get(brand_id)
        current = new_brands.get(brand_id)
        if previous and current:
            old_value = brand_value(previous, old_types)
            new_value = brand_value(current, new_types)
            if old_value == new_value:
                continue
            entries.append(
                audit_entry(
                    "inventory_brand_changed",
                    "inventory_brand",
                    brand_id,
                    f"{new_value['typeName']} / {new_value['brand']}",
                    old_value=old_value,
                    new_value=new_value,
                    summary=(
                        f"IT物资品牌已变更：{old_value['typeName']} / {old_value['brand']} -> "
                        f"{new_value['typeName']} / {new_value['brand']}"
                    ),
                )
            )
            continue

        item = current or previous or {}
        value = brand_value(item, new_types if current else old_types)
        action = "inventory_group_added" if current else "inventory_group_removed"
        entries.append(
            audit_entry(
                action,
                "inventory_brand",
                brand_id,
                f"{value['typeName']} / {value['brand']}",
                old_value=None if current else value,
                new_value=value if current else None,
                summary=(
                    f"IT物资品牌已{'新增' if current else '删除'}："
                    f"{value['typeName']} / {value['brand']}"
                ),
            )
        )

    old_models = {
        text_value(item.get("id")): item
        for item in old_snapshot.get("inventoryModels") or []
        if text_value(item.get("id"))
    }
    new_models = {
        text_value(item.get("id")): item
        for item in new_snapshot.get("inventoryModels") or []
        if text_value(item.get("id"))
    }
    for model_id in sorted(set(old_models) | set(new_models)):
        previous = old_models.get(model_id)
        current = new_models.get(model_id)
        if previous and current:
            old_value = model_value(previous, old_types, old_brands_by_id)
            new_value = model_value(current, new_types, new_brands_by_id)
            identity_changed = any(
                old_value[key] != new_value[key]
                for key in ("typeId", "brandId", "model", "batchKey", "inboundDate", "cpu", "memory", "storage", "gpu")
            )
            quantity_changed = old_value["quantity"] != new_value["quantity"]
            if not identity_changed and not quantity_changed:
                continue

            if identity_changed:
                summary = (
                    f"IT物资型号信息已变更：{inventory_path(old_value)} -> "
                    f"{inventory_path(new_value)}"
                )
                if quantity_changed:
                    summary += (
                        f"；库存数量 {old_value['quantity']} -> "
                        f"{new_value['quantity']}"
                    )
                action = "inventory_model_changed"
            else:
                action = "inventory_stock_changed"
                summary = (
                    f"IT物资库存数量已变更：{inventory_path(new_value)}（"
                    f"{old_value['quantity']} -> {new_value['quantity']}）"
                )
            entries.append(
                audit_entry(
                    action,
                    "inventory_model",
                    model_id,
                    inventory_path(new_value) or inventory_path(old_value) or model_id,
                    old_value=old_value,
                    new_value=new_value,
                    summary=summary,
                )
            )
            continue

        item = current or previous or {}
        value = model_value(
            item,
            new_types if current else old_types,
            new_brands_by_id if current else old_brands_by_id,
        )
        action = "inventory_group_added" if current else "inventory_group_removed"
        entries.append(
            audit_entry(
                action,
                "inventory_model",
                model_id,
                inventory_path(value) or model_id,
                old_value=None if current else value,
                new_value=value if current else None,
                summary=(
                    f"IT物资型号已{'新增' if current else '删除'}："
                    f"{inventory_path(value) or model_id}"
                ),
            )
        )
    return entries


def build_audit_entries(old_snapshot: dict, new_payload: dict) -> list[dict]:
    old = normalize_payload(old_snapshot)
    new = normalize_payload(new_payload)
    old_employees_by_id, _ = employee_indexes(old)
    new_employees_by_id, _ = employee_indexes(new)
    old_left_employees = left_employee_indexes(old)
    new_left_employees = left_employee_indexes(new)
    old_computers = computer_snapshot(old)
    new_computers = computer_snapshot(new)
    entries: list[dict] = []
    archived_logged_sources: set[str] = set()
    entries.extend(build_inventory_audit_entries_v2(old, new))

    for employee_id in sorted(set(new_employees_by_id) - set(old_employees_by_id)):
        current = new_employees_by_id[employee_id]
        employee_no = text_value(current.get("employeeNo"))
        employee_name = text_value(current.get("name"))
        entries.append(
            audit_entry(
                "employee_added",
                "employee",
                current.get("id"),
                employee_name or employee_no,
                employee_no,
                employee_name,
                "",
                None,
                {
                    "employeeNo": employee_no,
                    "department": text_value(current.get("department")),
                    "status": text_value(current.get("status")) or "active",
                },
                f"新增人员 {employee_name or employee_no}",
            )
        )

    for employee_id in sorted(set(old_employees_by_id) - set(new_employees_by_id)):
        previous = old_employees_by_id[employee_id]
        employee_no = text_value(previous.get("employeeNo"))
        employee_name = text_value(previous.get("name"))
        previous_status = text_value(previous.get("status")) or "active"
        archived = new_left_employees.get(employee_id) or new_left_employees.get(employee_no)
        if archived:
            archived_logged_sources.add(left_employee_source_key(archived))
            entries.append(
                audit_entry(
                    "employee_archived",
                    "employee",
                    archived.get("id") or previous.get("id"),
                    employee_name or employee_no,
                    employee_no,
                    employee_name,
                    "",
                    {"status": previous_status},
                    {
                        "status": "left",
                        "department": text_value(archived.get("department")),
                        "leaveDate": text_value(archived.get("leaveDate")),
                    },
                    f"人员 {employee_name or employee_no} 已归档到离职人员",
                )
            )
            continue
        entries.append(
            audit_entry(
                "employee_removed",
                "employee",
                previous.get("id"),
                employee_name or employee_no,
                employee_no,
                employee_name,
                "",
                {
                    "employeeNo": employee_no,
                    "department": text_value(previous.get("department")),
                    "status": previous_status,
                },
                None,
                f"删除人员 {employee_name or employee_no}",
            )
        )

    for archived in new.get("leftEmployees") or []:
        canonical_key = left_employee_source_key(archived)
        if not canonical_key or canonical_key in archived_logged_sources or canonical_key in old_left_employees:
            continue
        employee_no = text_value(archived.get("employeeNo"))
        employee_name = text_value(archived.get("name"))
        entries.append(
            audit_entry(
                "employee_archived",
                "employee",
                archived.get("id"),
                employee_name or employee_no,
                employee_no,
                employee_name,
                "",
                None,
                {
                    "status": "left",
                    "department": text_value(archived.get("department")),
                    "leaveDate": text_value(archived.get("leaveDate")),
                },
                f"人员 {employee_name or employee_no} 已归档到离职人员",
            )
        )
        archived_logged_sources.add(canonical_key)

    for employee_id in sorted(set(old_employees_by_id) & set(new_employees_by_id)):
        previous = old_employees_by_id[employee_id]
        current = new_employees_by_id[employee_id]
        previous_status = text_value(previous.get("status")) or "active"
        current_status = text_value(current.get("status")) or "active"
        if previous_status == current_status:
            continue
        employee_no = text_value(current.get("employeeNo")) or text_value(previous.get("employeeNo"))
        employee_name = text_value(current.get("name")) or text_value(previous.get("name"))
        entries.append(
            audit_entry(
                "employee_status_changed",
                "employee",
                current.get("id") or previous.get("id"),
                employee_name or employee_no,
                employee_no,
                employee_name,
                "",
                {"status": previous_status},
                {"status": current_status},
                f"人员 {employee_name or employee_no} 状态由 "
                f"{AUDIT_EMPLOYEE_STATUS_LABELS.get(previous_status, previous_status)} 变更为 "
                f"{AUDIT_EMPLOYEE_STATUS_LABELS.get(current_status, current_status)}",
            )
        )

    employee_info_labels = {
        "employeeNo": "人员编号",
        "name": "姓名",
        "orgId": "组织",
        "department": "部门",
        "position": "岗位",
        "email": "邮箱",
        "mobile": "手机",
    }
    for employee_id in sorted(set(old_employees_by_id) & set(new_employees_by_id)):
        previous = old_employees_by_id[employee_id]
        current = new_employees_by_id[employee_id]
        old_value = employee_info_snapshot(previous)
        new_value = employee_info_snapshot(current)
        if old_value == new_value:
            continue
        employee_no = text_value(current.get("employeeNo")) or text_value(previous.get("employeeNo"))
        employee_name = text_value(current.get("name")) or text_value(previous.get("name"))
        entries.append(
            audit_entry(
                "employee_info_changed",
                "employee",
                current.get("id") or previous.get("id"),
                employee_name or employee_no,
                employee_no,
                employee_name,
                old_value=old_value,
                new_value=new_value,
                summary=(
                    f"人员 {employee_name or employee_no} 信息变更："
                    f"{changed_field_summary(old_value, new_value, employee_info_labels)}"
                ),
            )
        )

    for key in sorted(set(old_computers) | set(new_computers)):
        previous = old_computers.get(key)
        current = new_computers.get(key)
        computer = current or previous or {}
        device_name = text_value(computer.get("deviceName")) or key
        current_assignment = computer_assignment_info(current, new_employees_by_id)
        previous_assignment = computer_assignment_info(previous, old_employees_by_id)
        employee_no = current_assignment["employeeNo"] or previous_assignment["employeeNo"]
        employee_name = current_assignment["employeeName"] or previous_assignment["employeeName"]

        if previous is None:
            entries.append(
                audit_entry(
                    "computer_added",
                    "computer",
                    computer.get("id"),
                    device_name,
                    employee_no,
                    employee_name,
                    device_name,
                    None,
                    {
                        "deviceName": device_name,
                        "status": text_value(computer.get("status")) or "idle",
                        "assignment": current_assignment,
                    },
                    f"新增办公终端 {device_name}",
                )
            )
            continue

        if current is None:
            entries.append(
                audit_entry(
                    "computer_removed",
                    "computer",
                    previous.get("id"),
                    device_name,
                    employee_no,
                    employee_name,
                    device_name,
                    {
                        "deviceName": device_name,
                        "status": text_value(previous.get("status")) or "idle",
                        "assignment": previous_assignment,
                    },
                    None,
                    f"删除办公终端 {device_name}",
                )
            )
            continue

        previous_status = text_value(previous.get("status")) or "idle"
        current_status = text_value(current.get("status")) or "idle"
        if previous_status != current_status:
            entries.append(
                audit_entry(
                    "computer_status_changed",
                    "computer",
                    current.get("id") or previous.get("id"),
                    device_name,
                    employee_no,
                    employee_name,
                    device_name,
                    {"status": previous_status},
                    {"status": current_status},
                    f"办公终端 {device_name} 状态由 {AUDIT_STATUS_LABELS.get(previous_status, previous_status)} "
                    f"变更为 {AUDIT_STATUS_LABELS.get(current_status, current_status)}",
                )
            )

        if previous_assignment != current_assignment:
            entries.append(
                audit_entry(
                    "computer_assignment_changed",
                    "computer",
                    current.get("id") or previous.get("id"),
                    device_name,
                    current_assignment["employeeNo"] or previous_assignment["employeeNo"],
                    current_assignment["employeeName"] or previous_assignment["employeeName"],
                    device_name,
                    previous_assignment,
                    current_assignment,
                    f"办公终端 {device_name} 使用人由 {assignment_label(previous_assignment)} "
                    f"变更为 {assignment_label(current_assignment)}",
                )
            )

        computer_info_labels = {
            "cpu": "CPU",
            "memory": "内存",
            "storage": "存储",
            "gpu": "显卡",
            "deviceName": "设备名",
            "orgId": "组织",
            "deviceType": "设备类型",
            "brand": "品牌",
            "model": "型号",
            "fixedAssetCode": "固资编码",
            "purchaseDate": "购置日期",
            "registeredDate": "注册日期",
            "snSt": "SN/ST",
            "wifiMac": "Wifi MAC",
            "ethernetMac": "网口 MAC",
            "location": "位置",
            "department": "部门",
            "remarks": "备注",
        }
        old_info = computer_info_snapshot(previous)
        new_info = computer_info_snapshot(current)
        if old_info != new_info:
            entries.append(
                audit_entry(
                    "computer_info_changed",
                    "computer",
                    current.get("id") or previous.get("id"),
                    device_name,
                    employee_no,
                    employee_name,
                    device_name,
                    old_info,
                    new_info,
                    f"办公终端 {device_name} 信息变更："
                    f"{changed_field_summary(old_info, new_info, computer_info_labels)}",
                )
            )

    old_monitors = monitor_counts(old)
    new_monitors = monitor_counts(new)
    for key in sorted(set(old_monitors) | set(new_monitors)):
        previous = old_monitors.get(key, {})
        current = new_monitors.get(key, {})
        old_quantity = sql_int(previous.get("quantity"), 0)
        new_quantity = sql_int(current.get("quantity"), 0)
        old_brand = text_value(previous.get("brand"))
        old_model = text_value(previous.get("model"))
        new_brand = text_value(current.get("brand"))
        new_model = text_value(current.get("model"))
        details_changed = (old_brand, old_model) != (new_brand, new_model)
        if old_quantity == new_quantity and not details_changed:
            continue
        item = current or previous
        employee_no = text_value(item.get("employeeNo"))
        employee_name = text_value(item.get("employeeName"))
        new_label = " ".join(part for part in (new_brand, new_model) if part) or "未填写品牌型号"
        old_label = " ".join(part for part in (old_brand, old_model) if part) or "未填写品牌型号"
        entity_name = f"{employee_name or employee_no}的显示屏"
        if old_quantity == 0:
            action = "monitor_added"
            summary = f"{employee_name or employee_no} 新增 {new_quantity} 个显示屏（{new_label}）"
        elif new_quantity == 0:
            action = "monitor_removed"
            summary = f"{employee_name or employee_no} 删除 {old_quantity} 个显示屏（{old_label}）"
        elif details_changed:
            action = "monitor_changed"
            summary = (
                f"{employee_name or employee_no} 显示屏信息由 {old_label} 变更为 {new_label}"
            )
            if old_quantity != new_quantity:
                summary += f"；数量 {old_quantity} -> {new_quantity}"
        else:
            action = "monitor_added" if new_quantity > old_quantity else "monitor_removed"
            change = new_quantity - old_quantity
            summary = (
                f"{employee_name or employee_no} {'增加' if change > 0 else '减少'} "
                f"{abs(change)} 个显示屏（{new_label}）"
            )
        entries.append(
            audit_entry(
                action,
                "monitor",
                "|".join(key),
                entity_name,
                employee_no,
                employee_name,
                "",
                {"quantity": old_quantity, "brand": old_brand, "model": old_model} if old_quantity else None,
                {"quantity": new_quantity, "brand": new_brand, "model": new_model} if new_quantity else None,
                summary,
            )
        )

    old_non_assets = non_asset_counts(old)
    new_non_assets = non_asset_counts(new)
    for key in sorted(set(old_non_assets) | set(new_non_assets)):
        previous = old_non_assets.get(key, {})
        current = new_non_assets.get(key, {})
        old_quantity = sql_int(previous.get("quantity"), 0)
        new_quantity = sql_int(current.get("quantity"), 0)
        old_type_name = text_value(previous.get("typeName")) or "非资产设备"
        new_type_name = text_value(current.get("typeName")) or "非资产设备"
        old_brand = text_value(previous.get("brand"))
        old_model = text_value(previous.get("model"))
        new_brand = text_value(current.get("brand"))
        new_model = text_value(current.get("model"))
        details_changed = (old_type_name, old_brand, old_model) != (
            new_type_name,
            new_brand,
            new_model,
        )
        if old_quantity == new_quantity and not details_changed:
            continue
        item = current or previous
        employee_no = text_value(item.get("employeeNo"))
        employee_name = text_value(item.get("employeeName"))
        new_detail = " ".join(part for part in (new_brand, new_model) if part) or "未填写品牌型号"
        old_detail = " ".join(part for part in (old_brand, old_model) if part) or "未填写品牌型号"
        entity_name = f"{employee_name or employee_no}的{new_type_name or old_type_name}"
        if old_quantity == 0:
            action = "non_asset_added"
            summary = f"{employee_name or employee_no} 新增 {new_quantity} 件{new_type_name}（{new_detail}）"
        elif new_quantity == 0:
            action = "non_asset_removed"
            summary = f"{employee_name or employee_no} 删除 {old_quantity} 件{old_type_name}（{old_detail}）"
        elif details_changed:
            action = "non_asset_changed"
            summary = (
                f"{employee_name or employee_no} 非资产物资信息由 "
                f"{old_type_name} / {old_detail} 变更为 {new_type_name} / {new_detail}"
            )
            if old_quantity != new_quantity:
                summary += f"；数量 {old_quantity} -> {new_quantity}"
        else:
            action = "non_asset_quantity_changed"
            change = new_quantity - old_quantity
            summary = (
                f"{employee_name or employee_no} {new_type_name}数量由 {old_quantity} 变更为 "
                f"{new_quantity}（{new_detail}）"
            )
        entries.append(
            audit_entry(
                action,
                "non_asset",
                "|".join(key),
                entity_name,
                employee_no,
                employee_name,
                "",
                {
                    "typeName": old_type_name,
                    "brand": old_brand,
                    "model": old_model,
                    "quantity": old_quantity,
                }
                if old_quantity
                else None,
                {
                    "typeName": new_type_name,
                    "brand": new_brand,
                    "model": new_model,
                    "quantity": new_quantity,
                }
                if new_quantity
                else None,
                summary,
            )
        )

    return entries


def sort_orgs_for_insert(orgs: list[dict]) -> list[dict]:
    by_id = {str(org.get("id") or ""): org for org in orgs}

    def depth(org: dict, trail: set[str] | None = None) -> int:
        trail = trail or set()
        org_id = str(org.get("id") or "")
        if org_id in trail:
            return 0
        trail = set(trail)
        trail.add(org_id)
        parent_id = str(org.get("parentId") or "")
        parent = by_id.get(parent_id)
        if not parent:
            return 0
        return depth(parent, trail) + 1

    return sorted(
        orgs,
        key=lambda org: (depth(org), sql_int(org.get("sortOrder"), 1000), str(org.get("code") or ""), str(org.get("name") or "")),
    )


def serialize_audit_log(item: dict) -> dict:
    action_type = item.get("actionType") or ""
    entity_type = item.get("entityType") or ""
    category = audit_category_key(action_type, entity_type)
    return {
        "id": str(item.get("id") or ""),
        "actionType": action_type,
        "entityType": entity_type,
        "category": category,
        "categoryLabel": AUDIT_CATEGORY_LABELS.get(category, AUDIT_CATEGORY_LABELS["other"]),
        "changeLabel": audit_change_label(action_type, item),
        "entityId": item.get("entityId") or "",
        "entityName": item.get("entityName") or "",
        "employeeId": item.get("employeeId") or "",
        "employeeName": item.get("employeeName") or "",
        "deviceName": item.get("deviceName") or "",
        "oldValue": item.get("oldValue"),
        "newValue": item.get("newValue"),
        "summary": item.get("summary") or "",
        "actor": item.get("actor") or "web",
        "source": item.get("source") or "web",
        "createdAt": item.get("createdAt") or "",
    }


def audit_log_where_clause(params: dict[str, list[str]]) -> str:
    start_date = (params.get("startDate") or [""])[0].strip()
    end_date = (params.get("endDate") or [""])[0].strip()
    employee = (params.get("employee") or [""])[0].strip()
    action_type = (params.get("actionType") or [""])[0].strip()
    category = (params.get("category") or [""])[0].strip()
    entity_type = (params.get("entityType") or [""])[0].strip()
    keyword = (params.get("keyword") or [""])[0].strip()
    conditions = []

    for name, value in (("startDate", start_date), ("endDate", end_date)):
        if value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ApiError(f"Invalid {name}; expected YYYY-MM-DD.")
    if start_date and end_date and start_date > end_date:
        raise ApiError("startDate cannot be later than endDate.")

    if start_date:
        conditions.append(f"created_at >= {sql_quote(start_date + ' 00:00:00')}")
    if end_date:
        conditions.append(
            f"created_at < DATE_ADD({sql_quote(end_date + ' 00:00:00')}, INTERVAL 1 DAY)"
        )
    if employee:
        conditions.append(
            "INSTR(CONCAT_WS(' ', COALESCE(employee_id, ''), COALESCE(employee_name, '')), "
            f"{sql_quote(employee)}) > 0"
        )
    if action_type:
        conditions.append(f"action_type = {sql_quote(action_type)}")
    if category:
        category_condition = audit_category_where_condition(category)
        if category_condition:
            conditions.append(category_condition)
    if entity_type == "it_inventory":
        conditions.append(
            "entity_type IN ('inventory_type', 'inventory_brand', 'inventory_model')"
        )
    elif entity_type:
        conditions.append(f"entity_type = {sql_quote(entity_type)}")
    if keyword:
        conditions.append(
            "INSTR(CONCAT_WS(' ', action_type, entity_type, entity_name, employee_id, "
            "employee_name, device_name, summary), "
            f"{sql_quote(keyword)}) > 0"
        )
    return " AND ".join(conditions) if conditions else "1 = 1"


def query_audit_logs(params: dict[str, list[str]]) -> dict:
    where_clause = audit_log_where_clause(params)
    raw_limit = (params.get("limit") or [str(AUDIT_QUERY_LIMIT)])[0]
    limit = max(1, min(AUDIT_QUERY_LIMIT, sql_int(raw_limit, AUDIT_QUERY_LIMIT)))
    count_sql = f"SELECT COUNT(*) FROM audit_log WHERE {where_clause};"
    log_sql = f"""
    SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
      'id', CAST(audit_log_id AS CHAR),
      'actionType', action_type,
      'entityType', entity_type,
      'entityId', COALESCE(entity_id, ''),
      'entityName', COALESCE(entity_name, ''),
      'employeeId', COALESCE(employee_id, ''),
      'employeeName', COALESCE(employee_name, ''),
      'deviceName', COALESCE(device_name, ''),
      'oldValue', old_value,
      'newValue', new_value,
      'summary', summary,
      'actor', actor,
      'source', source,
      'createdAt', DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s')
    )), JSON_ARRAY())
    FROM (
      SELECT audit_log_id, action_type, entity_type, entity_id, entity_name,
             employee_id, employee_name, device_name, old_value, new_value,
             summary, actor, source, created_at
      FROM audit_log
      WHERE {where_clause}
      ORDER BY created_at DESC, audit_log_id DESC
      LIMIT {limit}
    ) AS filtered_audit_logs
    """
    total = sql_int(run_mysql(count_sql, database=DB_NAME).strip(), 0)
    logs = run_mysql_json_queries(log_sql)[0]
    return {
        "logs": [serialize_audit_log(item) for item in logs],
        "total": total,
        "limit": limit,
    }


def build_state_payload() -> dict:
    queries = [
        """
        SELECT revision
        FROM app_state_revision
        WHERE revision_id = 1
        """,
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(org_unit_id AS CHAR),
          'code', org_code,
          'name', org_name,
          'parentId', COALESCE(CAST(parent_org_unit_id AS CHAR), ''),
          'sortOrder', sort_order
        )), JSON_ARRAY())
        FROM (
          SELECT org_unit_id, org_code, org_name, parent_org_unit_id, sort_order
          FROM org_unit
          WHERE is_active = 1
          ORDER BY sort_order, org_code, org_unit_id
        ) AS ordered_orgs
        """,
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(non_asset_type_id AS CHAR),
          'code', type_code,
          'name', type_name,
          'unit', unit_name
        )), JSON_ARRAY())
        FROM (
          SELECT non_asset_type_id, type_code, type_name, unit_name
          FROM non_asset_type
          WHERE is_active = 1
          ORDER BY non_asset_type_id
        ) AS ordered_types
        """,
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(brand_id AS CHAR),
          'typeId', CAST(non_asset_type_id AS CHAR),
          'name', brand_name,
          'sortOrder', sort_order
        )), JSON_ARRAY())
        FROM (
          SELECT brand_id, non_asset_type_id, brand_name, sort_order
          FROM it_inventory_brand
          WHERE is_active = 1
          ORDER BY non_asset_type_id, sort_order, brand_name, brand_id
        ) AS ordered_inventory_brands
        """,
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(model_id AS CHAR),
          'typeId', CAST(non_asset_type_id AS CHAR),
          'brandId', CAST(brand_id AS CHAR),
          'name', model_name,
          'batchKey', COALESCE(batch_key, ''),
          'quantity', quantity,
          'inboundDate', COALESCE(CAST(inbound_date AS CHAR), ''),
          'cpu', COALESCE(cpu, ''),
          'memory', COALESCE(memory, ''),
          'storage', COALESCE(storage, ''),
          'gpu', COALESCE(gpu, ''),
          'sortOrder', sort_order
        )), JSON_ARRAY())
        FROM (
          SELECT model_id, non_asset_type_id, brand_id, model_name, batch_key, quantity,
                 inbound_date, cpu, memory, storage, gpu, sort_order
          FROM it_inventory_model
          WHERE is_active = 1
          ORDER BY non_asset_type_id, brand_id, sort_order, model_name, model_id
        ) AS ordered_inventory_models
        """,
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(warehouse.warehouse_id AS CHAR),
          'code', warehouse.warehouse_code,
          'name', warehouse.warehouse_name,
          'orgId', CAST(warehouse.org_unit_id AS CHAR),
          'managerEmployeeId', COALESCE(CAST(warehouse.manager_employee_id AS CHAR), ''),
          'managerName', COALESCE(manager.employee_name, ''),
          'contactPhone', warehouse.contact_phone,
          'address', warehouse.address,
          'isActive', warehouse.is_active,
          'remarks', warehouse.remarks
        )), JSON_ARRAY())
        FROM (
          SELECT *
          FROM inventory_warehouse
          ORDER BY is_active DESC, warehouse_name, warehouse_id
        ) warehouse
        LEFT JOIN employee manager ON manager.employee_id = warehouse.manager_employee_id
        """,
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'warehouseId', CAST(stock.warehouse_id AS CHAR),
          'modelId', CAST(stock.model_id AS CHAR),
          'quantity', stock.quantity
        )), JSON_ARRAY())
        FROM inventory_warehouse_stock stock
        """,
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(employee_id AS CHAR),
          'employeeNo', employee_no,
          'name', employee_name,
          'orgId', COALESCE(CAST(org_unit_id AS CHAR), ''),
          'department', COALESCE(department, ''),
          'position', COALESCE(position_name, ''),
          'email', COALESCE(email, ''),
          'mobile', COALESCE(mobile, ''),
          'status', employment_status
        )), JSON_ARRAY())
        FROM (
          SELECT employee_id, employee_no, employee_name, org_unit_id, department, position_name, email, mobile, employment_status
          FROM employee
          WHERE is_active = 1 AND employment_status <> 'left'
          ORDER BY employee_no, employee_name, employee_id
        ) AS ordered_employees
        """,
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
           'id', CAST(monitor_usage_id AS CHAR),
           'employeeId', CAST(employee_id AS CHAR),
           'typeId', COALESCE(CAST(non_asset_type_id AS CHAR), ''),
           'brandId', COALESCE(CAST(inventory_brand_id AS CHAR), ''),
           'modelId', COALESCE(CAST(inventory_model_id AS CHAR), ''),
           'brand', display_name,
           'model', model,
           'stockAdjusted', stock_adjusted
        )), JSON_ARRAY())
        FROM (
           SELECT monitor_usage_id, employee_id, non_asset_type_id, inventory_brand_id,
                  inventory_model_id, display_name, model, stock_adjusted
          FROM employee_monitor_usage
          WHERE is_active = 1
          ORDER BY employee_id, monitor_usage_id
        ) AS ordered_monitors
        """,
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
           'id', CAST(non_asset_usage_id AS CHAR),
           'employeeId', CAST(employee_id AS CHAR),
           'typeId', CAST(non_asset_type_id AS CHAR),
           'brandId', COALESCE(CAST(inventory_brand_id AS CHAR), ''),
           'modelId', COALESCE(CAST(inventory_model_id AS CHAR), ''),
           'brand', brand,
           'model', model,
          'quantity', quantity,
          'stockAdjusted', stock_adjusted
        )), JSON_ARRAY())
        FROM (
           SELECT non_asset_usage_id, employee_id, non_asset_type_id, inventory_brand_id,
                  inventory_model_id, brand, model, quantity, stock_adjusted
          FROM employee_non_asset_usage
          WHERE is_active = 1
          ORDER BY employee_id, non_asset_usage_id
        ) AS ordered_non_assets
        """,
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(computer_id AS CHAR),
          'deviceName', device_name,
          'orgId', COALESCE(CAST(org_unit_id AS CHAR), ''),
           'deviceType', device_type,
           'brand', COALESCE(brand, ''),
           'model', COALESCE(model, ''),
           'inventoryModelId', COALESCE(CAST(inventory_model_id AS CHAR), ''),
          'inventoryStockAdjusted', inventory_stock_adjusted,
           'cpu', COALESCE(cpu, ''),
          'memory', COALESCE(memory, ''),
          'storage', COALESCE(storage, ''),
          'gpu', COALESCE(gpu, ''),
          'fixedAssetCode', COALESCE(fixed_asset_code, ''),
          'purchaseDate', COALESCE(CAST(purchase_date AS CHAR), ''),
          'registeredDate', COALESCE(CAST(registered_date AS CHAR), ''),
          'snSt', COALESCE(sn_st, ''),
          'wifiMac', COALESCE(wifi_mac, ''),
          'ethernetMac', COALESCE(ethernet_mac, ''),
          'location', COALESCE(location, ''),
          'department', COALESCE(department, ''),
          'status', it_asset_status,
          'remarks', COALESCE(remarks, ''),
          'userId', CASE WHEN active_employee_id IS NULL THEN NULL ELSE CAST(active_employee_id AS CHAR) END,
          'assignmentEmployeeId', CASE WHEN active_employee_id IS NULL THEN NULL ELSE CAST(active_employee_id AS CHAR) END,
          'assignmentEmployeeStatus', COALESCE(active_employee_status, '')
        )), JSON_ARRAY())
        FROM (
          SELECT
            ca.*, 
            ass.employee_id AS active_employee_id,
            emp.employment_status AS active_employee_status
          FROM computer_asset ca
          LEFT JOIN computer_assignment ass
            ON ass.computer_id = ca.computer_id
           AND ass.returned_at IS NULL
           AND ass.assignment_status = 'active'
          LEFT JOIN employee emp
            ON emp.employee_id = ass.employee_id
           AND emp.is_active = 1
           AND emp.employment_status <> 'left'
          WHERE ca.is_active = 1
            AND ca.is_archived = 0
          ORDER BY ca.device_name, ca.computer_id
        ) AS ordered_computers
        """,
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(archive_id AS CHAR),
          'sourceEmployeeId', COALESCE(source_employee_ref, ''),
          'employeeNo', COALESCE(employee_no, ''),
          'name', COALESCE(employee_name, ''),
          'orgId', COALESCE(CAST(org_unit_id AS CHAR), ''),
          'orgPath', COALESCE(org_path, ''),
          'department', COALESCE(department, ''),
          'position', COALESCE(position_name, ''),
          'email', COALESCE(email, ''),
          'mobile', COALESCE(mobile, ''),
          'leaveDate', COALESCE(CAST(leave_date AS CHAR), ''),
          'leaveInfo', COALESCE(leave_info, ''),
          'leaveRemark', COALESCE(leave_remark, ''),
          'archivedAt', DATE_FORMAT(archived_at, '%Y-%m-%d %H:%i:%s'),
          'devices', COALESCE(device_snapshot, JSON_ARRAY())
        )), JSON_ARRAY())
        FROM (
          SELECT archive_id, source_employee_ref, employee_no, employee_name, org_unit_id,
                 org_path, department, position_name, email, mobile,
                 leave_date, leave_info, leave_remark, archived_at, device_snapshot
          FROM left_employee_archive
          ORDER BY archived_at DESC, archive_id DESC
        ) AS ordered_left_employees
        """,
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(movement_log_id AS CHAR),
          'direction', movement_direction,
          'typeName', COALESCE(type_name, ''),
          'brandName', COALESCE(brand_name, ''),
          'modelName', COALESCE(model_name, ''),
           'quantity', quantity,
          'sourceLabel', COALESCE(source_label, ''),
          'sourceWarehouseId', COALESCE(CAST(source_warehouse_id AS CHAR), ''),
          'targetLabel', COALESCE(target_label, ''),
          'targetWarehouseId', COALESCE(CAST(target_warehouse_id AS CHAR), ''),
           'note', COALESCE(effective_note, ''),
           'originalNote', COALESCE(original_note, ''),
           'effectiveNote', COALESCE(effective_note, ''),
           'noteCorrections', COALESCE(note_corrections, JSON_ARRAY()),
          'relatedEmployeeNo', COALESCE(related_employee_no, ''),
          'relatedEmployeeName', COALESCE(related_employee_name, ''),
          'triggerAction', COALESCE(trigger_action, 'manual'),
          'occurredAt', DATE_FORMAT(occurred_at, '%Y-%m-%d %H:%i:%s')
        )), JSON_ARRAY())
        FROM (
          SELECT
            movement.movement_log_id,
            movement.movement_direction,
            movement.type_name,
            movement.brand_name,
            movement.model_name,
            movement.quantity,
            movement.source_label,
            movement.source_warehouse_id,
            movement.target_label,
            movement.target_warehouse_id,
            COALESCE(movement.note, '') AS original_note,
            COALESCE((
              SELECT correction.corrected_note
              FROM inventory_movement_note_correction correction
              WHERE correction.movement_log_id = movement.movement_log_id
              ORDER BY correction.created_at DESC, correction.correction_id DESC
              LIMIT 1
            ), movement.note, '') AS effective_note,
            (
              SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                'id', CAST(correction.correction_id AS CHAR),
                'correctedNote', correction.corrected_note,
                'correctionReason', correction.correction_reason,
                'createdBy', COALESCE(correction_user.display_name, correction_user.username, ''),
                'createdAt', DATE_FORMAT(correction.created_at, '%Y-%m-%d %H:%i:%s')
              )), JSON_ARRAY())
              FROM inventory_movement_note_correction correction
              LEFT JOIN user_account correction_user
                ON correction_user.user_id = correction.created_by
              WHERE correction.movement_log_id = movement.movement_log_id
            ) AS note_corrections,
            movement.related_employee_no,
            movement.related_employee_name,
            movement.trigger_action,
            movement.occurred_at
          FROM inventory_movement_log movement
          ORDER BY movement.occurred_at DESC, movement.movement_log_id DESC
        ) AS ordered_inventory_movement_logs
        """,
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(purchase_log_id AS CHAR),
          'typeName', COALESCE(type_name, ''),
          'brandName', COALESCE(brand_name, ''),
          'modelName', COALESCE(model_name, ''),
          'typeId', COALESCE(CAST(non_asset_type_id AS CHAR), ''),
          'brandId', COALESCE(CAST(brand_id AS CHAR), ''),
          'modelId', COALESCE(CAST(model_id AS CHAR), ''),
          'warehouseId', COALESCE(CAST(warehouse_id AS CHAR), ''),
          'quantity', quantity,
          'inboundDate', COALESCE(CAST(inbound_date AS CHAR), ''),
          'cpu', COALESCE(cpu, ''),
          'memory', COALESCE(memory, ''),
          'storage', COALESCE(storage, ''),
          'gpu', COALESCE(gpu, ''),
          'sourceLabel', COALESCE(source_label, ''),
          'note', COALESCE(note, ''),
          'sourceMovementLogId', COALESCE(CAST(source_movement_log_id AS CHAR), ''),
          'createdAt', DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s')
        )), JSON_ARRAY())
        FROM (
           SELECT purchase_log_id, type_name, brand_name, model_name, non_asset_type_id,
                  brand_id, model_id, warehouse_id, quantity, inbound_date, cpu, memory, storage, gpu, source_label, note,
                 source_movement_log_id, created_at
          FROM inventory_purchase_log
          WHERE is_active = 1
          ORDER BY inbound_date DESC, purchase_log_id DESC
        ) AS ordered_inventory_purchase_logs
        """,
        f"""
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', CAST(audit_log_id AS CHAR),
          'actionType', action_type,
          'entityType', entity_type,
          'entityId', COALESCE(entity_id, ''),
          'entityName', COALESCE(entity_name, ''),
          'employeeId', COALESCE(employee_id, ''),
          'employeeName', COALESCE(employee_name, ''),
          'deviceName', COALESCE(device_name, ''),
          'oldValue', old_value,
          'newValue', new_value,
          'summary', summary,
          'actor', actor,
          'source', source,
          'createdAt', DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s')
        )), JSON_ARRAY())
        FROM (
          SELECT audit_log_id, action_type, entity_type, entity_id, entity_name,
                 employee_id, employee_name, device_name, old_value, new_value,
                 summary, actor, source, created_at
          FROM audit_log
          ORDER BY created_at DESC, audit_log_id DESC
          LIMIT {AUDIT_LOG_LIMIT}
        ) AS ordered_audit_logs
        """,
    ]
    (
        state_revision,
        orgs,
        types,
        inventory_brands,
        inventory_models,
        warehouses,
        warehouse_stocks,
        employees,
        monitors,
        non_asset_items,
        computers,
        left_employees,
        inventory_movement_logs,
        inventory_purchase_logs,
        audit_logs,
    ) = run_mysql_json_queries(*queries)

    org_rows = [
        {
            "id": str(org["id"]),
            "code": org.get("code") or "",
            "name": org.get("name") or "",
            "parentId": str(org.get("parentId") or ""),
            "sortOrder": sql_int(org.get("sortOrder"), 1000),
        }
        for org in orgs
    ]
    orgs_by_id = {org["id"]: org for org in org_rows}

    type_rows = [
        {
            "id": str(item["id"]),
            "code": item.get("code") or "",
            "name": item.get("name") or "",
            "unit": item.get("unit") or "件",
        }
        for item in types
    ]
    type_names = {item["id"]: item["name"] for item in type_rows}
    inventory_brand_rows = [
        {
            "id": str(item["id"]),
            "typeId": str(item.get("typeId") or ""),
            "name": item.get("name") or "",
            "sortOrder": sql_int(item.get("sortOrder"), 1000),
        }
        for item in inventory_brands
    ]
    inventory_model_rows = [
        {
            "id": str(item["id"]),
            "typeId": str(item.get("typeId") or ""),
            "brandId": str(item.get("brandId") or ""),
            "name": item.get("name") or "",
            "batchKey": item.get("batchKey") or "",
            "quantity": max(0, sql_int(item.get("quantity"), 0)),
            "inboundDate": item.get("inboundDate") or "",
            "cpu": item.get("cpu") or "",
            "memory": item.get("memory") or "",
            "storage": item.get("storage") or "",
            "gpu": item.get("gpu") or "",
            "sortOrder": sql_int(item.get("sortOrder"), 1000),
        }
        for item in inventory_models
    ]
    warehouse_rows = [
        {
            "id": str(item.get("id") or ""),
            "code": item.get("code") or "",
            "name": item.get("name") or "",
            "orgId": str(item.get("orgId") or ""),
            "managerEmployeeId": str(item.get("managerEmployeeId") or ""),
            "managerName": item.get("managerName") or "",
            "contactPhone": item.get("contactPhone") or "",
            "address": item.get("address") or "",
            "isActive": bool(sql_int(item.get("isActive"), 0)),
            "remarks": item.get("remarks") or "",
        }
        for item in warehouses
        if str(item.get("id") or "")
    ]
    warehouse_ids = {item["id"] for item in warehouse_rows}
    warehouse_stock_rows = [
        {
            "warehouseId": str(item.get("warehouseId") or ""),
            "modelId": str(item.get("modelId") or ""),
            "quantity": max(0, sql_int(item.get("quantity"), 0)),
        }
        for item in warehouse_stocks
        if str(item.get("warehouseId") or "") in warehouse_ids
    ]
    inventory_brand_by_type_name = {
        (item["typeId"], item["name"]): item["id"] for item in inventory_brand_rows
    }
    inventory_model_by_brand_name = {
        (item["brandId"], item["name"]): item["id"] for item in inventory_model_rows
    }

    employees_by_id: dict[str, dict] = {}
    for employee in employees:
        employee_id = str(employee["id"])
        employees_by_id[employee_id] = {
            "id": employee_id,
            "employeeNo": employee.get("employeeNo") or "",
            "name": employee.get("name") or "",
            "orgId": str(employee.get("orgId") or ""),
            "department": employee.get("department") or "",
            "position": employee.get("position") or "",
            "email": employee.get("email") or "",
            "mobile": employee.get("mobile") or "",
            "status": employee.get("status") or "active",
            "monitors": [],
            "nonAssetItems": [],
        }

    for monitor in monitors:
        employee = employees_by_id.get(str(monitor.get("employeeId") or ""))
        if not employee:
            continue
        employee["monitors"].append(
            {
                "id": str(monitor["id"]),
                "typeId": str(monitor.get("typeId") or ""),
                "brand": monitor.get("brand") or "",
                "model": monitor.get("model") or "",
                "inventoryBrandId": str(monitor.get("brandId") or "") or inventory_brand_by_type_name.get(
                    (str(monitor.get("typeId") or ""), monitor.get("brand") or ""),
                    "",
                ),
                "inventoryModelId": str(monitor.get("modelId") or "") or inventory_model_by_brand_name.get(
                    (
                        inventory_brand_by_type_name.get(
                            (str(monitor.get("typeId") or ""), monitor.get("brand") or ""),
                            "",
                        ),
                        monitor.get("model") or "",
                    ),
                    "",
                ),
                "stockAdjusted": bool(sql_int(monitor.get("stockAdjusted"), 0)),
            }
        )

    for item in non_asset_items:
        employee = employees_by_id.get(str(item.get("employeeId") or ""))
        if not employee:
            continue
        employee["nonAssetItems"].append(
            {
                "id": str(item["id"]),
                "typeId": str(item["typeId"]),
                "brand": item.get("brand") or "",
                "model": item.get("model") or "",
                "quantity": sql_int(item.get("quantity"), 1),
                "inventoryBrandId": str(item.get("brandId") or "") or inventory_brand_by_type_name.get(
                    (str(item.get("typeId") or ""), item.get("brand") or ""),
                    "",
                ),
                "inventoryModelId": str(item.get("modelId") or "") or inventory_model_by_brand_name.get(
                    (
                        inventory_brand_by_type_name.get(
                            (str(item.get("typeId") or ""), item.get("brand") or ""),
                            "",
                        ),
                        item.get("model") or "",
                    ),
                    "",
                ),
                "stockAdjusted": bool(sql_int(item.get("stockAdjusted"), 0)),
            }
        )

    archived_records = normalize_left_employees(left_employees)
    archived_keys = {
        left_employee_source_key(item)
        for item in archived_records
        if left_employee_source_key(item)
    }
    active_employees: list[dict] = []
    for employee in employees_by_id.values():
        if text_value(employee.get("status")) == "left":
            legacy_record = legacy_left_employee_record(employee, computers, type_names, orgs_by_id)
            legacy_key = left_employee_source_key(legacy_record)
            if legacy_key and legacy_key not in archived_keys:
                archived_records.append(legacy_record)
                archived_keys.add(legacy_key)
            continue
        active_employees.append(employee)

    active_employee_ids = {employee["id"] for employee in active_employees}
    computer_rows = normalize_computers(computers, active_employee_ids)

    return {
        "stateRevision": max(0, sql_int(state_revision, 0)),
        "orgs": org_rows,
        "nonAssetTypes": type_rows,
        "inventoryBrands": inventory_brand_rows,
        "inventoryModels": inventory_model_rows,
        "warehouses": warehouse_rows,
        "warehouseStocks": warehouse_stock_rows,
        "inventoryMovementLogs": normalize_inventory_movement_logs(inventory_movement_logs),
        "inventoryPurchaseLogs": normalize_inventory_purchase_logs(inventory_purchase_logs),
        "employees": active_employees,
        "leftEmployees": archived_records,
        "computers": computer_rows,
        "auditLogs": [serialize_audit_log(item) for item in audit_logs],
    }


def permission_map(context: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in PERMISSIONS.permissions(context):
        if text_value(item.get("actionCode")) == "view":
            result[text_value(item.get("moduleCode"))] = item
    return result


def scoped_org_ids_for_state(context: dict) -> set[str]:
    user_id = sql_int(context.get("id"), 0)
    if user_id <= 0:
        return set()
    scopes = json_query_one(
        f"""
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'orgId', org_unit_id,
          'includeDescendants', include_descendants
        )), JSON_ARRAY())
        FROM user_org_scope
        WHERE user_id = {user_id}
        """,
        [],
    )
    if not scopes:
        return set()
    org_rows = json_query_one(
        """
        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
          'id', org_unit_id,
          'parentId', COALESCE(parent_org_unit_id, 0)
        )), JSON_ARRAY())
        FROM org_unit
        WHERE is_active = 1
        """,
        [],
    )
    children: dict[int, list[int]] = {}
    for row in org_rows or []:
        children.setdefault(sql_int(row.get("parentId"), 0), []).append(sql_int(row.get("id"), 0))
    allowed: set[str] = set()
    for scope in scopes or []:
        root = sql_int(scope.get("orgId"), 0)
        if root <= 0:
            continue
        allowed.add(str(root))
        if not bool(scope.get("includeDescendants")):
            continue
        pending = list(children.get(root, []))
        while pending:
            current = pending.pop()
            if str(current) in allowed:
                continue
            allowed.add(str(current))
            pending.extend(children.get(current, []))
    return allowed


def filter_state_payload(payload: dict, context: dict) -> dict:
    result = dict(payload)
    permissions = permission_map(context)

    def can_view(module_code: str) -> bool:
        return bool((permissions.get(module_code) or {}).get("canView"))

    def scope_for(module_code: str) -> str:
        return text_value((permissions.get(module_code) or {}).get("dataScope")) or "none"

    restricted_modules = {
        module_code
        for module_code in ("it_assets", "employees", "organizations", "warehouse_management")
        if scope_for(module_code) in {"organization", "own"}
    }
    allowed_orgs = scoped_org_ids_for_state(context) if restricted_modules else set()

    def filter_org_records(records: list[dict], module_code: str) -> list[dict]:
        scope = scope_for(module_code)
        if scope == "all":
            return records
        if scope == "organization":
            return [item for item in records if text_value(item.get("orgId")) in allowed_orgs]
        if scope == "own":
            employee_id = text_value((context.get("employee") or {}).get("employeeId"))
            if not employee_id:
                return []
            if module_code == "it_assets":
                return [item for item in records if text_value(item.get("userId")) == employee_id]
            if module_code == "employees":
                return [item for item in records if text_value(item.get("id")) == employee_id]
        # Assets have no submitter or assignee field, and unbound accounts must
        # not receive records through a permissive fallback.
        return []

    if can_view("organizations"):
        org_scope = scope_for("organizations")
        if org_scope == "organization":
            result["orgs"] = [
                item for item in result.get("orgs") or [] if text_value(item.get("id")) in allowed_orgs
            ]
        elif org_scope == "own":
            result["orgs"] = []
    else:
        result["orgs"] = []

    if can_view("employees"):
        result["employees"] = filter_org_records(list(result.get("employees") or []), "employees")
        result["leftEmployees"] = filter_org_records(
            list(result.get("leftEmployees") or []), "employees"
        )
    else:
        result["employees"] = []
        result["leftEmployees"] = []

    if can_view("it_assets"):
        result["computers"] = filter_org_records(list(result.get("computers") or []), "it_assets")
    else:
        result["computers"] = []

    visible_warehouse_ids: set[str] = set()
    if can_view("warehouse_management"):
        warehouse_scope = scope_for("warehouse_management")
        warehouses = list(result.get("warehouses") or [])
        if warehouse_scope == "all":
            visible_warehouses = warehouses
        elif warehouse_scope == "organization":
            visible_warehouses = [
                item for item in warehouses if text_value(item.get("orgId")) in allowed_orgs
            ]
        elif warehouse_scope == "own":
            employee_id = text_value((context.get("employee") or {}).get("employeeId"))
            visible_warehouses = [
                item
                for item in warehouses
                if employee_id and text_value(item.get("managerEmployeeId")) == employee_id
            ]
        else:
            visible_warehouses = []
        visible_warehouse_ids = {
            text_value(item.get("id")) for item in visible_warehouses if text_value(item.get("id"))
        }
        result["warehouses"] = visible_warehouses
        result["warehouseStocks"] = [
            item
            for item in result.get("warehouseStocks") or []
            if text_value(item.get("warehouseId")) in visible_warehouse_ids
        ]
    else:
        result["warehouses"] = []
        result["warehouseStocks"] = []

    can_view_inventory_catalog = can_view("inventory_catalog")
    can_view_inventory_operations = can_view("inventory_operations")
    can_view_warehouses = can_view("warehouse_management")
    if not (can_view_inventory_catalog or can_view_inventory_operations or can_view_warehouses):
        result["nonAssetTypes"] = []
        result["inventoryBrands"] = []
        result["inventoryModels"] = []
    elif can_view_warehouses:
        visible_quantities: dict[str, int] = {}
        for stock in result.get("warehouseStocks") or []:
            model_id = text_value(stock.get("modelId"))
            if model_id:
                visible_quantities[model_id] = visible_quantities.get(model_id, 0) + max(
                    0, sql_int(stock.get("quantity"), 0)
                )
        result["inventoryModels"] = [
            {
                **item,
                # The catalog quantity represents the caller's visible warehouse
                # stock, never an unfiltered system-wide total.
                "quantity": visible_quantities.get(text_value(item.get("id")), 0),
            }
            for item in result.get("inventoryModels") or []
        ]
    else:
        # Catalog-only access may inspect type and model definitions but must
        # not reveal stock quantities from warehouses outside its permissions.
        result["inventoryModels"] = [
            {**item, "quantity": 0} for item in result.get("inventoryModels") or []
        ]

    if not (can_view_inventory_operations and can_view_warehouses):
        result["inventoryMovementLogs"] = []
        result["inventoryPurchaseLogs"] = []
    elif scope_for("warehouse_management") != "all":
        result["inventoryMovementLogs"] = [
            item
            for item in result.get("inventoryMovementLogs") or []
            if text_value(item.get("sourceWarehouseId")) in visible_warehouse_ids
            or text_value(item.get("targetWarehouseId")) in visible_warehouse_ids
        ]
        result["inventoryPurchaseLogs"] = [
            item
            for item in result.get("inventoryPurchaseLogs") or []
            if text_value(item.get("warehouseId")) in visible_warehouse_ids
        ]
    if not can_view("audit_logs"):
        result["auditLogs"] = []
    return result


def build_sync_sql(
    payload: dict,
    audit_entries: list[dict] | None = None,
    id_starts: dict[str, int] | None = None,
) -> str:
    validate_state_payload(payload)
    data = normalize_payload(payload)
    id_starts = id_starts or {}
    orgs = sort_orgs_for_insert(data["orgs"])
    non_asset_types = list(data["nonAssetTypes"])
    inventory_brands = list(data["inventoryBrands"])
    inventory_models = list(data["inventoryModels"])
    inventory_movement_logs = list(data["inventoryMovementLogs"])
    inventory_purchase_logs = list(data["inventoryPurchaseLogs"])
    employees = list(data["employees"])
    left_employees = list(data["leftEmployees"])
    computers = list(data["computers"])

    org_id_map = allocate_ids(orgs, start_id=id_starts.get("orgs", 0))
    type_id_map = allocate_ids(non_asset_types, start_id=id_starts.get("types", 0))
    inventory_brand_id_map = allocate_ids(
        inventory_brands,
        start_id=id_starts.get("brands", 0),
    )
    inventory_model_id_map = allocate_ids(
        inventory_models,
        start_id=id_starts.get("models", 0),
    )
    inventory_movement_log_id_map = allocate_ids(
        inventory_movement_logs,
        start_id=id_starts.get("inventoryMovementLogs", 0),
    )
    inventory_purchase_log_id_map = allocate_ids(
        inventory_purchase_logs,
        start_id=id_starts.get("inventoryPurchaseLogs", 0),
    )
    employee_id_map = allocate_ids(employees, start_id=id_starts.get("employees", 0))
    left_employee_id_map = allocate_ids(
        left_employees,
        start_id=id_starts.get("leftEmployees", 0),
    )
    computer_id_map = allocate_ids(
        computers,
        start_id=id_starts.get("computers", 0),
    )

    monitor_records: list[dict] = []
    non_asset_records: list[dict] = []
    for employee in employees:
        employee_key = str(employee.get("id") or "")
        for monitor in employee.get("monitors") or []:
            monitor_records.append(
                {
                    "id": monitor.get("id"),
                    "employeeId": employee_key,
                    "typeId": monitor.get("typeId"),
                    "inventoryBrandId": monitor.get("inventoryBrandId"),
                    "inventoryModelId": monitor.get("inventoryModelId"),
                    "brand": monitor.get("brand") or "",
                    "model": monitor.get("model") or "",
                    "stockAdjusted": bool(monitor.get("stockAdjusted")),
                }
            )
        for item in employee.get("nonAssetItems") or []:
            non_asset_records.append(
                {
                    "id": item.get("id"),
                    "employeeId": employee_key,
                    "typeId": item.get("typeId"),
                    "inventoryBrandId": item.get("inventoryBrandId"),
                    "inventoryModelId": item.get("inventoryModelId"),
                    "brand": item.get("brand") or "",
                    "model": item.get("model") or "",
                    "quantity": sql_int(item.get("quantity"), 1),
                    "stockAdjusted": bool(item.get("stockAdjusted")),
                }
            )

    monitor_id_map = allocate_ids(
        monitor_records,
        start_id=id_starts.get("monitors", 0),
    )
    non_asset_id_map = allocate_ids(
        non_asset_records,
        start_id=id_starts.get("nonAssetItems", 0),
    )

    lines = [
        "SET NAMES utf8mb4;",
        "START TRANSACTION;",
        "UPDATE org_unit SET is_active = 0;",
        "UPDATE non_asset_type SET is_active = 0;",
        "UPDATE it_inventory_brand SET is_active = 0;",
        "UPDATE it_inventory_model SET is_active = 0;",
        "UPDATE inventory_purchase_log SET is_active = 0;",
        "UPDATE employee SET is_active = 0;",
        "UPDATE computer_asset SET is_active = 0;",
        "UPDATE employee_monitor_usage SET is_active = 0;",
        "UPDATE employee_non_asset_usage SET is_active = 0;",
        """
        INSERT IGNORE INTO computer_assignment_history
          (computer_id, device_name, employee_id, employee_no, employee_name,
           assigned_at, returned_at, assignment_status, notes)
        SELECT ass.computer_id, ca.device_name, ass.employee_id, e.employee_no,
               e.employee_name, ass.assigned_at, ass.returned_at,
               ass.assignment_status, ass.notes
        FROM computer_assignment ass
        JOIN computer_asset ca ON ca.computer_id = ass.computer_id
        JOIN employee e ON e.employee_id = ass.employee_id;
        """.strip(),
    ]

    if orgs:
        values = []
        for org in orgs:
            org_id = org_id_map[str(org.get("id") or "")]
            parent_key = str(org.get("parentId") or "")
            parent_id = "NULL" if not parent_key else str(org_id_map[parent_key])
            values.append(
                "("
                f"{org_id}, "
                f"{sql_quote(org.get('code') or '')}, "
                f"{sql_quote(org.get('name') or '')}, "
                f"{parent_id}, "
                f"{sql_int(org.get('sortOrder'), 1000)}, "
                "1)"
            )
        lines.append(
            "INSERT INTO org_unit (org_unit_id, org_code, org_name, parent_org_unit_id, sort_order, is_active)\nVALUES\n  "
            + ",\n  ".join(values)
            + "\nON DUPLICATE KEY UPDATE "
            "org_code = VALUES(org_code), "
            "org_name = VALUES(org_name), "
            "parent_org_unit_id = VALUES(parent_org_unit_id), "
            "sort_order = VALUES(sort_order), "
            "is_active = 1;"
        )

    if non_asset_types:
        values = []
        for item in non_asset_types:
            type_id = type_id_map[str(item.get("id") or "")]
            values.append(
                "("
                f"{type_id}, "
                f"{sql_quote(item.get('code') or '')}, "
                f"{sql_quote(item.get('name') or '')}, "
                f"{sql_quote(item.get('unit') or '件')}, "
                "1)"
            )
        lines.append(
            "INSERT INTO non_asset_type (non_asset_type_id, type_code, type_name, unit_name, is_active)\nVALUES\n  "
            + ",\n  ".join(values)
            + "\nON DUPLICATE KEY UPDATE "
            "type_code = VALUES(type_code), "
            "type_name = VALUES(type_name), "
            "unit_name = VALUES(unit_name), "
            "is_active = 1;"
        )

    if inventory_brands:
        values = []
        for item in inventory_brands:
            brand_id = inventory_brand_id_map[str(item.get("id") or "")]
            type_key = str(item.get("typeId") or "")
            if type_key not in type_id_map:
                continue
            values.append(
                "("
                f"{brand_id}, "
                f"{type_id_map[type_key]}, "
                f"{sql_quote(item.get('name') or '')}, "
                f"{max(0, sql_int(item.get('sortOrder'), 1000))}, 1)"
            )
        if values:
            lines.append(
                "INSERT INTO it_inventory_brand (brand_id, non_asset_type_id, brand_name, sort_order, is_active)\nVALUES\n  "
                + ",\n  ".join(values)
                + "\nON DUPLICATE KEY UPDATE "
                "non_asset_type_id = VALUES(non_asset_type_id), "
                "brand_name = VALUES(brand_name), "
                "sort_order = VALUES(sort_order), "
                "is_active = 1;"
            )

    if inventory_models:
        values = []
        for item in inventory_models:
            model_id = inventory_model_id_map[str(item.get("id") or "")]
            type_key = str(item.get("typeId") or "")
            brand_key = str(item.get("brandId") or "")
            if type_key not in type_id_map or brand_key not in inventory_brand_id_map:
                continue
            values.append(
                "("
                f"{model_id}, "
                f"{type_id_map[type_key]}, "
                f"{inventory_brand_id_map[brand_key]}, "
                f"{sql_quote(item.get('name') or '')}, "
                f"{sql_quote(item.get('batchKey') or '')}, "
                f"{max(0, sql_int(item.get('quantity'), 0))}, "
                f"{sql_nullable_text(item.get('inboundDate'))}, "
                f"{sql_nullable_text(item.get('cpu'))}, "
                f"{sql_nullable_text(item.get('memory'))}, "
                f"{sql_nullable_text(item.get('storage'))}, "
                f"{sql_nullable_text(item.get('gpu'))}, "
                f"{max(0, sql_int(item.get('sortOrder'), 1000))}, 1)"
            )
        if values:
            lines.append(
                "INSERT INTO it_inventory_model (model_id, non_asset_type_id, brand_id, model_name, batch_key, quantity, inbound_date, cpu, memory, storage, gpu, sort_order, is_active)\nVALUES\n  "
                + ",\n  ".join(values)
                + "\nON DUPLICATE KEY UPDATE "
                "non_asset_type_id = VALUES(non_asset_type_id), "
                "brand_id = VALUES(brand_id), "
                "model_name = VALUES(model_name), "
                "batch_key = VALUES(batch_key), "
                "quantity = VALUES(quantity), "
                "inbound_date = VALUES(inbound_date), "
                "cpu = VALUES(cpu), "
                "memory = VALUES(memory), "
                "storage = VALUES(storage), "
                "gpu = VALUES(gpu), "
                "sort_order = VALUES(sort_order), "
                "is_active = 1;"
            )

    if employees:
        values = []
        for employee in employees:
            employee_id = employee_id_map[str(employee.get("id") or "")]
            org_key = str(employee.get("orgId") or "")
            org_id = "NULL" if not org_key else str(org_id_map[org_key])
            values.append(
                "("
                f"{employee_id}, "
                f"{sql_quote(employee.get('employeeNo') or '')}, "
                f"{sql_quote(employee.get('name') or '')}, "
                f"{org_id}, "
                f"{sql_quote(employee.get('department') or '')}, "
                f"{sql_quote(employee.get('position') or '')}, "
                f"{sql_quote(employee.get('email') or '')}, "
                f"{sql_quote(employee.get('mobile') or '')}, "
                f"{sql_quote(employee.get('status') or 'active')}, 1)"
            )
        lines.append(
            "INSERT INTO employee (employee_id, employee_no, employee_name, org_unit_id, department, position_name, email, mobile, employment_status, is_active)\nVALUES\n  "
            + ",\n  ".join(values)
            + "\nON DUPLICATE KEY UPDATE "
            "employee_no = VALUES(employee_no), "
            "employee_name = VALUES(employee_name), "
            "org_unit_id = VALUES(org_unit_id), "
            "department = VALUES(department), "
            "position_name = VALUES(position_name), "
            "email = VALUES(email), "
            "mobile = VALUES(mobile), "
            "employment_status = VALUES(employment_status), "
            "is_active = 1;"
        )

    if left_employees:
        values = []
        for item in left_employees:
            archive_id = left_employee_id_map[str(item.get("id") or "")]
            org_key = str(item.get("orgId") or "")
            org_id = "NULL" if not org_key or org_key not in org_id_map else str(org_id_map[org_key])
            archived_at = text_value(item.get("archivedAt")).replace("T", " ")
            if len(archived_at) == 10:
                archived_at = f"{archived_at} 00:00:00"
            archived_at_sql = sql_quote(archived_at[:19]) if archived_at else "CURRENT_TIMESTAMP"
            values.append(
                "("
                f"{archive_id}, "
                f"{sql_nullable_text(item.get('sourceEmployeeId'))}, "
                f"{sql_quote(item.get('employeeNo') or '')}, "
                f"{sql_quote(item.get('name') or '')}, "
                f"{org_id}, "
                f"{sql_quote(item.get('orgPath') or '')}, "
                f"{sql_quote(item.get('department') or '')}, "
                f"{sql_quote(item.get('position') or '')}, "
                f"{sql_quote(item.get('email') or '')}, "
                f"{sql_quote(item.get('mobile') or '')}, "
                f"{sql_quote(item.get('leaveDate') or None)}, "
                f"{sql_quote(item.get('leaveInfo') or '')}, "
                f"{sql_quote(item.get('leaveRemark') or '')}, "
                f"{json_sql_value(item.get('devices') or [])}, "
                f"{archived_at_sql})"
            )
        lines.append(
            "INSERT INTO left_employee_archive (archive_id, source_employee_ref, employee_no, employee_name, org_unit_id, org_path, department, position_name, email, mobile, leave_date, leave_info, leave_remark, device_snapshot, archived_at)\nVALUES\n  "
            + ",\n  ".join(values)
            + "\nON DUPLICATE KEY UPDATE "
            "source_employee_ref = VALUES(source_employee_ref), "
            "employee_no = VALUES(employee_no), "
            "employee_name = VALUES(employee_name), "
            "org_unit_id = VALUES(org_unit_id), "
            "org_path = VALUES(org_path), "
            "department = VALUES(department), "
            "position_name = VALUES(position_name), "
            "email = VALUES(email), "
            "mobile = VALUES(mobile), "
            "leave_date = VALUES(leave_date), "
            "leave_info = VALUES(leave_info), "
            "leave_remark = VALUES(leave_remark), "
            "device_snapshot = VALUES(device_snapshot), "
            "archived_at = VALUES(archived_at);"
        )

    if computers:
        values = []
        for computer in computers:
            computer_id = computer_id_map[str(computer.get("id") or "")]
            org_key = str(computer.get("orgId") or "")
            org_id = "NULL" if not org_key else str(org_id_map[org_key])
            inventory_model_key = str(computer.get("inventoryModelId") or "")
            inventory_model_id_sql = (
                str(inventory_model_id_map[inventory_model_key])
                if inventory_model_key in inventory_model_id_map
                else "NULL"
            )
            values.append(
                "("
                f"{computer_id}, "
                f"{sql_quote(computer.get('deviceName') or '')}, "
                f"{org_id}, "
                 f"{sql_quote(computer.get('deviceType') or '')}, "
                 f"{sql_quote(computer.get('brand') or '')}, "
                 f"{sql_quote(computer.get('model') or '')}, "
                f"{inventory_model_id_sql}, "
                f"{1 if computer.get('inventoryStockAdjusted') else 0}, "
                 f"{sql_quote(computer.get('cpu') or '')}, "
                f"{sql_quote(computer.get('memory') or '')}, "
                f"{sql_quote(computer.get('storage') or '')}, "
                f"{sql_quote(computer.get('gpu') or '')}, "
                f"{sql_nullable_text(computer.get('fixedAssetCode'))}, "
                f"{sql_quote(computer.get('purchaseDate') or None)}, "
                f"{sql_quote(computer.get('registeredDate') or None)}, "
                f"{sql_nullable_text(computer.get('snSt'))}, "
                f"{sql_nullable_text(normalize_mac_address(computer.get('wifiMac')))}, "
                f"{sql_nullable_text(normalize_mac_address(computer.get('ethernetMac')))}, "
                f"{sql_quote(computer.get('location') or '')}, "
                f"{sql_quote(computer.get('department') or '')}, "
                "NULL, "
                f"{sql_quote(computer.get('status') or 'idle')}, "
                f"{sql_quote(computer.get('remarks') or '')}, 1)"
            )
        lines.append(
            "INSERT INTO computer_asset (computer_id, device_name, org_unit_id, device_type, brand, model, inventory_model_id, inventory_stock_adjusted, cpu, memory, storage, gpu, fixed_asset_code, purchase_date, registered_date, sn_st, wifi_mac, ethernet_mac, location, department, position_name, it_asset_status, remarks, is_active)\nVALUES\n  "
            + ",\n  ".join(values)
            + "\nON DUPLICATE KEY UPDATE "
            "device_name = VALUES(device_name), "
            "org_unit_id = VALUES(org_unit_id), "
             "device_type = VALUES(device_type), "
             "brand = VALUES(brand), "
             "model = VALUES(model), "
             "inventory_model_id = VALUES(inventory_model_id), "
             "inventory_stock_adjusted = VALUES(inventory_stock_adjusted), "
             "cpu = VALUES(cpu), "
            "memory = VALUES(memory), "
            "storage = VALUES(storage), "
            "gpu = VALUES(gpu), "
            "fixed_asset_code = VALUES(fixed_asset_code), "
            "purchase_date = VALUES(purchase_date), "
            "registered_date = VALUES(registered_date), "
            "sn_st = VALUES(sn_st), "
            "wifi_mac = VALUES(wifi_mac), "
            "ethernet_mac = VALUES(ethernet_mac), "
            "location = VALUES(location), "
            "department = VALUES(department), "
            "position_name = NULL, "
            "it_asset_status = VALUES(it_asset_status), "
            "remarks = VALUES(remarks), "
            "is_active = 1;"
        )

    lines.append(
        """
        UPDATE computer_assignment ass
        JOIN computer_asset ca ON ca.computer_id = ass.computer_id
        SET ass.returned_at = COALESCE(ass.returned_at, CURRENT_TIMESTAMP),
            ass.assignment_status = 'returned'
        WHERE ass.returned_at IS NULL
          AND ca.is_active = 0;
        """.strip()
    )
    for computer in computers:
        computer_id = computer_id_map[str(computer.get("id") or "")]
        user_key = str(computer.get("userId") or "")
        if user_key and user_key in employee_id_map:
            employee_id = employee_id_map[user_key]
            lines.append(
                f"UPDATE computer_assignment SET returned_at = CURRENT_TIMESTAMP, assignment_status = 'returned' "
                f"WHERE computer_id = {computer_id} AND returned_at IS NULL AND employee_id <> {employee_id};"
            )
            lines.append(
                f"INSERT INTO computer_assignment (computer_id, employee_id, assigned_at, returned_at, assignment_status, notes) "
                f"SELECT {computer_id}, {employee_id}, CURRENT_TIMESTAMP, NULL, 'active', NULL "
                f"WHERE NOT EXISTS (SELECT 1 FROM computer_assignment WHERE computer_id = {computer_id} AND returned_at IS NULL);"
            )
        else:
            lines.append(
                f"UPDATE computer_assignment SET returned_at = CURRENT_TIMESTAMP, assignment_status = 'returned' "
                f"WHERE computer_id = {computer_id} AND returned_at IS NULL;"
            )

    lines.extend(
        [
            """
            INSERT IGNORE INTO computer_assignment_history
              (computer_id, device_name, employee_id, employee_no, employee_name,
               assigned_at, returned_at, assignment_status, notes)
            SELECT ass.computer_id, ca.device_name, ass.employee_id, e.employee_no,
                   e.employee_name, ass.assigned_at, ass.returned_at,
                   ass.assignment_status, ass.notes
            FROM computer_assignment ass
            JOIN computer_asset ca ON ca.computer_id = ass.computer_id
            JOIN employee e ON e.employee_id = ass.employee_id;
            """.strip(),
            """
            UPDATE computer_assignment_history history
            LEFT JOIN computer_assignment active_assignment
              ON active_assignment.computer_id = history.computer_id
             AND active_assignment.employee_id = history.employee_id
             AND active_assignment.assigned_at = history.assigned_at
             AND active_assignment.returned_at IS NULL
            LEFT JOIN (
              SELECT computer_id, MAX(returned_at) AS latest_returned_at
              FROM computer_assignment
              WHERE returned_at IS NOT NULL
              GROUP BY computer_id
            ) returned_assignment
              ON returned_assignment.computer_id = history.computer_id
            SET history.returned_at = COALESCE(
                  history.returned_at,
                  returned_assignment.latest_returned_at,
                  CURRENT_TIMESTAMP
                ),
                history.assignment_status = 'returned'
            WHERE history.assignment_status = 'active'
              AND active_assignment.assignment_id IS NULL;
            """.strip(),
            """
            UPDATE computer_assignment_history history
            JOIN computer_assignment ass
              ON ass.computer_id = history.computer_id
             AND ass.employee_id = history.employee_id
             AND ass.assigned_at = history.assigned_at
            JOIN computer_asset ca ON ca.computer_id = ass.computer_id
            JOIN employee e ON e.employee_id = ass.employee_id
            SET history.device_name = ca.device_name,
                history.employee_no = e.employee_no,
                history.employee_name = e.employee_name,
                history.returned_at = ass.returned_at,
                history.assignment_status = ass.assignment_status,
                history.notes = ass.notes;
            """.strip(),
        ]
    )

    if monitor_records:
        values = []
        for monitor in monitor_records:
            monitor_id = monitor_id_map[str(monitor.get("id") or "")]
            employee_id = employee_id_map[str(monitor.get("employeeId") or "")]
            type_key = str(monitor.get("typeId") or "")
            type_id_sql = str(type_id_map[type_key]) if type_key in type_id_map else "NULL"
            brand_key = str(monitor.get("inventoryBrandId") or "")
            model_key = str(monitor.get("inventoryModelId") or "")
            brand_id_sql = (
                str(inventory_brand_id_map[brand_key])
                if brand_key in inventory_brand_id_map
                else "NULL"
            )
            model_id_sql = (
                str(inventory_model_id_map[model_key])
                if model_key in inventory_model_id_map
                else "NULL"
            )
            values.append(
                "("
                f"{monitor_id}, "
                 f"{employee_id}, "
                 f"{type_id_sql}, "
                 f"{brand_id_sql}, "
                 f"{model_id_sql}, "
                 f"{sql_quote(monitor.get('brand') or '')}, "
                f"{sql_quote(monitor.get('model') or '')}, "
                "1, "
                f"{1 if monitor.get('stockAdjusted') else 0}, "
                "NULL, "
                "NULL, 1)"
            )
        lines.append(
            "INSERT INTO employee_monitor_usage (monitor_usage_id, employee_id, non_asset_type_id, inventory_brand_id, inventory_model_id, display_name, model, quantity, stock_adjusted, last_counted_date, notes, is_active)\nVALUES\n  "
            + ",\n  ".join(values)
            + "\nON DUPLICATE KEY UPDATE "
             "employee_id = VALUES(employee_id), "
             "non_asset_type_id = VALUES(non_asset_type_id), "
             "inventory_brand_id = VALUES(inventory_brand_id), "
             "inventory_model_id = VALUES(inventory_model_id), "
             "display_name = VALUES(display_name), "
            "model = VALUES(model), "
            "quantity = VALUES(quantity), "
            "stock_adjusted = VALUES(stock_adjusted), "
            "is_active = 1;"
        )

    if non_asset_records:
        values = []
        for item in non_asset_records:
            usage_id = non_asset_id_map[str(item.get("id") or "")]
            employee_id = employee_id_map[str(item.get("employeeId") or "")]
            type_id = type_id_map[str(item.get("typeId") or "")]
            brand_key = str(item.get("inventoryBrandId") or "")
            model_key = str(item.get("inventoryModelId") or "")
            brand_id_sql = (
                str(inventory_brand_id_map[brand_key])
                if brand_key in inventory_brand_id_map
                else "NULL"
            )
            model_id_sql = (
                str(inventory_model_id_map[model_key])
                if model_key in inventory_model_id_map
                else "NULL"
            )
            values.append(
                "("
                f"{usage_id}, "
                 f"{employee_id}, "
                 f"{type_id}, "
                 f"{brand_id_sql}, "
                 f"{model_id_sql}, "
                 f"{sql_quote(item.get('brand') or '')}, "
                f"{sql_quote(item.get('model') or '')}, "
                f"{max(1, sql_int(item.get('quantity'), 1))}, "
                f"{1 if item.get('stockAdjusted') else 0}, "
                "NULL, "
                "NULL, 1)"
            )
        lines.append(
            "INSERT INTO employee_non_asset_usage (non_asset_usage_id, employee_id, non_asset_type_id, inventory_brand_id, inventory_model_id, brand, model, quantity, stock_adjusted, last_counted_date, notes, is_active)\nVALUES\n  "
            + ",\n  ".join(values)
            + "\nON DUPLICATE KEY UPDATE "
             "employee_id = VALUES(employee_id), "
             "non_asset_type_id = VALUES(non_asset_type_id), "
             "inventory_brand_id = VALUES(inventory_brand_id), "
             "inventory_model_id = VALUES(inventory_model_id), "
             "brand = VALUES(brand), "
            "model = VALUES(model), "
            "quantity = VALUES(quantity), "
            "stock_adjusted = VALUES(stock_adjusted), "
            "is_active = 1;"
        )

    if inventory_movement_logs:
        values = []
        for item in inventory_movement_logs:
            log_id = inventory_movement_log_id_map[str(item.get("id") or "")]
            occurred_at = text_value(item.get("occurredAt")).replace("T", " ")
            if len(occurred_at) == 10:
                occurred_at = f"{occurred_at} 00:00:00"
            occurred_at_sql = sql_quote(occurred_at[:19]) if occurred_at else "CURRENT_TIMESTAMP"
            values.append(
                "("
                f"{log_id}, "
                f"{sql_quote(item.get('direction') or 'increase')}, "
                f"{sql_quote(item.get('typeName') or '')}, "
                f"{sql_quote(item.get('brandName') or '')}, "
                f"{sql_quote(item.get('modelName') or '')}, "
                f"{max(1, sql_int(item.get('quantity'), 1))}, "
                f"{sql_quote(item.get('sourceLabel') or '')}, "
                f"{sql_quote(item.get('targetLabel') or '')}, "
                f"{sql_quote(item.get('note') or '')}, "
                f"{sql_quote(item.get('relatedEmployeeNo') or '')}, "
                f"{sql_quote(item.get('relatedEmployeeName') or '')}, "
                f"{sql_quote(item.get('triggerAction') or 'manual')}, "
                f"{occurred_at_sql})"
            )
        lines.append(
            "INSERT INTO inventory_movement_log (movement_log_id, movement_direction, type_name, brand_name, model_name, quantity, source_label, target_label, note, related_employee_no, related_employee_name, trigger_action, occurred_at)\nVALUES\n  "
            + ",\n  ".join(values)
            + "\nON DUPLICATE KEY UPDATE "
            "movement_direction = VALUES(movement_direction), "
            "type_name = VALUES(type_name), "
            "brand_name = VALUES(brand_name), "
            "model_name = VALUES(model_name), "
            "quantity = VALUES(quantity), "
            "source_label = VALUES(source_label), "
            "target_label = VALUES(target_label), "
            "note = VALUES(note), "
            "related_employee_no = VALUES(related_employee_no), "
            "related_employee_name = VALUES(related_employee_name), "
            "trigger_action = VALUES(trigger_action), "
            "occurred_at = VALUES(occurred_at);"
        )

    if inventory_purchase_logs:
        values = []
        for item in inventory_purchase_logs:
            purchase_id = inventory_purchase_log_id_map[str(item.get("id") or "")]
            type_key = str(item.get("typeId") or "")
            brand_key = str(item.get("brandId") or "")
            model_key = str(item.get("modelId") or "")
            purchase_type_id = str(type_id_map[type_key]) if type_key in type_id_map else "NULL"
            purchase_brand_id = (
                str(inventory_brand_id_map[brand_key])
                if brand_key in inventory_brand_id_map
                else "NULL"
            )
            purchase_model_id = (
                str(inventory_model_id_map[model_key])
                if model_key in inventory_model_id_map
                else "NULL"
            )
            source_movement_key = str(item.get("sourceMovementLogId") or "")
            source_movement_id = (
                str(inventory_movement_log_id_map[source_movement_key])
                if source_movement_key in inventory_movement_log_id_map
                else "NULL"
            )
            created_at = text_value(item.get("createdAt")).replace("T", " ")
            if len(created_at) == 10:
                created_at = f"{created_at} 00:00:00"
            created_at_sql = sql_quote(created_at[:19]) if created_at else "CURRENT_TIMESTAMP"
            values.append(
                "("
                f"{purchase_id}, "
                 f"{sql_quote(item.get('typeName') or '')}, "
                 f"{sql_quote(item.get('brandName') or '')}, "
                 f"{sql_quote(item.get('modelName') or '')}, "
                 f"{purchase_type_id}, "
                 f"{purchase_brand_id}, "
                 f"{purchase_model_id}, "
                 f"{max(1, sql_int(item.get('quantity'), 1))}, "
                f"{sql_nullable_text(item.get('inboundDate'))}, "
                f"{sql_nullable_text(item.get('cpu'))}, "
                f"{sql_nullable_text(item.get('memory'))}, "
                f"{sql_nullable_text(item.get('storage'))}, "
                f"{sql_nullable_text(item.get('gpu'))}, "
                f"{sql_quote(item.get('sourceLabel') or '')}, "
                f"{sql_quote(item.get('note') or '')}, "
                f"{source_movement_id}, "
                f"{created_at_sql})"
            )
        lines.append(
            "INSERT INTO inventory_purchase_log (purchase_log_id, type_name, brand_name, model_name, non_asset_type_id, brand_id, model_id, quantity, inbound_date, cpu, memory, storage, gpu, source_label, note, source_movement_log_id, created_at)\nVALUES\n  "
            + ",\n  ".join(values)
            + "\nON DUPLICATE KEY UPDATE "
             "type_name = VALUES(type_name), "
             "brand_name = VALUES(brand_name), "
             "model_name = VALUES(model_name), "
             "non_asset_type_id = VALUES(non_asset_type_id), "
             "brand_id = VALUES(brand_id), "
             "model_id = VALUES(model_id), "
             "quantity = VALUES(quantity), "
            "inbound_date = VALUES(inbound_date), "
            "cpu = VALUES(cpu), "
            "memory = VALUES(memory), "
            "storage = VALUES(storage), "
            "gpu = VALUES(gpu), "
            "source_label = VALUES(source_label), "
            "note = VALUES(note), "
            "source_movement_log_id = VALUES(source_movement_log_id), "
            "created_at = VALUES(created_at), "
            "is_active = 1;"
        )

    if audit_entries:
        values = []
        for entry in audit_entries:
            values.append(
                "("
                f"{sql_quote(entry.get('actionType') or '')}, "
                f"{sql_quote(entry.get('entityType') or '')}, "
                f"{sql_quote(entry.get('entityId') or '')}, "
                f"{sql_quote(entry.get('entityName') or '')}, "
                f"{sql_quote(entry.get('employeeId') or '')}, "
                f"{sql_quote(entry.get('employeeName') or '')}, "
                f"{sql_quote(entry.get('deviceName') or '')}, "
                f"{json_sql_value(entry.get('oldValue'))}, "
                f"{json_sql_value(entry.get('newValue'))}, "
                f"{sql_quote(entry.get('summary') or '')}, "
                f"{sql_quote(entry.get('actor') or 'web')}, "
                f"{sql_quote(entry.get('source') or 'web')})"
            )
        lines.append(
            "INSERT INTO audit_log (action_type, entity_type, entity_id, entity_name, employee_id, employee_name, device_name, old_value, new_value, summary, actor, source)\nVALUES\n  "
            + ",\n  ".join(values)
            + ";"
        )

    lines.append(
        "INSERT INTO app_state_revision (revision_id, revision) VALUES (1, 1) "
        "ON DUPLICATE KEY UPDATE revision = revision + 1;"
    )
    lines.append("COMMIT;")
    return "\n".join(lines)


def domain_execute(sql: str) -> str:
    return run_mysql(sql, database=DB_NAME)


DOMAIN_DB = SqlGateway(
    execute=domain_execute,
    query_json=json_query_one,
    quote=sql_quote,
    text=text_value,
    integer=sql_int,
)


PERMISSIONS = PermissionService(
    db=DOMAIN_DB,
    api_error=ApiError,
    forbidden_error=ForbiddenError,
)


def require_permission(context: dict, module_code: str, action_code: str) -> None:
    PERMISSIONS.require(context, module_code, action_code)


DOMAIN_ROUTER = DomainApiRouter(
    ApiDependencies(
        db=DOMAIN_DB,
        api_error=ApiError,
        conflict_error=ConflictError,
        forbidden_error=ForbiddenError,
        require_auth=require_auth,
        require_role=require_role,
        require_permission=require_permission,
        require_csrf=require_csrf,
    )
)


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} {format % args}")

    def send_json(
        self,
        payload: object,
        status: int = HTTPStatus.OK,
        headers: list[tuple[str, str]] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in headers or []:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, file_path: Path, download_name: str) -> None:
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", download_name) or "database-backup.sql.gz"
        file_size = file_path.stat().st_size
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/gzip")
        self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        self.send_header("Content-Length", str(file_size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            with file_path.open("rb") as source:
                shutil.copyfileobj(source, self.wfile, length=1024 * 1024)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def read_json(self, *, allow_empty: bool = False) -> dict:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except (TypeError, ValueError) as exc:
            raise ApiError("请求体长度无效。") from exc
        if content_length < 0:
            raise ApiError("请求体长度无效。")
        if content_length > MAX_REQUEST_BODY_BYTES:
            raise PayloadTooLargeError(
                f"请求体过大，最大允许 {MAX_REQUEST_BODY_BYTES // (1024 * 1024)} MB。"
            )
        if content_length == 0:
            if not allow_empty:
                raise ApiError("请求体不能为空。")
            return {}
        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"Invalid JSON body: {exc}")
            raise ApiError("请求体格式无效。") from exc
        if not isinstance(payload, dict):
            raise ApiError("请求体必须是 JSON 对象。")
        return payload

    def handle_api(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query, keep_blank_values=True)
        if DOMAIN_ROUTER.dispatch(self, parsed, params):
            return
        if parsed.path == "/api/health" and self.command == "GET":
            try:
                probe = sql_int(run_mysql("SELECT 1;", database=DB_NAME).strip(), 0)
                table_count = sql_int(
                    run_mysql(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        f"WHERE table_schema = {sql_quote(DB_NAME)} "
                        "AND table_name IN ("
                        "'org_unit', 'employee', 'computer_asset', 'computer_assignment', "
                        "'employee_monitor_usage', 'employee_non_asset_usage', "
                        "'non_asset_type', 'it_inventory_brand', 'it_inventory_model', "
                        "'inventory_movement_log', 'inventory_purchase_log', 'inventory_warehouse', "
                        "'inventory_warehouse_stock', 'inventory_transfer_log', 'computer_assignment_history', "
                        "'left_employee_archive', 'audit_log', 'app_state_revision', "
                        "'user_account', 'auth_session', 'system_setting', 'database_backup', "
                        "'schema_migration', 'user_org_scope', 'asset_relation', 'api_idempotency_key', "
                        "'inventory_allocation_history', 'asset_status_history', 'sync_source', 'sync_run', "
                        "'sync_staging_record', 'sync_entity_mapping', 'data_quality_issue', 'job_execution', "
                        "'itil_ticket', 'itil_ticket_history', 'auth_module', 'auth_role', "
                        "'auth_permission', 'auth_role_permission', 'auth_user_permission', "
                        "'service_form', 'service_form_field', 'service_ticket_extension', "
                        "'itil_change', 'itil_problem', 'knowledge_article', 'sla_policy', "
                        "'service_workflow', 'service_workflow_step', 'service_approval', "
                        "'service_approval_decision', 'service_notification', 'service_form_permission', "
                        "'scrap_reason', 'inventory_scrap_record', 'asset_scrap_record', "
                        "'asset_site', 'asset_rack', 'inspection_template', 'inspection_template_item', "
                        "'inspection_task', 'inspection_task_item', 'rack_device_placement'"
                        ");",
                        database=DB_NAME,
                    ).strip(),
                    0,
                )
                required_table_count = 64
                healthy = probe == 1 and table_count == required_table_count
                self.send_json(
                    {
                        "ok": healthy,
                        "databaseProbe": probe,
                        "requiredTables": table_count,
                        "requiredTableCount": required_table_count,
                    },
                    status=HTTPStatus.OK if healthy else HTTPStatus.SERVICE_UNAVAILABLE,
                )
            except ApiError as exc:
                print(f"Health check failed: {exc}")
                self.send_json(
                    {"ok": False, "error": "database_unavailable"},
                    status=HTTPStatus.SERVICE_UNAVAILABLE,
                )
            return

        if parsed.path == "/api/auth/bootstrap-status" and self.command == "GET":
            public_settings = settings_payload()
            self.send_json(
                {
                    "required": auth_user_count() == 0,
                    "settings": {
                        "app_name": public_settings.get("app_name", "办公资产管理系统"),
                        "login_notice": public_settings.get("login_notice", ""),
                    },
                }
            )
            return

        if parsed.path == "/api/auth/session" and self.command == "GET":
            context = current_auth_context(self)
            if not context:
                self.send_json({"authenticated": False}, status=HTTPStatus.UNAUTHORIZED)
                return
            self.send_json({"authenticated": True, "user": auth_user_public(context)})
            return

        if parsed.path == "/api/auth/bootstrap" and self.command == "POST":
            payload = self.read_json()
            username = validate_username(payload.get("username"))
            display_name = text_value(payload.get("displayName")) or username
            password = validate_password(payload.get("password"))
            confirm_password = validate_password(payload.get("confirmPassword"))
            if password != confirm_password:
                raise ApiError("两次输入的密码不一致。")
            stored_hash = password_hash(password)
            user = create_first_admin(username, display_name, stored_hash)
            session_token, csrf_token = create_auth_session(text_value(user.get("id")), self)
            write_auth_audit(username, "user_account_bootstrapped", text_value(user.get("id")), username, f"初始化管理员账号 {username}")
            self.send_json(
                {"authenticated": True, "user": auth_user_public(user)},
                headers=cookie_headers(session_token, csrf_token),
            )
            return

        if parsed.path == "/api/auth/login" and self.command == "POST":
            payload = self.read_json()
            username = validate_username(payload.get("username"))
            password = text_value(payload.get("password"))
            enforce_login_rate_limit(self, username)
            user = find_user_by_username(username)
            if not user or not bool(user.get("isActive", True)):
                raise UnauthorizedError("账号或密码错误。")
            if bool(user.get("locked")):
                raise UnauthorizedError("账号暂时锁定，请稍后再试。")
            if not verify_password(password, text_value(user.get("passwordHash"))):
                run_mysql(
                    f"""
                    UPDATE user_account
                    SET failed_attempts = failed_attempts + 1,
                        locked_until = CASE
                          WHEN failed_attempts + 1 >= 5 THEN DATE_ADD(NOW(), INTERVAL 15 MINUTE)
                          ELSE locked_until
                        END
                    WHERE user_id = {sql_quote(user.get("id"))};
                    """,
                    database=DB_NAME,
                )
                raise UnauthorizedError("账号或密码错误。")
            run_mysql(
                f"""
                UPDATE user_account
                SET failed_attempts = 0, locked_until = NULL, last_login_at = NOW()
                WHERE user_id = {sql_quote(user.get("id"))};
                """,
                database=DB_NAME,
            )
            clear_login_rate_limit(self, username)
            session_token, csrf_token = create_auth_session(text_value(user.get("id")), self)
            write_auth_audit(username, "user_login", text_value(user.get("id")), username, f"账号 {username} 登录系统")
            self.send_json(
                {"authenticated": True, "user": auth_user_public(user)},
                headers=cookie_headers(session_token, csrf_token),
            )
            return

        if parsed.path == "/api/auth/logout" and self.command == "POST":
            self.read_json(allow_empty=True)
            token = cookie_value(self, AUTH_COOKIE_NAME)
            if token:
                run_mysql(
                    f"""
                    UPDATE auth_session
                    SET revoked_at = NOW()
                    WHERE session_token_hash = {sql_quote(encode_token(token))}
                      AND revoked_at IS NULL;
                    """,
                    database=DB_NAME,
                )
            self.send_json({"authenticated": False}, headers=clear_auth_cookie_headers())
            return

        if parsed.path == "/api/auth/change-password" and self.command == "POST":
            context = require_auth(self)
            require_csrf(self, context)
            payload = self.read_json()
            current_password = text_value(payload.get("currentPassword"))
            new_password = validate_password(payload.get("newPassword"))
            confirm_password = validate_password(payload.get("confirmPassword"))
            user = find_user_by_id(text_value(context.get("id")))
            if not user or not verify_password(current_password, text_value(user.get("passwordHash"))):
                raise UnauthorizedError("当前密码不正确。")
            if new_password != confirm_password:
                raise ApiError("两次输入的新密码不一致。")
            stored_hash = password_hash(new_password)
            run_mysql(
                f"""
                UPDATE user_account
                SET password_hash = {sql_quote(stored_hash)}, failed_attempts = 0, locked_until = NULL
                WHERE user_id = {sql_quote(context.get("id"))};
                """,
                database=DB_NAME,
            )
            revoke_user_sessions(
                text_value(context.get("id")),
                except_session_token=cookie_value(self, AUTH_COOKIE_NAME),
            )
            write_auth_audit(text_value(context.get("username")), "user_password_changed", text_value(context.get("id")), text_value(context.get("username")), "账号修改了登录密码")
            self.send_json({"ok": True})
            return

        if parsed.path == "/api/auth/permissions" and self.command == "GET":
            context = require_auth(self)
            self.send_json(
                {
                    "isSuperAdmin": PERMISSIONS.is_super_admin(context),
                    "permissions": PERMISSIONS.permissions(context),
                }
            )
            return

        if parsed.path == "/api/access-control" and self.command == "GET":
            context = require_auth(self)
            require_permission(context, "role_management", "view")
            self.send_json(
                {
                    **PERMISSIONS.catalog(),
                    "roles": PERMISSIONS.list_roles(),
                    "users": list_users(),
                }
            )
            return

        if parsed.path == "/api/roles" and self.command == "POST":
            context = require_auth(self)
            require_permission(context, "role_management", "create")
            require_csrf(self, context)
            self.send_json({"role": PERMISSIONS.create_role(self.read_json(), context)}, status=HTTPStatus.CREATED)
            return

        role_match = re.fullmatch(r"/api/roles/(\d+)", parsed.path)
        if role_match and self.command == "PUT":
            context = require_auth(self)
            require_permission(context, "role_management", "update")
            require_csrf(self, context)
            self.send_json({"role": PERMISSIONS.update_role(role_match.group(1), self.read_json(), context)})
            return

        role_permission_match = re.fullmatch(r"/api/roles/(\d+)/permissions", parsed.path)
        if role_permission_match and self.command == "GET":
            context = require_auth(self)
            require_permission(context, "role_management", "view")
            self.send_json({"permissions": PERMISSIONS.role_permissions(role_permission_match.group(1))})
            return

        if role_permission_match and self.command == "PUT":
            context = require_auth(self)
            require_permission(context, "role_management", "update")
            require_csrf(self, context)
            entries = self.read_json().get("permissions")
            if not isinstance(entries, list):
                raise ApiError("permissions must be an array.")
            self.send_json(
                {
                    "permissions": PERMISSIONS.replace_role_permissions(
                        role_permission_match.group(1),
                        entries,
                        context,
                    )
                }
            )
            return

        user_permission_match = re.fullmatch(r"/api/users/(\d+)/permissions", parsed.path)
        if user_permission_match and self.command == "GET":
            context = require_auth(self)
            require_permission(context, "role_management", "view")
            self.send_json({"permissions": PERMISSIONS.user_permissions(user_permission_match.group(1))})
            return

        if user_permission_match and self.command == "PUT":
            context = require_auth(self)
            require_permission(context, "role_management", "update")
            require_csrf(self, context)
            entries = self.read_json().get("permissions")
            if not isinstance(entries, list):
                raise ApiError("permissions must be an array.")
            self.send_json(
                {
                    "permissions": PERMISSIONS.replace_user_permissions(
                        user_permission_match.group(1),
                        entries,
                        context,
                    )
                }
            )
            return

        if parsed.path == "/api/users" and self.command == "GET":
            context = require_auth(self)
            require_permission(context, "user_management", "view")
            self.send_json({"users": list_users()})
            return

        if parsed.path == "/api/users" and self.command == "POST":
            context = require_auth(self)
            require_permission(context, "user_management", "create")
            require_csrf(self, context)
            payload = self.read_json()
            username = validate_username(payload.get("username"))
            display_name = text_value(payload.get("displayName")) or username
            role = text_value(payload.get("roleCode") or payload.get("role")) or "operator"
            role_id = PERMISSIONS.db.scalar(
                f"SELECT role_id FROM auth_role WHERE role_code = {sql_quote(role)};"
            )
            role_record = PERMISSIONS.role(role_id)
            if not role_record:
                raise ApiError("Role does not exist.")
            if bool(role_record.get("isSuperAdmin")) and not PERMISSIONS.is_super_admin(context):
                raise ForbiddenError("Only a super administrator can assign a super administrator role.")
            if False:
                raise ApiError("账号角色无效。")
            password = validate_password(payload.get("password"))
            employee_id = validate_employee_binding(payload.get("employeeId"))
            if not bool(role_record.get("isSuperAdmin")) and not employee_id:
                raise ApiError("普通账号必须绑定组织架构中的人员。")
            if find_user_by_username(username):
                raise ConflictError("账号已经存在。")
            run_mysql(
                f"""
                INSERT INTO user_account (
                  username, display_name, password_hash, user_role, role_code, employee_id, is_active
                )
                VALUES (
                  {sql_quote(username)}, {sql_quote(display_name)}, {sql_quote(password_hash(password))},
                  {sql_quote(legacy_role_value(role))}, {sql_quote(role)}, {employee_id or 'NULL'}, 1
                );
                """,
                database=DB_NAME,
            )
            created = find_user_by_username(username)
            write_auth_audit(text_value(context.get("username")), "user_account_added", text_value(created.get("id")), username, f"新增账号 {username}")
            self.send_json({"user": auth_user_public(created)}, status=HTTPStatus.CREATED)
            return

        if parsed.path.startswith("/api/users/") and self.command == "PUT":
            context = require_auth(self)
            require_permission(context, "user_management", "update")
            require_csrf(self, context)
            user_id = parsed.path.rsplit("/", 1)[-1]
            target = find_user_by_id(user_id)
            if not target:
                self.send_json({"error": "账号不存在。"}, status=HTTPStatus.NOT_FOUND)
                return
            payload = self.read_json()
            display_name = text_value(payload.get("displayName")) or text_value(target.get("displayName")) or text_value(target.get("username"))
            role = text_value(payload.get("roleCode") or payload.get("role")) or text_value(target.get("role")) or "operator"
            role_id = PERMISSIONS.db.scalar(
                f"SELECT role_id FROM auth_role WHERE role_code = {sql_quote(role)};"
            )
            role_record = PERMISSIONS.role(role_id)
            if not role_record:
                raise ApiError("Role does not exist.")
            if bool(role_record.get("isSuperAdmin")) and not PERMISSIONS.is_super_admin(context):
                raise ForbiddenError("Only a super administrator can assign a super administrator role.")
            if False:
                raise ApiError("账号角色无效。")
            active = 1 if parse_bool(
                payload.get("isActive"),
                parse_bool(target.get("isActive", True), True),
            ) else 0
            employee_id = validate_employee_binding(
                payload.get("employeeId", target.get("employeeId")),
                user_id,
            )
            if not bool(role_record.get("isSuperAdmin")) and not employee_id:
                raise ApiError("普通账号必须绑定组织架构中的人员。")
            if user_id == text_value(context.get("id")) and (not active or not bool(role_record.get("isSuperAdmin"))):
                raise ApiError("不能停用或降级当前登录的管理员账号。")
            password_clause = ""
            password = validate_password(payload.get("password"), allow_empty=True)
            if password:
                password_clause = f", password_hash = {sql_quote(password_hash(password))}, failed_attempts = 0, locked_until = NULL"
            run_mysql(
                f"""
                UPDATE user_account
                SET display_name = {sql_quote(display_name)},
                    user_role = {sql_quote(legacy_role_value(role))},
                    role_code = {sql_quote(role)},
                    employee_id = {employee_id or 'NULL'},
                    is_active = {active}{password_clause}
                WHERE user_id = {sql_quote(user_id)};
                """,
                database=DB_NAME,
            )
            if password:
                current_token = cookie_value(self, AUTH_COOKIE_NAME) if user_id == text_value(context.get("id")) else ""
                revoke_user_sessions(user_id, except_session_token=current_token)
            updated = find_user_by_id(user_id)
            write_auth_audit(text_value(context.get("username")), "user_account_changed", user_id, text_value(updated.get("username")), f"修改账号 {updated.get('username')}")
            self.send_json({"user": auth_user_public(updated)})
            return

        if parsed.path == "/api/settings" and self.command == "GET":
            context = require_auth(self)
            require_permission(context, "system_settings", "view")
            self.send_json({"settings": settings_payload()})
            return

        if parsed.path == "/api/settings" and self.command == "PUT":
            context = require_auth(self)
            require_permission(context, "system_settings", "update")
            require_csrf(self, context)
            payload = self.read_json()
            settings = payload.get("settings") or {}
            allowed = {
                "app_name",
                "login_notice",
                "session_hours",
                "backup_enabled",
                "backup_time",
                "backup_retention_days",
            }
            updates = {key: text_value(value) for key, value in settings.items() if key in allowed}
            if "session_hours" in updates:
                hours = sql_int(updates["session_hours"], 0)
                if hours < 1 or hours > 168:
                    raise ApiError("登录会话时长必须在 1-168 小时之间。")
                updates["session_hours"] = str(hours)
            if "app_name" in updates and not updates["app_name"]:
                raise ApiError("系统名称不能为空。")
            backup_setting_keys = {"backup_enabled", "backup_time", "backup_retention_days"}
            changed_backup_settings = backup_setting_keys.intersection(updates)
            if changed_backup_settings:
                current_settings = settings_payload()
                if "backup_enabled" in updates:
                    updates["backup_enabled"] = "1" if backup_setting_enabled(updates["backup_enabled"]) else "0"
                effective_time = validate_backup_time(
                    updates.get("backup_time", current_settings.get("backup_time", "02:00"))
                )
                effective_retention_days = validate_backup_retention_days(
                    updates.get("backup_retention_days", current_settings.get("backup_retention_days", "30"))
                )
                if "backup_time" in updates:
                    updates["backup_time"] = effective_time
                if "backup_retention_days" in updates:
                    updates["backup_retention_days"] = str(effective_retention_days)
            if updates:
                statements = [
                    f"""
                    INSERT INTO system_setting (setting_key, setting_value, updated_by)
                    VALUES ({sql_quote(key)}, {sql_quote(value)}, {sql_quote(context.get("id"))})
                    ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value), updated_by = VALUES(updated_by)
                    """
                    for key, value in updates.items()
                ]
                run_mysql("START TRANSACTION;\n" + ";\n".join(statements) + ";\nCOMMIT;", database=DB_NAME)
                if changed_backup_settings:
                    write_database_backup_audit(
                        text_value(context.get("username")),
                        "database_backup_schedule_changed",
                        "",
                        "database_backup",
                        "修改数据库自动备份设置",
                    )
                    if "backup_retention_days" in updates:
                        try:
                            cleanup_expired_database_backups(
                                validate_backup_retention_days(updates["backup_retention_days"])
                            )
                        except ApiError as exc:
                            print(f"Backup cleanup skipped: {exc}")
                else:
                    write_auth_audit(
                        text_value(context.get("username")),
                        "system_settings_changed",
                        "",
                        "system_setting",
                        "修改系统设置",
                    )
            self.send_json({"settings": settings_payload()})
            return

        if parsed.path == "/api/updates/check" and self.command == "POST":
            context = require_auth(self)
            require_permission(context, "system_updates", "update")
            require_csrf(self, context)
            payload = self.read_json(allow_empty=True)
            repository_url = normalize_update_repository_url(payload.get("repositoryUrl", ""))
            release_channel = normalize_update_release_channel(
                payload.get("releaseChannel", DEFAULT_UPDATE_RELEASE_CHANNEL)
            )
            update_payload = request_update_service(
                repository_url=repository_url,
                release_channel=release_channel,
            )
            if "repositoryUrl" in payload and parse_bool(
                payload.get("persistRepositoryUrl", True), True
            ):
                run_mysql(
                    f"""
                    INSERT INTO system_setting (setting_key, setting_value, setting_description, updated_by)
                    VALUES (
                      'update_repository_url',
                      {sql_quote(repository_url)},
                      '用于版本检查的 GitHub 或 Gitea Git 仓库地址；为空时使用服务器部署目录 origin',
                      {sql_quote(context.get("id"))}
                    )
                    ON DUPLICATE KEY UPDATE
                      setting_value = VALUES(setting_value),
                      updated_by = VALUES(updated_by)
                    """,
                    database=DB_NAME,
                )
            write_auth_audit(
                text_value(context.get("username")),
                "system_update_checked",
                "",
                "system_update",
                f"检查 {release_channel} 通道可用版本：{repository_url or '服务器默认 origin'}",
            )
            self.send_json(update_payload)
            return

        if parsed.path == "/api/updates/apply" and self.command == "POST":
            context = require_auth(self)
            require_permission(context, "system_updates", "update")
            require_csrf(self, context)
            payload = self.read_json()
            target_sha = text_value(payload.get("targetSha")).lower()
            if not re.fullmatch(r"[0-9a-f]{40}", target_sha):
                raise ApiError("请选择有效的版本。")
            repository_url = normalize_update_repository_url(payload.get("repositoryUrl", ""))
            release_channel = normalize_update_release_channel(
                payload.get("releaseChannel", DEFAULT_UPDATE_RELEASE_CHANNEL)
            )
            update_payload = request_update_service(
                target_sha,
                repository_url,
                release_channel,
            )
            status = text_value(update_payload.get("status"))
            target_version = text_value(update_payload.get("targetVersion")) or target_sha[:7]
            write_auth_audit(
                text_value(context.get("username")),
                "system_update_queued" if status == "queued" else "system_update_checked",
                "",
                "system_update",
                f"手动选择 {release_channel} 版本 {target_version}（{target_sha[:7]}），来源：{repository_url or '服务器默认 origin'}",
            )
            response_status = HTTPStatus.ACCEPTED if status == "queued" else HTTPStatus.OK
            self.send_json(update_payload, status=response_status)
            return

        if parsed.path == "/api/backups" and self.command == "GET":
            context = require_auth(self)
            require_permission(context, "backups", "view")
            self.send_json({"backups": list_database_backups()})
            return

        if parsed.path == "/api/backups" and self.command == "POST":
            context = require_auth(self)
            require_permission(context, "backups", "create")
            require_csrf(self, context)
            self.read_json(allow_empty=True)
            record = create_database_backup("manual", context)
            public_record = serialize_database_backup(record)
            write_database_backup_audit(
                text_value(context.get("username")),
                "database_backup_created",
                public_record["id"],
                public_record["fileName"],
                f"手动创建数据库备份 {public_record['fileName']}",
            )
            self.send_json(
                {"backup": public_record, "backups": list_database_backups()},
                status=HTTPStatus.CREATED,
            )
            return

        backup_download_match = re.fullmatch(r"/api/backups/(\d+)/download", parsed.path)
        if backup_download_match and self.command == "POST":
            context = require_auth(self)
            require_permission(context, "backups", "export")
            require_csrf(self, context)
            payload = self.read_json()
            current_user = find_user_by_id(text_value(context.get("id")))
            if not current_user or not verify_password(
                text_value(payload.get("password")),
                text_value(current_user.get("passwordHash")),
            ):
                raise UnauthorizedError("当前登录账号密码不正确。")
            record = database_backup_record(backup_download_match.group(1))
            if not record:
                self.send_json({"error": "备份记录不存在。"}, status=HTTPStatus.NOT_FOUND)
                return
            if text_value(record.get("status")) != "completed":
                self.send_json({"error": "该备份文件已过期或不可下载。"}, status=HTTPStatus.GONE)
                return
            file_path = resolve_backup_file_path(record.get("filePath"))
            if not file_path.is_file() or file_path.stat().st_size < 1:
                self.send_json({"error": "备份文件不存在或已被移动。"}, status=HTTPStatus.NOT_FOUND)
                return
            write_database_backup_audit(
                text_value(context.get("username")),
                "database_backup_downloaded",
                text_value(record.get("id")),
                text_value(record.get("fileName")),
                f"下载数据库备份 {text_value(record.get('fileName'))}",
            )
            self.send_file(file_path, text_value(record.get("fileName")))
            return

        if parsed.path == "/api/state" and self.command != "GET":
            self.send_json(
                {
                    "error": "状态快照接口只支持读取，请使用资源接口和命令接口。",
                    "code": "STATE_WRITE_RETIRED",
                },
                status=HTTPStatus.METHOD_NOT_ALLOWED,
            )
            return

        if parsed.path == "/api/state" and self.command == "GET":
            context = require_auth(self)
            with DB_LOCK:
                payload = filter_state_payload(build_state_payload(), context)
            self.send_json(payload)
            return

        if parsed.path == "/api/audit-logs" and self.command == "GET":
            context = require_auth(self)
            require_permission(context, "audit_logs", "view")
            with DB_LOCK:
                payload = query_audit_logs(params)
            self.send_json(payload)
            return

        self.send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_GET(self) -> None:
        try:
            if self.path.startswith("/api/"):
                self.handle_api()
                return
            super().do_GET()
        except UnauthorizedError as exc:
            self.send_json({"error": str(exc), "code": "AUTH_REQUIRED"}, status=HTTPStatus.UNAUTHORIZED)
        except CsrfError as exc:
            self.send_json({"error": str(exc), "code": "CSRF_INVALID"}, status=HTTPStatus.FORBIDDEN)
        except ForbiddenError as exc:
            self.send_json({"error": str(exc), "code": "FORBIDDEN"}, status=HTTPStatus.FORBIDDEN)
        except PayloadTooLargeError as exc:
            self.send_json(
                {"error": str(exc), "code": "PAYLOAD_TOO_LARGE"},
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        except RateLimitError as exc:
            self.send_json(
                {"error": str(exc), "code": "LOGIN_RATE_LIMITED"},
                status=HTTPStatus.TOO_MANY_REQUESTS,
                headers=[("Retry-After", str(exc.retry_after))],
            )
        except InternalServerError as exc:
            print(f"Internal server error: {exc}")
            traceback.print_exc()
            self.send_json(
                {"error": "服务器内部错误。", "code": "INTERNAL_ERROR"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        except ConflictError as exc:
            self.send_json({"error": str(exc), "code": "STATE_CONFLICT"}, status=HTTPStatus.CONFLICT)
        except ApiError as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            self.send_json(
                {"error": "服务器内部错误。", "code": "INTERNAL_ERROR"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_PUT(self) -> None:
        try:
            if self.path.startswith("/api/"):
                self.handle_api()
                return
            self.send_json({"error": "Method not allowed"}, status=HTTPStatus.METHOD_NOT_ALLOWED)
        except UnauthorizedError as exc:
            self.send_json({"error": str(exc), "code": "AUTH_REQUIRED"}, status=HTTPStatus.UNAUTHORIZED)
        except CsrfError as exc:
            self.send_json({"error": str(exc), "code": "CSRF_INVALID"}, status=HTTPStatus.FORBIDDEN)
        except ForbiddenError as exc:
            self.send_json({"error": str(exc), "code": "FORBIDDEN"}, status=HTTPStatus.FORBIDDEN)
        except PayloadTooLargeError as exc:
            self.send_json(
                {"error": str(exc), "code": "PAYLOAD_TOO_LARGE"},
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        except RateLimitError as exc:
            self.send_json(
                {"error": str(exc), "code": "LOGIN_RATE_LIMITED"},
                status=HTTPStatus.TOO_MANY_REQUESTS,
                headers=[("Retry-After", str(exc.retry_after))],
            )
        except InternalServerError as exc:
            print(f"Internal server error: {exc}")
            traceback.print_exc()
            self.send_json(
                {"error": "服务器内部错误。", "code": "INTERNAL_ERROR"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        except ConflictError as exc:
            self.send_json({"error": str(exc), "code": "STATE_CONFLICT"}, status=HTTPStatus.CONFLICT)
        except ApiError as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            self.send_json(
                {"error": "服务器内部错误。", "code": "INTERNAL_ERROR"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_POST(self) -> None:
        try:
            if self.path.startswith("/api/"):
                self.handle_api()
                return
            self.send_json({"error": "Method not allowed"}, status=HTTPStatus.METHOD_NOT_ALLOWED)
        except UnauthorizedError as exc:
            self.send_json({"error": str(exc), "code": "AUTH_REQUIRED"}, status=HTTPStatus.UNAUTHORIZED)
        except CsrfError as exc:
            self.send_json({"error": str(exc), "code": "CSRF_INVALID"}, status=HTTPStatus.FORBIDDEN)
        except ForbiddenError as exc:
            self.send_json({"error": str(exc), "code": "FORBIDDEN"}, status=HTTPStatus.FORBIDDEN)
        except PayloadTooLargeError as exc:
            self.send_json(
                {"error": str(exc), "code": "PAYLOAD_TOO_LARGE"},
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        except RateLimitError as exc:
            self.send_json(
                {"error": str(exc), "code": "LOGIN_RATE_LIMITED"},
                status=HTTPStatus.TOO_MANY_REQUESTS,
                headers=[("Retry-After", str(exc.retry_after))],
            )
        except InternalServerError as exc:
            print(f"Internal server error: {exc}")
            traceback.print_exc()
            self.send_json(
                {"error": "服务器内部错误。", "code": "INTERNAL_ERROR"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        except ConflictError as exc:
            self.send_json({"error": str(exc), "code": "STATE_CONFLICT"}, status=HTTPStatus.CONFLICT)
        except ApiError as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            self.send_json(
                {"error": "服务器内部错误。", "code": "INTERNAL_ERROR"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_DELETE(self) -> None:
        try:
            if self.path.startswith("/api/"):
                self.handle_api()
                return
            self.send_json({"error": "Method not allowed"}, status=HTTPStatus.METHOD_NOT_ALLOWED)
        except UnauthorizedError as exc:
            self.send_json({"error": str(exc), "code": "AUTH_REQUIRED"}, status=HTTPStatus.UNAUTHORIZED)
        except CsrfError as exc:
            self.send_json({"error": str(exc), "code": "CSRF_INVALID"}, status=HTTPStatus.FORBIDDEN)
        except ForbiddenError as exc:
            self.send_json({"error": str(exc), "code": "FORBIDDEN"}, status=HTTPStatus.FORBIDDEN)
        except PayloadTooLargeError as exc:
            self.send_json(
                {"error": str(exc), "code": "PAYLOAD_TOO_LARGE"},
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        except RateLimitError as exc:
            self.send_json(
                {"error": str(exc), "code": "LOGIN_RATE_LIMITED"},
                status=HTTPStatus.TOO_MANY_REQUESTS,
                headers=[("Retry-After", str(exc.retry_after))],
            )
        except InternalServerError as exc:
            print(f"Internal server error: {exc}")
            traceback.print_exc()
            self.send_json(
                {"error": "服务器内部错误。", "code": "INTERNAL_ERROR"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        except ConflictError as exc:
            self.send_json({"error": str(exc), "code": "STATE_CONFLICT"}, status=HTTPStatus.CONFLICT)
        except ApiError as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            self.send_json(
                {"error": "服务器内部错误。", "code": "INTERNAL_ERROR"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def end_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        parsed_path = urlparse(self.path).path
        if origin in {"http://127.0.0.1:8011", "http://localhost:8011"}:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Content-Security-Policy", SECURITY_CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), microphone=(), payment=(), usb=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        if AUTH_COOKIE_SECURE:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if self.command == "GET" and (
            parsed_path == "/"
            or parsed_path.endswith(".html")
            or parsed_path.endswith(".js")
            or parsed_path.endswith(".css")
        ):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-CSRF-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()


def main() -> None:
    if not WEB_DIR.exists():
        raise SystemExit(f"Web directory not found: {WEB_DIR}")
    if not Path(MYSQL_BIN).exists():
        raise SystemExit(f"MySQL client not found: {MYSQL_BIN}")
    if not DB_PASSWORD:
        raise SystemExit("DB_PASSWORD environment variable is required.")
    if not AUTH_COOKIE_SECURE and SERVER_HOST not in {"127.0.0.1", "localhost", "::1"}:
        print("WARNING: AUTH_COOKIE_SECURE is disabled while the server is not loopback-only.")
    if UPDATE_SERVICE_URL.startswith("http://") and not UPDATE_SERVICE_ALLOW_HTTP:
        print("WARNING: HTTP update service is disabled; configure HTTPS or explicitly allow isolated development HTTP.")

    server = ThreadingHTTPServer((SERVER_HOST, SERVER_PORT), AppHandler)
    scheduler = threading.Thread(
        target=database_backup_scheduler_loop,
        name="database-backup-scheduler",
        daemon=True,
    )
    scheduler.start()
    print(f"Serving web app on http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"Using MySQL {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    server.serve_forever()


if __name__ == "__main__":
    main()
