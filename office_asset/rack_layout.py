"""机柜视图（独立模块）。

把台账设备放到机柜的具体 U 位。位置规则：

* U 位从下往上编号，`position_u` 是起始 U，`u_height` 是占用高度（整数 U）；
* 安装面取 `front`、`rear` 或 `both`：前后面板各自成层，可以同位共存，
  整机深度（`both`）独占该 U 位；
* 位置冲突、超界、设备重复上架都在服务层校验，数据库只保证范围合法。

台账（`computer_asset`、`it_inventory_model`）是设备信息的唯一来源，
这里只保存"哪台设备在哪个机柜的哪个位置"以及少量快照字段。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from .scope import OrganizationScopeService
from .sql import SqlGateway, parse_bool


SOURCE_KINDS = {"computer", "custom"}
FACES = {"front", "rear", "both"}
CATEGORIES = {
    "server",
    "network",
    "patch-panel",
    "power",
    "storage",
    "kvm",
    "av-media",
    "cooling",
    "shelf",
    "blank",
    "cable-management",
    "other",
}
MIN_U_HEIGHT = 1
MAX_U_HEIGHT = 50


@dataclass
class RackLayoutService:
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

    def _org_filter(self, context: dict, column: str) -> str:
        allowed = self.scope.permitted_org_ids(context)
        if allowed is None:
            return ""
        if not allowed:
            return "AND 1 = 0"
        values = ", ".join(str(value) for value in sorted(allowed))
        return f"AND ({column} IS NULL OR {column} IN ({values}))"

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

    def _rack_row(self, rack_id: object) -> dict | None:
        rack_id_int = self.db.integer(rack_id, 0)
        if rack_id_int <= 0:
            return None
        return self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(rack.rack_id AS CHAR),
              'code', rack.rack_code,
              'name', rack.rack_name,
              'heightU', rack.height_u,
              'descUnits', rack.desc_units,
              'siteId', CAST(site.site_id AS CHAR),
              'siteName', site.site_name,
              'siteType', site.site_type,
              'orgId', COALESCE(CAST(rack.org_unit_id AS CHAR), ''),
              'isActive', rack.is_active
            )
            FROM asset_rack rack
            JOIN asset_site site ON site.site_id = rack.site_id
            WHERE rack.rack_id = {rack_id_int}
            """,
            None,
        )

    def _assert_rack_access(self, context: dict, rack: dict) -> None:
        self.scope.assert_org_access(context, self.db.integer(rack.get("orgId"), 0))

    def _conflicting_placements(
        self,
        rack_id: int,
        position_u: int,
        u_height: int,
        face: str,
        ignore_placement_id: int = 0,
    ) -> list[dict]:
        ignore = f"AND placement.placement_id <> {ignore_placement_id}" if ignore_placement_id > 0 else ""
        face_filter = (
            "1 = 1"
            if face == "both"
            else f"(placement.face = 'both' OR placement.face = {self.db.quote(face)})"
        )
        return list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(placement.placement_id AS CHAR),
                  'name', placement.display_name,
                  'positionU', placement.position_u,
                  'uHeight', placement.u_height,
                  'face', placement.face
                )), JSON_ARRAY())
                FROM rack_device_placement placement
                WHERE placement.rack_id = {rack_id}
                  AND placement.is_active = 1
                  AND {face_filter}
                  AND placement.position_u <= {position_u + u_height - 1}
                  AND (placement.position_u + placement.u_height - 1) >= {position_u}
                  {ignore}
                """,
                [],
            )
            or []
        )

    def _validate_slot(
        self,
        rack: dict,
        position_u: int,
        u_height: int,
        face: str,
        ignore_placement_id: int = 0,
    ) -> None:
        rack_id = self.db.integer(rack.get("id"), 0)
        height = self.db.integer(rack.get("heightU"), 42)
        if position_u < 1:
            raise self.api_error("起始 U 位必须从 1 开始。")
        if u_height < MIN_U_HEIGHT or u_height > MAX_U_HEIGHT:
            raise self.api_error(f"占用高度必须在 {MIN_U_HEIGHT}-{MAX_U_HEIGHT}U 之间。")
        if position_u + u_height - 1 > height:
            raise self.conflict_error(
                f"超出机柜范围：{rack.get('name')} 共 {height}U，"
                f"U{position_u}-U{position_u + u_height - 1} 放不下。"
            )
        hits = self._conflicting_placements(rack_id, position_u, u_height, face, ignore_placement_id)
        if hits:
            names = "、".join(self.db.text(item.get("name")) for item in hits[:3])
            raise self.conflict_error(f"U 位已被占用（{names}），请换位置或先调整它。")

    @staticmethod
    def _occupied_units(placements: list[dict]) -> int:
        """Count distinct occupied U rows: front and rear planes share a row."""
        rows: set[int] = set()
        for placement in placements:
            position = int(placement.get("positionU") or 0)
            height = int(placement.get("uHeight") or 1)
            for unit in range(position, position + height):
                rows.add(unit)
        return len(rows)

    # -------------------------------------------------------------------- reads

    def list_racks(self, context: dict, params: dict[str, list[str]] | None = None) -> list[dict]:
        site_id = self.db.integer((params or {}).get("siteId", [""])[0], 0)
        filters = ["rack.is_active = 1", "site.is_active = 1"]
        if site_id > 0:
            filters.append(f"rack.site_id = {site_id}")
        org_filter = self._org_filter(context, "rack.org_unit_id")
        racks = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(rack.rack_id AS CHAR),
                  'code', rack.rack_code,
                  'name', rack.rack_name,
                  'heightU', rack.height_u,
                  'descUnits', rack.desc_units,
                  'siteId', CAST(rack.site_id AS CHAR),
                  'siteName', site.site_name,
                  'siteType', site.site_type,
                  'usedUnits', 0,
                  'deviceCount', 0
                )), JSON_ARRAY())
                FROM (
                  SELECT rack.rack_id, rack.rack_code, rack.rack_name, rack.height_u,
                         rack.desc_units, rack.site_id
                  FROM asset_rack rack
                  JOIN asset_site site ON site.site_id = rack.site_id
                  WHERE {' AND '.join(filters)}
                    {org_filter}
                  ORDER BY site.site_code, rack.rack_code
                ) rack
                JOIN asset_site site ON site.site_id = rack.site_id
                """,
                [],
            )
            or []
        )
        if not racks:
            return []
        rack_ids = ", ".join(str(self.db.integer(rack.get("id"), 0)) for rack in racks)
        rows = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'rackId', CAST(rack_id AS CHAR),
                  'positionU', position_u,
                  'uHeight', u_height
                )), JSON_ARRAY())
                FROM rack_device_placement
                WHERE is_active = 1 AND rack_id IN ({rack_ids})
                """,
                [],
            )
            or []
        )
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(self.db.text(row.get("rackId")), []).append(row)
        for rack in racks:
            own = grouped.get(self.db.text(rack.get("id")), [])
            rack["deviceCount"] = len(own)
            rack["usedUnits"] = self._occupied_units(own)
        return racks

    def list_placements(self, rack_id: object, context: dict) -> dict:
        rack = self._rack_row(rack_id)
        if not rack:
            raise self.api_error("机柜不存在。")
        self._assert_rack_access(context, rack)
        rack_id_int = self.db.integer(rack.get("id"), 0)
        placements = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(placement.placement_id AS CHAR),
                  'rackId', CAST(placement.rack_id AS CHAR),
                  'sourceKind', placement.source_kind,
                  'computerId', COALESCE(CAST(placement.computer_id AS CHAR), ''),
                  'inventoryModelId', COALESCE(CAST(placement.inventory_model_id AS CHAR), ''),
                  'name', placement.display_name,
                  'brandModel', placement.brand_model,
                  'category', placement.category,
                  'positionU', placement.position_u,
                  'uHeight', placement.u_height,
                  'face', placement.face,
                  'status', COALESCE(NULLIF(placement.status_snapshot, ''), placement.live_status, ''),
                  'assetCode', COALESCE(NULLIF(placement.asset_code, ''), placement.live_asset_code, ''),
                  'serialNumber', COALESCE(NULLIF(placement.serial_number, ''), placement.live_serial, ''),
                  'ownerLabel', COALESCE(NULLIF(placement.owner_label, ''), placement.live_owner, ''),
                  'notes', placement.notes
                )), JSON_ARRAY())
                FROM (
                  SELECT placement.placement_id, placement.rack_id, placement.source_kind,
                         placement.computer_id, placement.inventory_model_id, placement.display_name,
                         placement.brand_model, placement.category, placement.position_u,
                         placement.u_height, placement.face, placement.status_snapshot,
                         placement.asset_code, placement.serial_number, placement.owner_label,
                         placement.notes,
                         COALESCE(computer.it_asset_status, '') AS live_status,
                         COALESCE(computer.fixed_asset_code, '') AS live_asset_code,
                         COALESCE(computer.sn_st, '') AS live_serial,
                         COALESCE(holder.employee_name, '') AS live_owner
                  FROM rack_device_placement placement
                  LEFT JOIN computer_asset computer ON computer.computer_id = placement.computer_id
                  LEFT JOIN (
                    SELECT assignment.computer_id, employee.employee_name
                    FROM computer_assignment assignment
                    JOIN employee ON employee.employee_id = assignment.employee_id
                    WHERE assignment.returned_at IS NULL AND assignment.assignment_status = 'active'
                  ) holder ON holder.computer_id = placement.computer_id
                  WHERE placement.rack_id = {rack_id_int}
                    AND placement.is_active = 1
                  ORDER BY placement.position_u DESC, placement.placement_id
                ) placement
                """,
                [],
            )
            or []
        )
        used_units = self._occupied_units(placements)
        rack["placements"] = placements
        rack["usedUnits"] = used_units
        rack["freeUnits"] = max(0, self.db.integer(rack.get("heightU"), 0) - used_units)
        return rack

    def available_devices(self, context: dict, params: dict[str, list[str]] | None = None) -> dict:
        keyword = self.db.text((params or {}).get("keyword", [""])[0])[:64]
        keyword_sql = self.db.quote(f"%{keyword}%") if keyword else "NULL"
        keyword_filter = (
            f"AND (asset.device_name LIKE {keyword_sql} OR COALESCE(asset.fixed_asset_code, '') LIKE {keyword_sql} "
            f"OR COALESCE(asset.model, '') LIKE {keyword_sql})"
            if keyword
            else ""
        )
        org_filter = self._org_filter(context, "asset.org_unit_id")
        computers = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'computerId', CAST(asset.computer_id AS CHAR),
                  'name', asset.device_name,
                  'brandModel', TRIM(BOTH ' ' FROM CONCAT(COALESCE(asset.brand, ''), ' ', COALESCE(asset.model, ''))),
                  'category', CASE
                    WHEN COALESCE(asset.device_type, '') IN ('server', 'storage', 'network', 'power') THEN asset.device_type
                    ELSE 'server'
                  END,
                  'status', asset.it_asset_status,
                  'assetCode', COALESCE(asset.fixed_asset_code, ''),
                  'serialNumber', COALESCE(asset.sn_st, ''),
                  'ownerLabel', asset.holder_name
                )), JSON_ARRAY())
                FROM (
                  SELECT asset.computer_id, asset.device_name, asset.brand, asset.model, asset.device_type,
                         asset.it_asset_status, asset.fixed_asset_code, asset.sn_st,
                         COALESCE(holder.employee_name, '') AS holder_name
                  FROM computer_asset asset
                  LEFT JOIN (
                    SELECT assignment.computer_id, employee.employee_name
                    FROM computer_assignment assignment
                    JOIN employee ON employee.employee_id = assignment.employee_id
                    WHERE assignment.returned_at IS NULL AND assignment.assignment_status = 'active'
                  ) holder ON holder.computer_id = asset.computer_id
                  WHERE asset.is_active = 1
                    AND asset.is_archived = 0
                    AND NOT EXISTS (
                      SELECT 1 FROM rack_device_placement placement
                      WHERE placement.computer_id = asset.computer_id AND placement.is_active = 1
                    )
                    {keyword_filter}
                    {org_filter}
                  ORDER BY asset.device_name
                  LIMIT 200
                ) asset
                """,
                [],
            )
            or []
        )
        models = list(
            self.db.json(
                """
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'inventoryModelId', CAST(model.model_id AS CHAR),
                  'name', TRIM(BOTH ' ' FROM CONCAT(COALESCE(model.brand_name, ''), ' ', model.model_name)),
                  'brandModel', TRIM(BOTH ' ' FROM CONCAT(COALESCE(model.brand_name, ''), ' ', model.model_name)),
                  'category', CASE
                    WHEN COALESCE(model.type_name, '') LIKE '%交换%' OR COALESCE(model.type_name, '') LIKE '%路由%' THEN 'network'
                    WHEN COALESCE(model.type_name, '') LIKE '%UPS%' OR COALESCE(model.type_name, '') LIKE '%电源%' THEN 'power'
                    WHEN COALESCE(model.type_name, '') LIKE '%存储%' OR COALESCE(model.type_name, '') LIKE '%NAS%' THEN 'storage'
                    WHEN COALESCE(model.type_name, '') LIKE '%配线%' THEN 'patch-panel'
                    ELSE 'other'
                  END,
                  'quantity', model.quantity,
                  'typeName', COALESCE(model.type_name, ''),
                  'uHeight', 1
                )), JSON_ARRAY())
                FROM (
                  SELECT model.model_id, model.model_name, model.quantity,
                         COALESCE(brand.brand_name, '') AS brand_name,
                         COALESCE(type_row.type_name, '') AS type_name
                  FROM it_inventory_model model
                  LEFT JOIN it_inventory_brand brand ON brand.brand_id = model.brand_id
                  LEFT JOIN non_asset_type type_row ON type_row.non_asset_type_id = model.non_asset_type_id
                  WHERE model.quantity > 0
                  ORDER BY brand.brand_name, model.model_name
                  LIMIT 200
                ) model
                """,
                [],
            )
            or []
        )
        return {"computers": computers, "inventoryModels": models}

    # ------------------------------------------------------------------- writes

    def place_device(
        self,
        rack_id: object,
        payload: dict,
        context: dict,
        idempotency_key: str = "",
    ) -> dict:
        cached = self._idempotency_result("rack.placement.create", idempotency_key, payload)
        if cached:
            return cached

        rack = self._rack_row(rack_id)
        if not rack:
            raise self.api_error("机柜不存在。")
        if not parse_bool(rack.get("isActive"), True):
            raise self.conflict_error("该机柜已停用。")
        self._assert_rack_access(context, rack)
        rack_id_int = self.db.integer(rack.get("id"), 0)

        source_kind = self.db.text(payload.get("sourceKind")) or "custom"
        if source_kind not in SOURCE_KINDS:
            raise self.api_error("设备来源无效。")
        category = self.db.text(payload.get("category")) or "other"
        if category not in CATEGORIES:
            raise self.api_error("设备类型无效。")
        face = self.db.text(payload.get("face")) or "front"
        if face not in FACES:
            raise self.api_error("安装面板无效。")
        position_u = self.db.integer(payload.get("positionU"), 0)
        u_height = self.db.integer(payload.get("uHeight"), 1)
        notes = self.db.text(payload.get("notes"))[:500]

        computer_id = 0
        inventory_model_id = self.db.integer(payload.get("inventoryModelId"), 0)
        display_name = self.db.text(payload.get("displayName"))[:128]
        brand_model = self.db.text(payload.get("brandModel"))[:160]
        asset_code = ""
        serial_number = ""
        status_snapshot = ""
        owner_label = self.db.text(payload.get("ownerLabel"))[:128]

        if source_kind == "computer":
            computer_id = self.db.integer(payload.get("computerId"), 0)
            if computer_id <= 0:
                raise self.api_error("请选择要上架的办公终端。")
            computer = self.db.json(
                f"""
                SELECT JSON_OBJECT(
                  'id', CAST(asset.computer_id AS CHAR),
                  'name', asset.device_name,
                  'brand', COALESCE(asset.brand, ''),
                  'model', COALESCE(asset.model, ''),
                  'status', asset.it_asset_status,
                  'assetCode', COALESCE(asset.fixed_asset_code, ''),
                  'serialNumber', COALESCE(asset.sn_st, ''),
                  'orgId', COALESCE(CAST(asset.org_unit_id AS CHAR), ''),
                  'isArchived', asset.is_archived,
                  'ownerLabel', COALESCE(holder.employee_name, '')
                )
                FROM computer_asset asset
                LEFT JOIN (
                  SELECT assignment.computer_id, employee.employee_name
                  FROM computer_assignment assignment
                  JOIN employee ON employee.employee_id = assignment.employee_id
                  WHERE assignment.returned_at IS NULL AND assignment.assignment_status = 'active'
                ) holder ON holder.computer_id = asset.computer_id
                WHERE asset.computer_id = {computer_id}
                  AND asset.is_active = 1
                """,
                None,
            )
            if not computer:
                raise self.api_error("办公终端不存在或已停用。")
            if parse_bool(computer.get("isArchived")):
                raise self.conflict_error("已报废归档的办公终端不能上架。")
            self.scope.assert_org_access(context, self.db.integer(computer.get("orgId"), 0))
            existing = self.db.scalar(
                f"""
                SELECT COUNT(*) FROM rack_device_placement placement
                WHERE placement.computer_id = {computer_id} AND placement.is_active = 1;
                """
            )
            if existing > 0:
                raise self.conflict_error("该办公终端已经在某个机柜上架，请先下架或直接移动。")
            display_name = display_name or self.db.text(computer.get("name"))
            brand_model = brand_model or " ".join(
                part for part in [self.db.text(computer.get("brand")), self.db.text(computer.get("model"))] if part
            )[:160]
            asset_code = self.db.text(computer.get("assetCode"))[:128]
            serial_number = self.db.text(computer.get("serialNumber"))[:128]
            status_snapshot = self.db.text(computer.get("status"))[:32]
            owner_label = owner_label or self.db.text(computer.get("ownerLabel"))[:128]
        if not display_name:
            raise self.api_error("设备名称不能为空。")

        self._validate_slot(rack, position_u, u_height, face)
        actor_id = self._actor_id(context)
        output = self.db.execute(
            f"""
            START TRANSACTION;
            INSERT INTO rack_device_placement (
              rack_id, source_kind, computer_id, inventory_model_id, display_name, brand_model,
              category, position_u, u_height, face, status_snapshot, asset_code, serial_number,
              owner_label, notes, created_by, updated_by
            )
            VALUES (
              {rack_id_int},
              {self.db.quote(source_kind)},
              {computer_id if computer_id > 0 else 'NULL'},
              {inventory_model_id if inventory_model_id > 0 else 'NULL'},
              {self.db.quote(display_name)},
              {self.db.quote(brand_model)},
              {self.db.quote(category)},
              {position_u},
              {u_height},
              {self.db.quote(face)},
              {self.db.quote(status_snapshot)},
              {self.db.quote(asset_code)},
              {self.db.quote(serial_number)},
              {self.db.quote(owner_label)},
              {self.db.quote(notes)},
              {actor_id if actor_id > 0 else 'NULL'},
              {actor_id if actor_id > 0 else 'NULL'}
            );
            SET @new_placement_id = LAST_INSERT_ID();
            {self._audit_sql(
                "rack_placement_created",
                "rack_device_placement",
                "'new'",
                display_name,
                f"机柜上架：{rack.get('name')} U{position_u} {display_name}",
                context,
                None,
                {
                    "rackId": str(rack_id_int),
                    "positionU": position_u,
                    "uHeight": u_height,
                    "face": face,
                    "sourceKind": source_kind,
                },
            )};
            UPDATE audit_log
            SET entity_id = CAST(@new_placement_id AS CHAR)
            WHERE audit_log_id = LAST_INSERT_ID();
            SELECT @new_placement_id;
            COMMIT;
            """
        )
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        placement_id = self.db.integer(lines[-1] if lines else 0, 0)
        if placement_id <= 0:
            raise self.conflict_error("上架失败，请重试。")
        response = {"id": str(placement_id), "rackId": str(rack_id_int), "positionU": position_u}
        self._store_idempotency_result("rack.placement.create", idempotency_key, payload, response)
        return response

    def update_placement(self, placement_id: object, payload: dict, context: dict) -> dict:
        placement = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(placement.placement_id AS CHAR),
              'rackId', CAST(placement.rack_id AS CHAR),
              'name', placement.display_name,
              'brandModel', placement.brand_model,
              'category', placement.category,
              'positionU', placement.position_u,
              'uHeight', placement.u_height,
              'face', placement.face,
              'notes', placement.notes,
              'orgId', COALESCE(CAST(rack.org_unit_id AS CHAR), '')
            )
            FROM rack_device_placement placement
            JOIN asset_rack rack ON rack.rack_id = placement.rack_id
            WHERE placement.placement_id = {self.db.integer(placement_id, 0)}
              AND placement.is_active = 1
            """,
            None,
        )
        if not placement:
            raise self.api_error("机柜位置记录不存在或已下架。")
        self.scope.assert_org_access(context, self.db.integer(placement.get("orgId"), 0))

        target_rack_id = self.db.integer(payload.get("rackId", placement.get("rackId")), 0)
        rack = self._rack_row(target_rack_id)
        if not rack:
            raise self.api_error("目标机柜不存在。")
        self._assert_rack_access(context, rack)

        position_u = self.db.integer(payload.get("positionU", placement.get("positionU")), 0)
        u_height = self.db.integer(payload.get("uHeight", placement.get("uHeight")), 1)
        face = self.db.text(payload.get("face", placement.get("face"))) or "front"
        if face not in FACES:
            raise self.api_error("安装面板无效。")
        category = self.db.text(payload.get("category", placement.get("category"))) or "other"
        if category not in CATEGORIES:
            raise self.api_error("设备类型无效。")
        display_name = self.db.text(payload.get("displayName", placement.get("name")))[:128]
        if not display_name:
            raise self.api_error("设备名称不能为空。")
        brand_model = self.db.text(payload.get("brandModel", placement.get("brandModel")))[:160]
        notes = self.db.text(payload.get("notes", placement.get("notes")))[:500]
        placement_id_int = self.db.integer(placement.get("id"), 0)
        self._validate_slot(rack, position_u, u_height, face, placement_id_int)

        actor_id = self._actor_id(context)
        self.db.execute(
            f"""
            START TRANSACTION;
            UPDATE rack_device_placement
            SET rack_id = {self.db.integer(rack.get('id'), 0)},
                display_name = {self.db.quote(display_name)},
                brand_model = {self.db.quote(brand_model)},
                category = {self.db.quote(category)},
                position_u = {position_u},
                u_height = {u_height},
                face = {self.db.quote(face)},
                notes = {self.db.quote(notes)},
                updated_by = {actor_id if actor_id > 0 else 'NULL'}
            WHERE placement_id = {placement_id_int};
            {self._audit_sql(
                "rack_placement_updated",
                "rack_device_placement",
                str(placement_id_int),
                display_name,
                f"机柜位置变更：{display_name} → {rack.get('name')} U{position_u}（{u_height}U / {face}）",
                context,
                {
                    "rackId": self.db.text(placement.get("rackId")),
                    "positionU": self.db.integer(placement.get("positionU"), 0),
                    "uHeight": self.db.integer(placement.get("uHeight"), 1),
                    "face": self.db.text(placement.get("face")),
                },
                {
                    "rackId": str(self.db.integer(rack.get("id"), 0)),
                    "positionU": position_u,
                    "uHeight": u_height,
                    "face": face,
                },
            )};
            COMMIT;
            """
        )
        return {
            "id": str(placement_id_int),
            "rackId": str(self.db.integer(rack.get("id"), 0)),
            "positionU": position_u,
            "uHeight": u_height,
            "face": face,
        }

    def remove_placement(self, placement_id: object, payload: dict, context: dict) -> dict:
        placement = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(placement.placement_id AS CHAR),
              'rackId', CAST(placement.rack_id AS CHAR),
              'name', placement.display_name,
              'positionU', placement.position_u,
              'uHeight', placement.u_height,
              'face', placement.face,
              'orgId', COALESCE(CAST(rack.org_unit_id AS CHAR), '')
            )
            FROM rack_device_placement placement
            JOIN asset_rack rack ON rack.rack_id = placement.rack_id
            WHERE placement.placement_id = {self.db.integer(placement_id, 0)}
              AND placement.is_active = 1
            """,
            None,
        )
        if not placement:
            raise self.api_error("机柜位置记录不存在或已下架。")
        self.scope.assert_org_access(context, self.db.integer(placement.get("orgId"), 0))
        reason = self.db.text(payload.get("reason"))[:500]
        placement_id_int = self.db.integer(placement.get("id"), 0)
        actor_id = self._actor_id(context)
        self.db.execute(
            f"""
            START TRANSACTION;
            UPDATE rack_device_placement
            SET is_active = 0,
                notes = {self.db.quote(reason or self.db.text(placement.get('name')))},
                updated_by = {actor_id if actor_id > 0 else 'NULL'}
            WHERE placement_id = {placement_id_int};
            {self._audit_sql(
                "rack_placement_removed",
                "rack_device_placement",
                str(placement_id_int),
                self.db.text(placement.get("name")),
                f"机柜下架：{self.db.text(placement.get('name'))}（U{self.db.integer(placement.get('positionU'), 0)}）"
                + (f"，原因：{reason}" if reason else ""),
                context,
                {
                    "rackId": self.db.text(placement.get("rackId")),
                    "positionU": self.db.integer(placement.get("positionU"), 0),
                },
                {"isActive": False, "reason": reason},
            )};
            COMMIT;
            """
        )
        return {"id": str(placement_id_int), "removed": True}
