"""设备面板与网络拓扑（阶段 1/2）。

本模块负责三件事：

1. **型号库**：从 NetBox devicetype-library 的 YAML 解析厂商型号与端口模板，
   也支持手工维护；端口模板在设备上架时复制成实例端口（快照）。
2. **端口与线缆**：端口属于已上架设备；一个端口最多只能挂一条活动链路，
   不允许自己连自己，跨机柜与跨站点允许（骨干需要）。
3. **拓扑坐标**：自动分层在前端计算，人工拖动后的坐标可选保存。

解析器只覆盖 devicetype YAML 需要的子集（顶层标量 + 端口列表），不引入第三方依赖。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from .sql import SqlGateway, parse_bool


PORT_KINDS = {"network", "fiber", "power", "console", "other"}
FACES = {"front", "rear"}
DIRECTIONS = {"in", "out", "bidi"}
PORT_STATUSES = {"up", "down", "disabled", "unknown"}
MEDIUMS = {"cat5e", "cat6", "fiber-om3", "fiber-os2", "dac", "power", "console", "other"}
CABLE_STATUSES = {"connected", "planned", "disconnected", "fault"}
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
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

FIBER_HINTS = ("sfp", "sfpp", "base-x", "base-lr", "base-sr", "qsfp", "fiber", "optical")
POWER_HINTS = ("power", "psu", "iec-", "nema-", "c13", "c14", "c19", "c20")
CONSOLE_HINTS = ("console", "rj-45 console", "usb-console", "de-9")


def _unquote(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _kind_for(port_type: str, section: str) -> str:
    lowered = f"{port_type} {section}".lower()
    if section == "power-ports" or any(hint in lowered for hint in POWER_HINTS):
        return "power"
    if section == "console-ports" or any(hint in lowered for hint in CONSOLE_HINTS):
        return "console"
    if any(hint in lowered for hint in FIBER_HINTS):
        return "fiber"
    if lowered.strip():
        return "network"
    return "other"


PORT_SECTIONS = {
    "interfaces": "network",
    "power-ports": "power",
    "power-ports:": "power",
    "console-ports": "console",
    "console-server-ports": "console",
}


def parse_device_type_yaml(text: str) -> dict:
    """Parse the NetBox devicetype YAML subset into a device type dict.

    Only top-level scalars and the port lists (``interfaces``, ``power-ports``,
    ``console-ports``) are read; block scalars such as ``comments: |`` are skipped.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("YAML 内容为空。")
    scalars: dict[str, str] = {}
    ports: list[dict[str, str]] = []
    section = ""
    current: dict[str, str] | None = None
    skipping_block = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped in {"---", "..."}:
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            skipping_block = False
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if value in {"|", ">"}:
                skipping_block = True
                continue
            if value:
                scalars[key] = _unquote(value)
                section = ""
                current = None
                continue
            section = key
            current = None
            continue
        if skipping_block:
            continue
        if not section:
            continue
        if stripped.startswith("- "):
            name, _, value = stripped[2:].partition(":")
            current = {"__section": section}
            if name.strip() == "name":
                current["name"] = _unquote(value)
            if name.strip() not in {"name", ""}:
                current[name.strip()] = _unquote(value)
            ports.append(current)
            continue
        if current is None:
            continue
        key, _, value = stripped.partition(":")
        current[key.strip()] = _unquote(value)

    if not scalars.get("slug") and not scalars.get("model"):
        raise ValueError("YAML 缺少 slug 与 model，无法识别型号。")

    slug = (scalars.get("slug") or "").strip().lower()
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", f"{scalars.get('manufacturer', '')} {scalars.get('model', '')}".lower()).strip("-")
    if not SLUG_PATTERN.match(slug):
        raise ValueError(f"型号 slug 不合法：{slug}")

    try:
        u_height = float(scalars.get("u_height", "1") or 1)
    except ValueError as exc:
        raise ValueError("u_height 不是数字。") from exc
    u_height = min(50.0, max(0.5, u_height))

    parsed_ports: list[dict] = []
    counters: dict[str, int] = {}
    for item in ports:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        port_type = (item.get("type") or "").strip()
        kind = _kind_for(port_type, item.get("__section") or section)
        counters[kind] = counters.get(kind, 0) + 1
        parsed_ports.append(
            {
                "name": name[:64],
                "type": port_type[:64],
                "kind": kind,
                "face": "front" if kind != "power" else "rear",
            }
        )

    return {
        "slug": slug,
        "manufacturer": (scalars.get("manufacturer") or "")[:100],
        "model": (scalars.get("model") or slug)[:128],
        "part_number": (scalars.get("part_number") or "")[:100],
        "u_height": u_height,
        "category": infer_category(scalars.get("model", ""), scalars.get("slug", "")),
        "is_full_depth": parse_bool(scalars.get("is_full_depth", "true"), True),
        "front_image": parse_bool(scalars.get("front_image")),
        "rear_image": parse_bool(scalars.get("rear_image")),
        "ports": parsed_ports,
    }


def infer_category(model: str, slug: str) -> str:
    """Infer a rack category from the vendor model name."""
    text = f"{model} {slug}".lower()
    rules = [
        ("patch-panel", ("patch panel", "patch-panel", "patchpanel", "配线架")),
        ("power", ("ups", "pdu", "power supply", "psu")),
        ("storage", ("nas", "storage", "disk array", "rx1217", "rs1221")),
        ("kvm", ("kvm", "console drawer", "console server")),
        ("cooling", ("fan", "cooling", "散热")),
        ("shelf", ("shelf", "tray", "层板")),
        ("blank", ("blank", "filler", "挡板")),
        ("cable-management", ("cable manage", "brush", "理线")),
        ("network", ("switch", "router", "firewall", "gateway", "access point", "交换机", "路由", "防火墙")),
        ("server", ("poweredge", "proliant", "thinksystem", "uniserver", "server", "服务器")),
    ]
    for category, hints in rules:
        if any(hint in text for hint in hints):
            return category
    return "other"


def layout_template_ports(ports: list[dict]) -> list[dict]:
    """Assign row/position indexes so the panel view can render rows deterministically."""
    rows: dict[str, int] = {}
    counters: dict[str, int] = {}
    layouted: list[dict] = []
    order = {"network": 0, "fiber": 1, "power": 2, "console": 3, "other": 4}
    for item in sorted(ports, key=lambda entry: order.get(entry["kind"], 9)):
        kind = item["kind"]
        rows.setdefault(kind, len(rows) + 1)
        counters[kind] = counters.get(kind, 0) + 1
        per_row = 24 if kind in {"network", "fiber"} else 6
        position = counters[kind]
        layouted.append(
            {
                **item,
                "row_index": rows[kind] + (position - 1) // per_row,
                "position_index": (position - 1) % per_row + 1,
            }
        )
    return layouted


def _image_path(manufacturer: str, slug: str, face: str, ext: str = "png") -> str:
    vendor = re.sub(r"[^a-z0-9]+", "-", (manufacturer or "vendor").lower()).strip("-") or "vendor"
    return f"/assets/device-images/{vendor}/{slug}.{face}.{ext}"


def upsert_device_type(
    db: SqlGateway,
    parsed: dict,
    *,
    source: str,
    source_ref: str = "",
    image_paths: dict[str, str] | None = None,
) -> dict:
    """Insert or update a device type together with its port template rows."""
    slug = db.text(parsed.get("slug"))
    if not SLUG_PATTERN.match(slug):
        raise ValueError(f"型号 slug 不合法：{slug}")
    category = db.text(parsed.get("category")) or "other"
    if category not in CATEGORIES:
        category = "other"
    ports = layout_template_ports(list(parsed.get("ports") or []))
    has_image_info = image_paths is not None
    images = image_paths or {}
    front_path = db.text(images.get("front"))[:255]
    rear_path = db.text(images.get("rear"))[:255]
    if has_image_info:
        front_flag = 1 if front_path else 0
        rear_flag = 1 if rear_path else 0
    else:
        front_flag = 1 if parse_bool(parsed.get("front_image")) else 0
        rear_flag = 1 if parse_bool(parsed.get("rear_image")) else 0
    db.execute(
        f"""
        INSERT INTO device_type_catalog (
          slug, manufacturer, model, part_number, u_height, category, is_full_depth,
          front_image, rear_image, image_front_path, image_rear_path, source, source_ref
        )
        VALUES (
          {db.quote(slug)},
          {db.quote(db.text(parsed.get('manufacturer'))[:100])},
          {db.quote(db.text(parsed.get('model'))[:128])},
          {db.quote(db.text(parsed.get('part_number'))[:100])},
          {float(parsed.get('u_height') or 1)},
          {db.quote(category)},
          {1 if parse_bool(parsed.get('is_full_depth'), True) else 0},
          {front_flag},
          {rear_flag},
          {db.quote(front_path)},
          {db.quote(rear_path)},
          {db.quote(source[:32])},
          {db.quote(source_ref[:255])}
        )
        ON DUPLICATE KEY UPDATE
          manufacturer = VALUES(manufacturer),
          model = VALUES(model),
          part_number = VALUES(part_number),
          u_height = VALUES(u_height),
          category = VALUES(category),
          is_full_depth = VALUES(is_full_depth),
          front_image = VALUES(front_image),
          rear_image = VALUES(rear_image),
          image_front_path = VALUES(image_front_path),
          image_rear_path = VALUES(image_rear_path),
          source = VALUES(source),
          source_ref = VALUES(source_ref),
          is_active = 1;
        """
    )
    catalog_id = db.scalar(f"SELECT catalog_id FROM device_type_catalog WHERE slug = {db.quote(slug)};")
    if catalog_id <= 0:
        raise RuntimeError("型号写入失败。")
    db.execute(f"DELETE FROM device_type_port_template WHERE catalog_id = {catalog_id};")
    if ports:
        values = []
        for item in ports:
            values.append(
                "("
                + ", ".join(
                    [
                        str(catalog_id),
                        db.quote(item["face"]),
                        db.quote(item["name"]),
                        db.quote(item.get("type", "")),
                        db.quote(item["kind"]),
                        str(int(item.get("row_index", 1))),
                        str(int(item.get("position_index", 1))),
                    ]
                )
                + ")"
            )
        db.execute(
            "INSERT INTO device_type_port_template ("
            "catalog_id, face, port_name, port_type, port_kind, row_index, position_index"
            ") VALUES " + ", ".join(values) + ";"
        )
    return {"catalogId": str(catalog_id), "slug": slug, "portCount": len(ports)}


@dataclass
class DeviceTopologyService:
    db: SqlGateway
    scope: object
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
            SELECT JSON_OBJECT('requestHash', request_hash, 'response', response_json)
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

    def _placement_row(self, placement_id: object) -> dict | None:
        placement_id_int = self.db.integer(placement_id, 0)
        if placement_id_int <= 0:
            return None
        return self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(placement.placement_id AS CHAR),
              'name', placement.display_name,
              'brandModel', placement.brand_model,
              'category', placement.category,
              'rackId', CAST(placement.rack_id AS CHAR),
              'rackName', rack.rack_name,
              'siteId', CAST(site.site_id AS CHAR),
              'siteName', site.site_name,
              'orgId', COALESCE(CAST(rack.org_unit_id AS CHAR), ''),
              'uHeight', placement.u_height,
              'positionU', placement.position_u,
              'isActive', placement.is_active
            )
            FROM rack_device_placement placement
            JOIN asset_rack rack ON rack.rack_id = placement.rack_id
            JOIN asset_site site ON site.site_id = rack.site_id
            WHERE placement.placement_id = {placement_id_int}
              AND placement.is_active = 1
            """,
            None,
        )

    def _port_row(self, port_id: object) -> dict | None:
        port_id_int = self.db.integer(port_id, 0)
        if port_id_int <= 0:
            return None
        return self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(port.port_id AS CHAR),
              'placementId', CAST(port.placement_id AS CHAR),
              'placementName', placement.display_name,
              'rackId', CAST(placement.rack_id AS CHAR),
              'orgId', COALESCE(CAST(rack.org_unit_id AS CHAR), ''),
              'face', port.face,
              'name', port.port_name,
              'type', port.port_type,
              'kind', port.port_kind,
              'rowIndex', port.row_index,
              'positionIndex', port.position_index,
              'direction', port.direction,
              'speed', port.speed,
              'status', port.status,
              'notes', port.notes
            )
            FROM rack_device_port port
            JOIN rack_device_placement placement ON placement.placement_id = port.placement_id
            JOIN asset_rack rack ON rack.rack_id = placement.rack_id
            WHERE port.port_id = {port_id_int}
            """,
            None,
        )

    def _assert_org(self, context: dict, org_id: object) -> None:
        self.scope.assert_org_access(context, self.db.integer(org_id, 0))

    # -------------------------------------------------------------- device types

    def list_device_types(self, context: dict, params: dict[str, list[str]] | None = None) -> list[dict]:
        keyword = self.db.text((params or {}).get("keyword", [""])[0])[:64]
        keyword_sql = self.db.quote(f"%{keyword}%") if keyword else "NULL"
        keyword_filter = (
            f"AND (catalog.model LIKE {keyword_sql} OR catalog.manufacturer LIKE {keyword_sql} "
            f"OR catalog.slug LIKE {keyword_sql})"
            if keyword
            else ""
        )
        return list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(catalog.catalog_id AS CHAR),
                  'slug', catalog.slug,
                  'manufacturer', catalog.manufacturer,
                  'model', catalog.model,
                  'partNumber', catalog.part_number,
                  'uHeight', catalog.u_height,
                  'category', catalog.category,
                  'frontImage', catalog.front_image,
                  'rearImage', catalog.rear_image,
                  'imageFrontPath', catalog.image_front_path,
                  'imageRearPath', catalog.image_rear_path,
                  'source', catalog.source,
                  'portCount', catalog.port_count,
                  'isActive', catalog.is_active
                )), JSON_ARRAY())
                FROM (
                  SELECT catalog.*, (
                    SELECT COUNT(*) FROM device_type_port_template template
                    WHERE template.catalog_id = catalog.catalog_id
                  ) AS port_count
                  FROM device_type_catalog catalog
                  WHERE catalog.is_active = 1
                    {keyword_filter}
                  ORDER BY catalog.manufacturer, catalog.model
                  LIMIT 500
                ) catalog
                """,
                [],
            )
            or []
        )

    def get_device_type(self, catalog_id: object, context: dict) -> dict:
        catalog = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(catalog_id AS CHAR),
              'slug', slug,
              'manufacturer', manufacturer,
              'model', model,
              'partNumber', part_number,
              'uHeight', u_height,
              'category', category,
              'isFullDepth', is_full_depth,
              'frontImage', front_image,
              'rearImage', rear_image,
              'imageFrontPath', image_front_path,
              'imageRearPath', image_rear_path,
              'source', source,
              'isActive', is_active
            )
            FROM device_type_catalog
            WHERE catalog_id = {self.db.integer(catalog_id, 0)}
            """,
            None,
        )
        if not catalog:
            raise self.api_error("型号不存在。")
        catalog_id_int = self.db.integer(catalog.get("id"), 0)
        catalog["ports"] = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'name', port_name,
                  'type', port_type,
                  'kind', port_kind,
                  'face', face,
                  'rowIndex', row_index,
                  'positionIndex', position_index
                )), JSON_ARRAY())
                FROM (
                  SELECT * FROM device_type_port_template
                  WHERE catalog_id = {catalog_id_int}
                  ORDER BY face, row_index, position_index, template_port_id
                ) template
                """,
                [],
            )
            or []
        )
        return catalog

    def import_device_type(self, payload: dict, context: dict) -> dict:
        source = self.db.text(payload.get("source")) or "inline"
        if source not in {"inline", "netbox"}:
            raise self.api_error("导入来源只支持 inline 或 netbox。")
        yaml_text = self.db.text(payload.get("yamlText"))
        source_ref = self.db.text(payload.get("sourceRef"))[:255]
        if source == "netbox":
            slug = self.db.text(payload.get("slug")).strip().lower()
            if not SLUG_PATTERN.match(slug):
                raise self.api_error("请提供合法的型号 slug。")
            yaml_text = fetch_netbox_yaml(slug)
            source_ref = source_ref or f"netbox:{slug}"
        try:
            parsed = parse_device_type_yaml(yaml_text)
        except ValueError as exc:
            raise self.api_error(f"型号 YAML 解析失败：{exc}") from exc
        result = upsert_device_type(
            self.db,
            parsed,
            source=source,
            source_ref=source_ref,
            # 接口导入不落图片文件，面板图由 tools/import_device_types.py 下载后写入路径。
            image_paths={},
        )
        self.db.execute(
            self._audit_sql(
                "device_type_imported",
                "device_type_catalog",
                result["catalogId"],
                f"{parsed['manufacturer']} {parsed['model']}".strip(),
                f"导入型号：{parsed['slug']}（{result['portCount']} 个端口模板）",
                context,
                None,
                {"slug": parsed["slug"], "source": source, "portCount": result["portCount"]},
            )
            + ";"
        )
        return result

    # --------------------------------------------------------------------- ports

    def list_rack_ports(self, rack_id: object, context: dict) -> dict:
        rack = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(rack.rack_id AS CHAR),
              'name', rack.rack_name,
              'code', rack.rack_code,
              'heightU', rack.height_u,
              'siteName', site.site_name,
              'orgId', COALESCE(CAST(rack.org_unit_id AS CHAR), '')
            )
            FROM asset_rack rack
            JOIN asset_site site ON site.site_id = rack.site_id
            WHERE rack.rack_id = {self.db.integer(rack_id, 0)}
            """,
            None,
        )
        if not rack:
            raise self.api_error("机柜不存在。")
        self._assert_org(context, rack.get("orgId"))
        rack_id_int = self.db.integer(rack.get("id"), 0)
        placements = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'placementId', CAST(placement.placement_id AS CHAR),
                  'name', placement.display_name,
                  'brandModel', placement.brand_model,
                  'category', placement.category,
                  'positionU', placement.position_u,
                  'uHeight', placement.u_height,
                  'face', placement.face,
                  'catalogSlug', placement.catalog_slug,
                  'ports', COALESCE(placement.ports, JSON_ARRAY())
                )), JSON_ARRAY())
                FROM (
                  SELECT placement.placement_id, placement.display_name, placement.brand_model,
                         placement.category, placement.position_u, placement.u_height, placement.face,
                         COALESCE(catalog.slug, '') AS catalog_slug,
                         (
                           SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                             'id', CAST(port.port_id AS CHAR),
                             'name', port.port_name,
                             'type', port.port_type,
                             'kind', port.port_kind,
                             'face', port.face,
                             'rowIndex', port.row_index,
                             'positionIndex', port.position_index,
                             'direction', port.direction,
                             'speed', port.speed,
                             'status', port.status,
                             'notes', port.notes,
                             'cableId', COALESCE(CAST(cable.cable_id AS CHAR), ''),
                             'cableLabel', COALESCE(cable.label, ''),
                             'cableMedium', COALESCE(cable.medium, ''),
                             'cableStatus', COALESCE(cable.status, ''),
                             'peerPlacementId', COALESCE(CAST(peer_placement.placement_id AS CHAR), ''),
                             'peerPlacementName', COALESCE(peer_placement.display_name, ''),
                             'peerPortName', COALESCE(peer_port.port_name, '')
                           )), JSON_ARRAY())
                           FROM rack_device_port port
                           LEFT JOIN rack_cable_run cable
                             ON cable.is_active = 1 AND (cable.a_port_id = port.port_id OR cable.b_port_id = port.port_id)
                           LEFT JOIN rack_device_port peer_port
                             ON peer_port.port_id = IF(cable.a_port_id = port.port_id, cable.b_port_id, cable.a_port_id)
                           LEFT JOIN rack_device_placement peer_placement
                             ON peer_placement.placement_id = peer_port.placement_id
                           WHERE port.placement_id = placement.placement_id
                           ORDER BY port.face, port.row_index, port.position_index, port.port_id
                         ) AS ports
                  FROM rack_device_placement placement
                  LEFT JOIN device_type_catalog catalog
                    ON catalog.catalog_id = (
                      SELECT catalog_row.catalog_id FROM device_type_catalog catalog_row
                      WHERE catalog_row.is_active = 1
                        AND catalog_row.model <> ''
                        AND placement.brand_model LIKE CONCAT('%', catalog_row.model, '%')
                      ORDER BY CHAR_LENGTH(catalog_row.model) DESC
                      LIMIT 1
                    )
                  WHERE placement.rack_id = {rack_id_int}
                    AND placement.is_active = 1
                  ORDER BY placement.position_u DESC, placement.placement_id
                ) placement
                """,
                [],
            )
            or []
        )
        rack["placements"] = placements
        rack["portCount"] = sum(len(item.get("ports") or []) for item in placements)
        return rack

    def _validate_port_payload(self, payload: dict) -> dict:
        face = self.db.text(payload.get("face")) or "front"
        if face not in FACES:
            raise self.api_error("端口面板无效。")
        name = self.db.text(payload.get("name"))[:64]
        if not name:
            raise self.api_error("端口名称不能为空。")
        kind = self.db.text(payload.get("kind")) or "network"
        if kind not in PORT_KINDS:
            raise self.api_error("端口类型无效。")
        direction = self.db.text(payload.get("direction")) or "bidi"
        if direction not in DIRECTIONS:
            raise self.api_error("端口方向无效。")
        status = self.db.text(payload.get("status")) or "unknown"
        if status not in PORT_STATUSES:
            raise self.api_error("端口状态无效。")
        return {
            "face": face,
            "name": name,
            "type": self.db.text(payload.get("type"))[:64],
            "kind": kind,
            "rowIndex": max(1, self.db.integer(payload.get("rowIndex"), 1)),
            "positionIndex": max(1, self.db.integer(payload.get("positionIndex"), 1)),
            "direction": direction,
            "speed": self.db.text(payload.get("speed"))[:32],
            "status": status,
            "notes": self.db.text(payload.get("notes"))[:255],
        }

    def create_port(self, placement_id: object, payload: dict, context: dict) -> dict:
        placement = self._placement_row(placement_id)
        if not placement:
            raise self.api_error("设备不在机柜里，无法维护端口。")
        self._assert_org(context, placement.get("orgId"))
        fields = self._validate_port_payload(payload)
        placement_id_int = self.db.integer(placement.get("id"), 0)
        port_id = self._last_int(
            self.db.execute(
                f"""
            INSERT INTO rack_device_port (
              placement_id, face, port_name, port_type, port_kind, row_index, position_index,
              direction, speed, status, notes
            )
            VALUES (
              {placement_id_int},
              {self.db.quote(fields['face'])},
              {self.db.quote(fields['name'])},
              {self.db.quote(fields['type'])},
              {self.db.quote(fields['kind'])},
              {fields['rowIndex']},
              {fields['positionIndex']},
              {self.db.quote(fields['direction'])},
              {self.db.quote(fields['speed'])},
              {self.db.quote(fields['status'])},
              {self.db.quote(fields['notes'])}
            );
            SELECT LAST_INSERT_ID();
            """
            )
        )
        if port_id <= 0:
            raise self.conflict_error("端口名称在该设备上已存在。")
        self.db.execute(
            self._audit_sql(
                "rack_port_created",
                "rack_device_port",
                str(port_id),
                f"{self.db.text(placement.get('name'))} / {fields['name']}",
                f"新增端口：{self.db.text(placement.get('name'))} {fields['name']}",
                context,
                None,
                {"placementId": str(placement_id_int), **fields},
            )
            + ";"
        )
        return {"id": str(port_id), "placementId": str(placement_id_int), "name": fields["name"]}

    def update_port(self, port_id: object, payload: dict, context: dict) -> dict:
        port = self._port_row(port_id)
        if not port:
            raise self.api_error("端口不存在。")
        self._assert_org(context, port.get("orgId"))
        merged = {
            "face": payload.get("face", port.get("face")),
            "name": payload.get("name", port.get("name")),
            "type": payload.get("type", port.get("type")),
            "kind": payload.get("kind", port.get("kind")),
            "rowIndex": payload.get("rowIndex", port.get("rowIndex")),
            "positionIndex": payload.get("positionIndex", port.get("positionIndex")),
            "direction": payload.get("direction", port.get("direction")),
            "speed": payload.get("speed", port.get("speed")),
            "status": payload.get("status", port.get("status")),
            "notes": payload.get("notes", port.get("notes")),
        }
        fields = self._validate_port_payload(merged)
        port_id_int = self.db.integer(port.get("id"), 0)
        self.db.execute(
            f"""
            UPDATE rack_device_port
            SET face = {self.db.quote(fields['face'])},
                port_name = {self.db.quote(fields['name'])},
                port_type = {self.db.quote(fields['type'])},
                port_kind = {self.db.quote(fields['kind'])},
                row_index = {fields['rowIndex']},
                position_index = {fields['positionIndex']},
                direction = {self.db.quote(fields['direction'])},
                speed = {self.db.quote(fields['speed'])},
                status = {self.db.quote(fields['status'])},
                notes = {self.db.quote(fields['notes'])}
            WHERE port_id = {port_id_int};
            """
        )
        self.db.execute(
            self._audit_sql(
                "rack_port_updated",
                "rack_device_port",
                str(port_id_int),
                f"{self.db.text(port.get('placementName'))} / {fields['name']}",
                f"更新端口：{self.db.text(port.get('placementName'))} {fields['name']}",
                context,
                port,
                fields,
            )
            + ";"
        )
        return {"id": str(port_id_int), **fields}

    def remove_port(self, port_id: object, payload: dict, context: dict) -> dict:
        port = self._port_row(port_id)
        if not port:
            raise self.api_error("端口不存在。")
        self._assert_org(context, port.get("orgId"))
        port_id_int = self.db.integer(port.get("id"), 0)
        cables = self.db.scalar(
            f"SELECT COUNT(*) FROM rack_cable_run WHERE is_active = 1 AND (a_port_id = {port_id_int} OR b_port_id = {port_id_int});"
        )
        reason = self.db.text(payload.get("reason"))[:255]
        self.db.execute(
            f"""
            START TRANSACTION;
            DELETE FROM rack_cable_run WHERE a_port_id = {port_id_int} OR b_port_id = {port_id_int};
            DELETE FROM rack_device_port WHERE port_id = {port_id_int};
            {self._audit_sql(
                "rack_port_removed",
                "rack_device_port",
                str(port_id_int),
                f"{self.db.text(port.get('placementName'))} / {self.db.text(port.get('name'))}",
                f"删除端口：{self.db.text(port.get('placementName'))} {self.db.text(port.get('name'))}"
                + (f"，原因：{reason}" if reason else ""),
                context,
                port,
                {"isActive": False, "removedCables": cables},
            )};
            COMMIT;
            """
        )
        return {"id": str(port_id_int), "removed": True, "removedCables": cables}

    def import_ports_from_template(self, placement_id: object, payload: dict, context: dict) -> dict:
        placement = self._placement_row(placement_id)
        if not placement:
            raise self.api_error("设备不在机柜里，无法生成端口。")
        self._assert_org(context, placement.get("orgId"))
        catalog_id = self.db.integer(payload.get("catalogId"), 0)
        if catalog_id <= 0:
            slug = self.db.text(payload.get("slug")).strip().lower()
            if slug:
                catalog_id = self.db.scalar(
                    f"SELECT catalog_id FROM device_type_catalog WHERE slug = {self.db.quote(slug)};"
                )
        if catalog_id <= 0:
            raise self.api_error("请先选择型号库里的型号。")
        templates = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'name', port_name,
                  'type', port_type,
                  'kind', port_kind,
                  'face', face,
                  'rowIndex', row_index,
                  'positionIndex', position_index
                )), JSON_ARRAY())
                FROM (
                  SELECT * FROM device_type_port_template
                  WHERE catalog_id = {catalog_id}
                  ORDER BY face, row_index, position_index, template_port_id
                ) template
                """,
                [],
            )
            or []
        )
        if not templates:
            raise self.conflict_error("该型号还没有端口模板。")
        placement_id_int = self.db.integer(placement.get("id"), 0)
        existing = {
            self.db.text(item)
            for item in (
                self.db.json(
                    f"""
                    SELECT COALESCE(JSON_ARRAYAGG(CONCAT(face, ':', port_name)), JSON_ARRAY())
                    FROM rack_device_port WHERE placement_id = {placement_id_int}
                    """,
                    [],
                )
                or []
            )
        }
        values = []
        created = 0
        for item in templates:
            key = f"{self.db.text(item.get('face'))}:{self.db.text(item.get('name'))}"
            if key in existing:
                continue
            values.append(
                "("
                + ", ".join(
                    [
                        str(placement_id_int),
                        self.db.quote(self.db.text(item.get("face"))),
                        self.db.quote(self.db.text(item.get("name"))),
                        self.db.quote(self.db.text(item.get("type"))),
                        self.db.quote(self.db.text(item.get("kind"))),
                        str(self.db.integer(item.get("rowIndex"), 1)),
                        str(self.db.integer(item.get("positionIndex"), 1)),
                    ]
                )
                + ")"
            )
            created += 1
        if values:
            self.db.execute(
                "INSERT INTO rack_device_port ("
                "placement_id, face, port_name, port_type, port_kind, row_index, position_index"
                ") VALUES " + ", ".join(values) + ";"
            )
        apply_height = parse_bool(payload.get("applyHeight"))
        if apply_height:
            u_height = self.db.integer(payload.get("uHeight"), self.db.integer(placement.get("uHeight"), 1))
            if u_height > 0:
                self.db.execute(
                    f"UPDATE rack_device_placement SET u_height = {u_height} WHERE placement_id = {placement_id_int};"
                )
        self.db.execute(
            self._audit_sql(
                "placement_ports_initialized",
                "rack_device_placement",
                str(placement_id_int),
                self.db.text(placement.get("name")),
                f"按型号模板生成端口：{self.db.text(placement.get('name'))}（新增 {created} 个）",
                context,
                {"existing": len(existing)},
                {"created": created, "catalogId": str(catalog_id), "applyHeight": bool(apply_height)},
            )
            + ";"
        )
        return {"placementId": str(placement_id_int), "created": created, "skipped": len(existing)}

    # -------------------------------------------------------------------- cables

    def list_cables(self, context: dict, params: dict[str, list[str]] | None = None) -> list[dict]:
        rack_id = self.db.integer((params or {}).get("rackId", [""])[0], 0)
        site_id = self.db.integer((params or {}).get("siteId", [""])[0], 0)
        filters = ["cable.is_active = 1"]
        if rack_id > 0:
            filters.append(f"(a_placement.rack_id = {rack_id} OR b_placement.rack_id = {rack_id})")
        if site_id > 0:
            filters.append(f"(a_rack.site_id = {site_id} OR b_rack.site_id = {site_id})")
        return list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(cable_row.cable_id AS CHAR),
                  'medium', cable_row.medium,
                  'lengthM', cable_row.length_m,
                  'label', cable_row.label,
                  'status', cable_row.status,
                  'notes', cable_row.notes,
                  'aPortId', CAST(cable_row.a_port_id AS CHAR),
                  'bPortId', CAST(cable_row.b_port_id AS CHAR),
                  'aPortName', cable_row.a_port_name,
                  'bPortName', cable_row.b_port_name,
                  'aPlacementId', CAST(cable_row.a_placement_id AS CHAR),
                  'bPlacementId', CAST(cable_row.b_placement_id AS CHAR),
                  'aPlacementName', cable_row.a_placement_name,
                  'bPlacementName', cable_row.b_placement_name,
                  'aRackId', CAST(cable_row.a_rack_id AS CHAR),
                  'bRackId', CAST(cable_row.b_rack_id AS CHAR),
                  'aRackName', cable_row.a_rack_name,
                  'bRackName', cable_row.b_rack_name,
                  'aSiteName', cable_row.a_site_name,
                  'bSiteName', cable_row.b_site_name
                )), JSON_ARRAY())
                FROM (
                  SELECT cable.cable_id, cable.medium, cable.length_m, cable.label, cable.status, cable.notes,
                         cable.a_port_id, cable.b_port_id,
                         a_port.port_name AS a_port_name,
                         b_port.port_name AS b_port_name,
                         a_placement.placement_id AS a_placement_id,
                         b_placement.placement_id AS b_placement_id,
                         a_placement.display_name AS a_placement_name,
                         b_placement.display_name AS b_placement_name,
                         a_rack.rack_id AS a_rack_id,
                         b_rack.rack_id AS b_rack_id,
                         a_rack.rack_name AS a_rack_name,
                         b_rack.rack_name AS b_rack_name,
                         a_site.site_name AS a_site_name,
                         b_site.site_name AS b_site_name
                  FROM rack_cable_run cable
                  JOIN rack_device_port a_port ON a_port.port_id = cable.a_port_id
                  JOIN rack_device_port b_port ON b_port.port_id = cable.b_port_id
                  JOIN rack_device_placement a_placement ON a_placement.placement_id = a_port.placement_id
                  JOIN rack_device_placement b_placement ON b_placement.placement_id = b_port.placement_id
                  JOIN asset_rack a_rack ON a_rack.rack_id = a_placement.rack_id
                  JOIN asset_rack b_rack ON b_rack.rack_id = b_placement.rack_id
                  JOIN asset_site a_site ON a_site.site_id = a_rack.site_id
                  JOIN asset_site b_site ON b_site.site_id = b_rack.site_id
                  WHERE {' AND '.join(filters)}
                  ORDER BY cable.cable_id DESC
                  LIMIT 1000
                ) cable_row
                """,
                [],
            )
            or []
        )

    def _validate_cable_endpoints(self, a_port_id: object, b_port_id: object) -> tuple[dict, dict]:
        a_port = self._port_row(a_port_id)
        b_port = self._port_row(b_port_id)
        if not a_port or not b_port:
            raise self.api_error("链路两端的端口都必须存在。")
        if self.db.integer(a_port.get("id"), 0) == self.db.integer(b_port.get("id"), 0):
            raise self.api_error("链路两端不能是同一个端口。")
        for port in (a_port, b_port):
            occupied = self.db.json(
                f"""
                SELECT JSON_OBJECT(
                  'id', CAST(cable.cable_id AS CHAR),
                  'label', cable.label,
                  'peer', COALESCE(peer_placement.display_name, '')
                )
                FROM rack_cable_run cable
                LEFT JOIN rack_device_port peer_port
                  ON peer_port.port_id = IF(cable.a_port_id = {self.db.integer(port.get('id'), 0)}, cable.b_port_id, cable.a_port_id)
                LEFT JOIN rack_device_placement peer_placement
                  ON peer_placement.placement_id = peer_port.placement_id
                WHERE cable.is_active = 1
                  AND (cable.a_port_id = {self.db.integer(port.get('id'), 0)} OR cable.b_port_id = {self.db.integer(port.get('id'), 0)})
                LIMIT 1
                """,
                None,
            )
            if occupied:
                raise self.conflict_error(
                    f"端口 {self.db.text(port.get('placementName'))} / {self.db.text(port.get('name'))} "
                    f"已经连接到 {self.db.text(occupied.get('peer')) or '其它设备'}。"
                )
        return a_port, b_port

    def _validate_cable_payload(self, payload: dict) -> dict:
        medium = self.db.text(payload.get("medium")) or "cat6"
        if medium not in MEDIUMS:
            raise self.api_error("链路介质无效。")
        status = self.db.text(payload.get("status")) or "connected"
        if status not in CABLE_STATUSES:
            raise self.api_error("链路状态无效。")
        length_raw = payload.get("lengthM")
        length_m: float | None = None
        if length_raw not in (None, ""):
            try:
                length_m = float(length_raw)
            except (TypeError, ValueError) as exc:
                raise self.api_error("链路长度必须是数字。") from exc
            if length_m <= 0 or length_m > 10000:
                raise self.api_error("链路长度必须在 0-10000 米之间。")
        return {
            "medium": medium,
            "status": status,
            "lengthM": length_m,
            "label": self.db.text(payload.get("label"))[:128],
            "notes": self.db.text(payload.get("notes"))[:500],
        }

    def create_cable(self, payload: dict, context: dict, idempotency_key: str = "") -> dict:
        cached = self._idempotency_result("rack.cable.create", idempotency_key, payload)
        if cached:
            return cached
        a_port_id = self.db.integer(payload.get("aPortId"), 0)
        b_port_id = self.db.integer(payload.get("bPortId"), 0)
        a_port, b_port = self._validate_cable_endpoints(a_port_id, b_port_id)
        for port in (a_port, b_port):
            self._assert_org(context, port.get("orgId"))
        fields = self._validate_cable_payload(payload)
        actor_id = self._actor_id(context)
        length_sql = "NULL" if fields["lengthM"] is None else str(fields["lengthM"])
        cable_id = self._last_int(
            self.db.execute(
                f"""
            INSERT INTO rack_cable_run (
              a_port_id, b_port_id, medium, length_m, label, status, notes, created_by, updated_by
            )
            VALUES (
              {self.db.integer(a_port.get('id'), 0)},
              {self.db.integer(b_port.get('id'), 0)},
              {self.db.quote(fields['medium'])},
              {length_sql},
              {self.db.quote(fields['label'])},
              {self.db.quote(fields['status'])},
              {self.db.quote(fields['notes'])},
              {actor_id if actor_id > 0 else 'NULL'},
              {actor_id if actor_id > 0 else 'NULL'}
            );
            SELECT LAST_INSERT_ID();
            """
            )
        )
        if cable_id <= 0:
            raise self.conflict_error("链路创建失败，请检查端口占用。")
        self.db.execute(
            self._audit_sql(
                "rack_cable_created",
                "rack_cable_run",
                str(cable_id),
                f"{self.db.text(a_port.get('placementName'))} {self.db.text(a_port.get('name'))} ↔ "
                f"{self.db.text(b_port.get('placementName'))} {self.db.text(b_port.get('name'))}",
                f"新增链路：{self.db.text(a_port.get('placementName'))}/{self.db.text(a_port.get('name'))} ↔ "
                f"{self.db.text(b_port.get('placementName'))}/{self.db.text(b_port.get('name'))}",
                context,
                None,
                {"aPortId": str(self.db.integer(a_port.get("id"), 0)), "bPortId": str(self.db.integer(b_port.get("id"), 0)), **fields},
            )
            + ";"
        )
        response = {"id": str(cable_id), "aPortId": str(self.db.integer(a_port.get("id"), 0)), "bPortId": str(self.db.integer(b_port.get("id"), 0))}
        self._store_idempotency_result("rack.cable.create", idempotency_key, payload, response)
        return response

    def update_cable(self, cable_id: object, payload: dict, context: dict) -> dict:
        cable = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(cable_id AS CHAR),
              'medium', medium,
              'lengthM', length_m,
              'label', label,
              'status', status,
              'notes', notes,
              'orgId', COALESCE(CAST(rack.org_unit_id AS CHAR), '')
            )
            FROM rack_cable_run cable
            JOIN rack_device_port port ON port.port_id = cable.a_port_id
            JOIN rack_device_placement placement ON placement.placement_id = port.placement_id
            JOIN asset_rack rack ON rack.rack_id = placement.rack_id
            WHERE cable.cable_id = {self.db.integer(cable_id, 0)} AND cable.is_active = 1
            """,
            None,
        )
        if not cable:
            raise self.api_error("链路不存在或已删除。")
        self._assert_org(context, cable.get("orgId"))
        merged = {
            "medium": payload.get("medium", cable.get("medium")),
            "status": payload.get("status", cable.get("status")),
            "lengthM": payload.get("lengthM", cable.get("lengthM")),
            "label": payload.get("label", cable.get("label")),
            "notes": payload.get("notes", cable.get("notes")),
        }
        fields = self._validate_cable_payload(merged)
        length_sql = "NULL" if fields["lengthM"] is None else str(fields["lengthM"])
        actor_id = self._actor_id(context)
        cable_id_int = self.db.integer(cable.get("id"), 0)
        self.db.execute(
            f"""
            UPDATE rack_cable_run
            SET medium = {self.db.quote(fields['medium'])},
                length_m = {length_sql},
                label = {self.db.quote(fields['label'])},
                status = {self.db.quote(fields['status'])},
                notes = {self.db.quote(fields['notes'])},
                updated_by = {actor_id if actor_id > 0 else 'NULL'}
            WHERE cable_id = {cable_id_int};
            """
        )
        self.db.execute(
            self._audit_sql(
                "rack_cable_updated",
                "rack_cable_run",
                str(cable_id_int),
                self.db.text(cable.get("label")) or f"链路 {cable_id_int}",
                f"更新链路 {cable_id_int}：{fields['medium']} / {fields['status']}",
                context,
                cable,
                fields,
            )
            + ";"
        )
        return {"id": str(cable_id_int), **fields}

    def remove_cable(self, cable_id: object, payload: dict, context: dict) -> dict:
        cable = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(cable.cable_id AS CHAR),
              'label', label,
              'medium', medium,
              'orgId', COALESCE(CAST(rack.org_unit_id AS CHAR), '')
            )
            FROM rack_cable_run cable
            JOIN rack_device_port port ON port.port_id = cable.a_port_id
            JOIN rack_device_placement placement ON placement.placement_id = port.placement_id
            JOIN asset_rack rack ON rack.rack_id = placement.rack_id
            WHERE cable.cable_id = {self.db.integer(cable_id, 0)} AND cable.is_active = 1
            """,
            None,
        )
        if not cable:
            raise self.api_error("链路不存在或已删除。")
        self._assert_org(context, cable.get("orgId"))
        reason = self.db.text(payload.get("reason"))[:255]
        cable_id_int = self.db.integer(cable.get("id"), 0)
        self.db.execute(
            f"""
            UPDATE rack_cable_run
            SET is_active = 0,
                notes = {self.db.quote(reason or self.db.text(cable.get('label')))}
            WHERE cable_id = {cable_id_int};
            """
        )
        self.db.execute(
            self._audit_sql(
                "rack_cable_removed",
                "rack_cable_run",
                str(cable_id_int),
                self.db.text(cable.get("label")) or f"链路 {cable_id_int}",
                f"删除链路 {cable_id_int}" + (f"，原因：{reason}" if reason else ""),
                context,
                cable,
                {"isActive": False, "reason": reason},
            )
            + ";"
        )
        return {"id": str(cable_id_int), "removed": True}

    def import_cables(self, payload: dict, context: dict) -> dict:
        rows = payload.get("rows")
        if not isinstance(rows, list) or not rows:
            raise self.api_error("请提供链路清单。")
        if len(rows) > 200:
            raise self.api_error("一次最多导入 200 条链路。")
        created: list[dict] = []
        skipped: list[dict] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                skipped.append({"row": index + 1, "reason": "格式无效"})
                continue
            try:
                result = self.create_cable(
                    {
                        "aPortId": row.get("aPortId"),
                        "bPortId": row.get("bPortId"),
                        "medium": row.get("medium") or "cat6",
                        "lengthM": row.get("lengthM"),
                        "label": row.get("label") or "",
                        "status": row.get("status") or "connected",
                        "notes": row.get("notes") or "",
                    },
                    context,
                )
                created.append({"row": index + 1, "id": result["id"]})
            except Exception as exc:  # 逐行容错，便于人工核对导入结果
                skipped.append({"row": index + 1, "reason": str(exc)})
        return {"created": len(created), "skipped": skipped, "rows": created}

    # ------------------------------------------------------------------ topology

    def topology_graph(self, context: dict, params: dict[str, list[str]] | None = None) -> dict:
        site_id = self.db.integer((params or {}).get("siteId", [""])[0], 0)
        rack_id = self.db.integer((params or {}).get("rackId", [""])[0], 0)
        only_linked = parse_bool((params or {}).get("onlyLinked", ["0"])[0])
        filters = ["placement.is_active = 1", "rack.is_active = 1", "site.is_active = 1"]
        if site_id > 0:
            filters.append(f"site.site_id = {site_id}")
        if rack_id > 0:
            filters.append(f"rack.rack_id = {rack_id}")
        allowed = self.scope.permitted_org_ids(context)
        if allowed is not None:
            if not allowed:
                return {"nodes": [], "links": [], "positions": []}
            allowed_sql = ", ".join(str(value) for value in sorted(allowed))
            filters.append(f"(rack.org_unit_id IS NULL OR rack.org_unit_id IN ({allowed_sql}))")
        nodes = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(node.placement_id AS CHAR),
                  'name', node.display_name,
                  'brandModel', node.brand_model,
                  'category', node.category,
                  'status', COALESCE(node.live_status, node.status_snapshot, ''),
                  'positionU', node.position_u,
                  'uHeight', node.u_height,
                  'rackId', CAST(node.rack_id AS CHAR),
                  'rackName', node.rack_name,
                  'siteId', CAST(node.site_id AS CHAR),
                  'siteName', node.site_name,
                  'portCount', node.port_count,
                  'linkedPortCount', node.linked_port_count
                )), JSON_ARRAY())
                FROM (
                  SELECT placement.placement_id, placement.display_name, placement.brand_model,
                         placement.category, placement.position_u, placement.u_height,
                         placement.status_snapshot, computer.it_asset_status AS live_status,
                         rack.rack_id, rack.rack_name, site.site_id, site.site_name,
                         (
                           SELECT COUNT(*) FROM rack_device_port port
                           WHERE port.placement_id = placement.placement_id
                         ) AS port_count,
                         (
                           SELECT COUNT(DISTINCT cable.cable_id)
                           FROM rack_device_port port
                           JOIN rack_cable_run cable
                             ON cable.is_active = 1 AND (cable.a_port_id = port.port_id OR cable.b_port_id = port.port_id)
                           WHERE port.placement_id = placement.placement_id
                         ) AS linked_port_count
                  FROM rack_device_placement placement
                  JOIN asset_rack rack ON rack.rack_id = placement.rack_id
                  JOIN asset_site site ON site.site_id = rack.site_id
                  LEFT JOIN computer_asset computer ON computer.computer_id = placement.computer_id
                  WHERE {' AND '.join(filters)}
                  ORDER BY site.site_code, rack.rack_code, placement.position_u DESC
                ) node
                """,
                [],
            )
            or []
        )
        node_ids = {self.db.text(item.get("id")) for item in nodes}
        links = [
            link
            for link in self.list_cables(context, params)
            if self.db.text(link.get("aPlacementId")) in node_ids and self.db.text(link.get("bPlacementId")) in node_ids
        ]
        if only_linked:
            linked_ids = set()
            for link in links:
                linked_ids.add(self.db.text(link.get("aPlacementId")))
                linked_ids.add(self.db.text(link.get("bPlacementId")))
            nodes = [item for item in nodes if self.db.text(item.get("id")) in linked_ids]
        positions = list(
            self.db.json(
                """
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'nodeId', CAST(node_id AS CHAR),
                  'x', x,
                  'y', y
                )), JSON_ARRAY())
                FROM topology_node_position
                WHERE node_kind = 'placement'
                """,
                [],
            )
            or []
        )
        return {"nodes": nodes, "links": links, "positions": positions}

    def save_topology_positions(self, payload: dict, context: dict) -> dict:
        nodes = payload.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            raise self.api_error("请提供节点坐标。")
        if len(nodes) > 2000:
            raise self.api_error("一次最多保存 2000 个节点坐标。")
        actor_id = self._actor_id(context)
        values = []
        for item in nodes:
            if not isinstance(item, dict):
                continue
            node_id = self.db.integer(item.get("nodeId"), 0)
            if node_id <= 0:
                continue
            values.append(
                f"({node_id}, {max(0, min(100000, self.db.integer(item.get('x'), 0)))}, "
                f"{max(0, min(100000, self.db.integer(item.get('y'), 0)))}, "
                f"{actor_id if actor_id > 0 else 'NULL'})"
            )
        if not values:
            raise self.api_error("没有可保存的节点坐标。")
        self.db.execute(
            "INSERT INTO topology_node_position (node_id, x, y, updated_by) VALUES "
            + ", ".join(values)
            + " ON DUPLICATE KEY UPDATE x = VALUES(x), y = VALUES(y), updated_by = VALUES(updated_by);"
        )
        self.db.execute(
            self._audit_sql(
                "topology_positions_saved",
                "topology_node_position",
                "'batch'",
                "拓扑布局",
                f"保存拓扑节点坐标：{len(values)} 个节点",
                context,
                None,
                {"count": len(values)},
            )
            + ";"
        )
        return {"saved": len(values)}


NETBOX_DEVICE_TYPE_URL = (
    "https://raw.githubusercontent.com/netbox-community/devicetype-library/master/device-types/{vendor}/{model}.yaml"
)


def netbox_yaml_url(slug: str, manufacturer: str = "", model: str = "") -> str:
    """Build the devicetype-library raw URL for a slug (vendor folder derived from slug)."""
    vendor = manufacturer.strip() or slug.split("-")[0]
    file_name = model.strip().replace(" ", "-") or slug
    return NETBOX_DEVICE_TYPE_URL.format(vendor=vendor, model=file_name)


def fetch_netbox_yaml(slug: str, timeout: int = 15) -> str:
    """Fetch a devicetype YAML from GitHub raw (server needs outbound access)."""
    import urllib.error
    import urllib.request

    candidates: list[str] = []
    parts = slug.split("-")
    for split_at in range(1, len(parts)):
        vendor = "".join(word.capitalize() for word in parts[:split_at])
        model = "-".join(word.capitalize() for word in parts[split_at:])
        candidates.append(netbox_yaml_url(slug, vendor, model))
    candidates.append(netbox_yaml_url(slug))
    last_error = ""
    for url in candidates:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "office-asset-mgmt"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
        except Exception as exc:  # 网络不可用时回退到人工粘贴 YAML
            last_error = str(exc)
    raise ValueError(f"无法从 devicetype-library 获取 {slug}（{last_error}），请改用 yamlText 手工导入。")
