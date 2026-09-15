from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .scope import OrganizationScopeService
from .sql import SqlGateway, parse_bool


FORM_TYPES = {"ticket", "change", "problem"}
FORM_FIELD_TYPES = {
    "text",
    "textarea",
    "number",
    "date",
    "datetime",
    "select",
    "multiselect",
    "checkbox",
    "employee",
    "asset",
    "organization",
    "system",
}

SYSTEM_FIELD_SOURCES = {
    "current_user_name",
    "current_employee_name",
    "current_employee_no",
    "current_department",
    "current_org",
    "current_position",
    "current_user_email",
    "current_user_mobile",
    "current_datetime",
}

CHANGE_TRANSITIONS = {
    "draft": {"submitted", "cancelled"},
    "submitted": {"assessing", "cancelled"},
    "assessing": {"scheduled", "rejected", "cancelled"},
    "approved": {"scheduled", "cancelled"},
    "rejected": {"draft", "cancelled"},
    "scheduled": {"implementing", "cancelled"},
    "implementing": {"verified", "cancelled"},
    "verified": {"closed", "implementing"},
    "closed": set(),
    "cancelled": set(),
}

PROBLEM_TRANSITIONS = {
    "new": {"investigating", "cancelled"},
    "investigating": {"known_error", "resolved", "cancelled"},
    "known_error": {"resolved", "cancelled"},
    "resolved": {"closed", "investigating"},
    "closed": set(),
    "cancelled": set(),
}

KNOWLEDGE_TRANSITIONS = {
    "draft": {"review", "archived"},
    "review": {"published", "draft", "archived"},
    "published": {"archived", "draft"},
    "archived": {"draft"},
}


def _priority_label(value: object) -> str:
    value = str(value or "").strip().lower()
    return value if value in {"low", "medium", "high"} else "medium"


@dataclass
class ServiceManagementService:
    db: SqlGateway
    scope: OrganizationScopeService
    api_error: type[Exception]
    conflict_error: type[Exception]
    forbidden_error: type[Exception]

    def _actor_id(self, context: dict) -> int:
        return self.db.integer(context.get("id"), 0)

    def _actor_name(self, context: dict) -> str:
        return self.db.text(context.get("username")) or "web"

    def _actor_employee_id(self, context: dict) -> int:
        employee = context.get("employee") if isinstance(context.get("employee"), dict) else {}
        return self.db.integer(employee.get("employeeId"), 0)

    def _scope(self, context: dict, module_code: str) -> str:
        return self.db.text((context.get("_permissionScopes") or {}).get(module_code)) or "all"

    def _active_employee(self, employee_id: object) -> dict:
        employee_id_int = self.db.integer(employee_id, 0)
        if employee_id_int <= 0:
            raise self.api_error("Requester employee does not exist.")
        employee = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(employee_id AS CHAR),
              'orgId', COALESCE(CAST(org_unit_id AS CHAR), '')
            )
            FROM employee
            WHERE employee_id = {employee_id_int}
              AND is_active = 1
              AND employment_status <> 'left'
            """,
            None,
        )
        if not employee:
            raise self.api_error("Requester employee does not exist.")
        return dict(employee)

    def _validated_assignee_id(self, value: object) -> int:
        assignee_id = self.db.integer(value, 0)
        if assignee_id <= 0:
            return 0
        account = self.db.scalar(
            f"""
            SELECT COUNT(*)
            FROM user_account
            WHERE user_id = {assignee_id}
              AND is_active = 1
            """
        )
        if account != 1:
            raise self.api_error("Assigned operator does not exist.")
        return assignee_id

    def _assert_related_ticket_access(self, ticket_id: object, context: dict) -> None:
        ticket_id_int = self.db.integer(ticket_id, 0)
        if ticket_id_int <= 0:
            return
        ticket = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'orgId', COALESCE(CAST(org_unit_id AS CHAR), ''),
              'createdByUserId', COALESCE(CAST(created_by AS CHAR), ''),
              'assignedToUserId', COALESCE(CAST(assigned_to_user_id AS CHAR), '')
            )
            FROM itil_ticket
            WHERE ticket_id = {ticket_id_int}
            """,
            None,
        )
        if not ticket:
            raise self.api_error("Related ticket does not exist.")
        ticket_scope = self.db.text(
            (context.get("_permissionScopes") or {}).get("tickets")
        ) or "none"
        if ticket_scope == "none":
            raise self.forbidden_error("You are not authorized to link this ticket.")
        self._assert_org_access(context, ticket.get("orgId"))
        actor_id = self._actor_id(context)
        if ticket_scope in {"own", "submitted"} and self.db.integer(
            ticket.get("createdByUserId"), 0
        ) != actor_id:
            raise self.forbidden_error("You can only link tickets submitted by you.")
        if ticket_scope == "assigned" and self.db.integer(
            ticket.get("assignedToUserId"), 0
        ) != actor_id:
            raise self.forbidden_error("You can only link tickets assigned to you.")

    def _record_create_context(
        self,
        module_code: str,
        payload: dict,
        context: dict,
        *,
        includes_requester: bool,
    ) -> tuple[int, int, int, int]:
        scope = self._scope(context, module_code)
        org_id = self.db.integer(payload.get("orgId"), 0)
        requester_id = self.db.integer(payload.get("requesterEmployeeId"), 0)
        assignee_id = self.db.integer(payload.get("assignedToUserId"), 0)
        actor_id = self._actor_id(context)

        if scope in {"own", "submitted"}:
            actor_employee_id = self._actor_employee_id(context)
            if actor_employee_id <= 0:
                raise self.forbidden_error(
                    "A submitter must bind an employee identity before creating records."
                )
            actor_employee = self._active_employee(actor_employee_id)
            actor_org_id = self.db.integer(actor_employee.get("orgId"), 0)
            if includes_requester:
                if requester_id and requester_id != actor_employee_id:
                    raise self.forbidden_error(
                        "You can only submit records for your bound employee identity."
                    )
                requester_id = actor_employee_id
            if org_id and actor_org_id and org_id != actor_org_id:
                raise self.forbidden_error(
                    "You can only submit records for your bound organization."
                )
            if not org_id:
                org_id = actor_org_id

        if scope == "assigned":
            if assignee_id and assignee_id != actor_id:
                raise self.forbidden_error(
                    "You can only create records assigned to your own account."
                )
            assignee_id = actor_id

        if includes_requester and requester_id:
            requester = self._active_employee(requester_id)
            requester_org_id = self.db.integer(requester.get("orgId"), 0)
            if org_id and requester_org_id and org_id != requester_org_id:
                raise self.api_error(
                    "Requester employee and record organization do not match."
                )
            if not org_id:
                org_id = requester_org_id

        self._assert_org_access(context, org_id)
        assignee_id = self._validated_assignee_id(assignee_id)
        related_ticket_id = self.db.integer(payload.get("relatedTicketId"), 0)
        if related_ticket_id:
            self._assert_related_ticket_access(related_ticket_id, context)
        return org_id, requester_id, assignee_id, related_ticket_id

    def _form_fields(self, form_id: int) -> list[dict]:
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', CAST(field_id AS CHAR),
              'key', field_key,
              'label', field_label,
              'type', field_type,
              'placeholder', placeholder,
              'defaultValue', COALESCE(default_value, JSON_OBJECT()),
              'options', COALESCE(options_json, JSON_ARRAY()),
              'config', COALESCE(field_config, JSON_OBJECT()),
              'required', is_required,
              'readonly', is_readonly,
              'sortOrder', sort_order
            )), JSON_ARRAY())
            FROM (
              SELECT *
              FROM service_form_field
              WHERE form_id = {form_id} AND is_active = 1
              ORDER BY sort_order, field_id
            ) ordered_fields
            """,
            [],
        )
        return list(rows or [])

    def _form_row(self, form_id: object = 0, form_code: str = "") -> dict | None:
        form_id_int = self.db.integer(form_id, 0)
        code_sql = self.db.quote(form_code) if form_code else "NULL"
        row = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(form_id AS CHAR),
              'code', form_code,
              'name', form_name,
              'recordType', record_type,
              'description', description,
              'layout', COALESCE(layout_json, JSON_OBJECT()),
              'workflow', COALESCE(workflow_json, JSON_OBJECT()),
              'workflowId', COALESCE(CAST(workflow_id AS CHAR), ''),
              'listConfig', COALESCE(list_config_json, JSON_OBJECT()),
              'settings', COALESCE(settings_json, JSON_OBJECT()),
              'version', version_no,
              'isActive', is_active,
              'publishedAt', COALESCE(CAST(published_at AS CHAR), ''),
              'createdAt', CAST(created_at AS CHAR),
              'updatedAt', CAST(updated_at AS CHAR)
            )
            FROM service_form
            WHERE is_active = 1
              AND ({form_id_int} <= 0 OR form_id = {form_id_int})
              AND ({code_sql} IS NULL OR form_code = {code_sql})
            ORDER BY form_id
            LIMIT 1
            """,
            None,
        )
        if not row:
            return None
        result = dict(row)
        result["fields"] = self._form_fields(self.db.integer(result.get("id"), 0))
        return result

    def _validate_field_definitions(self, fields: object) -> list[dict]:
        if not isinstance(fields, list):
            raise self.api_error("表单字段必须是数组。")
        if len(fields) > 100:
            raise self.api_error("单个表单最多支持 100 个字段。")
        output: list[dict] = []
        seen: set[str] = set()
        for index, item in enumerate(fields):
            if not isinstance(item, dict):
                raise self.api_error("表单字段必须是对象。")
            key = self.db.text(item.get("key") or item.get("fieldKey")).lower()
            label = self.db.text(item.get("label") or item.get("fieldLabel"))
            field_type = self.db.text(item.get("type") or item.get("fieldType")).lower() or "text"
            if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", key):
                raise self.api_error("字段标识只能使用小写字母、数字和下划线，且必须以字母开头。")
            if key in seen:
                raise self.api_error(f"字段标识重复：{key}。")
            if not label:
                raise self.api_error(f"字段 {key} 缺少显示名称。")
            if field_type not in FORM_FIELD_TYPES:
                raise self.api_error(f"不支持的表单字段类型：{field_type}。")
            config = item.get("config")
            if config is None:
                config = {}
            if not isinstance(config, dict):
                raise self.api_error("Field config must be an object.")
            if field_type == "system":
                source = self.db.text(item.get("systemSource") or config.get("source"))
                if source not in SYSTEM_FIELD_SOURCES:
                    raise self.api_error("System field source is invalid.")
                config["source"] = source
                config["readonly"] = True
            options = item.get("options")
            if field_type in {"select", "multiselect"}:
                if not isinstance(options, list) or not options or len(options) > 100:
                    raise self.api_error(f"字段 {key} 必须提供选项数组。")
                options = [
                    {
                        "value": self.db.text(option.get("value")) if isinstance(option, dict) else self.db.text(option),
                        "label": self.db.text(option.get("label")) if isinstance(option, dict) else self.db.text(option),
                    }
                    for option in options
                ]
            elif options is not None and not isinstance(options, list):
                raise self.api_error(f"字段 {key} 的选项必须是数组。")
            seen.add(key)
            output.append(
                {
                    "key": key,
                    "label": label,
                    "type": field_type,
                    "placeholder": self.db.text(item.get("placeholder")),
                    "defaultValue": item.get("defaultValue"),
                    "options": options or [],
                    "config": config,
                    "required": parse_bool(item.get("required")),
                    "readonly": parse_bool(item.get("readonly")) or field_type == "system",
                    "sortOrder": self.db.integer(item.get("sortOrder"), (index + 1) * 10),
                }
            )
        return output

    def _form_for_payload(self, record_type: str, payload: dict) -> dict | None:
        form_id = self.db.integer(payload.get("formId"), 0)
        form_code = self.db.text(payload.get("formCode"))
        form = self._form_row(form_id, form_code) if form_id > 0 or form_code else None
        if form and self.db.text(form.get("recordType")) != record_type:
            raise self.api_error("表单类型与业务对象不匹配。")
        if not form:
            default_code = (
                "request_default"
                if record_type == "ticket" and self.db.text(payload.get("type")) == "request"
                else "incident_default"
                if record_type == "ticket"
                else f"{record_type}_default"
            )
            form = self._form_row(form_code=default_code)
        return form

    def _system_field_value(self, source: str, context: dict | None) -> object:
        context = context or {}
        employee = context.get("employee") or {}
        values = {
            "current_user_name": context.get("displayName") or context.get("username") or "",
            "current_employee_name": employee.get("employeeName") or "",
            "current_employee_no": employee.get("employeeNo") or "",
            "current_department": employee.get("department") or "",
            "current_org": employee.get("orgName") or employee.get("orgId") or "",
            "current_position": employee.get("positionName") or "",
            "current_user_email": employee.get("email") or "",
            "current_user_mobile": employee.get("mobile") or "",
            "current_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return values.get(source, "")

    def _validated_custom_fields(
        self,
        record_type: str,
        payload: dict,
        context: dict | None = None,
    ) -> tuple[int, dict]:
        form = self._form_for_payload(record_type, payload)
        custom_fields = payload.get("customFields")
        if custom_fields is None:
            custom_fields = {}
        if not isinstance(custom_fields, dict):
            raise self.api_error("自定义字段必须是对象。")
        if not form:
            return 0, custom_fields
        form_id = self.db.integer(form.get("id"), 0)
        if form_id > 0 and context is not None:
            self.assert_form_permission(form_id, context, "submit")
        fields = list(form.get("fields") or [])
        field_map = {self.db.text(item.get("key")): item for item in fields}
        for key, field in field_map.items():
            if self.db.text(field.get("type")) == "system":
                config = field.get("config") or {}
                custom_fields[key] = self._system_field_value(
                    self.db.text(config.get("source")),
                    context,
                )
        unknown = sorted(set(custom_fields) - set(field_map))
        if unknown:
            raise self.api_error("存在未定义的自定义字段：" + ", ".join(unknown))
        for key, field in field_map.items():
            value = custom_fields.get(key)
            if field.get("required") and (value is None or value == "" or value == []):
                raise self.api_error(f"字段“{field.get('label') or key}”不能为空。")
            field_type = self.db.text(field.get("type"))
            if value in (None, ""):
                continue
            if field_type == "multiselect" and not isinstance(value, list):
                raise self.api_error(f"字段“{field.get('label') or key}”必须是多选数组。")
            if field_type == "number":
                try:
                    float(value)
                except (TypeError, ValueError) as exc:
                    raise self.api_error(f"字段“{field.get('label') or key}”必须是数字。") from exc
            if field_type in {"select", "multiselect"}:
                allowed = {self.db.text(option.get("value")) for option in field.get("options") or []}
                values = value if field_type == "multiselect" else [value]
                if any(self.db.text(item) not in allowed for item in values):
                    raise self.api_error(f"字段“{field.get('label') or key}”包含无效选项。")
        return self.db.integer(form.get("id"), 0), custom_fields

    def list_forms(self, record_type: str = "", context: dict | None = None) -> list[dict]:
        condition = "1 = 1"
        if record_type:
            if record_type not in FORM_TYPES:
                raise self.api_error("不支持的表单业务类型。")
            condition += f" AND record_type = {self.db.quote(record_type)}"
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', CAST(form_id AS CHAR),
              'code', form_code,
              'name', form_name,
              'recordType', record_type,
              'description', description,
              'version', version_no,
              'isActive', is_active,
              'updatedAt', CAST(updated_at AS CHAR)
            )), JSON_ARRAY())
            FROM (
              SELECT *
              FROM service_form
              WHERE is_active = 1 AND {condition}
              ORDER BY record_type, form_name, form_id
            ) ordered_forms
            """,
            [],
        )
        result = []
        for row in rows or []:
            item = dict(row)
            if context is not None:
                try:
                    self.assert_form_permission(item.get("id"), context, "view")
                except (self.api_error, self.forbidden_error):
                    continue
            item["fields"] = self._form_fields(self.db.integer(item.get("id"), 0))
            result.append(item)
        return result

    def list_forms_for_submission(self, record_type: str, context: dict | None = None) -> list[dict]:
        if record_type not in FORM_TYPES:
            raise self.api_error("不支持的表单业务类型。")
        forms = self.list_forms(record_type, context)
        if context is None:
            return forms
        visible: list[dict] = []
        for form in forms:
            try:
                self.assert_form_permission(form.get("id"), context, "view")
                self.assert_form_permission(form.get("id"), context, "submit")
            except (self.api_error, self.forbidden_error):
                continue
            visible.append(form)
        return visible

    def get_form(self, form_id: object) -> dict:
        form = self._form_row(form_id)
        if not form:
            raise self.api_error("表单不存在。")
        return form

    def _form_permission_row(self, form_id: object, context: dict) -> dict | None:
        form_id_int = self.db.integer(form_id, 0)
        user_id = self._actor_id(context)
        role_code = self.db.text(context.get("role"))
        return self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'canView', can_view,
              'canSubmit', can_submit,
              'canUpdate', can_update,
              'canDelete', can_delete,
              'canApprove', can_approve,
              'canExport', can_export,
              'dataScope', data_scope
            )
            FROM service_form_permission permission
            LEFT JOIN auth_role role_row
              ON permission.subject_type = 'role'
             AND role_row.role_id = permission.subject_id
            WHERE permission.form_id = {form_id_int}
              AND (
                (permission.subject_type = 'user' AND permission.subject_id = {user_id})
                OR (
                  permission.subject_type = 'role'
                  AND role_row.role_code = {self.db.quote(role_code)}
                )
              )
            ORDER BY CASE WHEN permission.subject_type = 'user' THEN 0 ELSE 1 END
            LIMIT 1
            """,
            None,
        )

    def assert_form_permission(self, form_id: object, context: dict, action: str) -> None:
        if parse_bool(context.get("isSuperAdmin")):
            return
        row = self._form_permission_row(form_id, context)
        configured_count = self.db.scalar(
            f"SELECT COUNT(*) FROM service_form_permission WHERE form_id = {self.db.integer(form_id, 0)};"
        )
        if not row and configured_count == 0:
            return
        if not row:
            raise self.forbidden_error("This account is not authorized to use this form.")
        key = {
            "view": "canView",
            "submit": "canSubmit",
            "update": "canUpdate",
            "delete": "canDelete",
            "approve": "canApprove",
            "export": "canExport",
        }.get(action)
        if not key or not parse_bool(row.get(key)) or self.db.text(row.get("dataScope")) == "none":
            raise self.forbidden_error("This account is not authorized to use this form.")

    def list_form_permissions(self, form_id: object) -> list[dict]:
        form_id_int = self.db.integer(form_id, 0)
        self.get_form(form_id_int)
        return list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'subjectType', permission.subject_type,
                  'subjectId', CAST(permission.subject_id AS CHAR),
                  'subjectName', CASE
                    WHEN permission.subject_type = 'role' THEN COALESCE(role_row.role_name, '')
                    ELSE COALESCE(user_row.display_name, user_row.username, '')
                  END,
                  'canView', permission.can_view,
                  'canSubmit', permission.can_submit,
                  'canUpdate', permission.can_update,
                  'canDelete', permission.can_delete,
                  'canApprove', permission.can_approve,
                  'canExport', permission.can_export,
                  'dataScope', permission.data_scope
                )), JSON_ARRAY())
                FROM service_form_permission permission
                LEFT JOIN auth_role role_row
                  ON permission.subject_type = 'role' AND role_row.role_id = permission.subject_id
                LEFT JOIN user_account user_row
                  ON permission.subject_type = 'user' AND user_row.user_id = permission.subject_id
                WHERE permission.form_id = {form_id_int}
                ORDER BY permission.subject_type, permission.subject_id
                """,
                [],
            )
            or []
        )

    def replace_form_permissions(self, form_id: object, items: object, context: dict) -> list[dict]:
        if not parse_bool(context.get("isSuperAdmin")):
            raise self.forbidden_error("只有超级管理员可以配置表单权限。")
        form_id_int = self.db.integer(form_id, 0)
        self.get_form(form_id_int)
        if not isinstance(items, list):
            raise self.api_error("表单权限必须是数组。")
        rows: list[str] = []
        seen: set[tuple[str, int]] = set()
        for item in items:
            if not isinstance(item, dict):
                raise self.api_error("表单权限项格式无效。")
            subject_type = self.db.text(item.get("subjectType")).lower()
            subject_id = self.db.integer(item.get("subjectId"), 0)
            if subject_type not in {"role", "user"} or subject_id <= 0:
                raise self.api_error("表单权限对象无效。")
            key = (subject_type, subject_id)
            if key in seen:
                raise self.api_error("表单权限对象不能重复。")
            seen.add(key)
            table = "auth_role" if subject_type == "role" else "user_account"
            id_column = "role_id" if subject_type == "role" else "user_id"
            if self.db.scalar(f"SELECT COUNT(*) FROM {table} WHERE {id_column} = {subject_id} AND is_active = 1;") != 1:
                raise self.api_error("表单权限对象不存在或已停用。")
            scope = self.db.text(item.get("dataScope")) or "all"
            if scope not in {"all", "organization", "own", "submitted", "assigned", "none"}:
                raise self.api_error("表单数据范围无效。")
            rows.append(
                "("
                + ", ".join(
                    [
                        str(form_id_int),
                        self.db.quote(subject_type),
                        str(subject_id),
                        "1" if parse_bool(item.get("canView")) else "0",
                        "1" if parse_bool(item.get("canSubmit")) else "0",
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
            f"DELETE FROM service_form_permission WHERE form_id = {form_id_int}",
        ]
        if rows:
            statements.append(
                """
                INSERT INTO service_form_permission (
                  form_id, subject_type, subject_id, can_view, can_submit,
                  can_update, can_delete, can_approve, can_export, data_scope
                ) VALUES
                """
                + ", ".join(rows)
            )
        statements.append("COMMIT")
        self.db.execute(";\n".join(statements) + ";")
        return self.list_form_permissions(form_id_int)

    def create_form(self, payload: dict, context: dict) -> dict:
        code = self.db.text(payload.get("code")).lower()
        name = self.db.text(payload.get("name"))
        record_type = self.db.text(payload.get("recordType")).lower()
        if not re.fullmatch(r"[a-z][a-z0-9._-]{2,63}", code):
            raise self.api_error("表单编码格式无效。")
        if not name or record_type not in FORM_TYPES:
            raise self.api_error("表单名称和业务类型不能为空。")
        fields = self._validate_field_definitions(payload.get("fields", []))
        self._form_workflow_steps(payload.get("workflow"))
        if self.db.scalar(
            f"SELECT COUNT(*) FROM service_form WHERE form_code = {self.db.quote(code)};"
        ):
            raise self.api_error("表单编码已经存在。")
        form_id = self.db.one_id(
            f"""
            INSERT INTO service_form (
              form_code, form_name, record_type, description,
              layout_json, workflow_json, list_config_json, settings_json, created_by
            )
            VALUES (
              {self.db.quote(code)}, {self.db.quote(name)}, {self.db.quote(record_type)},
              {self.db.quote(payload.get('description'))},
              {self.db.json_value(payload.get('layout') or {})},
              {self.db.json_value(payload.get('workflow') or {})},
              {self.db.json_value(payload.get('listConfig') or {})},
              {self.db.json_value(payload.get('settings') or {})},
              {self._actor_id(context)}
            );
            SELECT LAST_INSERT_ID();
            """
        )
        self._replace_form_fields(form_id, fields)
        self._sync_form_workflow(form_id, code, name, record_type, payload.get("workflow"), context)
        return self.get_form(form_id)

    def update_form(self, form_id: object, payload: dict, context: dict) -> dict:
        existing = self.get_form(form_id)
        requested_code = self.db.text(payload.get("code")).lower()
        requested_record_type = self.db.text(payload.get("recordType")).lower()
        if requested_code and requested_code != self.db.text(existing.get("code")):
            raise self.api_error("已创建的表单不能修改编码。")
        if requested_record_type and requested_record_type != self.db.text(existing.get("recordType")):
            raise self.api_error("已创建的表单不能修改业务类型。")
        name = self.db.text(payload.get("name")) or self.db.text(existing.get("name"))
        description = self.db.text(payload.get("description"))
        fields = self._validate_field_definitions(payload.get("fields", existing.get("fields", [])))
        self.db.execute(
            f"""
            UPDATE service_form
            SET form_name = {self.db.quote(name)},
                description = {self.db.quote(description)},
                layout_json = {self.db.json_value(payload.get('layout') or existing.get('layout') or {})},
                workflow_json = {self.db.json_value(payload.get('workflow') or existing.get('workflow') or {})},
                list_config_json = {self.db.json_value(payload.get('listConfig') or existing.get('listConfig') or {})},
                settings_json = {self.db.json_value(payload.get('settings') or existing.get('settings') or {})},
                version_no = version_no + 1
            WHERE form_id = {self.db.integer(form_id, 0)};
            """
        )
        self._replace_form_fields(self.db.integer(form_id, 0), fields)
        self._sync_form_workflow(
            self.db.integer(form_id, 0),
            self.db.text(existing.get("code")),
            name,
            self.db.text(existing.get("recordType")),
            payload.get("workflow", existing.get("workflow") or {}),
            context,
        )
        return self.get_form(form_id)

    def _replace_form_fields(self, form_id: int, fields: list[dict]) -> None:
        rows = []
        for field in fields:
            rows.append(
                "("
                + ", ".join(
                    [
                        str(form_id),
                        self.db.quote(field["key"]),
                        self.db.quote(field["label"]),
                        self.db.quote(field["type"]),
                        self.db.quote(field["placeholder"]),
                        self.db.json_value(field["defaultValue"]) if field["defaultValue"] is not None else "NULL",
                        self.db.json_value(field["options"]) if field["options"] else "NULL",
                        self.db.json_value(field["config"]) if field.get("config") else "NULL",
                        "1" if field["required"] else "0",
                        "1" if field["readonly"] else "0",
                        str(max(0, field["sortOrder"])),
                    ]
                )
                + ")"
            )
        statements = [
            "START TRANSACTION",
            f"DELETE FROM service_form_field WHERE form_id = {form_id}",
        ]
        if rows:
            statements.append(
                """
                INSERT INTO service_form_field (
                  form_id, field_key, field_label, field_type, placeholder,
                  default_value, options_json, field_config, is_required, is_readonly, sort_order
                ) VALUES
                """
                + ", ".join(rows)
            )
        statements.append("COMMIT")
        self.db.execute(";\n".join(statements) + ";")

    def ticket_extension_values(self, payload: dict, priority: str, context: dict | None = None) -> dict:
        form_id, custom_fields = self._validated_custom_fields("ticket", payload, context)
        policy = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(sla_policy_id AS CHAR),
              'responseMinutes', response_minutes,
              'resolutionMinutes', resolution_minutes
            )
            FROM sla_policy
            WHERE priority = {self.db.quote(_priority_label(priority))}
              AND is_active = 1
            ORDER BY sla_policy_id
            LIMIT 1
            """,
            None,
        )
        return {"formId": form_id, "customFields": custom_fields, "sla": dict(policy or {})}

    def save_ticket_extension(self, ticket_id: int, extension: dict) -> None:
        sla = extension.get("sla") or {}
        form_id = self.db.integer(extension.get("formId"), 0)
        policy_id = self.db.integer(sla.get("id"), 0)
        response_minutes = self.db.integer(sla.get("responseMinutes"), 0)
        resolution_minutes = self.db.integer(sla.get("resolutionMinutes"), 0)
        form_sql = "NULL" if form_id <= 0 else str(form_id)
        policy_sql = "NULL" if policy_id <= 0 else str(policy_id)
        response_sql = "NULL" if response_minutes <= 0 else f"DATE_ADD(CURRENT_TIMESTAMP, INTERVAL {response_minutes} MINUTE)"
        resolution_sql = "NULL" if resolution_minutes <= 0 else f"DATE_ADD(CURRENT_TIMESTAMP, INTERVAL {resolution_minutes} MINUTE)"
        self.db.execute(
            f"""
            INSERT INTO service_ticket_extension (
              ticket_id, form_id, custom_fields, sla_policy_id, sla_started_at,
              response_due_at, resolution_due_at
            )
            VALUES (
              {ticket_id}, {form_sql}, {self.db.json_value(extension.get('customFields') or {})},
              {policy_sql}, CURRENT_TIMESTAMP, {response_sql}, {resolution_sql}
            )
            ON DUPLICATE KEY UPDATE
              form_id = VALUES(form_id),
              custom_fields = VALUES(custom_fields),
              sla_policy_id = VALUES(sla_policy_id),
              response_due_at = VALUES(response_due_at),
              resolution_due_at = VALUES(resolution_due_at);
            """
        )

    def ticket_extension_row(self, ticket_id: object) -> dict:
        return dict(
            self.db.json(
                f"""
                SELECT JSON_OBJECT(
                  'formId', COALESCE(CAST(extension.form_id AS CHAR), ''),
                  'formCode', COALESCE(form.form_code, ''),
                  'formName', COALESCE(form.form_name, ''),
                  'customFields', extension.custom_fields,
                  'slaPolicyId', COALESCE(CAST(extension.sla_policy_id AS CHAR), ''),
                  'slaStartedAt', COALESCE(CAST(extension.sla_started_at AS CHAR), ''),
                  'responseDueAt', COALESCE(CAST(extension.response_due_at AS CHAR), ''),
                  'resolutionDueAt', COALESCE(CAST(extension.resolution_due_at AS CHAR), ''),
                  'approvalStatus', extension.approval_status,
                  'slaState', CASE
                    WHEN extension.resolution_due_at IS NULL THEN 'not_configured'
                    WHEN ticket.status IN ('closed', 'cancelled') THEN 'stopped'
                    WHEN CURRENT_TIMESTAMP > extension.resolution_due_at THEN 'breached'
                    ELSE 'running'
                  END,
                  'slaRemainingMinutes', CASE
                    WHEN extension.resolution_due_at IS NULL THEN NULL
                    ELSE TIMESTAMPDIFF(MINUTE, CURRENT_TIMESTAMP, extension.resolution_due_at)
                  END
                )
                FROM service_ticket_extension extension
                JOIN itil_ticket ticket ON ticket.ticket_id = extension.ticket_id
                LEFT JOIN service_form form ON form.form_id = extension.form_id
                WHERE extension.ticket_id = {self.db.integer(ticket_id, 0)}
                """,
                None,
            )
            or {}
        )

    def _record_owner(self, record_type: str, record_id: int) -> tuple[int, int]:
        if record_type == "ticket":
            row = self.db.json(
                f"SELECT JSON_OBJECT('createdBy', COALESCE(created_by, 0), 'assignedTo', COALESCE(assigned_to_user_id, 0)) FROM itil_ticket WHERE ticket_id = {record_id}",
                None,
            )
        elif record_type == "change":
            row = self.db.json(
                f"SELECT JSON_OBJECT('createdBy', COALESCE(created_by, 0), 'assignedTo', COALESCE(assigned_to_user_id, 0)) FROM itil_change WHERE change_id = {record_id}",
                None,
            )
        elif record_type == "problem":
            row = self.db.json(
                f"SELECT JSON_OBJECT('createdBy', COALESCE(created_by, 0), 'assignedTo', COALESCE(assigned_to_user_id, 0)) FROM itil_problem WHERE problem_id = {record_id}",
                None,
            )
        else:
            row = None
        return (
            self.db.integer((row or {}).get("createdBy"), 0),
            self.db.integer((row or {}).get("assignedTo"), 0),
        )

    def notify_record_change(self, record_type: str, record_id: int, title: str, content: str) -> None:
        created_by, assigned_to = self._record_owner(record_type, record_id)
        recipients = sorted({item for item in (created_by, assigned_to) if item > 0})
        if not recipients:
            recipients = [
                self.db.integer(item.get("id"), 0)
                for item in (
                    self.db.json(
                        """
                        SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT('id', CAST(user_id AS CHAR))), JSON_ARRAY())
                        FROM user_account
                        WHERE is_active = 1 AND user_role IN ('admin', 'operator')
                        """,
                        [],
                    )
                    or []
                )
            ]
        rows = [
            "("
            + ", ".join(
                [
                    str(user_id),
                    self.db.quote(record_type),
                    str(record_id),
                    self.db.quote("status_change"),
                    self.db.quote(title),
                    self.db.quote(content),
                ]
            )
            + ")"
            for user_id in recipients
            if user_id > 0
        ]
        if rows:
            self.db.execute(
                """
                INSERT INTO service_notification (
                  recipient_user_id, record_type, record_id, notification_type, title, content
                ) VALUES
                """
                + ", ".join(rows)
                + ";"
            )

    def _assert_org_access(self, context: dict, org_id: object) -> None:
        self.scope.assert_org_access(context, org_id)

    def _change_row(self, change_id: object) -> dict:
        row = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(change_row.change_id AS CHAR),
              'number', change_row.change_number,
              'title', change_row.title,
              'description', change_row.description,
              'type', change_row.change_type,
              'status', change_row.status,
              'impact', change_row.impact,
              'risk', change_row.risk,
              'plannedStartAt', COALESCE(CAST(change_row.planned_start_at AS CHAR), ''),
              'plannedEndAt', COALESCE(CAST(change_row.planned_end_at AS CHAR), ''),
              'assignedToUserId', COALESCE(CAST(change_row.assigned_to_user_id AS CHAR), ''),
              'assignedToName', COALESCE(assignee.display_name, ''),
              'requesterEmployeeId', COALESCE(CAST(change_row.requester_employee_id AS CHAR), ''),
              'orgId', COALESCE(CAST(change_row.org_unit_id AS CHAR), ''),
              'orgName', COALESCE(org.org_name, ''),
              'relatedTicketId', COALESCE(CAST(change_row.related_ticket_id AS CHAR), ''),
              'formId', COALESCE(CAST(change_row.form_id AS CHAR), ''),
              'customFields', change_row.custom_fields,
              'createdByUserId', COALESCE(CAST(change_row.created_by AS CHAR), ''),
              'createdAt', CAST(change_row.created_at AS CHAR),
              'updatedAt', CAST(change_row.updated_at AS CHAR)
            )
            FROM itil_change change_row
            LEFT JOIN user_account assignee ON assignee.user_id = change_row.assigned_to_user_id
            LEFT JOIN org_unit org ON org.org_unit_id = change_row.org_unit_id
            WHERE change_row.change_id = {self.db.integer(change_id, 0)}
            """,
            None,
        )
        if not row:
            raise self.api_error("变更记录不存在。")
        return dict(row)

    def _assert_record_access(self, context: dict, module_code: str, row: dict) -> None:
        self._assert_org_access(context, row.get("orgId"))
        scope = self._scope(context, module_code)
        actor_id = self._actor_id(context)
        if scope in {"own", "submitted"} and self.db.integer(row.get("createdByUserId"), 0) != actor_id:
            raise self.api_error("当前账号只能访问本人提交的数据。")
        if scope == "assigned" and self.db.integer(row.get("assignedToUserId"), 0) != actor_id:
            raise self.api_error("当前账号只能访问本人负责的数据。")

    def list_changes(self, context: dict) -> list[dict]:
        scope = self._scope(context, "changes")
        condition = "1 = 1"
        actor_id = self._actor_id(context)
        if scope in {"own", "submitted"}:
            condition += f" AND change_row.created_by = {actor_id}"
        elif scope == "assigned":
            condition += f" AND change_row.assigned_to_user_id = {actor_id}"
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', CAST(change_row.change_id AS CHAR),
              'number', change_row.change_number,
              'title', change_row.title,
              'type', change_row.change_type,
              'status', change_row.status,
              'impact', change_row.impact,
              'risk', change_row.risk,
              'assignedToName', COALESCE(assignee.display_name, ''),
              'orgId', COALESCE(CAST(change_row.org_unit_id AS CHAR), ''),
              'orgName', COALESCE(org.org_name, ''),
              'createdAt', CAST(change_row.created_at AS CHAR),
              'updatedAt', CAST(change_row.updated_at AS CHAR)
            )), JSON_ARRAY())
            FROM (
              SELECT change_row.*
              FROM itil_change change_row
              WHERE {condition}
              ORDER BY FIELD(change_row.status, 'submitted', 'assessing', 'scheduled', 'implementing', 'verified', 'draft', 'closed'),
                       change_row.updated_at DESC
              LIMIT 500
            ) change_row
            LEFT JOIN user_account assignee ON assignee.user_id = change_row.assigned_to_user_id
            LEFT JOIN org_unit org ON org.org_unit_id = change_row.org_unit_id
            """,
            [],
        )
        records = list(rows or [])
        allowed = self.scope.permitted_org_ids(context)
        return records if allowed is None else [item for item in records if self.db.integer(item.get("orgId"), 0) in allowed]

    def create_change(self, payload: dict, context: dict) -> dict:
        title = self.db.text(payload.get("title"))
        description = self.db.text(payload.get("description"))
        if not title or not description:
            raise self.api_error("变更标题和说明不能为空。")
        change_type = self.db.text(payload.get("type")) or "normal"
        if change_type not in {"standard", "normal", "emergency"}:
            raise self.api_error("变更类型无效。")
        impact = _priority_label(payload.get("impact"))
        risk = _priority_label(payload.get("risk"))
        form_id, custom_fields = self._validated_custom_fields("change", payload, context)
        org_id, requester_id, assignee_id, related_ticket_id = self._record_create_context(
            "changes",
            payload,
            context,
            includes_requester=True,
        )
        change_id = self.db.one_id(
            f"""
            INSERT INTO itil_change (
              title, description, change_type, status, impact, risk,
              planned_start_at, planned_end_at, assigned_to_user_id,
              requester_employee_id, org_unit_id, related_ticket_id,
              form_id, custom_fields, created_by
            )
            VALUES (
              {self.db.quote(title)}, {self.db.quote(description)}, {self.db.quote(change_type)}, 'draft',
              {self.db.quote(impact)}, {self.db.quote(risk)},
              {self.db.quote(payload.get('plannedStartAt')) if self.db.text(payload.get('plannedStartAt')) else 'NULL'},
              {self.db.quote(payload.get('plannedEndAt')) if self.db.text(payload.get('plannedEndAt')) else 'NULL'},
              {assignee_id or 'NULL'},
              {requester_id or 'NULL'},
              {org_id or 'NULL'}, {related_ticket_id or 'NULL'},
              {form_id or 'NULL'}, {self.db.json_value(custom_fields)}, {self._actor_id(context)}
            );
            SET @change_id = LAST_INSERT_ID();
            UPDATE itil_change
            SET change_number = CONCAT('CHG-', DATE_FORMAT(CURRENT_DATE, '%Y'), '-', LPAD(@change_id, 6, '0'))
            WHERE change_id = @change_id;
            SELECT @change_id;
            """
        )
        self.notify_record_change("change", change_id, "新建变更", f"变更 {change_id} 已创建，等待评估。")
        return self._change_row(change_id)

    def transition_change(self, change_id: object, payload: dict, context: dict) -> dict:
        current = self._change_row(change_id)
        self._assert_record_access(context, "changes", current)
        next_status = self.db.text(payload.get("status"))
        current_status = self.db.text(current.get("status"))
        if next_status not in CHANGE_TRANSITIONS.get(current_status, set()):
            raise self.conflict_error(f"变更状态不允许从 {current_status} 转为 {next_status}。")
        approval = self.get_approval_for_record("change", self.db.integer(change_id, 0))
        approval_status = self.db.text((approval or {}).get("status"))
        if approval_status == "pending" and next_status != "cancelled":
            raise self.conflict_error("该变更正在审批，审批完成前只能取消。")
        if approval_status == "rejected" and next_status not in {"draft", "cancelled"}:
            raise self.conflict_error("该变更已被驳回，请回退到草稿后重新提交。")
        if next_status == "submitted":
            output = self.db.execute(
                f"""
                START TRANSACTION;
                UPDATE itil_change
                SET status = 'submitted'
                WHERE change_id = {self.db.integer(change_id, 0)}
                  AND status = {self.db.quote(current_status)};
                SET @changed_count = ROW_COUNT();
                SELECT @changed_count;
                COMMIT;
                """
            )
            changed_count = self.db.integer(output.splitlines()[-1] if output else 0, 0)
            if changed_count != 1:
                raise self.conflict_error("Change changed by another request. Reload and try again.")
            self.start_approval("change", self.db.integer(change_id, 0), context)
        else:
            values = [f"status = {self.db.quote(next_status)}"]
            if "assignedToUserId" in payload:
                assignee_id = self._validated_assignee_id(payload.get("assignedToUserId"))
                values.append(f"assigned_to_user_id = {assignee_id or 'NULL'}")
            output = self.db.execute(
                f"""
                START TRANSACTION;
                UPDATE itil_change
                SET {", ".join(values)}
                WHERE change_id = {self.db.integer(change_id, 0)}
                  AND status = {self.db.quote(current_status)};
                SET @changed_count = ROW_COUNT();
                SELECT @changed_count;
                COMMIT;
                """
            )
            changed_count = self.db.integer(output.splitlines()[-1] if output else 0, 0)
            if changed_count != 1:
                raise self.conflict_error("Change changed by another request. Reload and try again.")
        self.notify_record_change("change", self.db.integer(change_id, 0), "变更状态更新", f"变更状态已更新为 {next_status}。")
        return self._change_row(change_id)

    def list_problems(self, context: dict) -> list[dict]:
        scope = self._scope(context, "problems")
        condition = "1 = 1"
        actor_id = self._actor_id(context)
        if scope in {"own", "submitted"}:
            condition += f" AND problem.created_by = {actor_id}"
        elif scope == "assigned":
            condition += f" AND problem.assigned_to_user_id = {actor_id}"
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', CAST(problem.problem_id AS CHAR),
              'number', problem.problem_number,
              'title', problem.title,
              'status', problem.status,
              'impact', problem.impact,
              'assignedToName', COALESCE(assignee.display_name, ''),
              'orgId', COALESCE(CAST(problem.org_unit_id AS CHAR), ''),
              'orgName', COALESCE(org.org_name, ''),
              'createdAt', CAST(problem.created_at AS CHAR),
              'updatedAt', CAST(problem.updated_at AS CHAR)
            )), JSON_ARRAY())
            FROM (
              SELECT *
              FROM itil_problem problem
              WHERE {condition}
              ORDER BY problem.updated_at DESC
              LIMIT 500
            ) problem
            LEFT JOIN user_account assignee ON assignee.user_id = problem.assigned_to_user_id
            LEFT JOIN org_unit org ON org.org_unit_id = problem.org_unit_id
            """,
            [],
        )
        records = list(rows or [])
        allowed = self.scope.permitted_org_ids(context)
        return records if allowed is None else [item for item in records if self.db.integer(item.get("orgId"), 0) in allowed]

    def _problem_row(self, problem_id: object) -> dict:
        row = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(problem.problem_id AS CHAR),
              'number', problem.problem_number,
              'title', problem.title,
              'description', problem.description,
              'status', problem.status,
              'impact', problem.impact,
              'rootCause', COALESCE(problem.root_cause, ''),
              'workaround', COALESCE(problem.workaround, ''),
              'resolution', COALESCE(problem.resolution, ''),
              'assignedToUserId', COALESCE(CAST(problem.assigned_to_user_id AS CHAR), ''),
              'assignedToName', COALESCE(assignee.display_name, ''),
              'orgId', COALESCE(CAST(problem.org_unit_id AS CHAR), ''),
              'orgName', COALESCE(org.org_name, ''),
              'relatedTicketId', COALESCE(CAST(problem.related_ticket_id AS CHAR), ''),
              'formId', COALESCE(CAST(problem.form_id AS CHAR), ''),
              'customFields', problem.custom_fields,
              'createdByUserId', COALESCE(CAST(problem.created_by AS CHAR), ''),
              'createdAt', CAST(problem.created_at AS CHAR),
              'updatedAt', CAST(problem.updated_at AS CHAR)
            )
            FROM itil_problem problem
            LEFT JOIN user_account assignee ON assignee.user_id = problem.assigned_to_user_id
            LEFT JOIN org_unit org ON org.org_unit_id = problem.org_unit_id
            WHERE problem.problem_id = {self.db.integer(problem_id, 0)}
            """,
            None,
        )
        if not row:
            raise self.api_error("问题记录不存在。")
        return dict(row)

    def create_problem(self, payload: dict, context: dict) -> dict:
        title = self.db.text(payload.get("title"))
        description = self.db.text(payload.get("description"))
        if not title or not description:
            raise self.api_error("问题标题和说明不能为空。")
        impact = _priority_label(payload.get("impact"))
        form_id, custom_fields = self._validated_custom_fields("problem", payload, context)
        org_id, _, assignee_id, related_ticket_id = self._record_create_context(
            "problems",
            payload,
            context,
            includes_requester=False,
        )
        problem_id = self.db.one_id(
            f"""
            INSERT INTO itil_problem (
              title, description, status, impact, assigned_to_user_id, org_unit_id,
              related_ticket_id, form_id, custom_fields, created_by
            )
            VALUES (
              {self.db.quote(title)}, {self.db.quote(description)}, 'new', {self.db.quote(impact)},
              {assignee_id or 'NULL'},
              {org_id or 'NULL'}, {related_ticket_id or 'NULL'},
              {form_id or 'NULL'}, {self.db.json_value(custom_fields)}, {self._actor_id(context)}
            );
            SET @problem_id = LAST_INSERT_ID();
            UPDATE itil_problem
            SET problem_number = CONCAT('PRB-', DATE_FORMAT(CURRENT_DATE, '%Y'), '-', LPAD(@problem_id, 6, '0'))
            WHERE problem_id = @problem_id;
            SELECT @problem_id;
            """
        )
        self.notify_record_change("problem", problem_id, "新建问题", f"问题 {problem_id} 已创建。")
        self.start_approval("problem", problem_id, context)
        return self._problem_row(problem_id)

    def transition_problem(self, problem_id: object, payload: dict, context: dict) -> dict:
        current = self._problem_row(problem_id)
        self._assert_record_access(context, "problems", current)
        next_status = self.db.text(payload.get("status"))
        current_status = self.db.text(current.get("status"))
        if next_status not in PROBLEM_TRANSITIONS.get(current_status, set()):
            raise self.conflict_error(f"问题状态不允许从 {current_status} 转为 {next_status}。")
        approval = self.get_approval_for_record("problem", self.db.integer(problem_id, 0))
        approval_status = self.db.text((approval or {}).get("status"))
        if approval_status == "pending" and next_status != "cancelled":
            raise self.conflict_error("该问题正在审批，审批完成前只能取消。")
        if approval_status == "rejected" and next_status not in {"new", "cancelled"}:
            raise self.conflict_error("该问题已被驳回，请回退到新建后重新处理。")
        if next_status == "resolved" and not self.db.text(
            payload.get("resolution") or current.get("resolution")
        ):
            raise self.api_error("A resolution is required before resolving a problem.")
        values = [f"status = {self.db.quote(next_status)}"]
        if "assignedToUserId" in payload:
            assignee_id = self._validated_assignee_id(payload.get("assignedToUserId"))
            values.append(f"assigned_to_user_id = {assignee_id or 'NULL'}")
        for key, column in (("rootCause", "root_cause"), ("workaround", "workaround"), ("resolution", "resolution")):
            if key in payload:
                values.append(f"{column} = {self.db.quote(payload.get(key))}")
        output = self.db.execute(
            f"""
            START TRANSACTION;
            UPDATE itil_problem
            SET {", ".join(values)}
            WHERE problem_id = {self.db.integer(problem_id, 0)}
              AND status = {self.db.quote(current_status)};
            SET @changed_count = ROW_COUNT();
            SELECT @changed_count;
            COMMIT;
            """
        )
        changed_count = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        if changed_count != 1:
            raise self.conflict_error("Problem changed by another request. Reload and try again.")
        self.notify_record_change("problem", self.db.integer(problem_id, 0), "问题状态更新", f"问题状态已更新为 {next_status}。")
        return self._problem_row(problem_id)

    def _assert_article_scope(self, article: dict, context: dict) -> None:
        if parse_bool(context.get("isSuperAdmin")):
            return
        scope = self._scope(context, "knowledge")
        actor_id = self._actor_id(context)
        owner_ids = {
            self.db.integer(article.get("ownerUserId"), 0),
            self.db.integer(article.get("createdByUserId"), 0),
        }
        owner_ids.discard(0)
        if scope == "none":
            raise self.forbidden_error("This account is not authorized to access knowledge articles.")
        if scope in {"own", "submitted", "assigned"} and actor_id not in owner_ids:
            raise self.forbidden_error("This account can only access its own knowledge articles.")
        if scope == "organization":
            self.scope.assert_org_access(context, article.get("ownerOrgId"))

    def assert_article_read_access(self, article: dict, context: dict) -> None:
        self._assert_article_scope(article, context)
        if parse_bool(context.get("isSuperAdmin")):
            return
        actor_id = self._actor_id(context)
        owner_ids = {
            self.db.integer(article.get("ownerUserId"), 0),
            self.db.integer(article.get("createdByUserId"), 0),
        }
        owner_ids.discard(0)
        if self.db.text(article.get("status")) != "published" and actor_id not in owner_ids:
            raise self.forbidden_error("This knowledge article is not published.")
        visibility = self.db.text(article.get("visibility")) or "all"
        if visibility == "private" and actor_id not in owner_ids:
            raise self.forbidden_error("This knowledge article is private.")
        if visibility == "operator" and actor_id not in owner_ids:
            if self.db.text(context.get("role")) not in {"admin", "operator"}:
                raise self.forbidden_error("This knowledge article is restricted to service operators.")

    def list_articles(self, params: dict[str, list[str]], context: dict) -> list[dict]:
        keyword = self.db.text((params.get("q") or [""])[0])
        condition = "1 = 1"
        if keyword:
            safe = self.db.quote(f"%{keyword}%")
            condition += f" AND (article.title LIKE {safe} OR article.summary LIKE {safe} OR article.body LIKE {safe})"
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', CAST(article.article_id AS CHAR),
              'number', article.article_number,
              'title', article.title,
              'summary', article.summary,
              'category', article.category,
              'status', article.status,
              'visibility', article.visibility,
              'ownerUserId', COALESCE(CAST(article.owner_user_id AS CHAR), ''),
              'createdByUserId', COALESCE(CAST(article.created_by AS CHAR), ''),
              'ownerOrgId', COALESCE(CAST(COALESCE(owner_employee.org_unit_id, creator_employee.org_unit_id) AS CHAR), ''),
              'ownerName', COALESCE(owner.display_name, ''),
              'updatedAt', CAST(article.updated_at AS CHAR)
            )), JSON_ARRAY())
            FROM (
              SELECT *
              FROM knowledge_article article
              WHERE {condition}
              ORDER BY article.updated_at DESC
              LIMIT 500
            ) article
            LEFT JOIN user_account owner ON owner.user_id = article.owner_user_id
            LEFT JOIN employee owner_employee ON owner_employee.employee_id = owner.employee_id
            LEFT JOIN user_account creator ON creator.user_id = article.created_by
            LEFT JOIN employee creator_employee ON creator_employee.employee_id = creator.employee_id
            """,
            [],
        )
        visible: list[dict] = []
        for row in rows or []:
            item = dict(row)
            try:
                self.assert_article_read_access(item, context)
            except self.forbidden_error:
                continue
            visible.append(item)
        return visible

    def article(self, article_id: object) -> dict:
        row = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(article.article_id AS CHAR),
              'number', article.article_number,
              'title', article.title,
              'summary', article.summary,
              'body', article.body,
              'category', article.category,
              'status', article.status,
              'visibility', article.visibility,
              'ownerUserId', COALESCE(CAST(article.owner_user_id AS CHAR), ''),
              'ownerName', COALESCE(owner.display_name, ''),
              'createdByUserId', COALESCE(CAST(article.created_by AS CHAR), ''),
              'ownerOrgId', COALESCE(CAST(COALESCE(owner_employee.org_unit_id, creator_employee.org_unit_id) AS CHAR), ''),
              'updatedAt', CAST(article.updated_at AS CHAR),
              'publishedAt', COALESCE(CAST(article.published_at AS CHAR), '')
            )
            FROM knowledge_article article
            LEFT JOIN user_account owner ON owner.user_id = article.owner_user_id
            LEFT JOIN employee owner_employee ON owner_employee.employee_id = owner.employee_id
            LEFT JOIN user_account creator ON creator.user_id = article.created_by
            LEFT JOIN employee creator_employee ON creator_employee.employee_id = creator.employee_id
            WHERE article.article_id = {self.db.integer(article_id, 0)}
            """,
            None,
        )
        if not row:
            raise self.api_error("知识文章不存在。")
        return dict(row)

    def create_article(self, payload: dict, context: dict) -> dict:
        title = self.db.text(payload.get("title"))
        body = self.db.text(payload.get("body"))
        if not title or not body:
            raise self.api_error("知识文章标题和正文不能为空。")
        visibility = self.db.text(payload.get("visibility")) or "all"
        if visibility not in {"all", "operator", "private"}:
            raise self.api_error("Knowledge visibility is invalid.")
        owner_user_id = self.db.integer(payload.get("ownerUserId"), 0) or self._actor_id(context)
        if self.db.scalar(
            f"SELECT COUNT(*) FROM user_account WHERE user_id = {owner_user_id} AND is_active = 1;"
        ) != 1:
            raise self.api_error("Knowledge article owner does not exist.")
        scope = self._scope(context, "knowledge")
        if scope in {"own", "submitted", "assigned"} and owner_user_id != self._actor_id(context):
            raise self.forbidden_error("This account can only create knowledge articles for itself.")
        if scope == "organization":
            owner_org_id = self.db.scalar(
                f"""
                SELECT COALESCE(employee.org_unit_id, 0)
                FROM user_account user_row
                LEFT JOIN employee ON employee.employee_id = user_row.employee_id
                WHERE user_row.user_id = {owner_user_id};
                """
            )
            self.scope.assert_org_access(context, owner_org_id)
        article_id = self.db.one_id(
            f"""
            INSERT INTO knowledge_article (
              title, summary, body, category, status, visibility,
              owner_user_id, created_by, updated_by
            )
            VALUES (
              {self.db.quote(title)}, {self.db.quote(payload.get('summary'))},
              {self.db.quote(body)}, {self.db.quote(payload.get('category') or '通用')},
              'draft', {self.db.quote(visibility)},
              {owner_user_id},
              {self._actor_id(context)}, {self._actor_id(context)}
            );
            SET @article_id = LAST_INSERT_ID();
            UPDATE knowledge_article
            SET article_number = CONCAT('KB-', DATE_FORMAT(CURRENT_DATE, '%Y'), '-', LPAD(@article_id, 6, '0'))
            WHERE article_id = @article_id;
            SELECT @article_id;
            """
        )
        return self.article(article_id)

    def update_article(self, article_id: object, payload: dict, context: dict) -> dict:
        existing = self.article(article_id)
        self._assert_article_scope(existing, context)
        visibility = self.db.text(payload.get("visibility")) or self.db.text(existing.get("visibility")) or "all"
        if visibility not in {"all", "operator", "private"}:
            raise self.api_error("Knowledge visibility is invalid.")
        self.db.execute(
            f"""
            UPDATE knowledge_article
            SET title = {self.db.quote(payload.get('title') or existing.get('title'))},
                summary = {self.db.quote(payload.get('summary') if 'summary' in payload else existing.get('summary'))},
                body = {self.db.quote(payload.get('body') or existing.get('body'))},
                category = {self.db.quote(payload.get('category') or existing.get('category'))},
                visibility = {self.db.quote(visibility)},
                updated_by = {self._actor_id(context)}
            WHERE article_id = {self.db.integer(article_id, 0)};
            """
        )
        return self.article(article_id)

    def transition_article(self, article_id: object, payload: dict, context: dict) -> dict:
        current = self.article(article_id)
        self._assert_article_scope(current, context)
        next_status = self.db.text(payload.get("status"))
        current_status = self.db.text(current.get("status"))
        if next_status not in KNOWLEDGE_TRANSITIONS.get(current_status, set()):
            raise self.conflict_error(f"知识文章状态不允许从 {current_status} 转为 {next_status}。")
        published_sql = "CURRENT_TIMESTAMP" if next_status == "published" else "NULL"
        self.db.execute(
            f"""
            UPDATE knowledge_article
            SET status = {self.db.quote(next_status)},
                published_at = {published_sql},
                updated_by = {self._actor_id(context)}
            WHERE article_id = {self.db.integer(article_id, 0)}
              AND status = {self.db.quote(current_status)};
            """
        )
        return self.article(article_id)

    def list_sla_policies(self) -> list[dict]:
        return list(
            self.db.json(
                """
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(sla_policy_id AS CHAR),
                  'code', policy_code,
                  'name', policy_name,
                  'priority', priority,
                  'responseMinutes', response_minutes,
                  'resolutionMinutes', resolution_minutes,
                  'isActive', is_active
                )), JSON_ARRAY())
                FROM sla_policy
                ORDER BY priority DESC, sla_policy_id
                """,
                [],
            )
            or []
        )

    def save_sla_policy(self, payload: dict, context: dict, policy_id: object = 0) -> dict:
        code = self.db.text(payload.get("code")).lower()
        name = self.db.text(payload.get("name"))
        priority = _priority_label(payload.get("priority"))
        response = self.db.integer(payload.get("responseMinutes"), 0)
        resolution = self.db.integer(payload.get("resolutionMinutes"), 0)
        if not re.fullmatch(r"[a-z][a-z0-9._-]{2,63}", code) or not name or response <= 0 or resolution <= 0:
            raise self.api_error("SLA 编码、名称和时长必须有效。")
        policy_id_int = self.db.integer(policy_id, 0)
        if policy_id_int and not self.db.scalar(
            f"SELECT COUNT(*) FROM sla_policy WHERE sla_policy_id = {policy_id_int};"
        ):
            raise self.api_error("SLA 策略不存在。")
        if self.db.scalar(
            f"""
            SELECT COUNT(*)
            FROM sla_policy
            WHERE policy_code = {self.db.quote(code)}
              AND sla_policy_id <> {policy_id_int};
            """
        ):
            raise self.api_error("SLA 编码已经存在。")
        if policy_id_int:
            self.db.execute(
                f"""
                UPDATE sla_policy
                SET policy_code = {self.db.quote(code)}, policy_name = {self.db.quote(name)},
                    priority = {self.db.quote(priority)}, response_minutes = {response},
                    resolution_minutes = {resolution}, is_active = {1 if parse_bool(payload.get('isActive'), True) else 0}
                WHERE sla_policy_id = {policy_id_int};
                """
            )
        else:
            policy_id_int = self.db.one_id(
                f"""
                INSERT INTO sla_policy (
                  policy_code, policy_name, priority, response_minutes, resolution_minutes, is_active, created_by
                )
                VALUES (
                  {self.db.quote(code)}, {self.db.quote(name)}, {self.db.quote(priority)},
                  {response}, {resolution}, {1 if parse_bool(payload.get('isActive'), True) else 0}, {self._actor_id(context)}
                );
                SELECT LAST_INSERT_ID();
                """
            )
        return next((item for item in self.list_sla_policies() if self.db.integer(item.get("id"), 0) == policy_id_int), {})

    def _workflow_row(self, workflow_id: object) -> dict:
        workflow_id_int = self.db.integer(workflow_id, 0)
        row = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(workflow_id AS CHAR),
              'code', workflow_code,
              'name', workflow_name,
              'recordType', record_type,
              'isActive', is_active,
              'createdAt', CAST(created_at AS CHAR),
              'updatedAt', CAST(updated_at AS CHAR)
            )
            FROM service_workflow
            WHERE workflow_id = {workflow_id_int}
            """,
            None,
        )
        if not row:
            raise self.api_error("审批流程不存在。")
        result = dict(row)
        result["steps"] = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(step_id AS CHAR),
                  'order', step_order,
                  'name', step_name,
                  'approverUserId', COALESCE(CAST(approver_user_id AS CHAR), ''),
                  'approverRoleCode', COALESCE(approver_role_code, ''),
                  'required', is_required
                )), JSON_ARRAY())
                FROM (
                  SELECT *
                  FROM service_workflow_step
                  WHERE workflow_id = {workflow_id_int}
                  ORDER BY step_order, step_id
                ) ordered_steps
                """,
                [],
            )
            or []
        )
        return result

    def _validate_workflow_steps(self, steps: object) -> list[dict]:
        if not isinstance(steps, list) or not steps:
            raise self.api_error("审批流程至少需要一个审批步骤。")
        if len(steps) > 20:
            raise self.api_error("单个审批流程最多支持 20 个步骤。")
        output: list[dict] = []
        for index, item in enumerate(steps):
            if not isinstance(item, dict):
                raise self.api_error("审批步骤必须是对象。")
            name = self.db.text(item.get("name")) or f"第 {index + 1} 级审批"
            user_id = self.db.integer(item.get("approverUserId"), 0)
            role_code = self.db.text(item.get("approverRoleCode")).lower()
            if bool(user_id) == bool(role_code):
                raise self.api_error("每个审批步骤必须指定一个用户或一个角色。")
            if user_id and self.db.scalar(
                f"SELECT COUNT(*) FROM user_account WHERE user_id = {user_id} AND is_active = 1;"
            ) != 1:
                raise self.api_error(f"审批用户不存在或已停用：第 {index + 1} 步。")
            if role_code and self.db.scalar(
                f"""
                SELECT COUNT(*)
                FROM auth_role
                WHERE role_code = {self.db.quote(role_code)}
                  AND is_active = 1;
                """
            ) != 1:
                raise self.api_error(f"审批角色不存在或已停用：第 {index + 1} 步。")
            output.append(
                {
                    "name": name,
                    "approverUserId": user_id,
                    "approverRoleCode": role_code,
                    "required": parse_bool(item.get("required"), True),
                    "order": index + 1,
                }
            )
        return output

    def _replace_workflow_steps(self, workflow_id: int, steps: list[dict]) -> None:
        rows = [
            "("
            + ", ".join(
                [
                    str(workflow_id),
                    str(step["order"]),
                    self.db.quote(step["name"]),
                    str(step["approverUserId"]) if step["approverUserId"] else "NULL",
                    self.db.quote(step["approverRoleCode"]) if step["approverRoleCode"] else "NULL",
                    "1" if step["required"] else "0",
                ]
            )
            + ")"
            for step in steps
        ]
        self.db.execute(
            f"""
            START TRANSACTION;
            DELETE FROM service_workflow_step WHERE workflow_id = {workflow_id};
            INSERT INTO service_workflow_step (
              workflow_id, step_order, step_name, approver_user_id, approver_role_code, is_required
            )
            VALUES {", ".join(rows)};
            COMMIT;
            """
        )

    def _form_workflow_steps(self, workflow: object) -> list[dict]:
        if workflow in (None, {}):
            return []
        if not isinstance(workflow, dict):
            raise self.api_error("表单流程必须是对象。")
        raw_steps = workflow.get("steps", [])
        if not isinstance(raw_steps, list):
            raise self.api_error("表单流程步骤必须是数组。")
        executable_steps: list[dict] = []
        for item in raw_steps:
            if not isinstance(item, dict):
                raise self.api_error("表单流程步骤必须是对象。")
            node_type = self.db.text(item.get("nodeType")) or "approval"
            if node_type not in {"handler", "approval", "cc"}:
                raise self.api_error("表单流程节点类型无效。")
            if node_type == "cc":
                continue
            executable_steps.append(item)
        return self._validate_workflow_steps(executable_steps) if executable_steps else []

    def _sync_form_workflow(
        self,
        form_id: int,
        form_code: str,
        form_name: str,
        record_type: str,
        workflow: object,
        context: dict,
    ) -> None:
        steps = self._form_workflow_steps(workflow)
        existing_workflow_id = self.db.integer(
            self.db.scalar(
                f"SELECT COALESCE(workflow_id, 0) FROM service_form WHERE form_id = {form_id};"
            ),
            0,
        )
        if not steps:
            if existing_workflow_id:
                self.db.execute(
                    f"""
                    UPDATE service_workflow
                    SET is_active = 0
                    WHERE workflow_id = {existing_workflow_id};
                    UPDATE service_form
                    SET workflow_id = NULL
                    WHERE form_id = {form_id};
                    """
                )
            return

        workflow_name = f"{form_name} - 表单审批流程"
        if existing_workflow_id:
            existing = self._workflow_row(existing_workflow_id)
            existing_steps = [
                {
                    "name": self.db.text(item.get("name")),
                    "approverUserId": self.db.integer(item.get("approverUserId"), 0),
                    "approverRoleCode": self.db.text(item.get("approverRoleCode")).lower(),
                    "required": parse_bool(item.get("required"), True),
                    "order": index + 1,
                }
                for index, item in enumerate(existing.get("steps") or [])
            ]
            if steps != existing_steps and self.db.scalar(
                f"""
                SELECT COUNT(*)
                FROM service_approval
                WHERE workflow_id = {existing_workflow_id}
                  AND status = 'pending';
                """
            ):
                raise self.conflict_error("该表单存在待处理审批，完成或取消后才能调整流程。")
            self.db.execute(
                f"""
                UPDATE service_workflow
                SET workflow_name = {self.db.quote(workflow_name)},
                    record_type = {self.db.quote(record_type)},
                    is_active = 1
                WHERE workflow_id = {existing_workflow_id};
                """
            )
            self._replace_workflow_steps(existing_workflow_id, steps)
            return

        workflow_id = self.db.one_id(
            f"""
            INSERT INTO service_workflow (
              workflow_code, workflow_name, record_type, is_active, created_by
            )
            VALUES (
              {self.db.quote(f"form_{form_id}")}, {self.db.quote(workflow_name)},
              {self.db.quote(record_type)}, 1, {self._actor_id(context)}
            );
            SELECT LAST_INSERT_ID();
            """
        )
        self._replace_workflow_steps(workflow_id, steps)
        self.db.execute(
            f"""
            UPDATE service_form
            SET workflow_id = {workflow_id}
            WHERE form_id = {form_id};
            """
        )

    def list_workflows(self) -> list[dict]:
        workflow_ids = self.db.json(
            """
            SELECT COALESCE(JSON_ARRAYAGG(CAST(workflow_id AS CHAR)), JSON_ARRAY())
            FROM (
              SELECT workflow_id
              FROM service_workflow workflow
              WHERE NOT EXISTS (
                SELECT 1
                FROM service_form form
                WHERE form.workflow_id = workflow.workflow_id
              )
              ORDER BY record_type, is_active DESC, workflow_id
            ) ordered_workflows
            """,
            [],
        )
        return [self._workflow_row(workflow_id) for workflow_id in workflow_ids or []]

    def save_workflow(self, payload: dict, context: dict, workflow_id: object = 0) -> dict:
        workflow_id_int = self.db.integer(workflow_id, 0)
        if workflow_id_int:
            if self.db.scalar(
                f"SELECT COUNT(*) FROM service_form WHERE workflow_id = {workflow_id_int};"
            ):
                raise self.forbidden_error("表单绑定的流程只能在表单设计中维护。")
            existing = self._workflow_row(workflow_id_int)
            code = self.db.text(existing.get("code"))
            record_type = self.db.text(existing.get("recordType"))
            if self.db.text(payload.get("code")) and self.db.text(payload.get("code")).lower() != code:
                raise self.api_error("已创建的审批流程不能修改编码。")
            if self.db.text(payload.get("recordType")) and self.db.text(payload.get("recordType")) != record_type:
                raise self.api_error("已创建的审批流程不能修改业务类型。")
            name = self.db.text(payload.get("name")) or self.db.text(existing.get("name"))
            is_active = 1 if parse_bool(
                payload.get("isActive"),
                parse_bool(existing.get("isActive"), True),
            ) else 0
            steps = self._validate_workflow_steps(payload.get("steps", existing.get("steps", [])))
            existing_steps = [
                {
                    "name": self.db.text(step.get("name")),
                    "approverUserId": self.db.integer(step.get("approverUserId"), 0),
                    "approverRoleCode": self.db.text(step.get("approverRoleCode")).lower(),
                    "required": parse_bool(step.get("required")),
                    "order": index + 1,
                }
                for index, step in enumerate(existing.get("steps") or [])
            ]
            if steps != existing_steps and self.db.scalar(
                f"""
                SELECT COUNT(*)
                FROM service_approval
                WHERE workflow_id = {workflow_id_int}
                  AND status = 'pending';
                """
            ):
                raise self.conflict_error("该审批流程存在待处理实例，不能修改步骤。请先完成或取消待审批记录。")
            if is_active and self.db.scalar(
                f"""
                SELECT COUNT(*)
                FROM service_workflow
                WHERE record_type = {self.db.quote(record_type)}
                  AND is_active = 1
                  AND workflow_id <> {workflow_id_int}
                  AND NOT EXISTS (
                    SELECT 1
                    FROM service_form form
                    WHERE form.workflow_id = service_workflow.workflow_id
                  );
                """
            ):
                raise self.conflict_error("同一业务类型只能启用一个审批流程。请先停用当前流程。")
            self.db.execute(
                f"""
                UPDATE service_workflow
                SET workflow_name = {self.db.quote(name)},
                    is_active = {is_active}
                WHERE workflow_id = {workflow_id_int};
                """
            )
            self._replace_workflow_steps(workflow_id_int, steps)
            return self._workflow_row(workflow_id_int)

        code = self.db.text(payload.get("code")).lower()
        name = self.db.text(payload.get("name"))
        record_type = self.db.text(payload.get("recordType")).lower()
        if not re.fullmatch(r"[a-z][a-z0-9._-]{2,63}", code) or not name or record_type not in FORM_TYPES:
            raise self.api_error("审批流程编码、名称和业务类型必须有效。")
        if self.db.scalar(
            f"SELECT COUNT(*) FROM service_workflow WHERE workflow_code = {self.db.quote(code)};"
        ):
            raise self.api_error("审批流程编码已经存在。")
        steps = self._validate_workflow_steps(payload.get("steps"))
        is_active = 1 if parse_bool(payload.get("isActive"), True) else 0
        if is_active and self.db.scalar(
            f"""
            SELECT COUNT(*)
            FROM service_workflow
            WHERE record_type = {self.db.quote(record_type)}
              AND is_active = 1
              AND NOT EXISTS (
                SELECT 1
                FROM service_form form
                WHERE form.workflow_id = service_workflow.workflow_id
              );
            """
        ):
            raise self.conflict_error("同一业务类型只能启用一个审批流程。请先停用当前流程。")
        workflow_id_int = self.db.one_id(
            f"""
            INSERT INTO service_workflow (
              workflow_code, workflow_name, record_type, is_active, created_by
            )
            VALUES (
              {self.db.quote(code)}, {self.db.quote(name)}, {self.db.quote(record_type)},
              {is_active}, {self._actor_id(context)}
            );
            SELECT LAST_INSERT_ID();
            """
        )
        self._replace_workflow_steps(workflow_id_int, steps)
        return self._workflow_row(workflow_id_int)

    def _approval_recipients(self, workflow_id: object, step_order: object) -> list[int]:
        users = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(CAST(user_id AS CHAR)), JSON_ARRAY())
            FROM (
              SELECT DISTINCT user_account.user_id
              FROM service_workflow_step step
              JOIN user_account
                ON user_account.is_active = 1
               AND (
                 user_account.user_id = step.approver_user_id
                 OR COALESCE(user_account.role_code, user_account.user_role) = step.approver_role_code
               )
              WHERE step.workflow_id = {self.db.integer(workflow_id, 0)}
                AND step.step_order = {self.db.integer(step_order, 0)}
            ) eligible_users
            """,
            [],
        )
        return [self.db.integer(user_id, 0) for user_id in users or [] if self.db.integer(user_id, 0) > 0]

    def notify_approval_step(self, approval: dict) -> None:
        recipients = self._approval_recipients(
            approval.get("workflowId"),
            approval.get("currentStepOrder"),
        )
        if not recipients:
            return
        record_type = self.db.text(approval.get("recordType"))
        record_id = self.db.integer(approval.get("recordId"), 0)
        type_name = {"ticket": "工单", "change": "变更", "problem": "问题"}.get(record_type, record_type)
        rows = [
            "("
            + ", ".join(
                [
                    str(user_id),
                    self.db.quote("approval"),
                    str(record_id),
                    self.db.quote("approval_pending"),
                    self.db.quote("待您审批"),
                    self.db.quote(f"{type_name} {record_id} 正在等待第 {approval.get('currentStepOrder')} 级审批。"),
                ]
            )
            + ")"
            for user_id in recipients
        ]
        self.db.execute(
            """
            INSERT INTO service_notification (
              recipient_user_id, record_type, record_id, notification_type, title, content
            ) VALUES
            """
            + ", ".join(rows)
            + ";"
        )

    def start_approval(self, record_type: str, record_id: int, context: dict) -> dict | None:
        workflow = self.db.json(
            f"""
            SELECT JSON_OBJECT('id', CAST(workflow.workflow_id AS CHAR))
            FROM service_workflow workflow
            JOIN service_form form ON form.workflow_id = workflow.workflow_id
            JOIN (
              SELECT form_id FROM (
                SELECT extension.form_id
                FROM service_ticket_extension extension
                WHERE {self.db.quote(record_type)} = 'ticket'
                  AND extension.ticket_id = {record_id}
                UNION ALL
                SELECT change_row.form_id
                FROM itil_change change_row
                WHERE {self.db.quote(record_type)} = 'change'
                  AND change_row.change_id = {record_id}
                UNION ALL
                SELECT problem.form_id
                FROM itil_problem problem
                WHERE {self.db.quote(record_type)} = 'problem'
                  AND problem.problem_id = {record_id}
              ) selected_form
              WHERE form_id IS NOT NULL
              LIMIT 1
            ) record_form ON record_form.form_id = form.form_id
            WHERE workflow.record_type = {self.db.quote(record_type)}
              AND workflow.is_active = 1
            LIMIT 1
            """,
            None,
        )
        if not workflow:
            workflow = self.db.json(
                f"""
                SELECT JSON_OBJECT('id', CAST(workflow.workflow_id AS CHAR))
                FROM service_workflow workflow
                WHERE workflow.record_type = {self.db.quote(record_type)}
                  AND workflow.is_active = 1
                  AND NOT EXISTS (
                    SELECT 1
                    FROM service_form form
                    WHERE form.workflow_id = workflow.workflow_id
                  )
                ORDER BY workflow.workflow_id
                LIMIT 1
                """,
                None,
            )
        if not workflow:
            return None
        existing = self.db.scalar(
            f"""
            SELECT COUNT(*)
            FROM service_approval
            WHERE record_type = {self.db.quote(record_type)}
              AND record_id = {record_id}
              AND status = 'pending'
            """
        )
        if existing:
            return self.get_approval_for_record(record_type, record_id)
        approval_id = self.db.one_id(
            f"""
            INSERT INTO service_approval (
              record_type, record_id, workflow_id, current_step_order, status, requested_by
            )
            VALUES (
              {self.db.quote(record_type)}, {record_id}, {self.db.integer(workflow.get('id'), 0)},
              1, 'pending', {self._actor_id(context)}
            );
            SELECT LAST_INSERT_ID();
            """
        )
        if record_type == "ticket":
            self.db.execute(
                f"UPDATE service_ticket_extension SET approval_status = 'pending' WHERE ticket_id = {record_id};"
            )
        self.notify_record_change(record_type, record_id, "待审批", f"{record_type} {record_id} 已进入审批流程。")
        approval = self.get_approval(approval_id)
        self.notify_approval_step(approval)
        return approval

    def get_approval(self, approval_id: object) -> dict:
        row = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(approval.approval_id AS CHAR),
              'recordType', approval.record_type,
              'recordId', CAST(approval.record_id AS CHAR),
              'workflowId', CAST(approval.workflow_id AS CHAR),
              'workflowName', workflow.workflow_name,
              'currentStepOrder', approval.current_step_order,
              'status', approval.status,
              'requestedBy', COALESCE(requester.display_name, ''),
              'requestedByUserId', COALESCE(CAST(approval.requested_by AS CHAR), ''),
              'createdAt', CAST(approval.created_at AS CHAR),
              'updatedAt', CAST(approval.updated_at AS CHAR)
            )
            FROM service_approval approval
            JOIN service_workflow workflow ON workflow.workflow_id = approval.workflow_id
            LEFT JOIN user_account requester ON requester.user_id = approval.requested_by
            WHERE approval.approval_id = {self.db.integer(approval_id, 0)}
            """,
            None,
        )
        if not row:
            raise self.api_error("审批实例不存在。")
        result = dict(row)
        result["decisions"] = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'stepOrder', step_order,
                  'decision', decision,
                  'comment', comment,
                  'decidedBy', COALESCE(user.display_name, ''),
                  'decidedAt', CAST(decided_at AS CHAR)
                )), JSON_ARRAY())
                FROM service_approval_decision decision
                LEFT JOIN user_account user ON user.user_id = decision.decided_by
                WHERE approval_id = {self.db.integer(approval_id, 0)}
                ORDER BY decision_id
                """,
                [],
            )
            or []
        )
        return result

    def get_approval_for_record(self, record_type: str, record_id: int) -> dict | None:
        approval_id = self.db.scalar(
            f"""
            SELECT COALESCE(approval_id, 0)
            FROM service_approval
            WHERE record_type = {self.db.quote(record_type)}
              AND record_id = {record_id}
            ORDER BY approval_id DESC
            LIMIT 1
            """
        )
        return self.get_approval(approval_id) if approval_id else None

    def _approval_record_org_id(self, approval: dict) -> int:
        record_type = self.db.text(approval.get("recordType"))
        record_id = self.db.integer(approval.get("recordId"), 0)
        sources = {
            "ticket": ("itil_ticket", "ticket_id"),
            "change": ("itil_change", "change_id"),
            "problem": ("itil_problem", "problem_id"),
        }
        source = sources.get(record_type)
        if not source or record_id <= 0:
            raise self.api_error("Approval record is invalid.")
        table, id_column = source
        return self.db.scalar(
            f"SELECT COALESCE(org_unit_id, 0) FROM {table} WHERE {id_column} = {record_id};"
        )

    def _is_current_approver(self, approval: dict, context: dict) -> bool:
        if parse_bool(context.get("isSuperAdmin")):
            return True
        return self.db.scalar(
            f"""
            SELECT COUNT(*)
            FROM service_workflow_step step
            WHERE step.workflow_id = {self.db.integer(approval.get('workflowId'), 0)}
              AND step.step_order = {self.db.integer(approval.get('currentStepOrder'), 0)}
              AND (
                step.approver_user_id = {self._actor_id(context)}
                OR step.approver_role_code = {self.db.quote(self.db.text(context.get('role')))}
              );
            """
        ) == 1

    def _assert_approval_access(self, approval: dict, context: dict) -> None:
        if parse_bool(context.get("isSuperAdmin")):
            return
        scope = self._scope(context, "approvals")
        requested_by_actor = self.db.integer(
            approval.get("requestedByUserId"),
            0,
        ) == self._actor_id(context)
        current_approver = self._is_current_approver(approval, context)
        if scope == "none":
            raise self.forbidden_error("This account is not authorized to access approvals.")
        if scope in {"own", "submitted"} and not requested_by_actor:
            raise self.forbidden_error("This account can only access its submitted approvals.")
        if scope == "assigned" and not current_approver:
            raise self.forbidden_error("This account can only access its assigned approvals.")
        self.scope.assert_org_access(context, self._approval_record_org_id(approval))

    def list_approvals(self, context: dict) -> list[dict]:
        actor_id = self._actor_id(context)
        role_code = self.db.text(context.get("role"))
        scope = self._scope(context, "approvals")
        if parse_bool(context.get("isSuperAdmin")):
            condition = "approval.status = 'pending'"
        else:
            approver_condition = f"""
              EXISTS (
                SELECT 1
                FROM service_workflow_step step
                WHERE step.workflow_id = approval.workflow_id
                  AND step.step_order = approval.current_step_order
                  AND (
                    step.approver_user_id = {actor_id}
                    OR step.approver_role_code = {self.db.quote(role_code)}
                  )
              )
            """
            if scope in {"own", "submitted"}:
                condition = f"approval.status = 'pending' AND approval.requested_by = {actor_id}"
            elif scope == "assigned":
                condition = f"approval.status = 'pending' AND {approver_condition}"
            else:
                condition = "approval.status = 'pending'"
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', CAST(approval.approval_id AS CHAR),
              'recordType', approval.record_type,
              'recordId', CAST(approval.record_id AS CHAR),
              'workflowId', CAST(approval.workflow_id AS CHAR),
              'workflowName', workflow.workflow_name,
              'currentStepOrder', approval.current_step_order,
              'status', approval.status,
              'requestedBy', COALESCE(requester.display_name, ''),
              'requestedByUserId', COALESCE(CAST(approval.requested_by AS CHAR), ''),
              'createdAt', CAST(approval.created_at AS CHAR)
            )), JSON_ARRAY())
            FROM service_approval approval
            JOIN service_workflow workflow ON workflow.workflow_id = approval.workflow_id
            LEFT JOIN user_account requester ON requester.user_id = approval.requested_by
            WHERE {condition}
            ORDER BY approval.created_at
            """,
            [],
        )
        visible: list[dict] = []
        for row in rows or []:
            item = dict(row)
            try:
                self._assert_approval_access(item, context)
            except self.forbidden_error:
                continue
            visible.append(item)
        return visible

    def decide_approval(self, approval_id: object, payload: dict, context: dict) -> dict:
        approval = self.get_approval(approval_id)
        self._assert_approval_access(approval, context)
        if approval.get("status") != "pending":
            raise self.conflict_error("审批实例已经结束。")
        step = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'order', step_order,
              'userId', COALESCE(CAST(approver_user_id AS CHAR), ''),
              'roleCode', COALESCE(approver_role_code, '')
            )
            FROM service_workflow_step
            WHERE workflow_id = {self.db.integer(approval.get('workflowId'), 0)}
              AND step_order = {self.db.integer(approval.get('currentStepOrder'), 0)}
            """,
            None,
        )
        if not step:
            raise self.api_error("审批步骤不存在。")
        is_super_admin = parse_bool(context.get("isSuperAdmin"))
        if not is_super_admin and self.db.text(step.get("userId")) and self.db.integer(step.get("userId"), 0) != self._actor_id(context):
            raise self.api_error("当前账号不是本审批步骤的指定审批人。")
        if not is_super_admin and self.db.text(step.get("roleCode")) and self.db.text(context.get("role")) != self.db.text(step.get("roleCode")):
            raise self.api_error("当前账号不具备本审批步骤要求的角色。")
        decision = self.db.text(payload.get("decision")).lower()
        if decision not in {"approved", "rejected"}:
            raise self.api_error("审批结果必须是 approved 或 rejected。")
        output = self.db.execute(
            f"""
            START TRANSACTION;
            SET @locked_approval_id = NULL;
            SELECT approval_id INTO @locked_approval_id
            FROM service_approval
            WHERE approval_id = {self.db.integer(approval_id, 0)}
              AND status = 'pending'
              AND current_step_order = {self.db.integer(step.get('order'), 0)}
            FOR UPDATE;
            INSERT INTO service_approval_decision (
              approval_id, step_order, decision, comment, decided_by
            )
            SELECT
              {self.db.integer(approval_id, 0)}, {self.db.integer(step.get('order'), 0)},
              {self.db.quote(decision)}, {self.db.quote(payload.get('comment'))}, {self._actor_id(context)}
            FROM DUAL
            WHERE @locked_approval_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1
                FROM service_approval_decision existing_decision
                WHERE existing_decision.approval_id = {self.db.integer(approval_id, 0)}
                  AND existing_decision.step_order = {self.db.integer(step.get('order'), 0)}
              );
            SET @decision_written = ROW_COUNT();
            UPDATE service_approval
            SET status = CASE
                  WHEN {self.db.quote(decision)} = 'rejected' THEN 'rejected'
                  WHEN EXISTS (
                    SELECT 1 FROM service_workflow_step next_step
                    WHERE next_step.workflow_id = service_approval.workflow_id
                      AND next_step.step_order > service_approval.current_step_order
                  ) THEN 'pending'
                  ELSE 'approved'
                END,
                current_step_order = CASE
                  WHEN {self.db.quote(decision)} = 'approved' THEN COALESCE((
                    SELECT MIN(next_step.step_order)
                    FROM service_workflow_step next_step
                    WHERE next_step.workflow_id = service_approval.workflow_id
                      AND next_step.step_order > service_approval.current_step_order
                  ), current_step_order)
                  ELSE current_step_order
                END,
                completed_at = CASE
                  WHEN {self.db.quote(decision)} = 'rejected'
                    OR NOT EXISTS (
                      SELECT 1 FROM service_workflow_step next_step
                    WHERE next_step.workflow_id = service_approval.workflow_id
                      AND next_step.step_order > service_approval.current_step_order
                    )
                  THEN CURRENT_TIMESTAMP ELSE NULL END
            WHERE approval_id = {self.db.integer(approval_id, 0)}
              AND status = 'pending'
              AND current_step_order = {self.db.integer(step.get('order'), 0)}
              AND @decision_written = 1;
            SET @approval_updated = ROW_COUNT();
            SELECT @decision_written, @approval_updated;
            COMMIT;
            """
        )
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        counts = (lines[-1] if lines else "").split("\t")
        if self.db.integer(counts[0] if counts else 0, 0) != 1 or self.db.integer(
            counts[1] if len(counts) > 1 else 0, 0
        ) != 1:
            raise self.conflict_error("This approval was already handled or advanced by another user.")
        result = self.get_approval(approval_id)
        record_type = self.db.text(result.get("recordType"))
        record_id = self.db.integer(result.get("recordId"), 0)
        if result.get("status") == "approved" and record_type == "change":
            self.db.execute(f"UPDATE itil_change SET status = 'approved' WHERE change_id = {record_id} AND status IN ('submitted', 'assessing');")
        elif result.get("status") == "rejected" and record_type == "change":
            self.db.execute(f"UPDATE itil_change SET status = 'rejected' WHERE change_id = {record_id} AND status = 'submitted';")
        if record_type == "ticket":
            extension_status = "approved" if result.get("status") == "approved" else "rejected" if result.get("status") == "rejected" else "pending"
            self.db.execute(f"UPDATE service_ticket_extension SET approval_status = {self.db.quote(extension_status)} WHERE ticket_id = {record_id};")
        if result.get("status") == "pending":
            self.notify_approval_step(result)
        self.notify_record_change(record_type, record_id, "审批结果更新", f"审批结果：{result.get('status')}。")
        return result

    def list_notifications(self, context: dict) -> list[dict]:
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', CAST(notification_id AS CHAR),
              'recordType', record_type,
              'recordId', COALESCE(CAST(record_id AS CHAR), ''),
              'type', notification_type,
              'title', title,
              'content', content,
              'isRead', is_read,
              'createdAt', CAST(created_at AS CHAR),
              'readAt', COALESCE(CAST(read_at AS CHAR), '')
            )), JSON_ARRAY())
            FROM (
              SELECT *
              FROM service_notification
              WHERE recipient_user_id = {self._actor_id(context)}
              ORDER BY created_at DESC
              LIMIT 200
            ) recent_notifications
            """,
            [],
        )
        return list(rows or [])

    def mark_notification_read(self, notification_id: object, context: dict) -> dict:
        notification_id_int = self.db.integer(notification_id, 0)
        self.db.execute(
            f"""
            UPDATE service_notification
            SET is_read = 1, read_at = CURRENT_TIMESTAMP
            WHERE notification_id = {notification_id_int}
              AND recipient_user_id = {self._actor_id(context)};
            """
        )
        return {"ok": True}
