from __future__ import annotations

import re
from dataclasses import dataclass

from .sql import SqlGateway, parse_bool


ACTION_CODES = ("view", "create", "update", "delete", "approve", "export")
DATA_SCOPES = ("all", "organization", "own", "submitted", "assigned", "none")
ACTION_LABELS = {
    "view": "查看",
    "create": "新增",
    "update": "修改",
    "delete": "删除",
    "approve": "审批",
    "export": "导出",
}
DATA_SCOPE_LABELS = {
    "all": "全部数据",
    "organization": "所属部门及下属部门",
    "own": "本人数据",
    "submitted": "本人提交",
    "assigned": "本人负责",
    "none": "无数据",
}
ROLE_CATEGORIES = ("admin", "ordinary", "custom")
ROLE_CATEGORY_LABELS = {
    "admin": "管理员",
    "ordinary": "普通用户",
    "custom": "自定义角色",
}


@dataclass
class PermissionService:
    db: SqlGateway
    api_error: type[Exception]
    forbidden_error: type[Exception]

    def is_super_admin(self, context: dict) -> bool:
        if parse_bool(context.get("isSuperAdmin")):
            return True
        role_code = self.db.text(context.get("role"))
        if not role_code:
            return False
        return (
            self.db.scalar(
                f"""
                SELECT COUNT(*)
                FROM auth_role
                WHERE role_code = {self.db.quote(role_code)}
                  AND is_active = 1
                  AND is_super_admin = 1
                """
            )
            == 1
        )

    def _permission_rows(self, context: dict) -> list[dict]:
        user_id = self.db.integer(context.get("id"), 0)
        role_code = self.db.text(context.get("role"))
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'moduleCode', permission.module_code,
              'moduleName', module.module_name,
              'actionCode', permission.action_code,
              'canView', COALESCE(user_permission.can_view, role_permission.can_view, 0),
              'canCreate', COALESCE(user_permission.can_create, role_permission.can_create, 0),
              'canUpdate', COALESCE(user_permission.can_update, role_permission.can_update, 0),
              'canDelete', COALESCE(user_permission.can_delete, role_permission.can_delete, 0),
              'canApprove', COALESCE(user_permission.can_approve, role_permission.can_approve, 0),
              'canExport', COALESCE(user_permission.can_export, role_permission.can_export, 0),
              'dataScope', COALESCE(user_permission.data_scope, role_permission.data_scope, 'none')
            )), JSON_ARRAY())
            FROM auth_permission permission
            JOIN auth_module module ON module.module_code = permission.module_code
            LEFT JOIN auth_role role_row
              ON role_row.role_code = {self.db.quote(role_code)}
             AND role_row.is_active = 1
            LEFT JOIN auth_role_permission role_permission
              ON role_permission.role_id = role_row.role_id
             AND role_permission.permission_id = permission.permission_id
            LEFT JOIN auth_user_permission user_permission
              ON user_permission.user_id = {user_id}
             AND user_permission.permission_id = permission.permission_id
            WHERE module.is_active = 1
            """,
            [],
        )
        return list(rows or [])

    def permissions(self, context: dict) -> list[dict]:
        rows = self._permission_rows(context)
        for row in rows:
            action_code = self.db.text(row.get("actionCode"))
            scope = self.db.text(row.get("dataScope"))
            row["actionName"] = ACTION_LABELS.get(action_code, action_code)
            row["dataScopeName"] = DATA_SCOPE_LABELS.get(scope, scope)
        if not self.is_super_admin(context):
            return rows
        for row in rows:
            for action in ACTION_CODES:
                row_key = f"can{action.capitalize()}"
                row[row_key] = True
            row["dataScope"] = "all"
            row["dataScopeName"] = DATA_SCOPE_LABELS["all"]
        return rows

    def permission(self, context: dict, module_code: str, action_code: str) -> dict:
        if action_code not in ACTION_CODES:
            raise self.api_error("Unsupported permission action.")
        for row in self.permissions(context):
            if (
                self.db.text(row.get("moduleCode")) == module_code
                and self.db.text(row.get("actionCode")) == action_code
            ):
                return row
        return {
            "moduleCode": module_code,
            "actionCode": action_code,
            "actionName": ACTION_LABELS.get(action_code, action_code),
            "canView": False,
            "canCreate": False,
            "canUpdate": False,
            "canDelete": False,
            "canApprove": False,
            "canExport": False,
            "dataScope": "none",
        }

    def require(self, context: dict, module_code: str, action_code: str) -> None:
        row = self.permission(context, module_code, action_code)
        key = f"can{action_code.capitalize()}"
        scope = self.db.text(row.get("dataScope")) or "none"
        if not parse_bool(row.get(key)) or scope == "none":
            raise self.forbidden_error("当前账号没有执行此操作的权限。")
        scopes = context.setdefault("_permissionScopes", {})
        scopes[module_code] = scope

    def catalog(self) -> dict:
        modules = self.db.json(
            """
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'code', module_code,
              'name', module_name,
              'category', category,
              'sortOrder', sort_order
            )), JSON_ARRAY())
            FROM (
              SELECT module_code, module_name, category, sort_order
              FROM auth_module
              WHERE is_active = 1
              ORDER BY sort_order, module_code
            ) ordered_modules
            """,
            [],
        )
        permissions = self.db.json(
            """
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', permission_id,
              'moduleCode', module_code,
              'actionCode', action_code
            )), JSON_ARRAY())
            FROM (
              SELECT permission_id, module_code, action_code
              FROM auth_permission
              ORDER BY permission_id
            ) ordered_permissions
            """,
            [],
        )
        module_rows = list(modules or [])
        permission_rows = list(permissions or [])
        for item in permission_rows:
            action_code = self.db.text(item.get("actionCode"))
            item["actionName"] = ACTION_LABELS.get(action_code, action_code)
        return {"modules": module_rows, "permissions": permission_rows}

    def list_roles(self) -> list[dict]:
        rows = self.db.json(
            """
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', role_id,
              'code', role_code,
              'name', role_name,
              'category', role_category,
              'categoryName', CASE role_category
                WHEN 'admin' THEN '管理员'
                WHEN 'ordinary' THEN '普通用户'
                ELSE '自定义角色'
              END,
              'isSystem', is_system,
              'isSuperAdmin', is_super_admin,
              'isActive', is_active
            )), JSON_ARRAY())
            FROM (
              SELECT role_id, role_code, role_name, role_category, is_system, is_super_admin, is_active
              FROM auth_role
              WHERE is_active = 1
              ORDER BY is_super_admin DESC, role_category, is_system DESC, role_name, role_id
            ) ordered_roles
            """,
            [],
        )
        return list(rows or [])

    def role(self, role_id: object) -> dict | None:
        role_id_int = self.db.integer(role_id, 0)
        if role_id_int <= 0:
            return None
        return self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', role_id,
              'code', role_code,
              'name', role_name,
              'category', role_category,
              'categoryName', CASE role_category
                WHEN 'admin' THEN '管理员'
                WHEN 'ordinary' THEN '普通用户'
                ELSE '自定义角色'
              END,
              'isSystem', is_system,
              'isSuperAdmin', is_super_admin,
              'isActive', is_active
            )
            FROM auth_role
            WHERE role_id = {role_id_int}
              AND is_active = 1
            """,
            None,
        )

    def role_permissions(self, role_id: object) -> list[dict]:
        role_id_int = self.db.integer(role_id, 0)
        if role_id_int <= 0:
            raise self.api_error("Invalid role identifier.")
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'moduleCode', permission.module_code,
              'actionCode', permission.action_code,
              'canView', COALESCE(role_permission.can_view, 0),
              'canCreate', COALESCE(role_permission.can_create, 0),
              'canUpdate', COALESCE(role_permission.can_update, 0),
              'canDelete', COALESCE(role_permission.can_delete, 0),
              'canApprove', COALESCE(role_permission.can_approve, 0),
              'canExport', COALESCE(role_permission.can_export, 0),
              'dataScope', COALESCE(role_permission.data_scope, 'none')
            )), JSON_ARRAY())
            FROM auth_permission permission
            LEFT JOIN auth_role_permission role_permission
              ON role_permission.permission_id = permission.permission_id
             AND role_permission.role_id = {role_id_int}
            """,
            [],
        )
        return list(rows or [])

    def user_permissions(self, user_id: object) -> list[dict]:
        user_id_int = self.db.integer(user_id, 0)
        if user_id_int <= 0:
            raise self.api_error("Invalid user identifier.")
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'moduleCode', permission.module_code,
              'actionCode', permission.action_code,
              'canView', user_permission.can_view,
              'canCreate', user_permission.can_create,
              'canUpdate', user_permission.can_update,
              'canDelete', user_permission.can_delete,
              'canApprove', user_permission.can_approve,
              'canExport', user_permission.can_export,
              'dataScope', user_permission.data_scope
            )), JSON_ARRAY())
            FROM auth_user_permission user_permission
            JOIN auth_permission permission ON permission.permission_id = user_permission.permission_id
            WHERE user_permission.user_id = {user_id_int}
            """,
            [],
        )
        return list(rows or [])

    def create_role(self, payload: dict, context: dict) -> dict:
        if not self.is_super_admin(context):
            raise self.forbidden_error("只有超级管理员可以创建角色。")
        code = self.db.text(payload.get("code")).lower()
        name = self.db.text(payload.get("name"))
        category = self.db.text(payload.get("category")).lower() or "custom"
        if not re.fullmatch(r"[a-z][a-z0-9._-]{2,63}", code):
            raise self.api_error("角色编码需使用 3-64 位小写字母、数字、点、下划线或短横线。")
        if not name:
            raise self.api_error("角色名称不能为空。")
        if category not in ROLE_CATEGORIES:
            raise self.api_error("角色类别无效。")
        is_super_admin = 1 if parse_bool(payload.get("isSuperAdmin")) else 0
        if is_super_admin and not self.is_super_admin(context):
            raise self.forbidden_error("只有超级管理员可以创建超级管理员角色。")
        if is_super_admin and category != "admin":
            raise self.api_error("超级管理员角色的类别必须是管理员。")
        if self.db.scalar(
            f"SELECT COUNT(*) FROM auth_role WHERE role_code = {self.db.quote(code)};"
        ):
            raise self.api_error("角色编码已经存在。")
        permission_items = payload.get("permissions")
        if permission_items is None:
            permission_items = []
        if not isinstance(permission_items, list):
            raise self.api_error("初始权限必须是数组。")
        permission_rows = self._permission_value_rows(0, permission_items, use_session_id=True)
        statements = [
            "START TRANSACTION",
            f"""
            INSERT INTO auth_role (
              role_code, role_name, role_category, is_system, is_super_admin, created_by
            )
            VALUES (
              {self.db.quote(code)}, {self.db.quote(name)}, {self.db.quote(category)}, 0,
              {is_super_admin}, {self.db.integer(context.get('id'), 0)}
            )
            """,
            "SET @created_role_id = LAST_INSERT_ID()",
        ]
        if permission_rows:
            statements.append(
                """
                INSERT INTO auth_role_permission (
                  role_id, permission_id, can_view, can_create, can_update,
                  can_delete, can_approve, can_export, data_scope
                ) VALUES
                """
                + ", ".join(permission_rows)
            )
        statements.extend(["COMMIT", "SELECT @created_role_id"])
        role_id = self.db.one_id(";\n".join(statements) + ";")
        return dict(self.role(role_id) or {})

    def update_role(self, role_id: object, payload: dict, context: dict) -> dict:
        if not self.is_super_admin(context):
            raise self.forbidden_error("只有超级管理员可以修改角色。")
        role = self.role(role_id)
        if not role:
            raise self.api_error("角色不存在。")
        is_super_admin = 1 if parse_bool(payload.get("isSuperAdmin"), parse_bool(role.get("isSuperAdmin"))) else 0
        if is_super_admin != int(parse_bool(role.get("isSuperAdmin"))) and not self.is_super_admin(context):
            raise self.forbidden_error("只有超级管理员可以变更超级管理员角色。")
        name = self.db.text(payload.get("name")) or self.db.text(role.get("name"))
        category = self.db.text(payload.get("category")).lower() or self.db.text(role.get("category")) or "custom"
        if not name:
            raise self.api_error("角色名称不能为空。")
        if category not in ROLE_CATEGORIES:
            raise self.api_error("角色类别无效。")
        if is_super_admin and category != "admin":
            raise self.api_error("超级管理员角色的类别必须是管理员。")
        self.db.execute(
            f"""
            UPDATE auth_role
            SET role_name = {self.db.quote(name)},
                role_category = {self.db.quote(category)},
                is_super_admin = {is_super_admin}
            WHERE role_id = {self.db.integer(role_id, 0)};
            """
        )
        return dict(self.role(role_id) or {})

    def _validate_permission_item(self, item: dict) -> tuple[int, list[str]]:
        module_code = self.db.text(item.get("moduleCode"))
        action_code = self.db.text(item.get("actionCode"))
        if action_code not in ACTION_CODES:
            raise self.api_error("Unsupported permission action.")
        permission_id = self.db.scalar(
            f"""
            SELECT permission_id
            FROM auth_permission
            WHERE module_code = {self.db.quote(module_code)}
              AND action_code = {self.db.quote(action_code)}
            """
        )
        if permission_id <= 0:
            raise self.api_error("Unsupported permission module.")
        scope = self.db.text(item.get("dataScope")) or "none"
        if scope not in DATA_SCOPES:
            raise self.api_error("Unsupported data scope.")
        return permission_id, [scope]

    def _permission_value_rows(
        self,
        role_id: object,
        items: list[dict],
        use_session_id: bool = False,
    ) -> list[str]:
        role_value = "@created_role_id" if use_session_id else str(self.db.integer(role_id, 0))
        rows: list[str] = []
        for item in items:
            permission_id, (scope,) = self._validate_permission_item(item)
            rows.append(
                "("
                + ", ".join(
                    [
                        role_value,
                        str(permission_id),
                        "1" if parse_bool(item.get("canView")) else "0",
                        "1" if parse_bool(item.get("canCreate")) else "0",
                        "1" if parse_bool(item.get("canUpdate")) else "0",
                        "1" if parse_bool(item.get("canDelete")) else "0",
                        "1" if parse_bool(item.get("canApprove")) else "0",
                        "1" if parse_bool(item.get("canExport")) else "0",
                        self.db.quote(scope),
                    ]
                )
                + ")"
            )
        return rows

    def replace_role_permissions(self, role_id: object, items: list[dict], context: dict) -> list[dict]:
        if not self.is_super_admin(context):
            raise self.forbidden_error("只有超级管理员可以修改角色权限。")
        role_id_int = self.db.integer(role_id, 0)
        if not self.role(role_id_int):
            raise self.api_error("角色不存在。")
        rows = self._permission_value_rows(role_id_int, items)
        statements = [
            "START TRANSACTION",
            f"DELETE FROM auth_role_permission WHERE role_id = {role_id_int}",
        ]
        if rows:
            statements.append(
                """
                INSERT INTO auth_role_permission (
                  role_id, permission_id, can_view, can_create, can_update,
                  can_delete, can_approve, can_export, data_scope
                ) VALUES
                """
                + ", ".join(rows)
            )
        statements.append("COMMIT")
        self.db.execute(";\n".join(statements) + ";")
        return self.role_permissions(role_id_int)

    def replace_user_permissions(self, user_id: object, items: list[dict], context: dict) -> list[dict]:
        if not self.is_super_admin(context):
            raise self.forbidden_error("只有超级管理员可以修改用户权限覆盖。")
        user_id_int = self.db.integer(user_id, 0)
        if user_id_int <= 0 or self.db.scalar(
            f"SELECT COUNT(*) FROM user_account WHERE user_id = {user_id_int};"
        ) != 1:
            raise self.api_error("User does not exist.")
        rows: list[str] = []
        for item in items:
            permission_id, (scope,) = self._validate_permission_item(item)
            rows.append(
                "("
                + ", ".join(
                    [
                        str(user_id_int),
                        str(permission_id),
                        "1" if parse_bool(item.get("canView")) else "0",
                        "1" if parse_bool(item.get("canCreate")) else "0",
                        "1" if parse_bool(item.get("canUpdate")) else "0",
                        "1" if parse_bool(item.get("canDelete")) else "0",
                        "1" if parse_bool(item.get("canApprove")) else "0",
                        "1" if parse_bool(item.get("canExport")) else "0",
                        self.db.quote(scope),
                    ]
                )
                + ")"
            )
        statements = [
            "START TRANSACTION",
            f"DELETE FROM auth_user_permission WHERE user_id = {user_id_int}",
        ]
        if rows:
            statements.append(
                """
                INSERT INTO auth_user_permission (
                  user_id, permission_id, can_view, can_create, can_update,
                  can_delete, can_approve, can_export, data_scope
                ) VALUES
                """
                + ", ".join(rows)
            )
        statements.append("COMMIT")
        self.db.execute(";\n".join(statements) + ";")
        return self.user_permissions(user_id_int)
