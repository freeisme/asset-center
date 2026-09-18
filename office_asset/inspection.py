"""机房、弱电间与机柜巡检管理。

巡检对象只包含机房、弱电间和它们下面的机柜。一次巡检会先把模板事项快照进
任务明细，之后修改模板不会影响已经开始的巡检表。

重要规则：

* 执行人默认是发起巡检的账号，也允许显式指定其他账号；
* 异常项必须填写说明，填写时和提交时都会校验；
* 只有手动发起巡检，没有周期计划或自动派单。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime

from .scope import OrganizationScopeService
from .sql import SqlGateway, parse_bool


SITE_TYPES = {"server_room", "weak_room"}
SITE_TYPE_LABELS = {"server_room": "机房", "weak_room": "弱电间", "both": "通用"}
TEMPLATE_SITE_TYPES = {"server_room", "weak_room", "both"}
SCOPE_KINDS = {"site", "rack"}
VALUE_TYPES = {"ok_fail", "number", "text", "select"}
CHECK_RESULTS = {"pending", "ok", "fail", "na"}
TASK_STATUSES = {"running", "submitted", "void"}
CODE_PATTERN = re.compile(r"^[A-Za-z0-9._-]{2,64}$")


@dataclass
class InspectionService:
    db: SqlGateway
    scope: OrganizationScopeService
    api_error: type[Exception]
    conflict_error: type[Exception]
    forbidden_error: type[Exception]

    # ------------------------------------------------------------------ helpers

    def _actor_id(self, context: dict) -> int:
        return self.db.integer(context.get("id"), 0)

    def _actor_name(self, context: dict) -> str:
        return self.db.text(context.get("username")) or "web"

    def _last_int(self, output: str, default: int = 0) -> int:
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        return self.db.integer(lines[-1] if lines else default, default)

    def _audit_sql(
        self,
        action: str,
        entity_type: str,
        entity_id_sql: str,
        entity_name: str,
        summary: str,
        context: dict,
        old_value: dict | None = None,
        new_value: dict | None = None,
    ) -> str:
        """Build an audit insert; entity_id_sql is a raw SQL expression."""
        return f"""
        INSERT INTO audit_log (
          action_type, entity_type, entity_id, entity_name,
          old_value, new_value, summary, actor, source
        )
        VALUES (
          {self.db.quote(action)},
          {self.db.quote(entity_type)},
          {entity_id_sql},
          {self.db.quote(entity_name)},
          {self.db.json_value(old_value or {})},
          {self.db.json_value(new_value or {})},
          {self.db.quote(summary[:500])},
          {self.db.quote(self._actor_name(context))},
          'api'
        )
        """

    def _conditional_audit_sql(
        self,
        action: str,
        entity_type: str,
        entity_id_sql: str,
        entity_name: str,
        summary: str,
        context: dict,
        condition: str,
        old_value: dict | None = None,
        new_value: dict | None = None,
    ) -> str:
        """Audit insert that only runs when the SQL condition holds."""
        return f"""
        INSERT INTO audit_log (
          action_type, entity_type, entity_id, entity_name,
          old_value, new_value, summary, actor, source
        )
        SELECT
          {self.db.quote(action)},
          {self.db.quote(entity_type)},
          {entity_id_sql},
          {self.db.quote(entity_name)},
          {self.db.json_value(old_value or {})},
          {self.db.json_value(new_value or {})},
          {self.db.quote(summary[:500])},
          {self.db.quote(self._actor_name(context))},
          'api'
        FROM DUAL
        WHERE {condition}
        """

    def _idempotency_result(self, operation: str, key: str, payload: dict) -> dict | None:
        if not key:
            return None
        if not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", key):
            raise self.api_error("Idempotency-Key must be 8-128 safe characters.")
        record = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'requestHash', request_hash,
              'response', response_json
            )
            FROM api_idempotency_key
            WHERE idempotency_key = {self.db.quote(key)}
              AND operation_code = {self.db.quote(operation)}
              AND expires_at > CURRENT_TIMESTAMP
            """,
            None,
        )
        if not record:
            return None
        request_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if self.db.text(record.get("requestHash")) != request_hash:
            raise self.conflict_error("The idempotency key was already used with another request.")
        return dict(record.get("response") or {})

    def _store_idempotency_result(self, operation: str, key: str, payload: dict, response: dict) -> None:
        if not key:
            return
        request_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.db.execute(
            f"""
            INSERT INTO api_idempotency_key (
              idempotency_key, operation_code, request_hash, response_json, expires_at
            )
            VALUES (
              {self.db.quote(key)},
              {self.db.quote(operation)},
              {self.db.quote(request_hash)},
              {self.db.json_value(response)},
              DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 24 HOUR)
            )
            ON DUPLICATE KEY UPDATE
              request_hash = VALUES(request_hash),
              response_json = VALUES(response_json),
              expires_at = VALUES(expires_at);
            """
        )

    def _require_code(self, value: object, field_label: str) -> str:
        code = self.db.text(value)
        if not CODE_PATTERN.match(code):
            raise self.api_error(f"{field_label}只能使用字母、数字、点、下划线和短横线，长度 2-64。")
        return code

    def _require_text(self, value: object, field_label: str, limit: int) -> str:
        text = self.db.text(value)
        if not text:
            raise self.api_error(f"{field_label}不能为空。")
        return text[:limit]

    # -------------------------------------------------------------------- sites

    def list_sites(self, context: dict, params: dict[str, list[str]] | None = None) -> list[dict]:
        include_inactive = parse_bool((params or {}).get("includeInactive", ["0"])[0])
        active_filter = "" if include_inactive else "WHERE site.is_active = 1"
        return list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(site.site_id AS CHAR),
                  'code', site.site_code,
                  'name', site.site_name,
                  'siteType', site.site_type,
                  'orgId', COALESCE(CAST(site.org_unit_id AS CHAR), ''),
                  'orgName', site.org_name,
                  'location', site.location_desc,
                  'remarks', site.remarks,
                  'isActive', site.is_active,
                  'rackCount', site.rack_count
                )), JSON_ARRAY())
                FROM (
                  SELECT site.*, COALESCE(org.org_name, '') AS org_name,
                    (
                    SELECT COUNT(*) FROM asset_rack rack
                    WHERE rack.site_id = site.site_id AND rack.is_active = 1
                    ) AS rack_count
                  FROM asset_site site
                  LEFT JOIN org_unit org ON org.org_unit_id = site.org_unit_id
                  {active_filter}
                  ORDER BY site.site_type, site.site_code
                ) site
                """,
                [],
            )
            or []
        )

    def create_site(self, payload: dict, context: dict) -> dict:
        code = self._require_code(payload.get("code"), "机房/弱电间编码")
        name = self._require_text(payload.get("name"), "机房/弱电间名称", 128)
        site_type = self.db.text(payload.get("siteType")) or "server_room"
        if site_type not in SITE_TYPES:
            raise self.api_error("机房/弱电间类型无效。")
        org_id = self.db.integer(payload.get("orgId"), 0)
        if org_id > 0:
            self.scope.assert_org_access(context, org_id)
        location = self.db.text(payload.get("location"))[:255]
        remarks = self.db.text(payload.get("remarks"))[:500]
        output = self.db.execute(
            f"""
            START TRANSACTION;
            INSERT INTO asset_site (site_code, site_name, site_type, org_unit_id, location_desc, remarks)
            VALUES (
              {self.db.quote(code)},
              {self.db.quote(name)},
              {self.db.quote(site_type)},
              {org_id if org_id > 0 else 'NULL'},
              {self.db.quote(location)},
              {self.db.quote(remarks)}
            );
            SET @new_site_id = LAST_INSERT_ID();
            {self._audit_sql(
                "inspection_site_created",
                "asset_site",
                "'new'",
                name,
                f"新增{SITE_TYPE_LABELS.get(site_type, '机房')}：{name}",
                context,
                None,
                {"code": code, "siteType": site_type},
            )};
            UPDATE audit_log
            SET entity_id = CAST(@new_site_id AS CHAR)
            WHERE audit_log_id = LAST_INSERT_ID();
            SELECT @new_site_id;
            COMMIT;
            """
        )
        site_id = self._last_int(output)
        if site_id <= 0:
            raise self.conflict_error("机房/弱电间编码已存在。")
        return {"id": str(site_id), "code": code, "name": name}

    def update_site(self, site_id: object, payload: dict, context: dict) -> dict:
        site = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(site_id AS CHAR),
              'code', site_code,
              'name', site_name,
              'siteType', site_type,
              'orgId', COALESCE(CAST(org_unit_id AS CHAR), ''),
              'location', location_desc,
              'remarks', remarks,
              'isActive', is_active
            )
            FROM asset_site
            WHERE site_id = {self.db.integer(site_id, 0)}
            """,
            None,
        )
        if not site:
            raise self.api_error("机房/弱电间不存在。")
        code = self._require_code(payload.get("code", site.get("code")), "机房/弱电间编码")
        name = self._require_text(payload.get("name", site.get("name")), "机房/弱电间名称", 128)
        site_type = self.db.text(payload.get("siteType", site.get("siteType"))) or "server_room"
        if site_type not in SITE_TYPES:
            raise self.api_error("机房/弱电间类型无效。")
        org_id = self.db.integer(payload.get("orgId", site.get("orgId")), 0)
        if org_id > 0:
            self.scope.assert_org_access(context, org_id)
        location = self.db.text(payload.get("location", site.get("location")))[:255]
        remarks = self.db.text(payload.get("remarks", site.get("remarks")))[:500]
        is_active = 1 if parse_bool(payload.get("isActive", site.get("isActive")), True) else 0
        self.db.execute(
            f"""
            START TRANSACTION;
            UPDATE asset_site
            SET site_code = {self.db.quote(code)},
                site_name = {self.db.quote(name)},
                site_type = {self.db.quote(site_type)},
                org_unit_id = {org_id if org_id > 0 else 'NULL'},
                location_desc = {self.db.quote(location)},
                remarks = {self.db.quote(remarks)},
                is_active = {is_active}
            WHERE site_id = {self.db.integer(site.get("id"), 0)};
            {self._audit_sql(
                "inspection_site_updated",
                "asset_site",
                str(self.db.integer(site.get("id"), 0)),
                name,
                f"更新{SITE_TYPE_LABELS.get(site_type, '机房')}：{name}",
                context,
                site,
                {"code": code, "name": name, "siteType": site_type, "isActive": is_active},
            )};
            COMMIT;
            """
        )
        return {"id": str(site.get("id")), "code": code, "name": name}

    # -------------------------------------------------------------------- racks

    def list_racks(self, context: dict, params: dict[str, list[str]] | None = None) -> list[dict]:
        site_filter = self.db.integer((params or {}).get("siteId", [""])[0], 0)
        where = ["rack.is_active = 1"] if not parse_bool((params or {}).get("includeInactive", ["0"])[0]) else ["1 = 1"]
        if site_filter > 0:
            where.append(f"rack.site_id = {site_filter}")
        return list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(rack.rack_id AS CHAR),
                  'code', rack.rack_code,
                  'name', rack.rack_name,
                  'siteId', CAST(rack.site_id AS CHAR),
                  'siteName', rack.site_name,
                  'siteType', rack.site_type,
                  'heightU', rack.height_u,
                  'descUnits', rack.desc_units,
                  'remarks', rack.remarks,
                  'isActive', rack.is_active
                )), JSON_ARRAY())
                FROM (
                  SELECT rack.rack_id, rack.rack_code, rack.rack_name, rack.site_id,
                         rack.height_u, rack.desc_units, rack.remarks, rack.is_active,
                         site.site_name, site.site_type
                  FROM asset_rack rack
                  JOIN asset_site site ON site.site_id = rack.site_id
                  WHERE {' AND '.join(where)}
                  ORDER BY site.site_code, rack.rack_code
                ) rack
                """,
                [],
            )
            or []
        )

    def create_rack(self, payload: dict, context: dict) -> dict:
        code = self._require_code(payload.get("code"), "机柜编码")
        name = self._require_text(payload.get("name"), "机柜名称", 128)
        site_id = self.db.integer(payload.get("siteId"), 0)
        if site_id <= 0:
            raise self.api_error("机柜必须归属一个机房或弱电间。")
        site = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(site_id AS CHAR),
              'name', site_name,
              'orgId', COALESCE(CAST(org_unit_id AS CHAR), '')
            )
            FROM asset_site
            WHERE site_id = {site_id} AND is_active = 1
            """,
            None,
        )
        if not site:
            raise self.api_error("机房/弱电间不存在或已停用。")
        height_u = self.db.integer(payload.get("heightU"), 42)
        if height_u < 1 or height_u > 100:
            raise self.api_error("机柜高度必须在 1-100U 之间。")
        desc_units = 1 if parse_bool(payload.get("descUnits")) else 0
        remarks = self.db.text(payload.get("remarks"))[:500]
        org_id = self.db.integer(site.get("orgId"), 0)
        output = self.db.execute(
            f"""
            START TRANSACTION;
            INSERT INTO asset_rack (
              rack_code, rack_name, site_id, height_u, desc_units, org_unit_id, remarks
            )
            VALUES (
              {self.db.quote(code)},
              {self.db.quote(name)},
              {site_id},
              {height_u},
              {desc_units},
              {org_id if org_id > 0 else 'NULL'},
              {self.db.quote(remarks)}
            );
            SET @new_rack_id = LAST_INSERT_ID();
            {self._audit_sql(
                "inspection_rack_created",
                "asset_rack",
                "'new'",
                name,
                f"新增机柜：{site.get('name')} / {name}",
                context,
                None,
                {"code": code, "siteId": str(site_id), "heightU": height_u},
            )};
            UPDATE audit_log
            SET entity_id = CAST(@new_rack_id AS CHAR)
            WHERE audit_log_id = LAST_INSERT_ID();
            SELECT @new_rack_id;
            COMMIT;
            """
        )
        rack_id = self._last_int(output)
        if rack_id <= 0:
            raise self.conflict_error("机柜编码已存在。")
        return {"id": str(rack_id), "code": code, "name": name}

    def update_rack(self, rack_id: object, payload: dict, context: dict) -> dict:
        rack = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(rack_id AS CHAR),
              'code', rack_code,
              'name', rack_name,
              'siteId', CAST(site_id AS CHAR),
              'heightU', height_u,
              'descUnits', desc_units,
              'remarks', remarks,
              'isActive', is_active
            )
            FROM asset_rack
            WHERE rack_id = {self.db.integer(rack_id, 0)}
            """,
            None,
        )
        if not rack:
            raise self.api_error("机柜不存在。")
        code = self._require_code(payload.get("code", rack.get("code")), "机柜编码")
        name = self._require_text(payload.get("name", rack.get("name")), "机柜名称", 128)
        site_id = self.db.integer(payload.get("siteId", rack.get("siteId")), 0)
        if site_id <= 0:
            raise self.api_error("机柜必须归属一个机房或弱电间。")
        height_u = self.db.integer(payload.get("heightU", rack.get("heightU")), 42)
        if height_u < 1 or height_u > 100:
            raise self.api_error("机柜高度必须在 1-100U 之间。")
        desc_units = 1 if parse_bool(payload.get("descUnits", rack.get("descUnits"))) else 0
        remarks = self.db.text(payload.get("remarks", rack.get("remarks")))[:500]
        is_active = 1 if parse_bool(payload.get("isActive", rack.get("isActive")), True) else 0
        self.db.execute(
            f"""
            START TRANSACTION;
            UPDATE asset_rack
            SET rack_code = {self.db.quote(code)},
                rack_name = {self.db.quote(name)},
                site_id = {site_id},
                height_u = {height_u},
                desc_units = {desc_units},
                remarks = {self.db.quote(remarks)},
                is_active = {is_active}
            WHERE rack_id = {self.db.integer(rack.get("id"), 0)};
            {self._audit_sql(
                "inspection_rack_updated",
                "asset_rack",
                str(self.db.integer(rack.get("id"), 0)),
                name,
                f"更新机柜：{name}",
                context,
                rack,
                {"code": code, "name": name, "heightU": height_u, "isActive": is_active},
            )};
            COMMIT;
            """
        )
        return {"id": str(rack.get("id")), "code": code, "name": name}

    # ---------------------------------------------------------------- templates

    def list_templates(self, context: dict) -> list[dict]:
        return list(
            self.db.json(
                """
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(template.template_id AS CHAR),
                  'code', template.template_code,
                  'name', template.template_name,
                  'siteType', template.site_type,
                  'description', template.description,
                  'isActive', template.is_active,
                  'itemCount', template.item_count
                )), JSON_ARRAY())
                FROM (
                  SELECT template.*, (
                    SELECT COUNT(*) FROM inspection_template_item item
                    WHERE item.template_id = template.template_id
                  ) AS item_count
                  FROM inspection_template template
                  ORDER BY template.template_code
                ) template
                """,
                [],
            )
            or []
        )

    def get_template(self, template_id: object, context: dict) -> dict:
        template = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(template_id AS CHAR),
              'code', template_code,
              'name', template_name,
              'siteType', site_type,
              'description', description,
              'isActive', is_active
            )
            FROM inspection_template
            WHERE template_id = {self.db.integer(template_id, 0)}
            """,
            None,
        )
        if not template:
            raise self.api_error("巡检模板不存在。")
        template["items"] = self._template_items(self.db.integer(template.get("id"), 0))
        return template

    def _template_items(self, template_id: int) -> list[dict]:
        if template_id <= 0:
            return []
        return list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'seqNo', seq_no,
                  'category', category,
                  'title', item_title,
                  'checkMethod', check_method,
                  'valueType', value_type,
                  'unit', unit,
                  'normalRange', normal_range,
                  'isRequired', is_required,
                  'remarks', remarks
                )), JSON_ARRAY())
                FROM (
                  SELECT *
                  FROM inspection_template_item
                  WHERE template_id = {template_id}
                  ORDER BY seq_no, item_id
                ) item
                """,
                [],
            )
            or []
        )

    def _validated_items(self, payload: dict) -> list[dict]:
        raw_items = payload.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise self.api_error("巡检事项至少需要一项。")
        if len(raw_items) > 200:
            raise self.api_error("单个模板的巡检事项不能超过 200 项。")
        items: list[dict] = []
        for index, raw in enumerate(raw_items):
            if not isinstance(raw, dict):
                raise self.api_error("巡检事项格式无效。")
            title = self._require_text(raw.get("title"), "巡检事项名称", 200)
            value_type = self.db.text(raw.get("valueType")) or "ok_fail"
            if value_type not in VALUE_TYPES:
                raise self.api_error("巡检事项取值类型无效。")
            seq_no = self.db.integer(raw.get("seqNo"), (index + 1) * 10)
            items.append(
                {
                    "seqNo": seq_no,
                    "category": self.db.text(raw.get("category"))[:64] or "通用",
                    "title": title,
                    "checkMethod": self.db.text(raw.get("checkMethod"))[:255],
                    "valueType": value_type,
                    "unit": self.db.text(raw.get("unit"))[:32],
                    "normalRange": self.db.text(raw.get("normalRange"))[:128],
                    "isRequired": 1 if parse_bool(raw.get("isRequired", True), True) else 0,
                }
            )
        return items

    def _template_item_insert_sql(self, template_id_sql: str, items: list[dict]) -> str:
        values = []
        for item in items:
            values.append(
                "("
                + ", ".join(
                    [
                        template_id_sql,
                        str(item["seqNo"]),
                        self.db.quote(item["category"]),
                        self.db.quote(item["title"]),
                        self.db.quote(item["checkMethod"]),
                        self.db.quote(item["valueType"]),
                        self.db.quote(item["unit"]),
                        self.db.quote(item["normalRange"]),
                        str(item["isRequired"]),
                    ]
                )
                + ")"
            )
        return (
            "INSERT INTO inspection_template_item ("
            "template_id, seq_no, category, item_title, check_method, value_type, unit, normal_range, "
            "is_required) VALUES " + ", ".join(values)
        )

    def create_template(self, payload: dict, context: dict) -> dict:
        code = self._require_code(payload.get("code"), "模板编码")
        name = self._require_text(payload.get("name"), "模板名称", 128)
        site_type = self.db.text(payload.get("siteType")) or "both"
        if site_type not in TEMPLATE_SITE_TYPES:
            raise self.api_error("模板适用对象无效。")
        description = self.db.text(payload.get("description"))[:500]
        items = self._validated_items(payload)
        actor_id = self._actor_id(context)
        output = self.db.execute(
            f"""
            START TRANSACTION;
            INSERT INTO inspection_template (
              template_code, template_name, site_type, description, created_by, updated_by
            )
            VALUES (
              {self.db.quote(code)},
              {self.db.quote(name)},
              {self.db.quote(site_type)},
              {self.db.quote(description)},
              {actor_id if actor_id > 0 else 'NULL'},
              {actor_id if actor_id > 0 else 'NULL'}
            );
            SET @new_template_id = LAST_INSERT_ID();
            {self._template_item_insert_sql('@new_template_id', items)};
            {self._audit_sql(
                "inspection_template_created",
                "inspection_template",
                "'new'",
                name,
                f"新增巡检模板：{name}",
                context,
                None,
                {"code": code, "siteType": site_type, "itemCount": len(items)},
            )};
            UPDATE audit_log
            SET entity_id = CAST(@new_template_id AS CHAR)
            WHERE audit_log_id = LAST_INSERT_ID();
            SELECT @new_template_id;
            COMMIT;
            """
        )
        template_id = self._last_int(output)
        if template_id <= 0:
            raise self.conflict_error("模板编码已存在。")
        return {"id": str(template_id), "code": code, "name": name, "itemCount": len(items)}

    def update_template(self, template_id: object, payload: dict, context: dict) -> dict:
        template = self.get_template(template_id, context)
        code = self._require_code(payload.get("code", template.get("code")), "模板编码")
        name = self._require_text(payload.get("name", template.get("name")), "模板名称", 128)
        site_type = self.db.text(payload.get("siteType", template.get("siteType"))) or "both"
        if site_type not in TEMPLATE_SITE_TYPES:
            raise self.api_error("模板适用对象无效。")
        description = self.db.text(payload.get("description", template.get("description")))[:500]
        is_active = 1 if parse_bool(payload.get("isActive", template.get("isActive")), True) else 0
        items = template.get("items") or []
        replace_items = isinstance(payload.get("items"), list)
        if replace_items:
            items = self._validated_items(payload)
        template_id_int = self.db.integer(template.get("id"), 0)
        actor_id = self._actor_id(context)
        statements = [
            "START TRANSACTION",
            f"""
            UPDATE inspection_template
            SET template_code = {self.db.quote(code)},
                template_name = {self.db.quote(name)},
                site_type = {self.db.quote(site_type)},
                description = {self.db.quote(description)},
                is_active = {is_active},
                updated_by = {actor_id if actor_id > 0 else 'NULL'}
            WHERE template_id = {template_id_int}
            """,
        ]
        if replace_items:
            statements.append(f"DELETE FROM inspection_template_item WHERE template_id = {template_id_int}")
            statements.append(self._template_item_insert_sql(str(template_id_int), items))
        statements.append(
            self._audit_sql(
                "inspection_template_updated",
                "inspection_template",
                template_id_int,
                name,
                f"更新巡检模板：{name}",
                context,
                {"code": template.get("code"), "itemCount": len(template.get("items") or [])},
                {"code": code, "itemCount": len(items), "isActive": is_active},
            )
        )
        statements.append("COMMIT")
        self.db.execute(";\n".join(statements) + ";")
        return {"id": str(template_id_int), "code": code, "name": name, "itemCount": len(items)}

    # -------------------------------------------------------------------- tasks

    def _next_task_no(self) -> str:
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"XJ-{today}-"
        sequence = self.db.scalar(
            f"""
            SELECT COALESCE(MAX(CAST(RIGHT(task_no, 3) AS UNSIGNED)), 0)
            FROM inspection_task
            WHERE task_no LIKE {self.db.quote(prefix + '%')};
            """
        )
        return f"{prefix}{sequence + 1:03d}"

    def list_tasks(self, context: dict, params: dict[str, list[str]] | None = None) -> list[dict]:
        status = self.db.text((params or {}).get("status", [""])[0])
        where = []
        if status in TASK_STATUSES:
            where.append(f"task.status = {self.db.quote(status)}")
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        return list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(task.task_id AS CHAR),
                  'taskNo', task.task_no,
                  'templateId', COALESCE(CAST(task.template_id AS CHAR), ''),
                  'templateName', task.template_name,
                  'scopeKind', task.scope_kind,
                  'scopeName', TRIM(BOTH ' /' FROM CONCAT(
                    COALESCE(task.site_name, ''), ' / ', COALESCE(task.rack_name, '')
                  )),
                  'siteName', task.site_name,
                  'rackName', task.rack_name,
                  'inspectorName', task.inspector_name,
                  'status', task.status,
                  'startedAt', COALESCE(CAST(task.started_at AS CHAR), ''),
                  'submittedAt', COALESCE(CAST(task.submitted_at AS CHAR), ''),
                  'itemTotal', task.item_total,
                  'itemOk', task.item_ok,
                  'itemFail', task.item_fail,
                  'itemNa', task.item_na,
                  'abnormalSummary', task.abnormal_summary
                )), JSON_ARRAY())
                FROM (
                  SELECT task.*
                  FROM inspection_task task
                  {clause}
                  ORDER BY task.started_at DESC, task.task_id DESC
                ) task
                """,
                [],
            )
            or []
        )

    def start_task(self, payload: dict, context: dict, idempotency_key: str = "") -> dict:
        cached = self._idempotency_result("inspection.task.start", idempotency_key, payload)
        if cached:
            return cached

        template_id = self.db.integer(payload.get("templateId"), 0)
        if template_id <= 0:
            raise self.api_error("请选择巡检模板。")
        template = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(template_id AS CHAR),
              'name', template_name,
              'siteType', site_type,
              'isActive', is_active
            )
            FROM inspection_template
            WHERE template_id = {template_id}
            """,
            None,
        )
        if not template:
            raise self.api_error("巡检模板不存在。")
        if not parse_bool(template.get("isActive"), True):
            raise self.conflict_error("该巡检模板已停用。")
        items = self._template_items(template_id)
        if not items:
            raise self.conflict_error("该巡检模板没有巡检事项，请先补充后再开始巡检。")

        scope_kind = self.db.text(payload.get("scopeKind")) or "site"
        if scope_kind not in SCOPE_KINDS:
            raise self.api_error("巡检对象类型无效。")
        site_id = 0
        rack_id = 0
        site_name = ""
        rack_name = ""
        site_type = ""
        if scope_kind == "site":
            site_id = self.db.integer(payload.get("siteId"), 0)
            if site_id <= 0:
                raise self.api_error("请选择要巡检的机房或弱电间。")
            site = self.db.json(
                f"""
                SELECT JSON_OBJECT(
                  'id', CAST(site_id AS CHAR),
                  'name', site_name,
                  'siteType', site_type,
                  'isActive', is_active
                )
                FROM asset_site
                WHERE site_id = {site_id}
                """,
                None,
            )
            if not site:
                raise self.api_error("机房/弱电间不存在。")
            if not parse_bool(site.get("isActive"), True):
                raise self.conflict_error("该机房/弱电间已停用。")
            site_name = self.db.text(site.get("name"))
            site_type = self.db.text(site.get("siteType"))
        else:
            rack_id = self.db.integer(payload.get("rackId"), 0)
            if rack_id <= 0:
                raise self.api_error("请选择要巡检的机柜。")
            rack = self.db.json(
                f"""
                SELECT JSON_OBJECT(
                  'id', CAST(rack.rack_id AS CHAR),
                  'name', rack.rack_name,
                  'siteId', CAST(rack.site_id AS CHAR),
                  'siteName', site.site_name,
                  'siteType', site.site_type,
                  'isActive', rack.is_active
                )
                FROM asset_rack rack
                JOIN asset_site site ON site.site_id = rack.site_id
                WHERE rack.rack_id = {rack_id}
                """,
                None,
            )
            if not rack:
                raise self.api_error("机柜不存在。")
            if not parse_bool(rack.get("isActive"), True):
                raise self.conflict_error("该机柜已停用。")
            site_id = self.db.integer(rack.get("siteId"), 0)
            site_name = self.db.text(rack.get("siteName"))
            site_type = self.db.text(rack.get("siteType"))
            rack_name = self.db.text(rack.get("name"))

        template_site_type = self.db.text(template.get("siteType")) or "both"
        if template_site_type != "both" and site_type and template_site_type != site_type:
            raise self.api_error(
                f"模板「{template.get('name')}」适用于{SITE_TYPE_LABELS.get(template_site_type, '指定对象')}，"
                f"与当前巡检对象（{SITE_TYPE_LABELS.get(site_type, site_type)}）不匹配。"
            )

        inspector_id = self.db.integer(payload.get("inspectorUserId"), 0)
        if inspector_id <= 0:
            inspector_id = self._actor_id(context)
        inspector_name = ""
        if inspector_id > 0:
            inspector_name = self.db.text(
                self.db.execute(
                    f"SELECT COALESCE(display_name, username) FROM user_account WHERE user_id = {inspector_id};"
                ).strip()
            )
        if not inspector_name:
            inspector_name = self._actor_name(context)

        remarks = self.db.text(payload.get("remarks"))[:500]
        task_no = self._next_task_no()
        item_values = []
        for item in items:
            item_values.append(
                "("
                + ", ".join(
                    [
                        "@new_task_id",
                        str(self.db.integer(item.get("seqNo"), 10)),
                        self.db.quote(self.db.text(item.get("category")) or "通用"),
                        self.db.quote(self.db.text(item.get("title"))),
                        self.db.quote(self.db.text(item.get("checkMethod"))),
                        self.db.quote(self.db.text(item.get("valueType")) or "ok_fail"),
                        self.db.quote(self.db.text(item.get("unit"))),
                        self.db.quote(self.db.text(item.get("normalRange"))),
                        str(1 if parse_bool(item.get("isRequired", True), True) else 0),
                    ]
                )
                + ")"
            )
        output = self.db.execute(
            f"""
            START TRANSACTION;
            INSERT INTO inspection_task (
              task_no, template_id, template_name, scope_kind, site_id, site_name,
              rack_id, rack_name, inspector_user_id, inspector_name, status, item_total, remarks
            )
            VALUES (
              {self.db.quote(task_no)},
              {template_id},
              {self.db.quote(self.db.text(template.get('name')))},
              {self.db.quote(scope_kind)},
              {site_id if site_id > 0 else 'NULL'},
              {self.db.quote(site_name)},
              {rack_id if rack_id > 0 else 'NULL'},
              {self.db.quote(rack_name)},
              {inspector_id if inspector_id > 0 else 'NULL'},
              {self.db.quote(inspector_name)},
              'running',
              {len(items)},
              {self.db.quote(remarks)}
            );
            SET @new_task_id = LAST_INSERT_ID();
            INSERT INTO inspection_task_item (
              task_id, seq_no, category, item_title, check_method, value_type, unit, normal_range,
              is_required
            ) VALUES {", ".join(item_values)};
            {self._audit_sql(
                "inspection_started",
                "inspection_task",
                "'new'",
                task_no,
                f"开始巡检：{task_no} / {SITE_TYPE_LABELS.get(site_type, '')}{site_name}{rack_name}",
                context,
                None,
                {
                    "taskNo": task_no,
                    "templateId": str(template_id),
                    "scopeKind": scope_kind,
                    "siteId": str(site_id) if site_id > 0 else "",
                    "rackId": str(rack_id) if rack_id > 0 else "",
                    "itemTotal": len(items),
                },
            )};
            UPDATE audit_log
            SET entity_id = CAST(@new_task_id AS CHAR)
            WHERE audit_log_id = LAST_INSERT_ID();
            SELECT @new_task_id;
            COMMIT;
            """
        )
        task_id = self._last_int(output)
        if task_id <= 0:
            raise self.conflict_error("巡检任务创建失败，请重试。")
        response = {"id": str(task_id), "taskNo": task_no, "itemTotal": len(items)}
        self._store_idempotency_result("inspection.task.start", idempotency_key, payload, response)
        return response

    def _task_items(self, task_id: int) -> list[dict]:
        return list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(task_item_id AS CHAR),
                  'seqNo', seq_no,
                  'category', category,
                  'title', item_title,
                  'checkMethod', check_method,
                  'valueType', value_type,
                  'unit', unit,
                  'normalRange', normal_range,
                  'isRequired', is_required,
                  'result', result,
                  'valueText', value_text,
                  'notes', notes,
                  'isAbnormal', is_abnormal,
                  'checkedAt', COALESCE(CAST(checked_at AS CHAR), ''),
                  'checkedByName', checked_by_name
                )), JSON_ARRAY())
                FROM (
                  SELECT *
                  FROM inspection_task_item
                  WHERE task_id = {task_id}
                  ORDER BY seq_no, task_item_id
                ) item
                """,
                [],
            )
            or []
        )

    def get_task(self, task_id: object, context: dict) -> dict:
        task_id_int = self.db.integer(task_id, 0)
        task = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(task.task_id AS CHAR),
              'taskNo', task.task_no,
              'templateId', COALESCE(CAST(task.template_id AS CHAR), ''),
              'templateName', task.template_name,
              'scopeKind', task.scope_kind,
              'siteId', COALESCE(CAST(task.site_id AS CHAR), ''),
              'siteName', task.site_name,
              'rackId', COALESCE(CAST(task.rack_id AS CHAR), ''),
              'rackName', task.rack_name,
              'inspectorUserId', COALESCE(CAST(task.inspector_user_id AS CHAR), ''),
              'inspectorName', task.inspector_name,
              'status', task.status,
              'startedAt', COALESCE(CAST(task.started_at AS CHAR), ''),
              'submittedAt', COALESCE(CAST(task.submitted_at AS CHAR), ''),
              'itemTotal', task.item_total,
              'itemOk', task.item_ok,
              'itemFail', task.item_fail,
              'itemNa', task.item_na,
              'abnormalSummary', task.abnormal_summary,
              'remarks', task.remarks,
              'siteType', COALESCE(site.site_type, '')
            )
            FROM inspection_task task
            LEFT JOIN asset_site site ON site.site_id = task.site_id
            WHERE task.task_id = {task_id_int}
            """,
            None,
        )
        if not task:
            raise self.api_error("巡检任务不存在。")
        task["items"] = self._task_items(task_id_int)
        return task

    def check_item(
        self,
        task_id: object,
        item_id: object,
        payload: dict,
        context: dict,
    ) -> dict:
        task = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(task_id AS CHAR),
              'taskNo', task_no,
              'status', status
            )
            FROM inspection_task
            WHERE task_id = {self.db.integer(task_id, 0)}
            """,
            None,
        )
        if not task:
            raise self.api_error("巡检任务不存在。")
        if self.db.text(task.get("status")) != "running":
            raise self.conflict_error("该巡检任务已提交或已作废，不能再修改。")
        result = self.db.text(payload.get("result"))
        if result not in CHECK_RESULTS - {"pending"}:
            raise self.api_error("巡检结论必须是正常、异常或不适用。")
        notes = self.db.text(payload.get("notes"))[:500]
        if result == "fail" and not notes:
            raise self.api_error("异常项必须填写说明。")
        value_text = self.db.text(payload.get("valueText"))[:255]
        item_id_int = self.db.integer(item_id, 0)
        actor_id = self._actor_id(context)
        actor_name = self._actor_name(context)
        is_abnormal = 1 if result == "fail" else 0
        output = self.db.execute(
            f"""
            START TRANSACTION;
            UPDATE inspection_task_item
            SET result = {self.db.quote(result)},
                value_text = {self.db.quote(value_text)},
                notes = {self.db.quote(notes)},
                is_abnormal = {is_abnormal},
                checked_at = CURRENT_TIMESTAMP,
                checked_by_user_id = {actor_id if actor_id > 0 else 'NULL'},
                checked_by_name = {self.db.quote(actor_name)}
            WHERE task_item_id = {item_id_int}
              AND task_id = {self.db.integer(task.get('id'), 0)};
            SET @checked_rows = ROW_COUNT();
            UPDATE inspection_task task
            SET item_ok = (
                  SELECT COUNT(*) FROM inspection_task_item item
                  WHERE item.task_id = task.task_id AND item.result = 'ok'
                ),
                item_fail = (
                  SELECT COUNT(*) FROM inspection_task_item item
                  WHERE item.task_id = task.task_id AND item.result = 'fail'
                ),
                item_na = (
                  SELECT COUNT(*) FROM inspection_task_item item
                  WHERE item.task_id = task.task_id AND item.result = 'na'
                )
            WHERE task.task_id = {self.db.integer(task.get('id'), 0)}
              AND @checked_rows > 0;
            SELECT @checked_rows;
            COMMIT;
            """
        )
        updated = self._last_int(output)
        if updated <= 0:
            raise self.api_error("巡检事项不存在。")
        return {"taskId": str(task.get("id")), "itemId": str(item_id_int), "result": result}

    def submit_task(self, task_id: object, payload: dict, context: dict) -> dict:
        task = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(task_id AS CHAR),
              'taskNo', task_no,
              'status', status,
              'itemTotal', item_total,
              'siteName', site_name,
              'rackName', rack_name
            )
            FROM inspection_task
            WHERE task_id = {self.db.integer(task_id, 0)}
            """,
            None,
        )
        if not task:
            raise self.api_error("巡检任务不存在。")
        if self.db.text(task.get("status")) == "submitted":
            raise self.conflict_error("该巡检任务已经提交。")
        if self.db.text(task.get("status")) != "running":
            raise self.conflict_error("该巡检任务已作废，不能提交。")

        items = self._task_items(self.db.integer(task.get("id"), 0))
        if not items:
            raise self.conflict_error("该巡检任务没有巡检事项。")
        pending = [item for item in items if self.db.text(item.get("result")) == "pending"]
        if pending:
            raise self.conflict_error(f"还有 {len(pending)} 项未检查，请补全后再提交。")
        missing_notes = [
            item for item in items if self.db.text(item.get("result")) == "fail" and not self.db.text(item.get("notes"))
        ]
        if missing_notes:
            raise self.api_error(f"有 {len(missing_notes)} 个异常项未填写说明，请补全后再提交。")

        fails = [item for item in items if self.db.text(item.get("result")) == "fail"]
        na_items = [item for item in items if self.db.text(item.get("result")) == "na"]
        ok_items = [item for item in items if self.db.text(item.get("result")) == "ok"]
        summary = self.db.text(payload.get("abnormalSummary"))[:1000]
        if not summary and fails:
            summary = "；".join(
                f"{self.db.text(item.get('title'))}：{self.db.text(item.get('notes'))}" for item in fails
            )[:1000]
        remarks = self.db.text(payload.get("remarks"))[:500]
        task_id_int = self.db.integer(task.get("id"), 0)
        output = self.db.execute(
            f"""
            START TRANSACTION;
            UPDATE inspection_task
            SET status = 'submitted',
                submitted_at = CURRENT_TIMESTAMP,
                item_total = {len(items)},
                item_ok = {len(ok_items)},
                item_fail = {len(fails)},
                item_na = {len(na_items)},
                abnormal_summary = {self.db.quote(summary)},
                remarks = {self.db.quote(remarks)}
            WHERE task_id = {task_id_int}
              AND status = 'running';
            SET @submitted_rows = ROW_COUNT();
            {self._conditional_audit_sql(
                "inspection_submitted",
                "inspection_task",
                str(task_id_int),
                self.db.text(task.get("taskNo")),
                f"提交巡检：{self.db.text(task.get('taskNo'))}，异常 {len(fails)} 项",
                context,
                "@submitted_rows > 0",
                None,
                {
                    "itemTotal": len(items),
                    "itemOk": len(ok_items),
                    "itemFail": len(fails),
                    "itemNa": len(na_items),
                },
            )};
            SELECT @submitted_rows;
            COMMIT;
            """
        )
        if self._last_int(output) <= 0:
            raise self.conflict_error("该巡检任务已经提交或已作废。")
        return {
            "id": str(task_id_int),
            "taskNo": self.db.text(task.get("taskNo")),
            "itemTotal": len(items),
            "itemOk": len(ok_items),
            "itemFail": len(fails),
            "itemNa": len(na_items),
        }

    def void_task(self, task_id: object, payload: dict, context: dict) -> dict:
        task_id_int = self.db.integer(task_id, 0)
        task = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(task_id AS CHAR),
              'taskNo', task_no,
              'status', status
            )
            FROM inspection_task
            WHERE task_id = {task_id_int}
            """,
            None,
        )
        if not task:
            raise self.api_error("巡检任务不存在。")
        if self.db.text(task.get("status")) == "submitted":
            raise self.conflict_error("已提交的巡检表不能作废。")
        reason = self.db.text(payload.get("reason"))[:500]
        if not reason:
            raise self.api_error("作废巡检任务必须填写原因。")
        output = self.db.execute(
            f"""
            START TRANSACTION;
            UPDATE inspection_task
            SET status = 'void',
                remarks = {self.db.quote(reason)}
            WHERE task_id = {task_id_int}
              AND status = 'running';
            SET @voided_rows = ROW_COUNT();
            {self._conditional_audit_sql(
                "inspection_voided",
                "inspection_task",
                str(task_id_int),
                self.db.text(task.get("taskNo")),
                f"作废巡检：{self.db.text(task.get('taskNo'))}，原因：{reason}",
                context,
                "@voided_rows > 0",
                {"status": self.db.text(task.get("status"))},
                {"status": "void", "reason": reason},
            )};
            SELECT @voided_rows;
            COMMIT;
            """
        )
        if self._last_int(output) <= 0:
            raise self.conflict_error("该巡检任务已提交或已作废。")
        return {"id": str(task_id_int), "taskNo": self.db.text(task.get("taskNo")), "status": "void"}
