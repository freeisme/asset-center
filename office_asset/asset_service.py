from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from .scope import OrganizationScopeService
from .sql import SqlGateway, parse_bool


COMPUTER_STATUS_TRANSITIONS = {
    "in_use": {"in_use", "idle", "repair", "lost", "retired"},
    "idle": {"idle", "in_use", "repair", "lost", "retired"},
    "repair": {"repair", "idle", "in_use", "lost", "retired"},
    "lost": {"lost", "idle", "retired"},
    "retired": {"retired"},
}


OFFBOARD_ACTION_LABELS = {
    "recover": "回收",
    "transfer": "转交他人",
    "exception": "异常待处理",
}


@dataclass
class AssetService:
    db: SqlGateway
    scope: OrganizationScopeService
    api_error: type[Exception]
    conflict_error: type[Exception]
    forbidden_error: type[Exception]

    def _actor_id(self, context: dict) -> int:
        return self.db.integer(context.get("id"), 0)

    def _actor_name(self, context: dict) -> str:
        return self.db.text(context.get("username")) or "web"

    def _permission_scope(self, context: dict, module_code: str = "inventory_operations") -> str:
        return self.db.text((context.get("_permissionScopes") or {}).get(module_code)) or "all"

    def _actor_employee_id(self, context: dict) -> int:
        employee = context.get("employee") or {}
        return self.db.integer(employee.get("employeeId"), 0)

    def _actor_org_id(self, context: dict) -> int:
        employee = context.get("employee") or {}
        org_id = self.db.integer(employee.get("orgId"), 0)
        if org_id <= 0:
            org_id = self.db.integer(context.get("orgId"), 0)
        if org_id > 0:
            return org_id

        employee_id = self._actor_employee_id(context)
        if employee_id <= 0:
            return 0
        return self.db.scalar(
            f"""
            SELECT COALESCE(org_unit_id, 0)
            FROM employee
            WHERE employee_id = {employee_id}
              AND is_active = 1;
            """
        )

    def _assert_employee_scope(self, context: dict, employee_id: object) -> None:
        scope = self._permission_scope(context)
        if scope in {"own", "submitted", "assigned"}:
            actor_employee_id = self._actor_employee_id(context)
            if actor_employee_id <= 0 or actor_employee_id != self.db.integer(employee_id, 0):
                raise self.forbidden_error("This account can only access its own asset records.")

    def _assert_inventory_issue_scope(self, context: dict) -> None:
        if self._permission_scope(context) not in {"all", "organization"}:
            raise self.forbidden_error(
                "Asset assignment and inventory issue require an all-data or organization data scope."
            )

    def _warehouse(self, warehouse_id: object, include_inactive: bool = False) -> dict:
        warehouse_id_int = self.db.integer(warehouse_id, 0)
        if warehouse_id_int <= 0:
            raise self.api_error("Warehouse identifier is required.")
        active_sql = "" if include_inactive else "AND warehouse.is_active = 1"
        warehouse = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(warehouse.warehouse_id AS CHAR),
              'code', warehouse.warehouse_code,
              'name', warehouse.warehouse_name,
              'orgId', CAST(warehouse.org_unit_id AS CHAR),
              'managerEmployeeId', COALESCE(CAST(warehouse.manager_employee_id AS CHAR), ''),
              'managerName', COALESCE(manager.employee_name, ''),
              'contactPhone', warehouse.contact_phone,
              'address', warehouse.address,
              'isActive', warehouse.is_active,
              'remarks', warehouse.remarks,
              'createdAt', DATE_FORMAT(warehouse.created_at, '%Y-%m-%d %H:%i:%s'),
              'updatedAt', DATE_FORMAT(warehouse.updated_at, '%Y-%m-%d %H:%i:%s')
            )
            FROM inventory_warehouse warehouse
            LEFT JOIN employee manager ON manager.employee_id = warehouse.manager_employee_id
            WHERE warehouse.warehouse_id = {warehouse_id_int}
              {active_sql}
            """,
            None,
        )
        if not warehouse:
            raise self.api_error("Warehouse does not exist or is disabled.")
        return dict(warehouse)

    def _default_warehouse(
        self,
        context: dict,
        preferred_org_id: object | None = None,
        module_code: str = "inventory_operations",
    ) -> dict:
        org_id = self.db.integer(preferred_org_id, 0) or self._actor_org_id(context)
        for ancestor_id in self.scope.ancestor_org_ids(org_id):
            candidate_output = self.db.execute(
                f"""
                SELECT warehouse_id
                FROM inventory_warehouse
                WHERE org_unit_id = {ancestor_id}
                  AND is_active = 1
                ORDER BY warehouse_name, warehouse_id
                """,
            )
            for candidate_id in candidate_output.splitlines():
                warehouse = self._warehouse(candidate_id.strip())
                try:
                    self._assert_warehouse_access(
                        context,
                        warehouse,
                        module_code,
                        require_active=True,
                    )
                    if module_code != "warehouse_management":
                        self._assert_warehouse_access(
                            context,
                            warehouse,
                            "warehouse_management",
                            require_active=True,
                        )
                except self.forbidden_error:
                    continue
                return warehouse

        raise self.conflict_error(
            "No enabled warehouse is available for the selected organization. Select an authorized warehouse or configure one for the organization."
        )

    def _assert_warehouse_access(
        self,
        context: dict,
        warehouse: dict,
        module_code: str = "warehouse_management",
        require_active: bool = False,
    ) -> None:
        if require_active and not parse_bool(warehouse.get("isActive"), True):
            raise self.conflict_error("The selected warehouse is disabled.")
        scope = self._permission_scope(context, module_code)
        if scope == "all":
            return
        if scope == "organization":
            self.scope.assert_org_access(context, warehouse.get("orgId"))
            return
        if scope == "own":
            actor_employee_id = self._actor_employee_id(context)
            if actor_employee_id > 0 and actor_employee_id == self.db.integer(
                warehouse.get("managerEmployeeId"), 0
            ):
                return
        raise self.forbidden_error("This account is not authorized to access this warehouse.")

    def _resolve_warehouse(
        self,
        payload: dict,
        context: dict,
        module_code: str,
        *,
        require_explicit: bool = False,
        preferred_org_id: object | None = None,
    ) -> dict:
        warehouse_id = self.db.integer(payload.get("warehouseId"), 0)
        if warehouse_id <= 0:
            if require_explicit:
                raise self.api_error("Select a target warehouse.")
            warehouse = self._default_warehouse(
                context,
                preferred_org_id=preferred_org_id,
                module_code=module_code,
            )
        else:
            warehouse = self._warehouse(warehouse_id)
        self._assert_warehouse_access(context, warehouse, module_code, require_active=True)
        if module_code != "warehouse_management":
            self._assert_warehouse_access(
                context,
                warehouse,
                "warehouse_management",
                require_active=True,
            )
        return warehouse

    def _warehouse_stock_rows(self, warehouse_id: int) -> list[dict]:
        return list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'modelId', CAST(stock.model_id AS CHAR),
                  'quantity', stock.quantity,
                  'typeId', CAST(model.non_asset_type_id AS CHAR),
                  'brandId', CAST(model.brand_id AS CHAR),
                  'typeName', type_row.type_name,
                  'brandName', brand.brand_name,
                  'modelName', model.model_name,
                  'unit', type_row.unit_name
                )), JSON_ARRAY())
                FROM (
                  SELECT warehouse_id, model_id, quantity
                  FROM inventory_warehouse_stock
                  WHERE warehouse_id = {warehouse_id}
                    AND quantity > 0
                  ORDER BY model_id
                ) stock
                JOIN it_inventory_model model ON model.model_id = stock.model_id
                  AND model.is_active = 1
                JOIN it_inventory_brand brand ON brand.brand_id = model.brand_id
                JOIN non_asset_type type_row ON type_row.non_asset_type_id = model.non_asset_type_id
                """,
                [],
            )
            or []
        )

    def _entity_org_id(self, entity_type: str, entity_id: int) -> int:
        queries = {
            "computer": f"SELECT COALESCE(org_unit_id, 0) FROM computer_asset WHERE computer_id = {entity_id} AND is_active = 1;",
            "employee": f"SELECT COALESCE(org_unit_id, 0) FROM employee WHERE employee_id = {entity_id} AND is_active = 1;",
            "organization": f"SELECT COALESCE(org_unit_id, 0) FROM org_unit WHERE org_unit_id = {entity_id} AND is_active = 1;",
            "ticket": f"SELECT COALESCE(org_unit_id, 0) FROM itil_ticket WHERE ticket_id = {entity_id};",
        }
        query = queries.get(entity_type)
        if not query:
            raise self.api_error("Unsupported relation entity.")
        if self.db.scalar(
            f"SELECT COUNT(*) FROM ({query[:-1]}) entity_row;"
        ) != 1:
            raise self.api_error("Relation entity does not exist.")
        return self.db.scalar(query)

    def _assert_relation_entity_access(self, entity_type: str, entity_id: int, context: dict) -> None:
        org_id = self._entity_org_id(entity_type, entity_id)
        self.scope.assert_org_access(context, org_id)
        scope = self._permission_scope(context, "organizations")
        if scope in {"all", "organization"}:
            return
        if scope == "none":
            raise self.forbidden_error("This account is not authorized to access asset relations.")

        actor_id = self._actor_id(context)
        actor_employee_id = self._actor_employee_id(context)
        if entity_type == "employee":
            if actor_employee_id > 0 and actor_employee_id == entity_id:
                return
        elif entity_type == "computer":
            assigned_employee_id = self.db.scalar(
                f"""
                SELECT COALESCE(employee_id, 0)
                FROM computer_assignment
                WHERE computer_id = {entity_id}
                  AND returned_at IS NULL
                  AND assignment_status = 'active'
                ORDER BY assignment_id DESC
                LIMIT 1;
                """
            )
            if actor_employee_id > 0 and actor_employee_id == assigned_employee_id:
                return
        elif entity_type == "organization":
            actor_org_id = self.db.integer((context.get("employee") or {}).get("orgId"), 0)
            if actor_org_id > 0 and actor_org_id == entity_id:
                return
        elif entity_type == "ticket":
            ticket = self.db.json(
                f"""
                SELECT JSON_OBJECT(
                  'createdBy', COALESCE(created_by, 0),
                  'assignedTo', COALESCE(assigned_to_user_id, 0)
                )
                FROM itil_ticket
                WHERE ticket_id = {entity_id};
                """,
                None,
            ) or {}
            if scope in {"own", "submitted"} and self.db.integer(ticket.get("createdBy"), 0) == actor_id:
                return
            if scope == "assigned" and self.db.integer(ticket.get("assignedTo"), 0) == actor_id:
                return
        raise self.forbidden_error("This account is not authorized to access this relation entity.")

    def _idempotency_result(
        self,
        operation: str,
        key: str,
        payload: dict,
    ) -> dict | None:
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

    def _store_idempotency_result(
        self,
        operation: str,
        key: str,
        payload: dict,
        response: dict,
    ) -> None:
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

    def _computer(self, computer_id: object) -> dict:
        computer_id_int = self.db.integer(computer_id, 0)
        computer = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(asset.computer_id AS CHAR),
              'deviceName', asset.device_name,
              'orgId', COALESCE(CAST(asset.org_unit_id AS CHAR), ''),
              'deviceType', asset.device_type,
              'brand', COALESCE(asset.brand, ''),
              'model', COALESCE(asset.model, ''),
              'inventoryModelId', COALESCE(CAST(asset.inventory_model_id AS CHAR), ''),
              'inventoryStockAdjusted', asset.inventory_stock_adjusted,
              'cpu', COALESCE(asset.cpu, ''),
              'memory', COALESCE(asset.memory, ''),
              'storage', COALESCE(asset.storage, ''),
              'gpu', COALESCE(asset.gpu, ''),
              'fixedAssetCode', COALESCE(asset.fixed_asset_code, ''),
              'purchaseDate', COALESCE(CAST(asset.purchase_date AS CHAR), ''),
              'registeredDate', COALESCE(CAST(asset.registered_date AS CHAR), ''),
              'snSt', COALESCE(asset.sn_st, ''),
              'wifiMac', COALESCE(asset.wifi_mac, ''),
              'ethernetMac', COALESCE(asset.ethernet_mac, ''),
              'location', COALESCE(asset.location, ''),
              'department', COALESCE(asset.department, ''),
              'position', COALESCE(asset.position_name, ''),
              'status', asset.it_asset_status,
              'remarks', COALESCE(asset.remarks, ''),
              'userId', COALESCE(CAST(current_assignment.employee_id AS CHAR), '')
            )
            FROM computer_asset asset
            LEFT JOIN computer_assignment current_assignment
              ON current_assignment.computer_id = asset.computer_id
             AND current_assignment.returned_at IS NULL
             AND current_assignment.assignment_status = 'active'
            WHERE asset.computer_id = {computer_id_int}
              AND asset.is_active = 1
              AND asset.is_archived = 0
            """,
            None,
        )
        if not computer:
            raise self.api_error("Computer does not exist.")
        return dict(computer)

    def _employee(self, employee_id: object) -> dict:
        employee_id_int = self.db.integer(employee_id, 0)
        employee = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(employee_id AS CHAR),
              'employeeNo', employee_no,
              'name', employee_name,
              'orgId', COALESCE(CAST(org_unit_id AS CHAR), ''),
              'status', employment_status
            )
            FROM employee
            WHERE employee_id = {employee_id_int}
              AND is_active = 1
            """,
            None,
        )
        if not employee:
            raise self.api_error("Employee does not exist.")
        return dict(employee)

    def _assert_computer_record_scope(
        self,
        context: dict,
        computer: dict,
        module_code: str = "it_assets",
    ) -> None:
        scope = self._permission_scope(context, module_code)
        if scope in {"all", "organization"}:
            return
        if scope == "own":
            actor_employee_id = self._actor_employee_id(context)
            if actor_employee_id > 0 and actor_employee_id == self.db.integer(computer.get("userId"), 0):
                return
        raise self.forbidden_error("This account is not authorized to access this computer record.")

    def computer_movement_history(self, computer_id: object, context: dict) -> list[dict]:
        computer = self._computer(computer_id)
        self.scope.assert_computer_access(context, computer_id)
        self._assert_computer_record_scope(context, computer, "it_assets")
        computer_id_int = self.db.integer(computer_id, 0)
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', event_id,
              'type', event_type,
              'occurredAt', DATE_FORMAT(occurred_at, '%Y-%m-%d %H:%i:%s'),
              'employeeId', employee_id,
              'employeeNo', employee_no,
              'employeeName', employee_name,
              'previousStatus', previous_status,
              'nextStatus', next_status,
              'notes', notes,
              'operatedBy', operated_by
            )), JSON_ARRAY())
            FROM (
              SELECT
                CONCAT('assignment-', history.history_id, '-assigned') AS event_id,
                'assigned' AS event_type,
                history.assigned_at AS occurred_at,
                CAST(history.employee_id AS CHAR) AS employee_id,
                history.employee_no,
                history.employee_name,
                '' AS previous_status,
                'in_use' AS next_status,
                COALESCE(history.notes, '') AS notes,
                COALESCE(assigned_user.display_name, assigned_user.username, '') AS operated_by
              FROM computer_assignment_history history
              LEFT JOIN user_account assigned_user ON assigned_user.user_id = history.assigned_by
              WHERE history.computer_id = {computer_id_int}

              UNION ALL

              SELECT
                CONCAT('assignment-', history.history_id, '-returned') AS event_id,
                'returned' AS event_type,
                history.returned_at AS occurred_at,
                CAST(history.employee_id AS CHAR) AS employee_id,
                history.employee_no,
                history.employee_name,
                'in_use' AS previous_status,
                '' AS next_status,
                COALESCE(history.notes, '') AS notes,
                COALESCE(returned_user.display_name, returned_user.username, '') AS operated_by
              FROM computer_assignment_history history
              LEFT JOIN user_account returned_user ON returned_user.user_id = history.returned_by
              WHERE history.computer_id = {computer_id_int}
                AND history.returned_at IS NOT NULL

              UNION ALL

              SELECT
                CONCAT('status-', status_history.status_history_id) AS event_id,
                'status_changed' AS event_type,
                status_history.changed_at AS occurred_at,
                '' AS employee_id,
                '' AS employee_no,
                '' AS employee_name,
                status_history.previous_status,
                status_history.next_status,
                status_history.reason AS notes,
                COALESCE(status_user.display_name, status_user.username, '') AS operated_by
              FROM asset_status_history status_history
              LEFT JOIN user_account status_user ON status_user.user_id = status_history.changed_by
              WHERE status_history.computer_id = {computer_id_int}
                AND status_history.reason NOT IN ('Computer assignment', 'Computer return')
            ) movement_events
            """,
            [],
        )
        return sorted(
            list(rows or []),
            key=lambda item: (
                self.db.text(item.get("occurredAt")),
                self.db.text(item.get("id")),
            ),
            reverse=True,
        )

    def add_inventory_movement_note_correction(
        self, movement_log_id: object, payload: dict, context: dict
    ) -> dict:
        movement_log_id_int = self.db.integer(movement_log_id, 0)
        corrected_note = self.db.text(payload.get("correctedNote")).strip()
        correction_reason = self.db.text(payload.get("correctionReason")).strip()
        if movement_log_id_int <= 0:
            raise self.api_error("物资流转记录不存在。")
        if not corrected_note:
            raise self.api_error("请填写更正后的备注。")
        if not correction_reason:
            raise self.api_error("请填写更正原因。")
        if len(corrected_note) > 500 or len(correction_reason) > 500:
            raise self.api_error("更正备注和更正原因不能超过 500 个字符。")

        movement = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(movement_log_id AS CHAR),
              'typeName', COALESCE(type_name, ''),
              'brandName', COALESCE(brand_name, ''),
              'modelName', COALESCE(model_name, ''),
              'sourceWarehouseId', COALESCE(CAST(source_warehouse_id AS CHAR), ''),
              'targetWarehouseId', COALESCE(CAST(target_warehouse_id AS CHAR), ''),
              'originalNote', COALESCE(note, '')
            )
            FROM inventory_movement_log
            WHERE movement_log_id = {movement_log_id_int}
            """,
            None,
        )
        if not movement:
            raise self.api_error("物资流转记录不存在。")
        for warehouse_id in {
            self.db.integer(movement.get("sourceWarehouseId"), 0),
            self.db.integer(movement.get("targetWarehouseId"), 0),
        }:
            if warehouse_id > 0:
                self._assert_warehouse_access(
                    context,
                    self._warehouse(warehouse_id, include_inactive=True),
                    "warehouse_management",
                )

        entity_name = " / ".join(
            item
            for item in (
                self.db.text(movement.get("typeName")),
                self.db.text(movement.get("brandName")),
                self.db.text(movement.get("modelName")),
            )
            if item
        ) or f"流转记录 #{movement_log_id_int}"
        actor_id = self._actor_id(context)
        actor_name = self._actor_name(context)
        output = self.db.execute(
            f"""
            START TRANSACTION;
            SET @movement_exists = 0;
            SET @original_note = '';
            SELECT 1, COALESCE(note, '') INTO @movement_exists, @original_note
            FROM inventory_movement_log
            WHERE movement_log_id = {movement_log_id_int}
            FOR UPDATE;
            SET @previous_corrected_note = NULL;
            SELECT corrected_note INTO @previous_corrected_note
            FROM inventory_movement_note_correction
            WHERE movement_log_id = {movement_log_id_int}
            ORDER BY created_at DESC, correction_id DESC
            LIMIT 1
            FOR UPDATE;
            INSERT INTO inventory_movement_note_correction (
              movement_log_id, corrected_note, correction_reason, created_by
            )
            SELECT
              {movement_log_id_int},
              {self.db.quote(corrected_note)},
              {self.db.quote(correction_reason)},
              {actor_id if actor_id > 0 else "NULL"}
            FROM DUAL
            WHERE @movement_exists = 1;
            SET @correction_id = IF(@movement_exists = 1, LAST_INSERT_ID(), 0);
            INSERT INTO audit_log (
              action_type, entity_type, entity_id, entity_name,
              old_value, new_value, summary, actor, source
            )
            SELECT
              'inventory_movement_note_corrected',
              'inventory_movement_log',
              {self.db.quote(str(movement_log_id_int))},
              {self.db.quote(entity_name)},
              JSON_OBJECT(
                'originalNote', COALESCE(@original_note, ''),
                'previousEffectiveNote', COALESCE(@previous_corrected_note, @original_note, '')
              ),
              JSON_OBJECT(
                'correctionId', @correction_id,
                'correctedNote', {self.db.quote(corrected_note)},
                'correctionReason', {self.db.quote(correction_reason)}
              ),
              {self.db.quote("已更正物资流转记录备注。")},
              {self.db.quote(actor_name)},
              'api'
            FROM DUAL
            WHERE @correction_id > 0;
            COMMIT;
            SELECT @correction_id;
            """
        )
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        correction_id = self.db.integer(lines[-1] if lines else 0, 0)
        if correction_id <= 0:
            raise self.conflict_error("物资流转记录已不存在或无法更正。")
        return {
            "id": str(correction_id),
            "movementLogId": str(movement_log_id_int),
            "correctedNote": corrected_note,
            "correctionReason": correction_reason,
        }

    def _audit_sql(
        self,
        action: str,
        entity_type: str,
        entity_id: object,
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
          {self.db.quote(str(entity_id))},
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

    def _normalize_status(self, value: object, default: str = "idle") -> str:
        status = self.db.text(value) or default
        if status not in COMPUTER_STATUS_TRANSITIONS:
            raise self.api_error("Unsupported computer lifecycle status.")
        return status

    def _assert_computer_unique_fields(
        self,
        computer_id: int,
        device_name: str,
        fixed_asset_code: str,
        sn_st: str,
    ) -> None:
        checks = (
            ("设备名称", "device_name", device_name),
            ("固定资产编码", "fixed_asset_code", fixed_asset_code),
            ("SN / ST", "sn_st", sn_st),
        )
        for label, column, value in checks:
            if not value:
                continue
            duplicate = self.db.scalar(
                f"""
                SELECT COUNT(*)
                FROM computer_asset
                WHERE {column} = {self.db.quote(value)}
                  AND computer_id <> {computer_id}
                """
            )
            if duplicate:
                raise self.conflict_error(f"{label} already exists.")

    def save_resource(
        self,
        resource_type: str,
        resource_id: object | None,
        payload: dict,
        context: dict,
    ) -> dict:
        if resource_type == "computer":
            return self._save_computer(resource_id, payload, context)
        if resource_type == "employee":
            return self._save_employee(resource_id, payload, context)
        if resource_type == "organization":
            return self._save_organization(resource_id, payload, context)
        if resource_type == "inventory-type":
            return self._save_inventory_type(resource_id, payload, context)
        if resource_type == "inventory-brand":
            return self._save_inventory_brand(resource_id, payload, context)
        if resource_type == "inventory-model":
            return self._save_inventory_model(resource_id, payload, context)
        raise self.api_error("Unsupported resource type.")

    def list_warehouses(self, context: dict) -> list[dict]:
        rows = list(
            self.db.json(
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
                  'remarks', warehouse.remarks,
                  'createdAt', DATE_FORMAT(warehouse.created_at, '%Y-%m-%d %H:%i:%s'),
                  'updatedAt', DATE_FORMAT(warehouse.updated_at, '%Y-%m-%d %H:%i:%s')
                )), JSON_ARRAY())
                FROM (
                  SELECT *
                  FROM inventory_warehouse
                  ORDER BY is_active DESC, warehouse_name, warehouse_id
                ) warehouse
                LEFT JOIN employee manager ON manager.employee_id = warehouse.manager_employee_id
                """,
                [],
            )
            or []
        )
        visible: list[dict] = []
        for warehouse in rows:
            try:
                self._assert_warehouse_access(context, warehouse, "warehouse_management")
            except Exception as exc:
                if isinstance(exc, self.forbidden_error):
                    continue
                raise
            visible.append(warehouse)
        return visible

    def save_warehouse(
        self,
        warehouse_id: object | None,
        payload: dict,
        context: dict,
    ) -> dict:
        warehouse_id_int = self.db.integer(warehouse_id, 0)
        code = self.db.text(payload.get("code")).upper()
        name = self.db.text(payload.get("name"))
        org_id = self.db.integer(payload.get("orgId"), 0)
        manager_employee_id = self.db.integer(payload.get("managerEmployeeId"), 0)
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{1,63}", code):
            raise self.api_error("Warehouse code must use 2-64 uppercase letters, numbers, dots, underscores, or hyphens.")
        if not name or org_id <= 0:
            raise self.api_error("Warehouse name and organization are required.")
        self.scope.assert_org_access(context, org_id)
        previous = self._warehouse(warehouse_id_int, include_inactive=True) if warehouse_id_int else None
        if previous:
            self._assert_warehouse_access(context, previous, "warehouse_management")
        if self.db.scalar(
            f"""
            SELECT COUNT(*)
            FROM org_unit
            WHERE org_unit_id = {org_id}
              AND is_active = 1;
            """
        ) != 1:
            raise self.api_error("Warehouse organization does not exist.")
        manager_sql = "NULL"
        if manager_employee_id > 0:
            if self.db.scalar(
                f"""
                SELECT COUNT(*)
                FROM employee
                WHERE employee_id = {manager_employee_id}
                  AND org_unit_id = {org_id}
                  AND is_active = 1
                  AND employment_status = 'active';
                """
            ) != 1:
                raise self.api_error("Warehouse manager must be an active employee of the selected organization.")
            manager_sql = str(manager_employee_id)
        duplicate_count = self.db.scalar(
            f"""
            SELECT COUNT(*)
            FROM inventory_warehouse
            WHERE warehouse_code = {self.db.quote(code)}
              AND warehouse_id <> {warehouse_id_int};
            """
        )
        if duplicate_count:
            raise self.conflict_error("Warehouse code already exists.")
        is_active = 1 if parse_bool(payload.get("isActive"), True) else 0
        assignments = {
            "warehouse_code": self.db.quote(code),
            "warehouse_name": self.db.quote(name),
            "org_unit_id": str(org_id),
            "manager_employee_id": manager_sql,
            "contact_phone": self.db.quote(self.db.text(payload.get("contactPhone"))),
            "address": self.db.quote(self.db.text(payload.get("address"))),
            "is_active": str(is_active),
            "remarks": self.db.quote(self.db.text(payload.get("remarks"))),
        }
        if warehouse_id_int:
            self.db.execute(
                f"""
                START TRANSACTION;
                UPDATE inventory_warehouse
                SET {", ".join(f"{column} = {value}" for column, value in assignments.items())}
                WHERE warehouse_id = {warehouse_id_int};
                {self._audit_sql(
                    'warehouse_updated',
                    'inventory_warehouse',
                    warehouse_id_int,
                    name,
                    'Warehouse updated',
                    context,
                    previous,
                    {
                        'code': code,
                        'name': name,
                        'orgId': org_id,
                        'managerEmployeeId': manager_employee_id,
                        'isActive': bool(is_active),
                    },
                )};
                COMMIT;
                """
            )
        else:
            output = self.db.execute(
                f"""
                START TRANSACTION;
                INSERT INTO inventory_warehouse ({", ".join(assignments.keys())})
                VALUES ({", ".join(assignments.values())});
                SET @warehouse_id = LAST_INSERT_ID();
                {self._audit_sql(
                    'warehouse_created',
                    'inventory_warehouse',
                    "'new'",
                    name,
                    'Warehouse created',
                    context,
                    None,
                    {'code': code, 'name': name, 'orgId': org_id, 'managerEmployeeId': manager_employee_id},
                )};
                UPDATE audit_log
                SET entity_id = CAST(@warehouse_id AS CHAR)
                WHERE audit_log_id = LAST_INSERT_ID();
                SELECT @warehouse_id;
                COMMIT;
                """
            )
            warehouse_id_int = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        return {"warehouse": self._warehouse(warehouse_id_int, include_inactive=True)}

    def delete_warehouse(self, warehouse_id: object, context: dict) -> dict:
        warehouse = self._warehouse(warehouse_id, include_inactive=True)
        self._assert_warehouse_access(context, warehouse, "warehouse_management")
        warehouse_id_int = self.db.integer(warehouse.get("id"), 0)
        if self.db.text(warehouse.get("code")) == "WH-001":
            raise self.conflict_error("默认仓库“仓库1”不能删除，可编辑或停用。")
        references = self.db.scalar(
            f"""
            SELECT
              (SELECT COUNT(*) FROM inventory_warehouse_stock
               WHERE warehouse_id = {warehouse_id_int} AND quantity > 0)
              + (SELECT COUNT(*) FROM inventory_allocation_history
                 WHERE warehouse_id = {warehouse_id_int})
              + (SELECT COUNT(*) FROM inventory_transfer_log
                 WHERE source_warehouse_id = {warehouse_id_int}
                    OR target_warehouse_id = {warehouse_id_int})
              + (SELECT COUNT(*) FROM inventory_movement_log
                 WHERE source_warehouse_id = {warehouse_id_int}
                    OR target_warehouse_id = {warehouse_id_int})
              + (SELECT COUNT(*) FROM inventory_purchase_log
                 WHERE warehouse_id = {warehouse_id_int});
            """
        )
        if references:
            raise self.conflict_error("The warehouse has inventory or historical references and cannot be deleted.")
        self.db.execute(
            f"""
            START TRANSACTION;
            DELETE FROM inventory_warehouse_stock WHERE warehouse_id = {warehouse_id_int};
            DELETE FROM inventory_warehouse WHERE warehouse_id = {warehouse_id_int};
            {self._audit_sql(
                'warehouse_deleted',
                'inventory_warehouse',
                warehouse_id_int,
                self.db.text(warehouse.get('name')),
                'Warehouse deleted',
                context,
                warehouse,
                None,
            )};
            COMMIT;
            """
        )
        return {"deleted": True, "warehouseId": str(warehouse_id_int)}

    def list_warehouse_stock(self, warehouse_id: object, context: dict) -> list[dict]:
        warehouse = self._warehouse(warehouse_id, include_inactive=True)
        self._assert_warehouse_access(context, warehouse, "warehouse_management")
        return self._warehouse_stock_rows(self.db.integer(warehouse.get("id"), 0))

    def _save_computer(self, resource_id: object | None, payload: dict, context: dict) -> dict:
        device_name = self.db.text(payload.get("deviceName"))
        if not device_name:
            raise self.api_error("Computer name is required.")
        org_id = self.db.integer(payload.get("orgId"), 0)
        self.scope.assert_org_access(context, org_id)
        status = self._normalize_status(payload.get("status"), "idle")
        computer_id = self.db.integer(resource_id, 0)
        old = self._computer(computer_id) if computer_id else None
        registration_mode = self.db.text(payload.get("registrationMode")).lower()
        if registration_mode and registration_mode not in {"custom", "warehouse"}:
            raise self.api_error("Computer registration mode must be custom or warehouse.")
        if not registration_mode:
            # Older clients did not send a mode. Treat their creates as custom
            # registration so a stale page cannot deduct stock unexpectedly.
            registration_mode = "custom"

        inventory_model_id = 0
        inventory_stock_adjusted = False
        warehouse = None
        inventory_model: dict | None = None
        if not old and registration_mode == "warehouse":
            self._assert_inventory_issue_scope(context)
            inventory_model_id = self.db.integer(payload.get("inventoryModelId"), 0)
            if inventory_model_id <= 0:
                raise self.api_error("Warehouse registration requires an inventory model.")
            warehouse = self._resolve_warehouse(
                payload,
                context,
                "inventory_operations",
                require_explicit=True,
            )
            inventory_model = self.db.json(
                f"""
                SELECT JSON_OBJECT(
                  'id', CAST(model.model_id AS CHAR),
                  'typeCode', type_row.type_code,
                  'typeName', type_row.type_name,
                  'brandName', brand.brand_name,
                  'modelName', model.model_name,
                  'inboundDate', COALESCE(CAST(model.inbound_date AS CHAR), ''),
                  'cpu', COALESCE(model.cpu, ''),
                  'memory', COALESCE(model.memory, ''),
                  'storage', COALESCE(model.storage, ''),
                  'gpu', COALESCE(model.gpu, '')
                )
                FROM it_inventory_model model
                JOIN it_inventory_brand brand ON brand.brand_id = model.brand_id
                JOIN non_asset_type type_row ON type_row.non_asset_type_id = model.non_asset_type_id
                WHERE model.model_id = {inventory_model_id}
                  AND model.is_active = 1
                """,
                None,
            )
            if not inventory_model:
                raise self.api_error("Inventory model does not exist.")
            type_code = self.db.text(inventory_model.get("typeCode")).lower()
            type_name = self.db.text(inventory_model.get("typeName")).lower()
            if type_code not in {"computer", "pc"} and type_name not in {
                "电脑",
                "办公终端",
                "办公设备终端",
                "computer",
                "pc",
            }:
                raise self.api_error("Warehouse registration can only use a computer inventory model.")
            inventory_stock_adjusted = True

        # The selected inventory model is the stock deduction reference only.
        # Device details remain editable and fall back to the model when omitted.
        inventory_defaults = inventory_model or {}
        brand = self.db.text(payload.get("brand")) or self.db.text(inventory_defaults.get("brandName"))
        model_name = self.db.text(payload.get("model")) or self.db.text(inventory_defaults.get("modelName"))
        cpu = self.db.text(payload.get("cpu")) or self.db.text(inventory_defaults.get("cpu"))
        memory = self.db.text(payload.get("memory")) or self.db.text(inventory_defaults.get("memory"))
        storage = self.db.text(payload.get("storage")) or self.db.text(inventory_defaults.get("storage"))
        gpu = self.db.text(payload.get("gpu")) or self.db.text(inventory_defaults.get("gpu"))
        purchase_date = self.db.text(payload.get("purchaseDate")) or self.db.text(
            inventory_defaults.get("inboundDate")
        )

        values = {
            "device_name": self.db.quote(device_name),
            "org_unit_id": "NULL" if org_id <= 0 else str(org_id),
            "device_type": self.db.quote(self.db.text(payload.get("deviceType")) or "desktop"),
            "brand": self.db.quote(brand) if brand else "NULL",
            "model": self.db.quote(model_name) if model_name else "NULL",
            "cpu": self.db.quote(cpu) if cpu else "NULL",
            "memory": self.db.quote(memory) if memory else "NULL",
            "storage": self.db.quote(storage) if storage else "NULL",
            "gpu": self.db.quote(gpu) if gpu else "NULL",
            "fixed_asset_code": (
                self.db.quote(self.db.text(payload.get("fixedAssetCode")))
                if self.db.text(payload.get("fixedAssetCode"))
                else "NULL"
            ),
            "purchase_date": self.db.quote(purchase_date) if purchase_date else "NULL",
            "registered_date": (
                self.db.quote(self.db.text(payload.get("registeredDate")))
                if self.db.text(payload.get("registeredDate"))
                else "NULL"
            ),
            "sn_st": self.db.quote(self.db.text(payload.get("snSt"))) if self.db.text(payload.get("snSt")) else "NULL",
            "wifi_mac": self.db.quote(self.db.text(payload.get("wifiMac"))) if self.db.text(payload.get("wifiMac")) else "NULL",
            "ethernet_mac": (
                self.db.quote(self.db.text(payload.get("ethernetMac")))
                if self.db.text(payload.get("ethernetMac"))
                else "NULL"
            ),
            "location": self.db.quote(self.db.text(payload.get("location"))) if self.db.text(payload.get("location")) else "NULL",
            "department": (
                self.db.quote(self.db.text(payload.get("department")))
                if self.db.text(payload.get("department"))
                else "NULL"
            ),
            "position_name": (
                self.db.quote(self.db.text(payload.get("position")))
                if self.db.text(payload.get("position"))
                else "NULL"
            ),
            "it_asset_status": self.db.quote(status),
            "remarks": self.db.quote(self.db.text(payload.get("remarks"))) if self.db.text(payload.get("remarks")) else "NULL",
        }

        self._assert_computer_unique_fields(
            computer_id,
            device_name,
            self.db.text(payload.get("fixedAssetCode")),
            self.db.text(payload.get("snSt")),
        )
        if old:
            self.scope.assert_org_access(context, old.get("orgId"))
            self._assert_computer_record_scope(context, old, "it_assets")
            old_status = self.db.text(old.get("status"))
            if status not in COMPUTER_STATUS_TRANSITIONS.get(old_status, set()):
                raise self.conflict_error(f"Invalid lifecycle transition: {old_status} -> {status}.")
            assignments = ",\n".join(f"{column} = {value}" for column, value in values.items())
            statements = [
                "START TRANSACTION",
                f"UPDATE computer_asset SET {assignments} WHERE computer_id = {computer_id}",
            ]
            if old_status != status:
                statements.append(
                    f"""
                    INSERT INTO asset_status_history (
                      computer_id, previous_status, next_status, reason, changed_by
                    )
                    VALUES (
                      {computer_id}, {self.db.quote(old_status)}, {self.db.quote(status)},
                      {self.db.quote(self.db.text(payload.get('statusReason')))}, {self._actor_id(context)}
                    )
                    """
                )
            statements.append(
                self._audit_sql(
                    "computer_updated",
                    "computer",
                    computer_id,
                    device_name,
                    "Computer asset updated",
                    context,
                    old,
                    {"status": status, "orgId": org_id},
                )
            )
            statements.append("COMMIT")
            self.db.execute(";\n".join(statements) + ";")
        else:
            values["inventory_model_id"] = (
                str(inventory_model_id) if inventory_model_id > 0 else "NULL"
            )
            values["inventory_stock_adjusted"] = "1" if inventory_stock_adjusted else "0"
            columns = ", ".join(values.keys())
            value_sql = ", ".join(values.values())
            if not inventory_stock_adjusted:
                output = self.db.execute(
                    f"""
                    START TRANSACTION;
                    INSERT INTO computer_asset ({columns}) VALUES ({value_sql});
                    SET @new_computer_id = LAST_INSERT_ID();
                    {self._audit_sql(
                        'computer_created',
                        'computer',
                        "'new'",
                        device_name,
                        'Computer asset created',
                        context,
                        None,
                        {'status': status, 'orgId': org_id, 'registrationMode': 'custom'},
                    )};
                    UPDATE audit_log
                    SET entity_id = CAST(@new_computer_id AS CHAR)
                    WHERE audit_log_id = LAST_INSERT_ID();
                    SELECT @new_computer_id;
                    COMMIT;
                    """
                )
                lines = [line.strip() for line in output.splitlines() if line.strip()]
                computer_id = self.db.integer(lines[-1] if lines else 0, 0)
            else:
                warehouse_id = self.db.integer((warehouse or {}).get("id"), 0)
                warehouse_name = self.db.text((warehouse or {}).get("name"))
                note = self.db.text(payload.get("remarks"))[:420]
                output = self.db.execute(
                    f"""
                    START TRANSACTION;
                    SET @stock_updated = 0;
                    SET @new_computer_id = 0;
                    SET @available_quantity = 0;
                    SET @warehouse_available_quantity = 0;
                    SELECT quantity
                    INTO @available_quantity
                    FROM it_inventory_model
                    WHERE model_id = {inventory_model_id}
                      AND is_active = 1
                    FOR UPDATE;
                    SELECT quantity
                    INTO @warehouse_available_quantity
                    FROM inventory_warehouse_stock
                    WHERE warehouse_id = {warehouse_id}
                      AND model_id = {inventory_model_id}
                    FOR UPDATE;
                    SET @stock_updated = IF(
                      @available_quantity >= 1 AND @warehouse_available_quantity >= 1,
                      1,
                      0
                    );
                    UPDATE it_inventory_model
                    SET quantity = quantity - 1
                    WHERE model_id = {inventory_model_id}
                      AND quantity >= 1
                      AND @stock_updated = 1;
                    UPDATE inventory_warehouse_stock
                    SET quantity = quantity - 1
                    WHERE warehouse_id = {warehouse_id}
                      AND model_id = {inventory_model_id}
                      AND quantity >= 1
                      AND @stock_updated = 1;
                    INSERT INTO computer_asset ({columns})
                    SELECT {value_sql}
                    FROM DUAL
                    WHERE @stock_updated = 1;
                    SET @new_computer_id = IF(@stock_updated = 1, LAST_INSERT_ID(), 0);
                    INSERT INTO inventory_movement_log (
                      movement_direction, type_name, brand_name, model_name, quantity,
                      source_label, source_warehouse_id, target_label, target_warehouse_id,
                      note, trigger_action
                    )
                    SELECT
                      'decrease',
                      {self.db.quote(self.db.text((inventory_model or {}).get('typeName')))},
                      {self.db.quote(brand)},
                      {self.db.quote(model_name)},
                      1,
                      {self.db.quote(warehouse_name)},
                      {warehouse_id},
                      {self.db.quote(device_name)},
                      NULL,
                      {self.db.quote(note)},
                      'computer_registration'
                    FROM DUAL
                    WHERE @stock_updated = 1;
                    {self._conditional_audit_sql(
                        'computer_created',
                        'computer',
                        'CAST(@new_computer_id AS CHAR)',
                        device_name,
                        'Computer asset created from warehouse inventory',
                        context,
                        '@stock_updated = 1',
                        None,
                        {
                            'status': status,
                            'orgId': org_id,
                            'registrationMode': 'warehouse',
                            'inventoryModelId': inventory_model_id,
                            'warehouseId': warehouse_id,
                            'inventoryStockAdjusted': True,
                        },
                    )};
                    SELECT @stock_updated, @new_computer_id;
                    COMMIT;
                    """
                )
                lines = [line.strip() for line in output.splitlines() if line.strip()]
                result = (lines[-1] if lines else "").split("\t")
                stock_updated = self.db.integer(result[0] if result else 0, 0)
                computer_id = self.db.integer(result[1] if len(result) > 1 else 0, 0)
                if stock_updated != 1:
                    raise self.conflict_error("The selected warehouse does not have enough inventory.")
            if computer_id <= 0:
                raise self.api_error("Unable to create computer.")
        return {"computer": self._computer(computer_id)}

    def _shared_employee_number(self, org_id: object, exclude_employee_id: object = 0) -> str:
        """Generate ``SHARED-<组织编码>-NN`` for a shared (non-personal) holder."""
        org = self.db.json(
            f"""
            SELECT JSON_OBJECT('code', org_code)
            FROM org_unit
            WHERE org_unit_id = {self.db.integer(org_id, 0)}
            """,
            None,
        )
        org_code = self.db.text((org or {}).get("code")).upper() or "ORG"
        prefix = f"SHARED-{org_code}-"
        existing = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(employee_no), JSON_ARRAY())
            FROM employee
            WHERE employee_no LIKE {self.db.quote(prefix + '%')}
              AND employee_id <> {self.db.integer(exclude_employee_id, 0)}
            """,
            [],
        )
        used = {
            self.db.text(value)[len(prefix):]
            for value in (existing or [])
            if self.db.text(value).startswith(prefix)
        }
        index = 1
        while f"{index:02d}" in used:
            index += 1
        return f"{prefix}{index:02d}"

    def _save_employee(self, resource_id: object | None, payload: dict, context: dict) -> dict:
        name = self.db.text(payload.get("name"))
        status = self.db.text(payload.get("status")) or "active"
        if status not in {"active", "inactive", "shared"}:
            raise self.api_error("Use the employee offboarding command for left employees.")
        org_id = self.db.integer(payload.get("orgId"), 0)
        self.scope.assert_org_access(context, org_id)
        employee_id = self.db.integer(resource_id, 0)
        employee_no = self.db.text(payload.get("employeeNo"))
        if not employee_no and status == "shared":
            employee_no = self._shared_employee_number(org_id, employee_id)
        if not employee_no or not name:
            raise self.api_error("Employee number and name are required.")
        old = self._employee(employee_id) if employee_id else None
        if old:
            self.scope.assert_org_access(context, old.get("orgId"))
        assignments = {
            "employee_no": self.db.quote(employee_no),
            "employee_name": self.db.quote(name),
            "org_unit_id": "NULL" if org_id <= 0 else str(org_id),
            "department": self.db.quote(self.db.text(payload.get("department"))) if self.db.text(payload.get("department")) else "NULL",
            "position_name": self.db.quote(self.db.text(payload.get("position"))) if self.db.text(payload.get("position")) else "NULL",
            "email": self.db.quote(self.db.text(payload.get("email"))) if self.db.text(payload.get("email")) else "NULL",
            "mobile": self.db.quote(self.db.text(payload.get("mobile"))) if self.db.text(payload.get("mobile")) else "NULL",
            "employment_status": self.db.quote(status),
        }
        if employee_id:
            self.db.execute(
                f"""
                START TRANSACTION;
                UPDATE employee
                SET {", ".join(f"{column} = {value}" for column, value in assignments.items())}
                WHERE employee_id = {employee_id};
                {self._audit_sql('employee_updated', 'employee', employee_id, name, 'Employee updated', context)};
                COMMIT;
                """
            )
        else:
            output = self.db.execute(
                f"""
                START TRANSACTION;
                INSERT INTO employee ({", ".join(assignments.keys())})
                VALUES ({", ".join(assignments.values())});
                SELECT LAST_INSERT_ID();
                COMMIT;
                """
            )
            employee_id = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        return {"employee": self._employee(employee_id)}

    def _save_organization(self, resource_id: object | None, payload: dict, context: dict) -> dict:
        code = self.db.text(payload.get("code")).upper()
        name = self.db.text(payload.get("name"))
        if not code or not name:
            raise self.api_error("Organization code and name are required.")
        parent_id = self.db.integer(payload.get("parentId"), 0)
        self.scope.assert_org_access(context, parent_id)
        org_id = self.db.integer(resource_id, 0)
        if org_id and parent_id == org_id:
            raise self.api_error("An organization cannot be its own parent.")
        sort_order = max(0, self.db.integer(payload.get("sortOrder"), 1000))
        if org_id:
            self.scope.assert_org_access(context, org_id)
            self.db.execute(
                f"""
                START TRANSACTION;
                UPDATE org_unit
                SET org_code = {self.db.quote(code)},
                    org_name = {self.db.quote(name)},
                    parent_org_unit_id = {"NULL" if parent_id <= 0 else parent_id},
                    sort_order = {sort_order}
                WHERE org_unit_id = {org_id};
                {self._audit_sql('organization_updated', 'org_unit', org_id, name, 'Organization updated', context)};
                COMMIT;
                """
            )
        else:
            output = self.db.execute(
                f"""
                INSERT INTO org_unit (org_code, org_name, parent_org_unit_id, sort_order)
                VALUES (
                  {self.db.quote(code)},
                  {self.db.quote(name)},
                  {"NULL" if parent_id <= 0 else parent_id},
                  {sort_order}
                );
                SELECT LAST_INSERT_ID();
                """
            )
            org_id = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        result = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(org_unit_id AS CHAR),
              'code', org_code,
              'name', org_name,
              'parentId', COALESCE(CAST(parent_org_unit_id AS CHAR), ''),
              'sortOrder', sort_order
            )
            FROM org_unit
            WHERE org_unit_id = {org_id}
            """,
            None,
        )
        return {"organization": result}

    def _save_inventory_model(self, resource_id: object | None, payload: dict, context: dict) -> dict:
        type_id = self.db.integer(payload.get("typeId"), 0)
        brand_id = self.db.integer(payload.get("brandId"), 0)
        name = self.db.text(payload.get("name"))
        if type_id <= 0 or brand_id <= 0 or not name:
            raise self.api_error("Inventory type, brand and model name are required.")
        model_id = self.db.integer(resource_id, 0)
        assignments = {
            "non_asset_type_id": str(type_id),
            "brand_id": str(brand_id),
            "model_name": self.db.quote(name),
            "batch_key": self.db.quote(self.db.text(payload.get("batchKey"))),
            "inbound_date": self.db.quote(self.db.text(payload.get("inboundDate"))) if self.db.text(payload.get("inboundDate")) else "NULL",
            "cpu": self.db.quote(self.db.text(payload.get("cpu"))) if self.db.text(payload.get("cpu")) else "NULL",
            "memory": self.db.quote(self.db.text(payload.get("memory"))) if self.db.text(payload.get("memory")) else "NULL",
            "storage": self.db.quote(self.db.text(payload.get("storage"))) if self.db.text(payload.get("storage")) else "NULL",
            "gpu": self.db.quote(self.db.text(payload.get("gpu"))) if self.db.text(payload.get("gpu")) else "NULL",
            "sort_order": str(max(0, self.db.integer(payload.get("sortOrder"), 1000))),
        }
        if model_id:
            self.db.execute(
                f"""
                UPDATE it_inventory_model
                SET {", ".join(f"{column} = {value}" for column, value in assignments.items())}
                WHERE model_id = {model_id} AND is_active = 1;
                """
            )
        else:
            output = self.db.execute(
                f"""
                INSERT INTO it_inventory_model ({", ".join(assignments.keys())}, quantity)
                VALUES ({", ".join(assignments.values())}, 0);
                SELECT LAST_INSERT_ID();
                """
            )
            model_id = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        model = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(model_id AS CHAR),
              'typeId', CAST(non_asset_type_id AS CHAR),
              'brandId', CAST(brand_id AS CHAR),
              'name', model_name,
              'quantity', quantity
            )
            FROM it_inventory_model WHERE model_id = {model_id}
            """,
            None,
        )
        return {"inventoryModel": model}

    def _save_inventory_type(self, resource_id: object | None, payload: dict, context: dict) -> dict:
        code = self.db.text(payload.get("code")).lower()
        name = self.db.text(payload.get("name"))
        unit = self.db.text(payload.get("unit")) or "item"
        if not code or not name:
            raise self.api_error("Inventory type code and name are required.")
        type_id = self.db.integer(resource_id, 0)
        if type_id:
            self.db.execute(
                f"""
                START TRANSACTION;
                UPDATE non_asset_type
                SET type_code = {self.db.quote(code)},
                    type_name = {self.db.quote(name)},
                    unit_name = {self.db.quote(unit)}
                WHERE non_asset_type_id = {type_id} AND is_active = 1;
                {self._audit_sql(
                    'inventory_type_updated',
                    'non_asset_type',
                    type_id,
                    name,
                    'Inventory type updated',
                    context,
                )};
                COMMIT;
                """
            )
        else:
            output = self.db.execute(
                f"""
                START TRANSACTION;
                INSERT INTO non_asset_type (type_code, type_name, unit_name)
                VALUES ({self.db.quote(code)}, {self.db.quote(name)}, {self.db.quote(unit)});
                SET @new_type_id = LAST_INSERT_ID();
                {self._audit_sql(
                    'inventory_type_created',
                    'non_asset_type',
                    "'new'",
                    name,
                    'Inventory type created',
                    context,
                )};
                UPDATE audit_log
                SET entity_id = CAST(@new_type_id AS CHAR)
                WHERE audit_log_id = LAST_INSERT_ID();
                SELECT @new_type_id;
                COMMIT;
                """
            )
            type_id = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        inventory_type = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(non_asset_type_id AS CHAR),
              'code', type_code,
              'name', type_name,
              'unit', unit_name
            )
            FROM non_asset_type
            WHERE non_asset_type_id = {type_id} AND is_active = 1
            """,
            None,
        )
        if not inventory_type:
            raise self.api_error("Inventory type does not exist.")
        return {"inventoryType": inventory_type}

    def _save_inventory_brand(self, resource_id: object | None, payload: dict, context: dict) -> dict:
        type_id = self.db.integer(payload.get("typeId"), 0)
        name = self.db.text(payload.get("name"))
        sort_order = max(0, self.db.integer(payload.get("sortOrder"), 1000))
        if type_id <= 0 or not name:
            raise self.api_error("Inventory brand type and name are required.")
        if self.db.scalar(
            f"SELECT COUNT(*) FROM non_asset_type WHERE non_asset_type_id = {type_id} AND is_active = 1;"
        ) != 1:
            raise self.api_error("Inventory type does not exist.")
        brand_id = self.db.integer(resource_id, 0)
        if brand_id:
            self.db.execute(
                f"""
                START TRANSACTION;
                UPDATE it_inventory_brand
                SET non_asset_type_id = {type_id},
                    brand_name = {self.db.quote(name)},
                    sort_order = {sort_order}
                WHERE brand_id = {brand_id} AND is_active = 1;
                {self._audit_sql(
                    'inventory_brand_updated',
                    'it_inventory_brand',
                    brand_id,
                    name,
                    'Inventory brand updated',
                    context,
                )};
                COMMIT;
                """
            )
        else:
            output = self.db.execute(
                f"""
                START TRANSACTION;
                INSERT INTO it_inventory_brand (non_asset_type_id, brand_name, sort_order)
                VALUES ({type_id}, {self.db.quote(name)}, {sort_order});
                SET @new_brand_id = LAST_INSERT_ID();
                {self._audit_sql(
                    'inventory_brand_created',
                    'it_inventory_brand',
                    "'new'",
                    name,
                    'Inventory brand created',
                    context,
                )};
                UPDATE audit_log
                SET entity_id = CAST(@new_brand_id AS CHAR)
                WHERE audit_log_id = LAST_INSERT_ID();
                SELECT @new_brand_id;
                COMMIT;
                """
            )
            brand_id = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        inventory_brand = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(brand_id AS CHAR),
              'typeId', CAST(non_asset_type_id AS CHAR),
              'name', brand_name,
              'sortOrder', sort_order
            )
            FROM it_inventory_brand
            WHERE brand_id = {brand_id} AND is_active = 1
            """,
            None,
        )
        if not inventory_brand:
            raise self.api_error("Inventory brand does not exist.")
        return {"inventoryBrand": inventory_brand}

    def assign_computer(self, computer_id: object, payload: dict, context: dict, idempotency_key: str = "") -> dict:
        cached = self._idempotency_result("computer.assign", idempotency_key, payload)
        if cached:
            return cached
        self._assert_inventory_issue_scope(context)
        computer = self._computer(computer_id)
        self.scope.assert_computer_access(context, computer_id)
        employee = self._employee(payload.get("employeeId"))
        self.scope.assert_org_access(context, employee.get("orgId"))
        self._assert_employee_scope(context, employee.get("id"))
        if self.db.text(employee.get("status")) not in {"active", "shared"}:
            raise self.conflict_error("办公终端只能分配给在职人员或公用人员。")
        if self.db.text(computer.get("status")) in {"retired", "lost"}:
            raise self.conflict_error("This computer cannot be assigned in its current lifecycle state.")
        computer_id_int = self.db.integer(computer_id, 0)
        employee_id = self.db.integer(employee.get("id"), 0)
        assigned_at = self.db.text(payload.get("assignedAt")) or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notes = self.db.text(payload.get("notes"))
        actor_id = self._actor_id(context)
        output = self.db.execute(
            f"""
            START TRANSACTION;
            SELECT computer_id FROM computer_asset WHERE computer_id = {computer_id_int} FOR UPDATE;
            SELECT employee_id FROM employee WHERE employee_id = {employee_id} FOR UPDATE;
            UPDATE computer_assignment
            SET returned_at = CURRENT_TIMESTAMP, assignment_status = 'returned'
            WHERE computer_id = {computer_id_int}
              AND returned_at IS NULL
              AND assignment_status = 'active';
            UPDATE computer_assignment_history
            SET returned_at = CURRENT_TIMESTAMP,
                assignment_status = 'returned',
                returned_by = {actor_id},
                notes = CONCAT_WS(' ', notes, 'Reassigned to another employee')
            WHERE computer_id = {computer_id_int}
              AND returned_at IS NULL
              AND assignment_status = 'active';
            INSERT INTO computer_assignment (
              computer_id, employee_id, assigned_at, assignment_status, notes
            )
            VALUES (
              {computer_id_int}, {employee_id}, {self.db.quote(assigned_at)}, 'active', {self.db.quote(notes)}
            );
            SET @assignment_id = LAST_INSERT_ID();
            INSERT INTO computer_assignment_history (
              computer_id, device_name, employee_id, employee_no, employee_name,
              assigned_at, assignment_status, notes, assigned_by
            )
            SELECT
              asset.computer_id, asset.device_name, employee.employee_id, employee.employee_no,
              employee.employee_name, {self.db.quote(assigned_at)}, 'active', {self.db.quote(notes)},
              {actor_id}
            FROM computer_asset asset
            JOIN employee ON employee.employee_id = {employee_id}
            WHERE asset.computer_id = {computer_id_int};
            UPDATE computer_asset
            SET it_asset_status = 'in_use'
            WHERE computer_id = {computer_id_int};
            INSERT INTO asset_status_history (
              computer_id, previous_status, next_status, reason, changed_by
            )
            VALUES (
              {computer_id_int}, {self.db.quote(self.db.text(computer.get('status')))}, 'in_use',
              'Computer assignment', {actor_id}
            );
            {self._audit_sql(
                'computer_assigned',
                'computer',
                computer_id_int,
                self.db.text(computer.get('deviceName')),
                'Computer assigned to ' + self.db.text(employee.get('name')),
                context,
                {'userId': computer.get('userId'), 'status': computer.get('status')},
                {'userId': employee.get('id'), 'status': 'in_use'},
            )};
            SELECT @assignment_id;
            COMMIT;
            """
        )
        assignment_id = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        response = {"assignmentId": str(assignment_id), "computer": self._computer(computer_id_int)}
        self._store_idempotency_result("computer.assign", idempotency_key, payload, response)
        return response

    def return_computer(self, computer_id: object, payload: dict, context: dict, idempotency_key: str = "") -> dict:
        cached = self._idempotency_result("computer.return", idempotency_key, payload)
        if cached:
            return cached
        computer = self._computer(computer_id)
        self.scope.assert_computer_access(context, computer_id)
        if self._permission_scope(context) in {"own", "submitted", "assigned"}:
            self._assert_employee_scope(context, computer.get("userId"))
        computer_id_int = self.db.integer(computer_id, 0)
        next_status = self._normalize_status(payload.get("nextStatus"), "idle")
        if next_status not in COMPUTER_STATUS_TRANSITIONS.get(self.db.text(computer.get("status")), set()):
            raise self.conflict_error("Invalid lifecycle transition for computer return.")
        notes = self.db.text(payload.get("notes"))
        output = self.db.execute(
            f"""
            START TRANSACTION;
            SELECT assignment_id
            FROM computer_assignment
            WHERE computer_id = {computer_id_int}
              AND returned_at IS NULL
              AND assignment_status = 'active'
            FOR UPDATE;
            UPDATE computer_assignment
            SET returned_at = CURRENT_TIMESTAMP,
                assignment_status = 'returned',
                notes = CONCAT_WS(' ', notes, {self.db.quote(notes)})
            WHERE computer_id = {computer_id_int}
              AND returned_at IS NULL
              AND assignment_status = 'active';
            SET @returned_count = ROW_COUNT();
            INSERT INTO computer_assignment_history (
              computer_id, device_name, employee_id, employee_no, employee_name,
              assigned_at, returned_at, assignment_status, notes, returned_by
            )
            SELECT
              assignment.computer_id, asset.device_name, assignment.employee_id,
              employee.employee_no, employee.employee_name,
              assignment.assigned_at, CURRENT_TIMESTAMP, 'returned', assignment.notes,
              {self._actor_id(context)}
            FROM computer_assignment assignment
            JOIN computer_asset asset ON asset.computer_id = assignment.computer_id
            JOIN employee ON employee.employee_id = assignment.employee_id
            WHERE assignment.computer_id = {computer_id_int}
              AND assignment.returned_at IS NOT NULL
              AND @returned_count = 1
            ORDER BY assignment.assignment_id DESC
            LIMIT 1
            ON DUPLICATE KEY UPDATE
              returned_at = VALUES(returned_at),
              assignment_status = VALUES(assignment_status),
              notes = VALUES(notes),
              returned_by = VALUES(returned_by);
            UPDATE computer_asset
            SET it_asset_status = {self.db.quote(next_status)}
            WHERE computer_id = {computer_id_int}
              AND @returned_count = 1;
            INSERT INTO asset_status_history (
              computer_id, previous_status, next_status, reason, changed_by
            )
            SELECT
              {computer_id_int}, {self.db.quote(self.db.text(computer.get('status')))},
              {self.db.quote(next_status)}, 'Computer return', {self._actor_id(context)}
            FROM DUAL
            WHERE @returned_count = 1;
            SELECT @returned_count;
            COMMIT;
            """
        )
        returned_count = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        if returned_count <= 0:
            raise self.conflict_error("The computer has no active assignment to return.")
        self.db.execute(
            self._audit_sql(
                "computer_returned",
                "computer",
                computer_id_int,
                self.db.text(computer.get("deviceName")),
                "Computer returned",
                context,
                {"userId": computer.get("userId"), "status": computer.get("status")},
                {"userId": "", "status": next_status},
            )
            + ";"
        )
        response = {"computer": self._computer(computer_id_int)}
        self._store_idempotency_result("computer.return", idempotency_key, payload, response)
        return response

    def receive_inventory(self, payload: dict, context: dict, idempotency_key: str = "") -> dict:
        cached = self._idempotency_result("inventory.receipt", idempotency_key, payload)
        if cached:
            return cached
        self._assert_inventory_issue_scope(context)
        model_id = self.db.integer(payload.get("modelId"), 0)
        quantity = self.db.integer(payload.get("quantity"), 0)
        if model_id <= 0 or quantity <= 0:
            raise self.api_error("Inventory receipt requires a model and a positive quantity.")
        warehouse = self._resolve_warehouse(
            payload,
            context,
            "inventory_operations",
            require_explicit=True,
        )
        warehouse_id = self.db.integer(warehouse.get("id"), 0)
        model = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', model.model_id,
              'typeId', model.non_asset_type_id,
              'brandId', model.brand_id,
              'modelName', model.model_name,
              'brandName', brand.brand_name,
              'typeName', type_row.type_name,
              'quantity', model.quantity
            )
            FROM it_inventory_model model
            JOIN it_inventory_brand brand ON brand.brand_id = model.brand_id
            JOIN non_asset_type type_row ON type_row.non_asset_type_id = model.non_asset_type_id
            WHERE model.model_id = {model_id} AND model.is_active = 1
            """,
            None,
        )
        if not model:
            raise self.api_error("Inventory model does not exist.")
        inbound_date = self.db.text(payload.get("inboundDate")) or datetime.now().strftime("%Y-%m-%d")
        note = self.db.text(payload.get("note"))
        source_label = self.db.text(payload.get("sourceLabel")) or "Inventory receipt"
        output = self.db.execute(
            f"""
            START TRANSACTION;
            SELECT model_id FROM it_inventory_model WHERE model_id = {model_id} FOR UPDATE;
            INSERT INTO inventory_warehouse_stock (warehouse_id, model_id, quantity)
            VALUES ({warehouse_id}, {model_id}, 0)
            ON DUPLICATE KEY UPDATE warehouse_id = VALUES(warehouse_id);
            SELECT quantity
            FROM inventory_warehouse_stock
            WHERE warehouse_id = {warehouse_id}
              AND model_id = {model_id}
            FOR UPDATE;
            UPDATE it_inventory_model
            SET quantity = quantity + {quantity},
                inbound_date = {self.db.quote(inbound_date)}
            WHERE model_id = {model_id};
            UPDATE inventory_warehouse_stock
            SET quantity = quantity + {quantity}
            WHERE warehouse_id = {warehouse_id}
              AND model_id = {model_id};
            INSERT INTO inventory_movement_log (
              movement_direction, type_name, brand_name, model_name, quantity,
              source_label, source_warehouse_id, target_label, target_warehouse_id,
              note, trigger_action
            )
            VALUES (
              'increase', {self.db.quote(self.db.text(model.get('typeName')))},
              {self.db.quote(self.db.text(model.get('brandName')))},
              {self.db.quote(self.db.text(model.get('modelName')))}, {quantity},
              {self.db.quote(source_label)}, NULL, {self.db.quote(self.db.text(warehouse.get('name')))},
              {warehouse_id}, {self.db.quote(note)}, 'inventory_receipt'
            );
            SET @movement_id = LAST_INSERT_ID();
            INSERT INTO inventory_purchase_log (
              type_name, brand_name, model_name, non_asset_type_id, brand_id, model_id,
              warehouse_id, quantity, inbound_date, source_label, note, source_movement_log_id
            )
            VALUES (
              {self.db.quote(self.db.text(model.get('typeName')))},
              {self.db.quote(self.db.text(model.get('brandName')))},
              {self.db.quote(self.db.text(model.get('modelName')))},
              {self.db.integer(model.get('typeId'), 0)}, {self.db.integer(model.get('brandId'), 0)}, {model_id},
              {warehouse_id}, {quantity}, {self.db.quote(inbound_date)}, {self.db.quote(source_label)},
              {self.db.quote(note)}, @movement_id
            );
            SET @purchase_id = LAST_INSERT_ID();
            {self._audit_sql(
                'inventory_received',
                'inventory_model',
                model_id,
                self.db.text(model.get('modelName')),
                'Inventory receipt',
                context,
                {'quantity': self.db.integer(model.get('quantity'), 0)},
                {'quantityDelta': quantity, 'warehouseId': warehouse_id},
            )};
            SELECT @purchase_id;
            COMMIT;
            """
        )
        purchase_id = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        response = {
            "purchaseId": str(purchase_id),
            "modelId": str(model_id),
            "warehouseId": str(warehouse_id),
            "quantityReceived": quantity,
        }
        self._store_idempotency_result("inventory.receipt", idempotency_key, payload, response)
        return response

    def allocate_inventory(self, payload: dict, context: dict, idempotency_key: str = "") -> dict:
        cached = self._idempotency_result("inventory.allocate", idempotency_key, payload)
        if cached:
            return cached
        self._assert_inventory_issue_scope(context)
        allocation_type = self.db.text(payload.get("allocationType"))
        if allocation_type not in {"monitor", "non_asset"}:
            raise self.api_error("Allocation type must be monitor or non_asset.")
        employee = self._employee(payload.get("employeeId"))
        self.scope.assert_org_access(context, employee.get("orgId"))
        self._assert_employee_scope(context, employee.get("id"))
        model_id = self.db.integer(payload.get("modelId"), 0)
        quantity = self.db.integer(payload.get("quantity"), 1)
        # Keep legacy callers deducting by default while honoring JSON false for reconciliation entries.
        stock_adjusted = parse_bool(payload.get("stockAdjusted"), True)
        if quantity <= 0:
            raise self.api_error("Allocation requires a positive quantity.")
        if allocation_type == "monitor" and quantity != 1:
            raise self.api_error("Monitor allocation quantity must be one.")
        warehouse = None
        if stock_adjusted:
            warehouse = self._resolve_warehouse(
                payload,
                context,
                "inventory_operations",
                preferred_org_id=employee.get("orgId"),
            )
        warehouse_id = self.db.integer((warehouse or {}).get("id"), 0)
        warehouse_id_sql = str(warehouse_id) if warehouse_id > 0 else "NULL"

        type_id = 0
        brand_id = 0
        type_name = ""
        brand_name = ""
        model_name = ""
        model_id_sql = "NULL"
        usage_display_name = ""
        if model_id > 0:
            model = self.db.json(
                f"""
                SELECT JSON_OBJECT(
                  'typeId', model.non_asset_type_id,
                  'brandId', model.brand_id,
                  'typeName', type_row.type_name,
                  'brandName', brand.brand_name,
                  'modelName', model.model_name
                )
                FROM it_inventory_model model
                JOIN it_inventory_brand brand ON brand.brand_id = model.brand_id
                JOIN non_asset_type type_row ON type_row.non_asset_type_id = model.non_asset_type_id
                WHERE model.model_id = {model_id} AND model.is_active = 1
                """,
                None,
            )
            if not model:
                raise self.api_error("Inventory model does not exist.")
            type_id = self.db.integer(model.get("typeId"), 0)
            brand_id = self.db.integer(model.get("brandId"), 0)
            type_name = self.db.text(model.get("typeName"))
            brand_name = self.db.text(model.get("brandName"))
            model_name = self.db.text(model.get("modelName"))
            usage_display_name = self.db.text(payload.get("displayName")) or brand_name
            model_id_sql = str(model_id)
        else:
            if stock_adjusted:
                raise self.api_error("Inventory deduction requires a registered inventory model.")
            type_id = self.db.integer(payload.get("typeId"), 0)
            if type_id <= 0:
                raise self.api_error("Custom allocation requires a type.")
            type_row = self.db.json(
                f"""
                SELECT JSON_OBJECT('typeName', type_name)
                FROM non_asset_type
                WHERE non_asset_type_id = {type_id}
                  AND is_active = 1
                """,
                None,
            )
            if not type_row:
                raise self.api_error("Allocation type does not exist.")
            brand_id = self.db.integer(payload.get("inventoryBrandId"), 0)
            if brand_id > 0:
                brand_row = self.db.json(
                    f"""
                    SELECT JSON_OBJECT('brandName', brand_name)
                    FROM it_inventory_brand
                    WHERE brand_id = {brand_id}
                      AND non_asset_type_id = {type_id}
                      AND is_active = 1
                    """,
                    None,
                )
                if not brand_row:
                    raise self.api_error("Inventory brand does not exist.")
                brand_name = self.db.text(payload.get("brand")) or self.db.text(brand_row.get("brandName"))
            else:
                brand_name = self.db.text(payload.get("brand"))
            model_name = self.db.text(payload.get("model"))
            usage_display_name = self.db.text(payload.get("displayName")) or brand_name
            if allocation_type == "monitor":
                brand_name = usage_display_name
            if not brand_name or not model_name:
                raise self.api_error("Custom allocation requires brand and model.")
            type_name = self.db.text(type_row.get("typeName"))

        employee_id = self.db.integer(employee.get("id"), 0)
        note = self.db.text(payload.get("notes"))
        brand_id_sql = self._nullable_id_sql(brand_id)
        model = {
            "typeName": type_name,
            "brandName": brand_name,
            "modelName": model_name,
        }
        if allocation_type == "monitor":
            display_name = usage_display_name or brand_name
            usage_sql = f"""
                INSERT INTO employee_monitor_usage (
                  employee_id, non_asset_type_id, inventory_brand_id, inventory_model_id,
                  display_name, model, quantity, stock_adjusted, notes
                )
                SELECT
                  {employee_id}, {type_id}, {brand_id_sql}, {model_id_sql},
                  {self.db.quote(display_name)}, {self.db.quote(model_name)}, 1,
                  {1 if stock_adjusted else 0}, {self.db.quote(note)}
                FROM DUAL
                WHERE @stock_updated = 1;
                SET @usage_ref = IF(@stock_updated = 1, LAST_INSERT_ID(), 0);
            """
        else:
            usage_sql = f"""
                INSERT INTO employee_non_asset_usage (
                  employee_id, non_asset_type_id, inventory_brand_id, inventory_model_id,
                  brand, model, quantity, stock_adjusted, notes
                )
                SELECT
                  {employee_id}, {type_id}, {brand_id_sql}, {model_id_sql},
                  {self.db.quote(brand_name)}, {self.db.quote(model_name)},
                  {quantity}, {1 if stock_adjusted else 0}, {self.db.quote(note)}
                FROM DUAL
                WHERE @stock_updated = 1;
                SET @usage_ref = IF(@stock_updated = 1, LAST_INSERT_ID(), 0);
            """

        if model_id > 0:
            inventory_guard_sql = f"""
            SELECT quantity INTO @available_quantity
            FROM it_inventory_model
            WHERE model_id = {model_id}
            FOR UPDATE;
            INSERT INTO inventory_warehouse_stock (warehouse_id, model_id, quantity)
            SELECT {warehouse_id}, {model_id}, 0
            FROM DUAL
            WHERE {1 if stock_adjusted else 0} = 1
            ON DUPLICATE KEY UPDATE warehouse_id = VALUES(warehouse_id);
            SELECT COALESCE(quantity, 0) INTO @warehouse_available_quantity
            FROM inventory_warehouse_stock
            WHERE warehouse_id = {warehouse_id}
              AND model_id = {model_id}
            FOR UPDATE;
            SET @stock_updated = IF(
              {1 if stock_adjusted else 0} = 0
              OR (@available_quantity >= {quantity} AND @warehouse_available_quantity >= {quantity}),
              1,
              0
            );
            UPDATE it_inventory_model
            SET quantity = quantity - {quantity}
            WHERE model_id = {model_id}
              AND @stock_updated = 1
              AND {1 if stock_adjusted else 0} = 1;
            UPDATE inventory_warehouse_stock
            SET quantity = quantity - {quantity}
            WHERE warehouse_id = {warehouse_id}
              AND model_id = {model_id}
              AND @stock_updated = 1
              AND {1 if stock_adjusted else 0} = 1;
            """
        else:
            inventory_guard_sql = """
            SET @available_quantity = 0;
            SET @stock_updated = 1;
            """

        output = self.db.execute(
            f"""
            START TRANSACTION;
            {inventory_guard_sql}
            {usage_sql}
            INSERT INTO inventory_allocation_history (
              allocation_type, employee_id, non_asset_type_id, inventory_model_id,
              warehouse_id, usage_record_id, quantity, stock_adjusted, status, notes, issued_by
            )
            SELECT
              {self.db.quote(allocation_type)}, {employee_id}, {type_id}, {model_id_sql},
              {warehouse_id_sql}, @usage_ref, {quantity}, {1 if stock_adjusted else 0}, 'active',
              {self.db.quote(note)}, {self._actor_id(context)}
            FROM DUAL
            WHERE @stock_updated = 1;
            SET @allocation_id = IF(@stock_updated = 1, LAST_INSERT_ID(), 0);
            INSERT INTO inventory_movement_log (
              movement_direction, type_name, brand_name, model_name, quantity,
              source_label, source_warehouse_id, target_label, target_warehouse_id,
              note, related_employee_no, related_employee_name, trigger_action
            )
            SELECT
              'decrease', {self.db.quote(self.db.text(model.get('typeName')))},
              {self.db.quote(self.db.text(model.get('brandName')))}, {self.db.quote(model_name)}, {quantity},
              {self.db.quote(self.db.text((warehouse or {}).get('name')))}, {warehouse_id_sql},
              {self.db.quote(self.db.text(employee.get('name')))}, NULL, {self.db.quote(note)},
              {self.db.quote(self.db.text(employee.get('employeeNo')))},
              {self.db.quote(self.db.text(employee.get('name')))}, 'inventory_allocation'
            FROM DUAL
            WHERE @stock_updated = 1 AND {1 if stock_adjusted else 0} = 1;
            {self._conditional_audit_sql(
                'inventory_allocated',
                'inventory_allocation',
                'CAST(@allocation_id AS CHAR)',
                model_name,
                'Inventory allocated to ' + self.db.text(employee.get('name')),
                context,
                '@stock_updated = 1',
                None,
                {
                    'quantity': quantity,
                    'employeeId': employee.get('id'),
                    'stockAdjusted': stock_adjusted,
                    'warehouseId': warehouse_id if stock_adjusted else None,
                },
            )};
            SELECT @stock_updated, @allocation_id, @usage_ref;
            COMMIT;
            """
        )
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        result = (lines[-1] if lines else "").split("\t")
        stock_updated = self.db.integer(result[0] if result else 0, 0)
        allocation_id = self.db.integer(result[1] if len(result) > 1 else 0, 0)
        usage_ref = self.db.integer(result[2] if len(result) > 2 else 0, 0)
        if stock_updated != 1 or allocation_id <= 0 or usage_ref <= 0:
            raise self.conflict_error("Insufficient inventory.")
        response = {
            "allocationId": str(allocation_id),
            "usageRecordId": str(usage_ref),
            "warehouseId": str(warehouse_id) if stock_adjusted else "",
        }
        self._store_idempotency_result("inventory.allocate", idempotency_key, payload, response)
        return response

    def adjust_inventory(self, payload: dict, context: dict, idempotency_key: str = "") -> dict:
        cached = self._idempotency_result("inventory.adjust", idempotency_key, payload)
        if cached:
            return cached
        self._assert_inventory_issue_scope(context)
        model_id = self.db.integer(payload.get("modelId"), 0)
        delta = self.db.integer(payload.get("quantityDelta"), 0)
        if model_id <= 0 or delta == 0:
            raise self.api_error("Inventory adjustment requires a model and a non-zero quantity delta.")
        warehouse = self._resolve_warehouse(
            payload,
            context,
            "inventory_operations",
            require_explicit=True,
        )
        warehouse_id = self.db.integer(warehouse.get("id"), 0)
        model = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'typeName', type_row.type_name,
              'brandName', brand.brand_name,
              'modelName', model.model_name,
              'quantity', model.quantity
            )
            FROM it_inventory_model model
            JOIN it_inventory_brand brand ON brand.brand_id = model.brand_id
            JOIN non_asset_type type_row ON type_row.non_asset_type_id = model.non_asset_type_id
            WHERE model.model_id = {model_id} AND model.is_active = 1
            """,
            None,
        )
        if not model:
            raise self.api_error("Inventory model does not exist.")
        direction = "increase" if delta > 0 else "decrease"
        quantity = abs(delta)
        note = self.db.text(payload.get("note"))
        output = self.db.execute(
            f"""
            START TRANSACTION;
            SELECT quantity INTO @current_quantity
            FROM it_inventory_model
            WHERE model_id = {model_id}
            FOR UPDATE;
            INSERT INTO inventory_warehouse_stock (warehouse_id, model_id, quantity)
            VALUES ({warehouse_id}, {model_id}, 0)
            ON DUPLICATE KEY UPDATE warehouse_id = VALUES(warehouse_id);
            SELECT quantity INTO @warehouse_current_quantity
            FROM inventory_warehouse_stock
            WHERE warehouse_id = {warehouse_id}
              AND model_id = {model_id}
            FOR UPDATE;
            SET @adjusted = IF(
              @current_quantity + ({delta}) >= 0
              AND @warehouse_current_quantity + ({delta}) >= 0,
              1,
              0
            );
            UPDATE it_inventory_model
            SET quantity = quantity + ({delta})
            WHERE model_id = {model_id} AND @adjusted = 1;
            UPDATE inventory_warehouse_stock
            SET quantity = quantity + ({delta})
            WHERE warehouse_id = {warehouse_id}
              AND model_id = {model_id}
              AND @adjusted = 1;
            INSERT INTO inventory_movement_log (
              movement_direction, type_name, brand_name, model_name, quantity,
              source_label, source_warehouse_id, target_label, target_warehouse_id,
              note, trigger_action
            )
            SELECT
              {self.db.quote(direction)},
              {self.db.quote(self.db.text(model.get('typeName')))},
              {self.db.quote(self.db.text(model.get('brandName')))},
              {self.db.quote(self.db.text(model.get('modelName')))},
              {quantity},
              {self.db.quote('Manual adjustment' if delta > 0 else self.db.text(warehouse.get('name')))},
              {"NULL" if delta > 0 else str(warehouse_id)},
              {self.db.quote(self.db.text(warehouse.get('name') if delta > 0 else 'Manual adjustment'))},
              {str(warehouse_id) if delta > 0 else "NULL"},
              {self.db.quote(note)},
              'inventory_adjustment'
            FROM DUAL
            WHERE @adjusted = 1;
            {self._conditional_audit_sql(
                'inventory_adjusted',
                'inventory_model',
                self.db.quote(str(model_id)),
                self.db.text(model.get('modelName')),
                'Inventory manually adjusted',
                context,
                '@adjusted = 1',
                {'quantity': self.db.integer(model.get('quantity'), 0)},
                {'quantityDelta': delta, 'warehouseId': warehouse_id},
            )};
            SELECT @adjusted;
            COMMIT;
            """
        )
        adjusted = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        if adjusted != 1:
            raise self.conflict_error("Inventory adjustment would make stock negative.")
        response = {"modelId": str(model_id), "warehouseId": str(warehouse_id), "quantityDelta": delta}
        self._store_idempotency_result("inventory.adjust", idempotency_key, payload, response)
        return response

    def transfer_inventory(self, payload: dict, context: dict, idempotency_key: str = "") -> dict:
        cached = self._idempotency_result("inventory.transfer", idempotency_key, payload)
        if cached:
            return cached
        self._assert_inventory_issue_scope(context)

        source_warehouse_id = self.db.integer(payload.get("sourceWarehouseId"), 0)
        target_warehouse_id = self.db.integer(payload.get("targetWarehouseId"), 0)
        model_id = self.db.integer(payload.get("modelId"), 0)
        quantity = self.db.integer(payload.get("quantity"), 0)
        note = self.db.text(payload.get("note")).strip()
        if source_warehouse_id <= 0 or target_warehouse_id <= 0:
            raise self.api_error("请选择调出仓库和调入仓库。")
        if source_warehouse_id == target_warehouse_id:
            raise self.api_error("调出仓库和调入仓库不能相同。")
        if model_id <= 0 or quantity <= 0:
            raise self.api_error("请选择物资型号并填写大于零的调拨数量。")
        if len(note) > 500:
            raise self.api_error("调拨备注不能超过 500 个字符。")

        source_warehouse = self._warehouse(source_warehouse_id)
        target_warehouse = self._warehouse(target_warehouse_id)
        self._assert_warehouse_access(
            context, source_warehouse, "warehouse_management", require_active=True
        )
        self._assert_warehouse_access(
            context, target_warehouse, "warehouse_management", require_active=True
        )
        model = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'typeName', type_row.type_name,
              'brandName', brand.brand_name,
              'modelName', model.model_name
            )
            FROM it_inventory_model model
            JOIN it_inventory_brand brand ON brand.brand_id = model.brand_id
            JOIN non_asset_type type_row ON type_row.non_asset_type_id = model.non_asset_type_id
            WHERE model.model_id = {model_id}
              AND model.is_active = 1;
            """,
            None,
        )
        if not model:
            raise self.api_error("物资型号不存在或已停用。")

        first_warehouse_id, second_warehouse_id = sorted(
            (source_warehouse_id, target_warehouse_id)
        )
        actor_id = self._actor_id(context)
        actor_sql = str(actor_id) if actor_id > 0 else "NULL"
        output = self.db.execute(
            f"""
            START TRANSACTION;
            SET @model_exists = 0;
            SELECT 1 INTO @model_exists
            FROM it_inventory_model
            WHERE model_id = {model_id}
              AND is_active = 1
            FOR UPDATE;
            INSERT INTO inventory_warehouse_stock (warehouse_id, model_id, quantity)
            VALUES ({first_warehouse_id}, {model_id}, 0)
            ON DUPLICATE KEY UPDATE warehouse_id = VALUES(warehouse_id);
            INSERT INTO inventory_warehouse_stock (warehouse_id, model_id, quantity)
            VALUES ({second_warehouse_id}, {model_id}, 0)
            ON DUPLICATE KEY UPDATE warehouse_id = VALUES(warehouse_id);
            SELECT quantity INTO @source_quantity
            FROM inventory_warehouse_stock
            WHERE warehouse_id = {source_warehouse_id}
              AND model_id = {model_id}
            FOR UPDATE;
            SELECT quantity
            FROM inventory_warehouse_stock
            WHERE warehouse_id = {target_warehouse_id}
              AND model_id = {model_id}
            FOR UPDATE;
            SET @transferred = IF(
              @model_exists = 1
              AND COALESCE(@source_quantity, 0) >= {quantity},
              1,
              0
            );
            UPDATE inventory_warehouse_stock
            SET quantity = quantity - {quantity}
            WHERE warehouse_id = {source_warehouse_id}
              AND model_id = {model_id}
              AND @transferred = 1;
            UPDATE inventory_warehouse_stock
            SET quantity = quantity + {quantity}
            WHERE warehouse_id = {target_warehouse_id}
              AND model_id = {model_id}
              AND @transferred = 1;
            INSERT INTO inventory_transfer_log (
              source_warehouse_id, target_warehouse_id, model_id, quantity, note, created_by
            )
            SELECT
              {source_warehouse_id}, {target_warehouse_id}, {model_id}, {quantity},
              {self.db.quote(note)}, {actor_sql}
            FROM DUAL
            WHERE @transferred = 1;
            SET @transfer_id = IF(@transferred = 1, LAST_INSERT_ID(), 0);
            INSERT INTO inventory_movement_log (
              movement_direction, type_name, brand_name, model_name, quantity,
              source_label, source_warehouse_id, target_label, target_warehouse_id,
              note, trigger_action
            )
            SELECT
              'decrease',
              {self.db.quote(self.db.text(model.get('typeName')))},
              {self.db.quote(self.db.text(model.get('brandName')))},
              {self.db.quote(self.db.text(model.get('modelName')))},
              {quantity},
              {self.db.quote(self.db.text(source_warehouse.get('name')))},
              {source_warehouse_id},
              {self.db.quote(self.db.text(target_warehouse.get('name')))},
              {target_warehouse_id},
              {self.db.quote(note)},
              'inventory_transfer'
            FROM DUAL
            WHERE @transferred = 1;
            {self._conditional_audit_sql(
                'inventory_transferred',
                'inventory_transfer',
                'CAST(@transfer_id AS CHAR)',
                self.db.text(model.get('modelName')),
                'Warehouse inventory transferred',
                context,
                '@transferred = 1',
                {
                    'sourceWarehouseId': source_warehouse_id,
                    'targetWarehouseId': target_warehouse_id,
                    'modelId': model_id,
                    'quantity': quantity,
                },
                {
                    'sourceWarehouseId': source_warehouse_id,
                    'targetWarehouseId': target_warehouse_id,
                    'modelId': model_id,
                    'quantity': quantity,
                    'note': note,
                },
            )};
            SELECT @transferred, @transfer_id;
            COMMIT;
            """
        )
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        result = (lines[-1] if lines else "").split("\t")
        transferred = self.db.integer(result[0] if result else 0, 0)
        transfer_id = self.db.integer(result[1] if len(result) > 1 else 0, 0)
        if transferred != 1 or transfer_id <= 0:
            raise self.conflict_error("调出仓库库存不足，无法完成调拨。")
        response = {
            "transferId": str(transfer_id),
            "sourceWarehouseId": str(source_warehouse_id),
            "targetWarehouseId": str(target_warehouse_id),
            "modelId": str(model_id),
            "quantity": quantity,
        }
        self._store_idempotency_result("inventory.transfer", idempotency_key, payload, response)
        return response

    def return_inventory(self, allocation_id: object, payload: dict, context: dict, idempotency_key: str = "") -> dict:
        cached = self._idempotency_result("inventory.return", idempotency_key, payload)
        if cached:
            return cached
        allocation_id_int = self.db.integer(allocation_id, 0)
        allocation = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', allocation.allocation_id,
              'type', allocation.allocation_type,
              'employeeId', allocation.employee_id,
              'employeeNo', employee.employee_no,
              'employeeName', employee.employee_name,
              'orgId', COALESCE(employee.org_unit_id, 0),
              'issuedBy', COALESCE(allocation.issued_by, 0),
              'typeId', COALESCE(allocation.non_asset_type_id, 0),
              'modelId', COALESCE(allocation.inventory_model_id, 0),
              'usageBrandId', COALESCE(monitor_usage.inventory_brand_id, non_asset_usage.inventory_brand_id, 0),
              'warehouseId', COALESCE(allocation.warehouse_id, 0),
              'usageRecordId', COALESCE(allocation.usage_record_id, 0),
              'quantity', allocation.quantity,
              'stockAdjusted', allocation.stock_adjusted,
              'status', allocation.status,
              'typeName', COALESCE(type_row.type_name, ''),
              'brandName', COALESCE(brand.brand_name, monitor_usage.display_name, non_asset_usage.brand, ''),
              'modelName', COALESCE(model.model_name, monitor_usage.model, non_asset_usage.model, '')
            )
            FROM inventory_allocation_history allocation
            JOIN employee ON employee.employee_id = allocation.employee_id
            LEFT JOIN it_inventory_model model ON model.model_id = allocation.inventory_model_id
            LEFT JOIN it_inventory_brand brand ON brand.brand_id = model.brand_id
            LEFT JOIN non_asset_type type_row ON type_row.non_asset_type_id = allocation.non_asset_type_id
            LEFT JOIN employee_monitor_usage monitor_usage
              ON monitor_usage.monitor_usage_id = allocation.usage_record_id
             AND allocation.allocation_type = 'monitor'
            LEFT JOIN employee_non_asset_usage non_asset_usage
              ON non_asset_usage.non_asset_usage_id = allocation.usage_record_id
             AND allocation.allocation_type = 'non_asset'
            WHERE allocation.allocation_id = {allocation_id_int}
            """,
            None,
        )
        if not allocation:
            raise self.api_error("Inventory allocation does not exist.")
        self.scope.assert_org_access(context, allocation.get("orgId"))
        scope = self._permission_scope(context)
        if scope == "own":
            self._assert_employee_scope(context, allocation.get("employeeId"))
        elif scope in {"submitted", "assigned"} and self.db.integer(
            allocation.get("issuedBy"), 0
        ) != self._actor_id(context):
            raise self.forbidden_error("This account can only return inventory it issued.")
        if self.db.text(allocation.get("status")) != "active":
            raise self.conflict_error("This inventory allocation has already been returned.")
        quantity = self.db.integer(allocation.get("quantity"), 0)
        stock_adjusted = self.db.integer(allocation.get("stockAdjusted"), 1) == 1
        source_warehouse_id = self.db.integer(allocation.get("warehouseId"), 0)
        if source_warehouse_id > 0:
            source_warehouse = self._warehouse(source_warehouse_id, include_inactive=True)
            self._assert_warehouse_access(
                context,
                source_warehouse,
                "inventory_operations",
            )
            self._assert_warehouse_access(
                context,
                source_warehouse,
                "warehouse_management",
            )
        # 回收统一入库：登记时未扣减库存的物资在归还/回收时同样进入库存，
        # 缺少库存型号时按品牌型号自动补齐目录。
        target_warehouse = self._resolve_warehouse(
            payload,
            context,
            "inventory_operations",
            preferred_org_id=self._actor_org_id(context),
        )
        target_warehouse_id = self.db.integer((target_warehouse or {}).get("id"), 0)
        if target_warehouse_id <= 0:
            raise self.conflict_error("请选择回收目标仓库。")
        target_warehouse_id_sql = str(target_warehouse_id)
        usage_id = self.db.integer(allocation.get("usageRecordId"), 0)
        usage_table = "employee_monitor_usage" if self.db.text(allocation.get("type")) == "monitor" else "employee_non_asset_usage"
        usage_pk = "monitor_usage_id" if usage_table == "employee_monitor_usage" else "non_asset_usage_id"
        movement_baseline = self.db.scalar(
            "SELECT COALESCE(MAX(movement_log_id), 0) FROM inventory_movement_log;"
        )
        output = self.db.execute(
            f"""
            START TRANSACTION;
            SET @usage_quantity = 0;
            SELECT quantity
            INTO @usage_quantity
            FROM {usage_table}
            WHERE {usage_pk} = {usage_id}
              AND is_active = 1
            FOR UPDATE;
            SET @return_allowed = IF(@usage_quantity >= {quantity}, 1, 0);
            SELECT allocation_id
            FROM inventory_allocation_history
            WHERE allocation_id = {allocation_id_int} AND status = 'active'
            FOR UPDATE;
            {self._recovery_catalog_sql(
                type_id_sql=str(self.db.integer(allocation.get('typeId'), 0)),
                brand_id_sql=str(self.db.integer(allocation.get('usageBrandId'), 0)),
                brand_name=allocation.get('brandName'),
                model_name=allocation.get('modelName'),
                model_id_sql=str(self.db.integer(allocation.get('modelId'), 0)),
                condition='@return_allowed = 1',
            )}
            INSERT INTO inventory_warehouse_stock (warehouse_id, model_id, quantity)
            SELECT {target_warehouse_id}, @recovery_model_id, 0
            FROM DUAL
            WHERE @recovery_model_id > 0
            ON DUPLICATE KEY UPDATE quantity = inventory_warehouse_stock.quantity;
            SELECT quantity
            FROM inventory_warehouse_stock
            WHERE warehouse_id = {target_warehouse_id}
              AND model_id = @recovery_model_id
            FOR UPDATE;
            UPDATE inventory_allocation_history
            SET status = 'returned',
                returned_at = CURRENT_TIMESTAMP,
                returned_by = {self._actor_id(context)},
                warehouse_id = CASE
                  WHEN warehouse_id IS NULL AND {target_warehouse_id_sql} IS NOT NULL
                    THEN {target_warehouse_id_sql}
                  ELSE warehouse_id
                END
            WHERE allocation_id = {allocation_id_int}
              AND status = 'active'
              AND @return_allowed = 1;
            SET @returned_count = ROW_COUNT();
            UPDATE {usage_table}
            SET quantity = quantity - {quantity}
            WHERE {usage_pk} = {usage_id}
              AND quantity > {quantity}
              AND @returned_count = 1;
            DELETE FROM {usage_table}
            WHERE {usage_pk} = {usage_id}
              AND quantity = {quantity}
              AND @returned_count = 1;
            UPDATE it_inventory_model
            SET quantity = quantity + {quantity}
            WHERE model_id = @recovery_model_id
              AND @returned_count = 1
              AND @recovery_model_id > 0;
            UPDATE inventory_warehouse_stock
            SET quantity = quantity + {quantity}
            WHERE warehouse_id = {target_warehouse_id}
              AND model_id = @recovery_model_id
              AND @returned_count = 1
              AND @recovery_model_id > 0;
            INSERT INTO inventory_movement_log (
              movement_direction, type_name, brand_name, model_name, quantity,
              source_label, source_warehouse_id, target_label, target_warehouse_id,
              note, related_employee_no, related_employee_name, trigger_action
            )
            SELECT
              'increase',
              COALESCE(
                (SELECT type_name FROM non_asset_type WHERE non_asset_type_id = (
                   SELECT non_asset_type_id FROM it_inventory_model WHERE model_id = @recovery_model_id)),
                {self.db.quote(self.db.text(allocation.get('typeName')))}
              ),
              COALESCE(
                (SELECT brand_name FROM it_inventory_brand WHERE brand_id = (
                   SELECT brand_id FROM it_inventory_model WHERE model_id = @recovery_model_id)),
                {self.db.quote(self.db.text(allocation.get('brandName')))}
              ),
              COALESCE(
                (SELECT model_name FROM it_inventory_model WHERE model_id = @recovery_model_id),
                {self.db.quote(self.db.text(allocation.get('modelName')))}
              ), {quantity},
              {self.db.quote(self.db.text(allocation.get('employeeName')))}, NULL,
              {self.db.quote(self.db.text((target_warehouse or {}).get('name')))}, {target_warehouse_id_sql},
              {self.db.quote(self.db.text(payload.get('notes')))},
              {self.db.quote(self.db.text(allocation.get('employeeNo')))},
              {self.db.quote(self.db.text(allocation.get('employeeName')))}, 'inventory_return'
            FROM DUAL
            WHERE @returned_count = 1 AND @recovery_model_id > 0;
            {self._conditional_audit_sql(
                'inventory_returned',
                'inventory_allocation',
                self.db.quote(str(allocation_id_int)),
                self.db.text(allocation.get('modelName')),
                'Inventory returned',
                context,
                '@returned_count = 1',
                {'status': 'active'},
                {
                    'status': 'returned',
                    'quantity': quantity,
                    'stockAdjusted': stock_adjusted,
                    'warehouseId': target_warehouse_id if stock_adjusted else None,
                },
            )};
            SELECT @returned_count;
            COMMIT;
            """
        )
        returned_count = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        if returned_count <= 0:
            raise self.conflict_error("This inventory allocation has already been returned.")
        response = {
            "allocationId": str(allocation_id_int),
            "warehouseId": str(target_warehouse_id),
            "status": "returned",
            "recoveryRecords": self._recovery_records_since(movement_baseline, ("inventory_return",)),
        }
        self._store_idempotency_result("inventory.return", idempotency_key, payload, response)
        return response

    def return_usage_inventory(
        self,
        allocation_type: object,
        usage_record_id: object,
        payload: dict,
        context: dict,
        idempotency_key: str = "",
    ) -> dict:
        """Return a legacy usage row that predates allocation history.

        The v2 allocation command registers every issue in
        ``inventory_allocation_history``. Older rows can legitimately exist
        without that record. This compatibility path writes an auditable
        returned allocation and removes the usage row in one transaction,
        without re-deducting stock.
        """
        cached = self._idempotency_result("inventory.usage-return", idempotency_key, payload)
        if cached:
            return cached

        normalized_type = self.db.text(allocation_type)
        if normalized_type not in {"monitor", "non_asset"}:
            raise self.api_error("Inventory usage type must be monitor or non_asset.")
        usage_id = self.db.integer(usage_record_id, 0)
        employee_id = self.db.integer(payload.get("employeeId"), 0)
        if usage_id <= 0 or employee_id <= 0:
            raise self.api_error("Inventory usage return requires an employee and usage record.")

        employee = self._employee(employee_id)
        self.scope.assert_org_access(context, employee.get("orgId"))
        permission_scope = self._permission_scope(context)
        if permission_scope == "own":
            self._assert_employee_scope(context, employee.get("id"))
        elif permission_scope in {"submitted", "assigned", "none"}:
            raise self.forbidden_error(
                "A legacy inventory usage can only be reconciled with own, organization, or all-data permission scope."
            )

        usage_table = "employee_monitor_usage" if normalized_type == "monitor" else "employee_non_asset_usage"
        usage_pk = "monitor_usage_id" if normalized_type == "monitor" else "non_asset_usage_id"
        brand_name_sql = (
            "COALESCE(brand.brand_name, usage_row.display_name, '')"
            if normalized_type == "monitor"
            else "COALESCE(brand.brand_name, usage_row.brand, '')"
        )
        model_name_sql = "COALESCE(model.model_name, usage_row.model, '')"
        usage = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', usage_row.{usage_pk},
              'employeeId', usage_row.employee_id,
              'typeId', COALESCE(usage_row.non_asset_type_id, 0),
              'modelId', COALESCE(usage_row.inventory_model_id, 0),
              'brandId', COALESCE(usage_row.inventory_brand_id, 0),
              'quantity', usage_row.quantity,
              'stockAdjusted', usage_row.stock_adjusted,
              'typeName', COALESCE(type_row.type_name, ''),
              'brandName', {brand_name_sql},
              'modelName', {model_name_sql}
            )
            FROM {usage_table} usage_row
            LEFT JOIN non_asset_type type_row ON type_row.non_asset_type_id = usage_row.non_asset_type_id
            LEFT JOIN it_inventory_model model ON model.model_id = usage_row.inventory_model_id
            LEFT JOIN it_inventory_brand brand ON brand.brand_id = model.brand_id
            WHERE usage_row.{usage_pk} = {usage_id}
              AND usage_row.employee_id = {employee_id}
              AND usage_row.is_active = 1
            """,
            None,
        )
        if not usage:
            raise self.api_error("Inventory usage record does not exist.")

        quantity = self.db.integer(usage.get("quantity"), 0)
        stock_adjusted = self.db.integer(usage.get("stockAdjusted"), 0) == 1
        model_id = self.db.integer(usage.get("modelId"), 0)
        type_id = self.db.integer(usage.get("typeId"), 0)
        if quantity <= 0:
            raise self.conflict_error("Inventory usage has no quantity left to return.")
        # 回收统一入库：未扣减库存的登记物资在回收时同样进库存，
        # 缺少库存型号时按品牌型号自动补齐目录。
        target_warehouse = self._resolve_warehouse(
            payload,
            context,
            "inventory_operations",
            preferred_org_id=self._actor_org_id(context),
        )
        target_warehouse_id = self.db.integer(target_warehouse.get("id"), 0)
        if target_warehouse_id <= 0:
            raise self.conflict_error("请选择回收目标仓库。")
        target_warehouse_id_sql = str(target_warehouse_id)

        existing_allocation_id = self.db.scalar(
            f"""
            SELECT COALESCE(MAX(allocation_id), 0)
            FROM inventory_allocation_history
            WHERE allocation_type = {self.db.quote(normalized_type)}
              AND employee_id = {employee_id}
              AND usage_record_id = {usage_id}
              AND status = 'active';
            """
        )
        if existing_allocation_id > 0:
            return self.return_inventory(existing_allocation_id, payload, context, idempotency_key)

        actor_id = self._actor_id(context)
        actor_sql = str(actor_id) if actor_id > 0 else "NULL"
        type_sql = str(type_id) if type_id > 0 else "NULL"
        model_sql = str(model_id) if model_id > 0 else "NULL"
        note = self.db.text(payload.get("notes"))[:420]
        reconciliation_note = f"Legacy usage reconciled during return. {note}".strip()

        movement_baseline = self.db.scalar(
            "SELECT COALESCE(MAX(movement_log_id), 0) FROM inventory_movement_log;"
        )
        output = self.db.execute(
            f"""
            START TRANSACTION;
            SET @usage_quantity = 0;
            SET @usage_stock_adjusted = 0;
            SET @usage_model_id = 0;
            SET @active_allocation_id = 0;
            SELECT quantity, stock_adjusted, COALESCE(inventory_model_id, 0)
            INTO @usage_quantity, @usage_stock_adjusted, @usage_model_id
            FROM {usage_table}
            WHERE {usage_pk} = {usage_id}
              AND employee_id = {employee_id}
              AND is_active = 1
            FOR UPDATE;
            SELECT allocation_id
            INTO @active_allocation_id
            FROM inventory_allocation_history
            WHERE allocation_type = {self.db.quote(normalized_type)}
              AND employee_id = {employee_id}
              AND usage_record_id = {usage_id}
              AND status = 'active'
            ORDER BY allocation_id DESC
            LIMIT 1
            FOR UPDATE;
            SET @usage_model_ready = IF(
              @usage_stock_adjusted = 0,
              1,
              (
                SELECT COUNT(*)
                FROM it_inventory_model
                WHERE model_id = @usage_model_id
                  AND is_active = 1
              )
            );
            {self._recovery_catalog_sql(
                type_id_sql=str(self.db.integer(usage.get('typeId'), 0)),
                brand_id_sql=str(self.db.integer(usage.get('brandId'), 0)),
                brand_name=usage.get('brandName'),
                model_name=usage.get('modelName'),
                model_id_sql='@usage_model_id',
                condition='@active_allocation_id = 0',
            )}
            SET @usage_model_id = @recovery_model_id;
            SET @return_allowed = IF(
              @usage_quantity > 0
              AND @recovery_model_id > 0
              AND @active_allocation_id = 0,
              1,
              0
            );
            INSERT INTO inventory_warehouse_stock (warehouse_id, model_id, quantity)
            SELECT {target_warehouse_id}, @usage_model_id, 0
            FROM DUAL
            WHERE @recovery_model_id > 0
            ON DUPLICATE KEY UPDATE quantity = inventory_warehouse_stock.quantity;
            SELECT quantity
            FROM inventory_warehouse_stock
            WHERE warehouse_id = {target_warehouse_id}
              AND model_id = @usage_model_id
            FOR UPDATE;
            INSERT INTO inventory_allocation_history (
              allocation_type, employee_id, non_asset_type_id, inventory_model_id,
              warehouse_id, usage_record_id, quantity, stock_adjusted, status, issued_at, returned_at,
              notes, issued_by, returned_by
            )
            SELECT
              {self.db.quote(normalized_type)}, {employee_id}, {type_sql}, {model_sql},
              {target_warehouse_id_sql}, {usage_id}, @usage_quantity, @usage_stock_adjusted, 'returned', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
              {self.db.quote(reconciliation_note)}, {actor_sql}, {actor_sql}
            FROM DUAL
            WHERE @return_allowed = 1;
            SET @allocation_id = IF(@return_allowed = 1, LAST_INSERT_ID(), 0);
            DELETE FROM {usage_table}
            WHERE {usage_pk} = {usage_id}
              AND employee_id = {employee_id}
              AND is_active = 1
              AND quantity = @usage_quantity
              AND @return_allowed = 1;
            UPDATE it_inventory_model
            SET quantity = quantity + @usage_quantity
            WHERE model_id = @usage_model_id
              AND @recovery_model_id > 0
              AND @return_allowed = 1;
            UPDATE inventory_warehouse_stock
            SET quantity = quantity + @usage_quantity
            WHERE warehouse_id = {target_warehouse_id}
              AND model_id = @usage_model_id
              AND @recovery_model_id > 0
              AND @return_allowed = 1;
            INSERT INTO inventory_movement_log (
              movement_direction, type_name, brand_name, model_name, quantity,
              source_label, source_warehouse_id, target_label, target_warehouse_id,
              note, related_employee_no, related_employee_name, trigger_action
            )
            SELECT
              'increase',
              COALESCE(
                (SELECT type_name FROM non_asset_type WHERE non_asset_type_id = (
                   SELECT non_asset_type_id FROM it_inventory_model WHERE model_id = @recovery_model_id)),
                {self.db.quote(self.db.text(usage.get('typeName')))}
              ),
              COALESCE(
                (SELECT brand_name FROM it_inventory_brand WHERE brand_id = (
                   SELECT brand_id FROM it_inventory_model WHERE model_id = @recovery_model_id)),
                {self.db.quote(self.db.text(usage.get('brandName')))}
              ),
              COALESCE(
                (SELECT model_name FROM it_inventory_model WHERE model_id = @recovery_model_id),
                {self.db.quote(self.db.text(usage.get('modelName')))}
              ),
              @usage_quantity, {self.db.quote(self.db.text(employee.get('name')))}, NULL,
              {self.db.quote(self.db.text((target_warehouse or {}).get('name')))}, {target_warehouse_id_sql},
              {self.db.quote(reconciliation_note)}, {self.db.quote(self.db.text(employee.get('employeeNo')))},
              {self.db.quote(self.db.text(employee.get('name')))}, 'inventory_return'
            FROM DUAL
            WHERE @return_allowed = 1 AND @recovery_model_id > 0;
            {self._conditional_audit_sql(
                'inventory_returned',
                'inventory_allocation',
                'CAST(@allocation_id AS CHAR)',
                self.db.text(usage.get('modelName')),
                'Legacy inventory usage reconciled and returned',
                context,
                '@return_allowed = 1',
                {'status': 'active', 'legacyUsage': True},
                {
                    'status': 'returned',
                    'quantity': quantity,
                    'stockAdjusted': stock_adjusted,
                    'warehouseId': target_warehouse_id if stock_adjusted else None,
                },
            )};
            SELECT @return_allowed, @allocation_id;
            COMMIT;
            """
        )
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        result = (lines[-1] if lines else "").split("\t")
        returned = self.db.integer(result[0] if result else 0, 0)
        allocation_id = self.db.integer(result[1] if len(result) > 1 else 0, 0)
        if returned != 1 or allocation_id <= 0:
            raise self.conflict_error("Inventory usage changed before it could be returned. Refresh and try again.")
        response = {
            "allocationId": str(allocation_id),
            "status": "returned",
            "legacyUsageReconciled": True,
            "warehouseId": str(target_warehouse_id),
            "recoveryRecords": self._recovery_records_since(movement_baseline, ("inventory_return",)),
        }
        self._store_idempotency_result("inventory.usage-return", idempotency_key, payload, response)
        return response

    def _scrap_scope(self, context: dict) -> str:
        scopes = context.get("_permissionScopes")
        if isinstance(scopes, dict) and "scrap_management" in scopes:
            return self.db.text(scopes.get("scrap_management")) or "all"
        return self._permission_scope(context)

    def _scrap_reason_fields(self, payload: dict, applies_to: str) -> tuple[str, str]:
        code = self.db.text(payload.get("reasonCode")).strip()
        custom = self.db.text(payload.get("reason")).strip()
        if code:
            row = self.db.json(
                f"""
                SELECT JSON_OBJECT('name', reason_name)
                FROM scrap_reason
                WHERE reason_code = {self.db.quote(code)}
                  AND is_active = 1
                  AND applies_to IN ({self.db.quote(applies_to)}, 'both')
                """,
                None,
            )
            if not row:
                raise self.api_error("报废原因无效，请选择系统提供的报废原因。")
            return code[:64], (custom or self.db.text(row.get("name")))[:255]
        if not custom:
            raise self.api_error("请选择报废原因或填写报废原因说明。")
        return "", custom[:255]

    def _scrap_attachment_ref(self, payload: dict) -> str:
        attachment = self.db.text(payload.get("attachmentRef")).strip()
        if len(attachment) > 500:
            raise self.api_error("附件说明过长，最多 500 个字符。")
        return attachment

    def _scrap_note(self, reason_code: str, reason: str, quantity: object = None) -> str:
        count = self.db.integer(quantity, 0)
        amount = f" {count} 件" if count > 0 else ""
        return f"报废{amount}（原因：{reason}）"

    def list_scrap_reasons(self, _context: dict) -> list[dict]:
        rows = self.db.json(
            """
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'code', reason_code,
              'name', reason_name,
              'appliesTo', applies_to,
              'sortOrder', sort_order
            )), JSON_ARRAY())
            FROM (
              SELECT reason_code, reason_name, applies_to, sort_order
              FROM scrap_reason
              WHERE is_active = 1
              ORDER BY sort_order, reason_code
            ) AS ordered_scrap_reasons
            """,
            [],
        )
        return list(rows or [])

    def scrap_inventory_usage(
        self,
        allocation_type: object,
        usage_record_id: object,
        payload: dict,
        context: dict,
        idempotency_key: str = "",
    ) -> dict:
        """Scrap an issued IT supply without returning it to any warehouse.

        The usage row is closed in place (never deleted) and the referenced
        allocation becomes ``scrapped``. Stock is intentionally untouched:
        quantities that were deducted when the item was issued are not added
        back, and items registered without deduction never increase stock.
        """
        cached = self._idempotency_result("inventory.scrap", idempotency_key, payload)
        if cached:
            return cached

        normalized_type = self.db.text(allocation_type)
        if normalized_type not in {"monitor", "non_asset"}:
            raise self.api_error("Inventory usage type must be monitor or non_asset.")
        usage_id = self.db.integer(usage_record_id, 0)
        if usage_id <= 0:
            raise self.api_error("Inventory scrap requires a usage record.")

        usage_table = "employee_monitor_usage" if normalized_type == "monitor" else "employee_non_asset_usage"
        usage_pk = "monitor_usage_id" if normalized_type == "monitor" else "non_asset_usage_id"
        brand_name_sql = (
            "COALESCE(brand.brand_name, usage_row.display_name, '')"
            if normalized_type == "monitor"
            else "COALESCE(brand.brand_name, usage_row.brand, '')"
        )
        usage = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', usage_row.{usage_pk},
              'employeeId', usage_row.employee_id,
              'employeeNo', employee.employee_no,
              'employeeName', employee.employee_name,
              'orgId', COALESCE(employee.org_unit_id, 0),
              'typeId', COALESCE(usage_row.non_asset_type_id, 0),
              'brandId', COALESCE(usage_row.inventory_brand_id, 0),
              'modelId', COALESCE(usage_row.inventory_model_id, 0),
              'quantity', usage_row.quantity,
              'stockAdjusted', usage_row.stock_adjusted,
              'typeName', COALESCE(type_row.type_name, ''),
              'brandName', {brand_name_sql},
              'modelName', COALESCE(model.model_name, usage_row.model, '')
            )
            FROM {usage_table} usage_row
            JOIN employee ON employee.employee_id = usage_row.employee_id
            LEFT JOIN non_asset_type type_row
              ON type_row.non_asset_type_id = usage_row.non_asset_type_id
            LEFT JOIN it_inventory_model model
              ON model.model_id = usage_row.inventory_model_id
            LEFT JOIN it_inventory_brand brand
              ON brand.brand_id = model.brand_id
            WHERE usage_row.{usage_pk} = {usage_id}
              AND usage_row.is_active = 1
            """,
            None,
        )
        if not usage:
            raise self.api_error("Inventory usage record does not exist or is already closed.")

        employee_id = self.db.integer(usage.get("employeeId"), 0)
        if employee_id <= 0:
            raise self.api_error("Inventory usage record has no holder to scrap.")
        self.scope.assert_org_access(context, usage.get("orgId"))
        permission_scope = self._scrap_scope(context)
        if permission_scope == "own":
            self._assert_employee_scope(context, employee_id)
        elif permission_scope in {"submitted", "assigned", "none"}:
            raise self.forbidden_error(
                "物资报废需要本人、本组织或全部数据范围，当前账号数据范围不允许报废。"
            )

        quantity = self.db.integer(usage.get("quantity"), 0)
        stock_adjusted = parse_bool(usage.get("stockAdjusted"))
        model_id = self.db.integer(usage.get("modelId"), 0)
        if quantity <= 0:
            raise self.conflict_error("该物资记录数量为 0，无法报废。")
        if stock_adjusted and model_id <= 0:
            raise self.conflict_error("该物资已扣减库存但没有关联库存型号，请先补齐库存型号再报废。")

        reason_code, reason_text = self._scrap_reason_fields(payload, "inventory")
        notes = self.db.text(payload.get("notes"))[:500]
        attachment_ref = self._scrap_attachment_ref(payload)
        scrap_note = self._scrap_note(reason_code, reason_text, quantity)
        recorded_note = f"{notes} {scrap_note}".strip() if notes else scrap_note

        actor_id = self._actor_id(context)
        actor_sql = str(actor_id) if actor_id > 0 else "NULL"
        output = self.db.execute(
            f"""
            START TRANSACTION;
            SET @usage_quantity = 0;
            SET @usage_stock_adjusted = 0;
            SET @usage_model_id = 0;
            SET @scrap_allowed = 0;
            SET @active_allocation_id = 0;
            SELECT quantity, stock_adjusted, COALESCE(inventory_model_id, 0)
            INTO @usage_quantity, @usage_stock_adjusted, @usage_model_id
            FROM {usage_table}
            WHERE {usage_pk} = {usage_id}
              AND employee_id = {employee_id}
              AND is_active = 1
            FOR UPDATE;
            SELECT allocation_id
            INTO @active_allocation_id
            FROM inventory_allocation_history
            WHERE allocation_type = {self.db.quote(normalized_type)}
              AND employee_id = {employee_id}
              AND usage_record_id = {usage_id}
              AND status = 'active'
            ORDER BY allocation_id DESC
            LIMIT 1
            FOR UPDATE;
            SET @scrap_allowed = IF(
              @usage_quantity > 0
              AND (@usage_stock_adjusted = 0 OR @usage_model_id > 0),
              1,
              0
            );
            UPDATE {usage_table}
            SET is_active = 0,
                notes = CONCAT_WS(' ', COALESCE(notes, ''), {self.db.quote(scrap_note)})
            WHERE {usage_pk} = {usage_id}
              AND employee_id = {employee_id}
              AND is_active = 1
              AND @scrap_allowed = 1;
            UPDATE inventory_allocation_history
            SET status = 'scrapped',
                returned_at = CURRENT_TIMESTAMP,
                returned_by = {actor_sql},
                notes = CONCAT_WS(' ', COALESCE(notes, ''), {self.db.quote(scrap_note)})
            WHERE allocation_id = @active_allocation_id
              AND status = 'active'
              AND @scrap_allowed = 1;
            SET @scrap_warehouse_id = (
              SELECT allocation.warehouse_id
              FROM inventory_allocation_history allocation
              WHERE allocation.allocation_id = @active_allocation_id
            );
            SET @scrap_warehouse_name = COALESCE((
              SELECT warehouse.warehouse_name
              FROM inventory_warehouse warehouse
              WHERE warehouse.warehouse_id = @scrap_warehouse_id
            ), '');
            INSERT INTO inventory_scrap_record (
              allocation_type, usage_record_id, allocation_id, employee_id, employee_no,
              employee_name, org_unit_id, non_asset_type_id, type_name, brand_id, brand_name,
              inventory_model_id, model_name, warehouse_id, warehouse_name, quantity,
              stock_adjusted, scrap_reason_code, scrap_reason, scrap_at, operated_by,
              operated_by_name, notes, attachment_ref
            )
            SELECT
              {self.db.quote(normalized_type)},
              {usage_id},
              NULLIF(@active_allocation_id, 0),
              {employee_id},
              {self.db.quote(self.db.text(usage.get('employeeNo')))},
              {self.db.quote(self.db.text(usage.get('employeeName')))},
              NULLIF({self.db.integer(usage.get('orgId'), 0)}, 0),
              NULLIF({self.db.integer(usage.get('typeId'), 0)}, 0),
              {self.db.quote(self.db.text(usage.get('typeName')))},
              NULLIF({self.db.integer(usage.get('brandId'), 0)}, 0),
              {self.db.quote(self.db.text(usage.get('brandName')))},
              NULLIF(@usage_model_id, 0),
              {self.db.quote(self.db.text(usage.get('modelName')))},
              @scrap_warehouse_id,
              @scrap_warehouse_name,
              @usage_quantity,
              @usage_stock_adjusted,
              {self.db.quote(reason_code)},
              {self.db.quote(reason_text)},
              CURRENT_TIMESTAMP,
              {actor_sql},
              {self.db.quote(self._actor_name(context))},
              {self.db.quote(notes)},
              {self.db.quote(attachment_ref)}
            FROM DUAL
            WHERE @scrap_allowed = 1;
            SET @scrap_id = IF(@scrap_allowed = 1, LAST_INSERT_ID(), 0);
            {self._conditional_audit_sql(
                'inventory_scrapped',
                'inventory_allocation',
                'CAST(@scrap_id AS CHAR)',
                self.db.text(usage.get('modelName')),
                f"Inventory scrapped without warehouse return: {reason_text}",
                context,
                '@scrap_allowed = 1',
                {
                    'status': 'active',
                    'usageRecordId': usage_id,
                    'quantity': quantity,
                    'stockAdjusted': stock_adjusted,
                },
                {
                    'status': 'scrapped',
                    'usageRecordId': usage_id,
                    'stockRestored': False,
                    'reason': reason_text,
                },
            )};
            SELECT @scrap_allowed, @scrap_id;
            COMMIT;
            """
        )
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        result = (lines[-1] if lines else "").split("\t")
        scrapped = self.db.integer(result[0] if result else 0, 0)
        scrap_id = self.db.integer(result[1] if len(result) > 1 else 0, 0)
        if scrapped != 1 or scrap_id <= 0:
            raise self.conflict_error("物资状态已变化，报废未执行，请刷新后重试。")
        response = {
            "scrapId": str(scrap_id),
            "kind": "inventory",
            "allocationType": normalized_type,
            "usageRecordId": str(usage_id),
            "status": "scrapped",
            "quantity": quantity,
            "stockAdjusted": stock_adjusted,
            "stockRestored": False,
        }
        self._store_idempotency_result("inventory.scrap", idempotency_key, payload, response)
        return response

    def scrap_computer(
        self,
        computer_id: object,
        payload: dict,
        context: dict,
        idempotency_key: str = "",
    ) -> dict:
        """Retire a computer asset and soft archive it with a scrap record.

        The asset row is never deleted, no stock is added back, and an active
        assignment is closed so the device stops appearing as an in-use device.
        """
        cached = self._idempotency_result("computer.scrap", idempotency_key, payload)
        if cached:
            return cached

        computer_id_int = self.db.integer(computer_id, 0)
        if computer_id_int <= 0:
            raise self.api_error("Computer identifier is required.")
        computer = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(asset.computer_id AS CHAR),
              'deviceName', asset.device_name,
              'orgId', COALESCE(asset.org_unit_id, 0),
              'deviceType', asset.device_type,
              'brand', COALESCE(asset.brand, ''),
              'model', COALESCE(asset.model, ''),
              'cpu', COALESCE(asset.cpu, ''),
              'memory', COALESCE(asset.memory, ''),
              'storage', COALESCE(asset.storage, ''),
              'gpu', COALESCE(asset.gpu, ''),
              'fixedAssetCode', COALESCE(asset.fixed_asset_code, ''),
              'snSt', COALESCE(asset.sn_st, ''),
              'purchaseDate', COALESCE(CAST(asset.purchase_date AS CHAR), ''),
              'registeredDate', COALESCE(CAST(asset.registered_date AS CHAR), ''),
              'status', asset.it_asset_status,
              'isArchived', asset.is_archived,
              'userId', COALESCE(CAST(current_assignment.employee_id AS CHAR), '')
            )
            FROM computer_asset asset
            LEFT JOIN computer_assignment current_assignment
              ON current_assignment.computer_id = asset.computer_id
             AND current_assignment.returned_at IS NULL
             AND current_assignment.assignment_status = 'active'
            WHERE asset.computer_id = {computer_id_int}
              AND asset.is_active = 1
            """,
            None,
        )
        if not computer:
            raise self.api_error("Computer does not exist.")
        self.scope.assert_computer_access(context, computer_id_int)
        self._assert_computer_record_scope(context, computer, "it_assets")
        if parse_bool(computer.get("isArchived")):
            raise self.conflict_error("该办公终端已报废归档，不能重复报废。")

        permission_scope = self._scrap_scope(context)
        if permission_scope == "own":
            actor_employee_id = self._actor_employee_id(context)
            holder_id = self.db.integer(computer.get("userId"), 0)
            if actor_employee_id <= 0 or holder_id != actor_employee_id:
                raise self.forbidden_error("只有当前使用人可以报废自己名下的办公终端。")
        elif permission_scope in {"submitted", "assigned", "none"}:
            raise self.forbidden_error(
                "办公终端报废需要本人、本组织或全部数据范围，当前账号数据范围不允许报废。"
            )

        previous_status = self.db.text(computer.get("status"))
        if "retired" not in COMPUTER_STATUS_TRANSITIONS.get(previous_status, set()):
            raise self.conflict_error("当前资产状态不允许报废。")

        reason_code, reason_text = self._scrap_reason_fields(payload, "asset")
        notes = self.db.text(payload.get("notes"))[:500]
        attachment_ref = self._scrap_attachment_ref(payload)
        scrap_note = self._scrap_note(reason_code, reason_text)
        actor_id = self._actor_id(context)
        actor_sql = str(actor_id) if actor_id > 0 else "NULL"

        output = self.db.execute(
            f"""
            START TRANSACTION;
            SET @previous_status = '';
            SET @scrap_allowed = 0;
            SET @returned_count = 0;
            SET @holder_employee_id = 0;
            SET @holder_employee_no = '';
            SET @holder_employee_name = '';
            SELECT it_asset_status
            INTO @previous_status
            FROM computer_asset
            WHERE computer_id = {computer_id_int}
              AND is_active = 1
              AND is_archived = 0
            FOR UPDATE;
            SET @scrap_allowed = IF(
              @previous_status IS NULL OR @previous_status = '',
              0,
              1
            );
            SELECT assignment.employee_id, employee.employee_no, employee.employee_name
            INTO @holder_employee_id, @holder_employee_no, @holder_employee_name
            FROM computer_assignment assignment
            JOIN employee ON employee.employee_id = assignment.employee_id
            WHERE assignment.computer_id = {computer_id_int}
              AND assignment.returned_at IS NULL
              AND assignment.assignment_status = 'active'
            ORDER BY assignment.assignment_id DESC
            LIMIT 1
            FOR UPDATE;
            UPDATE computer_assignment
            SET returned_at = CURRENT_TIMESTAMP,
                assignment_status = 'returned',
                notes = CONCAT_WS(' ', COALESCE(notes, ''), {self.db.quote(scrap_note)})
            WHERE computer_id = {computer_id_int}
              AND returned_at IS NULL
              AND assignment_status = 'active'
              AND @scrap_allowed = 1;
            SET @returned_count = ROW_COUNT();
            INSERT INTO computer_assignment_history (
              computer_id, device_name, employee_id, employee_no, employee_name,
              assigned_at, returned_at, assignment_status, notes, returned_by
            )
            SELECT
              assignment.computer_id, asset.device_name, assignment.employee_id,
              employee.employee_no, employee.employee_name,
              assignment.assigned_at, CURRENT_TIMESTAMP, 'returned', assignment.notes,
              {actor_sql}
            FROM computer_assignment assignment
            JOIN computer_asset asset ON asset.computer_id = assignment.computer_id
            JOIN employee ON employee.employee_id = assignment.employee_id
            WHERE assignment.computer_id = {computer_id_int}
              AND assignment.returned_at IS NOT NULL
              AND @returned_count = 1
            ORDER BY assignment.assignment_id DESC
            LIMIT 1
            ON DUPLICATE KEY UPDATE
              returned_at = VALUES(returned_at),
              assignment_status = VALUES(assignment_status),
              notes = VALUES(notes),
              returned_by = VALUES(returned_by);
            UPDATE computer_asset
            SET it_asset_status = 'retired',
                is_archived = 1,
                archived_at = CURRENT_TIMESTAMP,
                archived_by = {actor_sql}
            WHERE computer_id = {computer_id_int}
              AND @scrap_allowed = 1;
            INSERT INTO asset_status_history (
              computer_id, previous_status, next_status, reason, changed_by
            )
            SELECT
              {computer_id_int}, @previous_status, 'retired', 'Computer scrap', {actor_sql}
            FROM DUAL
            WHERE @scrap_allowed = 1;
            INSERT INTO asset_scrap_record (
              computer_id, device_name, org_unit_id, device_type, brand, model,
              cpu, memory, storage, gpu, fixed_asset_code, sn_st, purchase_date,
              registered_date, previous_status, employee_id, employee_no, employee_name,
              scrap_reason_code, scrap_reason, scrap_at, operated_by, operated_by_name,
              notes, attachment_ref
            )
            SELECT
              asset.computer_id,
              asset.device_name,
              asset.org_unit_id,
              asset.device_type,
              COALESCE(asset.brand, ''),
              COALESCE(asset.model, ''),
              COALESCE(asset.cpu, ''),
              COALESCE(asset.memory, ''),
              COALESCE(asset.storage, ''),
              COALESCE(asset.gpu, ''),
              COALESCE(asset.fixed_asset_code, ''),
              COALESCE(asset.sn_st, ''),
              asset.purchase_date,
              asset.registered_date,
              @previous_status,
              NULLIF(COALESCE(@holder_employee_id, 0), 0),
              COALESCE(@holder_employee_no, ''),
              COALESCE(@holder_employee_name, ''),
              {self.db.quote(reason_code)},
              {self.db.quote(reason_text)},
              CURRENT_TIMESTAMP,
              {actor_sql},
              {self.db.quote(self._actor_name(context))},
              {self.db.quote(notes)},
              {self.db.quote(attachment_ref)}
            FROM computer_asset asset
            WHERE asset.computer_id = {computer_id_int}
              AND @scrap_allowed = 1;
            SET @scrap_id = IF(@scrap_allowed = 1, LAST_INSERT_ID(), 0);
            {self._conditional_audit_sql(
                'computer_scrapped',
                'computer',
                str(computer_id_int),
                self.db.text(computer.get('deviceName')),
                f"Computer scrapped and archived: {reason_text}",
                context,
                '@scrap_allowed = 1',
                {
                    'status': previous_status,
                    'archived': False,
                    'userId': self.db.text(computer.get('userId')),
                },
                {
                    'status': 'retired',
                    'archived': True,
                    'stockRestored': False,
                    'reason': reason_text,
                },
            )};
            SELECT @scrap_allowed, @scrap_id, @returned_count;
            COMMIT;
            """
        )
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        result = (lines[-1] if lines else "").split("\t")
        scrapped = self.db.integer(result[0] if result else 0, 0)
        scrap_id = self.db.integer(result[1] if len(result) > 1 else 0, 0)
        returned_count = self.db.integer(result[2] if len(result) > 2 else 0, 0)
        if scrapped != 1 or scrap_id <= 0:
            raise self.conflict_error("办公终端状态已变化，报废未执行，请刷新后重试。")
        response = {
            "scrapId": str(scrap_id),
            "kind": "asset",
            "computerId": str(computer_id_int),
            "deviceName": self.db.text(computer.get("deviceName")),
            "status": "retired",
            "archived": True,
            "holderAssignmentClosed": returned_count == 1,
            "stockRestored": False,
        }
        self._store_idempotency_result("computer.scrap", idempotency_key, payload, response)
        return response

    def _inventory_scrap_rows(self, limit: int) -> list[dict]:
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', CAST(scrap_id AS CHAR),
              'kind', 'inventory',
              'allocationType', allocation_type,
              'usageRecordId', COALESCE(CAST(usage_record_id AS CHAR), ''),
              'allocationId', COALESCE(CAST(allocation_id AS CHAR), ''),
              'employeeId', COALESCE(CAST(employee_id AS CHAR), ''),
              'employeeNo', employee_no,
              'employeeName', employee_name,
              'orgId', COALESCE(CAST(org_unit_id AS CHAR), ''),
              'typeName', type_name,
              'brandName', brand_name,
              'modelName', model_name,
              'warehouseName', warehouse_name,
              'quantity', quantity,
              'stockAdjusted', stock_adjusted,
              'stockRestored', 0,
              'reasonCode', scrap_reason_code,
              'reason', scrap_reason,
              'scrapAt', DATE_FORMAT(scrap_at, '%Y-%m-%d %H:%i:%s'),
              'operatedById', COALESCE(CAST(operated_by AS CHAR), ''),
              'operatedByName', operated_by_name,
              'notes', notes,
              'attachmentRef', attachment_ref
            )), JSON_ARRAY())
            FROM (
              SELECT scrap_id, allocation_type, usage_record_id, allocation_id, employee_id,
                     employee_no, employee_name, org_unit_id, type_name, brand_name, model_name,
                     warehouse_name, quantity, stock_adjusted, scrap_reason_code, scrap_reason,
                     scrap_at, operated_by, operated_by_name, notes, attachment_ref
              FROM inventory_scrap_record
              ORDER BY scrap_at DESC, scrap_id DESC
              LIMIT {limit}
            ) AS ordered_inventory_scrap
            """,
            [],
        )
        return [dict(row) for row in (rows or [])]

    def _asset_scrap_rows(self, limit: int) -> list[dict]:
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', CAST(scrap_id AS CHAR),
              'kind', 'asset',
              'computerId', COALESCE(CAST(computer_id AS CHAR), ''),
              'deviceName', device_name,
              'deviceType', device_type,
              'brandName', brand,
              'modelName', model,
              'cpu', cpu,
              'memory', memory,
              'storage', storage,
              'gpu', gpu,
              'fixedAssetCode', fixed_asset_code,
              'snSt', sn_st,
              'purchaseDate', COALESCE(CAST(purchase_date AS CHAR), ''),
              'registeredDate', COALESCE(CAST(registered_date AS CHAR), ''),
              'previousStatus', previous_status,
              'employeeId', COALESCE(CAST(employee_id AS CHAR), ''),
              'employeeNo', employee_no,
              'employeeName', employee_name,
              'orgId', COALESCE(CAST(org_unit_id AS CHAR), ''),
              'quantity', 1,
              'stockAdjusted', 0,
              'stockRestored', 0,
              'reasonCode', scrap_reason_code,
              'reason', scrap_reason,
              'scrapAt', DATE_FORMAT(scrap_at, '%Y-%m-%d %H:%i:%s'),
              'operatedById', COALESCE(CAST(operated_by AS CHAR), ''),
              'operatedByName', operated_by_name,
              'notes', notes,
              'attachmentRef', attachment_ref
            )), JSON_ARRAY())
            FROM (
              SELECT scrap_id, computer_id, device_name, device_type, brand, model, cpu,
                     memory, storage, gpu, fixed_asset_code, sn_st, purchase_date,
                     registered_date, previous_status, employee_id, employee_no,
                     employee_name, org_unit_id, scrap_reason_code, scrap_reason,
                     scrap_at, operated_by, operated_by_name, notes, attachment_ref
              FROM asset_scrap_record
              ORDER BY scrap_at DESC, scrap_id DESC
              LIMIT {limit}
            ) AS ordered_asset_scrap
            """,
            [],
        )
        return [dict(row) for row in (rows or [])]

    def _scope_scrap_rows(self, rows: list[dict], context: dict) -> list[dict]:
        allowed = self.scope.permitted_org_ids(context)
        if allowed is not None:
            rows = [row for row in rows if self.db.integer(row.get("orgId"), 0) in allowed]
        scope = self._scrap_scope(context)
        if scope == "own":
            actor_employee_id = self._actor_employee_id(context)
            rows = [
                row
                for row in rows
                if actor_employee_id > 0
                and self.db.integer(row.get("employeeId"), 0) == actor_employee_id
            ]
        elif scope in {"submitted", "assigned"}:
            actor_id = self._actor_id(context)
            rows = [
                row
                for row in rows
                if actor_id > 0 and self.db.integer(row.get("operatedById"), 0) == actor_id
            ]
        return rows

    def list_scrap_records(self, context: dict, kind: str = "", limit: object = 500) -> list[dict]:
        requested = self.db.integer(limit, 500)
        row_limit = min(max(requested, 1), 2000)
        normalized_kind = self.db.text(kind)
        if normalized_kind not in {"", "inventory", "asset"}:
            raise self.api_error("报废记录类型必须为 inventory 或 asset。")
        records: list[dict] = []
        if normalized_kind in {"", "inventory"}:
            records.extend(self._inventory_scrap_rows(row_limit))
        if normalized_kind in {"", "asset"}:
            records.extend(self._asset_scrap_rows(row_limit))
        records = self._scope_scrap_rows(records, context)
        records.sort(
            key=lambda item: (
                self.db.text(item.get("scrapAt")),
                self.db.text(item.get("kind")),
                self.db.integer(item.get("id"), 0),
            ),
            reverse=True,
        )
        return records[:row_limit]

    def get_scrap_record(self, record_id: object, context: dict) -> dict:
        raw = self.db.text(record_id).strip()
        kind, _, identifier = raw.partition(":")
        kind = kind.strip().lower()
        identifier = identifier.strip()
        if kind not in {"inventory", "asset"} or not identifier.isdigit():
            raise self.api_error("报废记录标识无效，请使用 inventory:<id> 或 asset:<id>。")
        rows = self._inventory_scrap_rows(2000) if kind == "inventory" else self._asset_scrap_rows(2000)
        for row in rows:
            if self.db.text(row.get("id")) == identifier:
                visible = self._scope_scrap_rows([row], context)
                if not visible:
                    raise self.forbidden_error("当前账号无权访问该报废记录。")
                return row
        raise self.api_error("报废记录不存在。")

    def _recovery_catalog_sql(
        self,
        *,
        type_id_sql: str,
        brand_id_sql: str,
        brand_name: object,
        model_name: object,
        condition: str,
        model_id_sql: str = "0",
    ) -> str:
        """Resolve (and create when missing) the catalog model used by a recovery.

        Every recovered item must end up with a stock row, even when it was
        registered without stock deduction or has no brand/model in the
        catalog yet. The statement block sets ``@recovery_model_id``,
        ``@recovery_brand_id``, ``@recovery_type_id`` and
        ``@recovery_model_created`` for the following stock statements.
        """
        brand_value = self.db.quote(self.db.text(brand_name).strip() or "未填写品牌")
        model_value = self.db.quote(self.db.text(model_name).strip() or "未填写型号")
        return f"""
            SET @recovery_model_id = {model_id_sql};
            SET @recovery_type_id = {type_id_sql};
            SET @recovery_brand_id = {brand_id_sql};
            SET @recovery_ready = IF(
              @recovery_model_id > 0,
              1,
              IF(@recovery_type_id > 0, 1, 0)
            );
            SET @recovery_brand_id = IF(
              @recovery_model_id > 0,
              (SELECT brand_id FROM it_inventory_model WHERE model_id = @recovery_model_id),
              @recovery_brand_id
            );
            SET @recovery_brand_id = IFNULL(@recovery_brand_id, 0);
            SET @recovery_brand_id = IF(
              @recovery_brand_id > 0 OR @recovery_ready = 0,
              @recovery_brand_id,
              (SELECT brand_id FROM it_inventory_brand
               WHERE non_asset_type_id = @recovery_type_id
                 AND brand_name = {brand_value}
               ORDER BY is_active DESC, brand_id
               LIMIT 1)
            );
            SET @recovery_brand_id = IFNULL(@recovery_brand_id, 0);
            INSERT IGNORE INTO it_inventory_brand (non_asset_type_id, brand_name, is_active)
            SELECT @recovery_type_id, {brand_value}, 1
            FROM DUAL
            WHERE @recovery_ready = 1
              AND @recovery_brand_id = 0
              AND {condition};
            SET @recovery_brand_id = IF(
              @recovery_brand_id = 0 AND @recovery_ready = 1,
              (SELECT brand_id FROM it_inventory_brand
               WHERE non_asset_type_id = @recovery_type_id
                 AND brand_name = {brand_value}
               ORDER BY brand_id
               LIMIT 1),
              @recovery_brand_id
            );
            SET @recovery_brand_id = IFNULL(@recovery_brand_id, 0);
            SET @recovery_model_id = IF(
              @recovery_model_id > 0 OR @recovery_ready = 0,
              @recovery_model_id,
              (SELECT model_id FROM it_inventory_model
               WHERE brand_id = @recovery_brand_id
                 AND model_name = {model_value}
                 AND is_active = 1
               ORDER BY model_id
               LIMIT 1)
            );
            SET @recovery_model_created = IF(
              @recovery_model_id IS NULL OR @recovery_model_id = 0,
              1,
              0
            );
            INSERT IGNORE INTO it_inventory_model (
              non_asset_type_id, brand_id, model_name, batch_key, quantity, inbound_date, is_active
            )
            SELECT @recovery_type_id, @recovery_brand_id, {model_value}, '', 0, CURRENT_DATE, 1
            FROM DUAL
            WHERE @recovery_ready = 1
              AND @recovery_brand_id > 0
              AND @recovery_model_created = 1
              AND {condition};
            SET @recovery_model_id = IF(
              @recovery_model_created = 1 AND @recovery_brand_id > 0,
              (SELECT model_id FROM it_inventory_model
               WHERE brand_id = @recovery_brand_id
                 AND model_name = {model_value}
               ORDER BY model_id
               LIMIT 1),
              @recovery_model_id
            );
            SET @recovery_model_id = IFNULL(@recovery_model_id, 0);
            SET @recovery_model_created = IF(
              @recovery_model_created = 1 AND @recovery_model_id > 0,
              1,
              0
            );
        """

    def list_allocations(self, context: dict, active_only: bool = True) -> list[dict]:
        where = "WHERE allocation.status = 'active'" if active_only else ""
        rows = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(allocation.allocation_id AS CHAR),
                  'allocationType', allocation.allocation_type,
                  'employeeId', CAST(allocation.employee_id AS CHAR),
                  'employeeName', employee.employee_name,
                  'orgId', COALESCE(CAST(employee.org_unit_id AS CHAR), ''),
                  'issuedBy', COALESCE(CAST(allocation.issued_by AS CHAR), ''),
                  'modelId', COALESCE(CAST(allocation.inventory_model_id AS CHAR), ''),
                  'warehouseId', COALESCE(CAST(allocation.warehouse_id AS CHAR), ''),
                  'warehouseName', COALESCE(warehouse.warehouse_name, ''),
                  'usageRecordId', COALESCE(CAST(allocation.usage_record_id AS CHAR), ''),
                  'brandName', COALESCE(brand.brand_name, monitor_usage.display_name, non_asset_usage.brand, ''),
                  'modelName', COALESCE(model.model_name, monitor_usage.model, non_asset_usage.model, ''),
                  'quantity', allocation.quantity,
                  'stockAdjusted', allocation.stock_adjusted,
                  'status', allocation.status,
                  'issuedAt', CAST(allocation.issued_at AS CHAR)
                )), JSON_ARRAY())
                FROM inventory_allocation_history allocation
                JOIN employee ON employee.employee_id = allocation.employee_id
                LEFT JOIN it_inventory_model model ON model.model_id = allocation.inventory_model_id
                LEFT JOIN it_inventory_brand brand ON brand.brand_id = model.brand_id
                LEFT JOIN inventory_warehouse warehouse ON warehouse.warehouse_id = allocation.warehouse_id
                LEFT JOIN employee_monitor_usage monitor_usage
                  ON monitor_usage.monitor_usage_id = allocation.usage_record_id
                 AND allocation.allocation_type = 'monitor'
                LEFT JOIN employee_non_asset_usage non_asset_usage
                  ON non_asset_usage.non_asset_usage_id = allocation.usage_record_id
                 AND allocation.allocation_type = 'non_asset'
                {where}
                """,
                [],
            )
            or []
        )
        allowed = self.scope.permitted_org_ids(context)
        if allowed is not None:
            rows = [row for row in rows if self.db.integer(row.get("orgId"), 0) in allowed]
        visible_warehouse_ids = {
            self.db.text(item.get("id"))
            for item in self.list_warehouses(context)
            if self.db.text(item.get("id"))
        }
        rows = [
            row
            for row in rows
            if not self.db.text(row.get("warehouseId"))
            or self.db.text(row.get("warehouseId")) in visible_warehouse_ids
        ]
        scope = self._permission_scope(context)
        if scope == "own":
            actor_employee_id = self._actor_employee_id(context)
            return [
                row
                for row in rows
                if actor_employee_id > 0
                and self.db.integer(row.get("employeeId"), 0) == actor_employee_id
            ]
        if scope in {"submitted", "assigned"}:
            return [
                row
                for row in rows
                if self.db.integer(row.get("issuedBy"), 0) == self._actor_id(context)
            ]
        return rows

    def offboarding_preview(self, employee_id: object, context: dict) -> dict:
        employee_id_int = self.db.integer(employee_id, 0)
        if employee_id_int <= 0:
            raise self.api_error("人员不存在。")
        permission_scope = self._permission_scope(context, "employees")
        if permission_scope not in {"all", "organization"}:
            raise self.forbidden_error("办理离职需要使用人员的全部数据或所属部门数据权限。")
        if self._actor_employee_id(context) == employee_id_int:
            raise self.conflict_error("当前登录账号不能办理自身绑定人员离职。")

        employee = self._offboarding_employee(employee_id_int)
        if self.db.text(employee.get("status")) == "left":
            raise self.conflict_error("该人员已经办理离职。")
        self.scope.assert_org_access(context, employee.get("orgId"))
        return {
            "employee": employee,
            "items": self._offboarding_items(employee_id_int),
        }

    def _sql_id_list(self, values: list[int]) -> str:
        ids = [str(value) for value in sorted({value for value in values if value > 0})]
        return ", ".join(ids) if ids else "0"

    def _nullable_id_sql(self, value: object) -> str:
        value_int = self.db.integer(value, 0)
        return str(value_int) if value_int > 0 else "NULL"

    def _offboard_note(self, prefix: str, note: str = "") -> str:
        note = self.db.text(note).strip()
        return (f"{prefix}：{note}" if note else prefix)[:500]

    def _org_path(self, org_id: object) -> str:
        org_id_text = self.db.text(org_id)
        if not org_id_text:
            return ""
        rows = self.db.json(
            """
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', CAST(org_unit_id AS CHAR),
              'parentId', COALESCE(CAST(parent_org_unit_id AS CHAR), ''),
              'name', org_name
            )), JSON_ARRAY())
            FROM org_unit
            WHERE is_active = 1
            """,
            [],
        )
        by_id = {self.db.text(row.get("id")): row for row in rows or []}
        current = by_id.get(org_id_text)
        visited: set[str] = set()
        path: list[str] = []
        while current and self.db.text(current.get("id")) not in visited:
            current_id = self.db.text(current.get("id"))
            visited.add(current_id)
            path.append(self.db.text(current.get("name")))
            current = by_id.get(self.db.text(current.get("parentId")))
        return " / ".join(part for part in reversed(path) if part)

    def _offboarding_employee(self, employee_id: int) -> dict:
        employee = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(employee.employee_id AS CHAR),
              'employeeNo', employee.employee_no,
              'name', employee.employee_name,
              'orgId', COALESCE(CAST(employee.org_unit_id AS CHAR), ''),
              'department', COALESCE(employee.department, ''),
              'position', COALESCE(employee.position_name, ''),
              'email', COALESCE(employee.email, ''),
              'mobile', COALESCE(employee.mobile, ''),
              'status', employee.employment_status
            )
            FROM employee
            WHERE employee.employee_id = {employee_id}
              AND employee.is_active = 1
            """,
            None,
        )
        if not employee:
            raise self.api_error("人员不存在。")
        result = dict(employee)
        result["orgPath"] = self._org_path(result.get("orgId"))
        return result

    def _offboarding_items(self, employee_id: int) -> list[dict]:
        computers = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'itemType', 'computer',
              'id', CAST(computer_id AS CHAR),
              'key', CONCAT('computer:', computer_id),
              'label', device_name,
              'detail', detail,
              'quantity', 1,
              'status', it_asset_status,
              'assignmentId', CAST(assignment_id AS CHAR)
            )), JSON_ARRAY())
            FROM (
              SELECT
                asset.computer_id,
                asset.device_name,
                TRIM(CONCAT_WS(' ', asset.brand, asset.model)) AS detail,
                asset.it_asset_status,
                assignment.assignment_id
              FROM computer_assignment assignment
              JOIN computer_asset asset ON asset.computer_id = assignment.computer_id
              WHERE assignment.employee_id = {employee_id}
                AND assignment.returned_at IS NULL
                AND assignment.assignment_status = 'active'
                AND asset.is_active = 1
              ORDER BY asset.device_name, asset.computer_id
            ) active_computers
            """,
            [],
        )
        monitors = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'itemType', 'monitor',
              'id', CAST(monitor_usage_id AS CHAR),
              'key', CONCAT('monitor:', monitor_usage_id),
              'label', COALESCE(type_name, '显示屏'),
              'detail', detail,
              'quantity', quantity,
              'typeId', COALESCE(CAST(non_asset_type_id AS CHAR), ''),
              'typeName', COALESCE(type_name, '显示屏'),
              'brandId', COALESCE(CAST(inventory_brand_id AS CHAR), ''),
              'modelId', COALESCE(CAST(inventory_model_id AS CHAR), ''),
              'brand', display_name,
              'model', model,
              'stockAdjusted', stock_adjusted
            )), JSON_ARRAY())
            FROM (
              SELECT
                usage_row.monitor_usage_id,
                usage_row.non_asset_type_id,
                usage_row.inventory_brand_id,
                usage_row.inventory_model_id,
                COALESCE(type_row.type_name, '显示屏') AS type_name,
                usage_row.display_name,
                usage_row.model,
                TRIM(CONCAT_WS(' ', usage_row.display_name, usage_row.model)) AS detail,
                usage_row.quantity,
                usage_row.stock_adjusted
              FROM employee_monitor_usage usage_row
              LEFT JOIN non_asset_type type_row
                ON type_row.non_asset_type_id = usage_row.non_asset_type_id
              WHERE usage_row.employee_id = {employee_id}
                AND usage_row.is_active = 1
              ORDER BY usage_row.monitor_usage_id
            ) active_monitors
            """,
            [],
        )
        non_assets = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'itemType', 'non_asset',
              'id', CAST(non_asset_usage_id AS CHAR),
              'key', CONCAT('non_asset:', non_asset_usage_id),
              'label', type_name,
              'detail', detail,
              'quantity', quantity,
              'typeId', CAST(non_asset_type_id AS CHAR),
              'typeName', type_name,
              'brandId', COALESCE(CAST(inventory_brand_id AS CHAR), ''),
              'modelId', COALESCE(CAST(inventory_model_id AS CHAR), ''),
              'brand', brand,
              'model', model,
              'stockAdjusted', stock_adjusted
            )), JSON_ARRAY())
            FROM (
              SELECT
                usage_row.non_asset_usage_id,
                usage_row.non_asset_type_id,
                usage_row.inventory_brand_id,
                usage_row.inventory_model_id,
                COALESCE(type_row.type_name, '非资产物资') AS type_name,
                usage_row.brand,
                usage_row.model,
                TRIM(CONCAT_WS(' ', usage_row.brand, usage_row.model)) AS detail,
                usage_row.quantity,
                usage_row.stock_adjusted
              FROM employee_non_asset_usage usage_row
              JOIN non_asset_type type_row
                ON type_row.non_asset_type_id = usage_row.non_asset_type_id
              WHERE usage_row.employee_id = {employee_id}
                AND usage_row.is_active = 1
              ORDER BY type_row.type_name, usage_row.non_asset_usage_id
            ) active_non_assets
            """,
            [],
        )
        allocation_rows = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(allocation.allocation_id AS CHAR),
                  'allocationType', allocation.allocation_type,
                  'usageRecordId', CAST(allocation.usage_record_id AS CHAR),
                  'quantity', allocation.quantity,
                  'stockAdjusted', allocation.stock_adjusted,
                  'modelId', COALESCE(CAST(allocation.inventory_model_id AS CHAR), ''),
                  'warehouseId', COALESCE(CAST(allocation.warehouse_id AS CHAR), ''),
                  'warehouseName', COALESCE(warehouse.warehouse_name, '')
                )), JSON_ARRAY())
                FROM inventory_allocation_history allocation
                LEFT JOIN inventory_warehouse warehouse
                  ON warehouse.warehouse_id = allocation.warehouse_id
                WHERE allocation.employee_id = {employee_id}
                  AND allocation.status = 'active'
                  AND allocation.allocation_type IN ('monitor', 'non_asset')
                """,
                [],
            )
            or []
        )
        allocations_by_key: dict[str, list[dict]] = {}
        for allocation in allocation_rows:
            allocation_type = self.db.text(allocation.get("allocationType"))
            usage_record_id = self.db.text(allocation.get("usageRecordId"))
            if allocation_type and usage_record_id:
                allocations_by_key.setdefault(f"{allocation_type}:{usage_record_id}", []).append(dict(allocation))
        items = list(computers or []) + list(monitors or []) + list(non_assets or [])
        for item in items:
            item_type = self.db.text(item.get("itemType"))
            item["id"] = self.db.text(item.get("id"))
            item["key"] = f"{item_type}:{item['id']}"
            item["detail"] = self.db.text(item.get("detail")) or (
                self.db.text(item.get("status")) if item_type == "computer" else "未填写品牌型号"
            )
            item["quantity"] = max(1, self.db.integer(item.get("quantity"), 1))
            item["stockAdjusted"] = parse_bool(item.get("stockAdjusted"), False)
            if item_type in {"monitor", "non_asset"}:
                allocations = allocations_by_key.get(f"{item_type}:{item['id']}", [])
                item["stockAdjusted"] = item["stockAdjusted"] or any(
                    parse_bool(allocation.get("stockAdjusted"), False)
                    for allocation in allocations
                )
                warehouse_ids = [
                    self.db.text(allocation.get("warehouseId"))
                    for allocation in allocations
                    if self.db.text(allocation.get("warehouseId"))
                ]
                warehouse_names = [
                    self.db.text(allocation.get("warehouseName"))
                    for allocation in allocations
                    if self.db.text(allocation.get("warehouseName"))
                ]
                item["activeAllocationCount"] = len(allocations)
                item["activeAllocationQuantity"] = sum(
                    max(0, self.db.integer(allocation.get("quantity"), 0))
                    for allocation in allocations
                )
                item["activeAllocations"] = [
                    {
                        "id": self.db.text(allocation.get("id")),
                        "quantity": max(0, self.db.integer(allocation.get("quantity"), 0)),
                        "modelId": self.db.text(allocation.get("modelId")),
                        "stockAdjusted": parse_bool(allocation.get("stockAdjusted"), False),
                        "warehouseId": self.db.text(allocation.get("warehouseId")),
                        "warehouseName": self.db.text(allocation.get("warehouseName")),
                    }
                    for allocation in allocations
                ]
                item["sourceWarehouseIds"] = sorted(set(warehouse_ids), key=int)
                item["sourceWarehouseNames"] = list(dict.fromkeys(warehouse_names))
                item["requiresRecoveryWarehouse"] = bool(
                    item["stockAdjusted"]
                    and (
                        not allocations
                        or any(not self.db.text(allocation.get("warehouseId")) for allocation in allocations)
                    )
                )
        return items

    def _normalize_offboarding_plan(
        self,
        employee_id: int,
        current_items: list[dict],
        raw_items: object,
        context: dict,
    ) -> list[dict]:
        if raw_items is None:
            raw_items = []
        if not isinstance(raw_items, list):
            raise self.api_error("离职资产处理清单必须是数组。")

        current_by_key = {self.db.text(item.get("key")): item for item in current_items}
        submitted_keys: list[str] = []
        normalized: list[dict] = []
        target_cache: dict[int, dict] = {}
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                raise self.api_error("离职资产处理项格式无效。")
            item_type = self.db.text(raw_item.get("itemType") or raw_item.get("category")).replace("-", "_")
            if item_type == "nonasset":
                item_type = "non_asset"
            item_id = self.db.integer(raw_item.get("itemId") or raw_item.get("id"), 0)
            key = f"{item_type}:{item_id}"
            if item_id <= 0 or key not in current_by_key:
                raise self.api_error("离职资产处理清单包含不存在或已变化的项目，请刷新后重试。")
            if key in submitted_keys:
                raise self.api_error("离职资产处理清单包含重复项目。")
            action = self.db.text(raw_item.get("action"))
            if action not in OFFBOARD_ACTION_LABELS:
                raise self.api_error("每项资产或物资都必须选择处理方式。")
            note = self.db.text(raw_item.get("note") or raw_item.get("handlingNote")).strip()
            if len(note) > 500:
                raise self.api_error("单项处理说明不能超过 500 个字符。")
            target: dict | None = None
            target_id = self.db.integer(raw_item.get("targetEmployeeId"), 0)
            if action == "transfer":
                if target_id <= 0:
                    raise self.api_error("转交他人时必须选择接收人员。")
                if target_id == employee_id:
                    raise self.api_error("离职资产不能转交给离职人员本人。")
                target = target_cache.get(target_id)
                if target is None:
                    target = self._employee(target_id)
                    if self.db.text(target.get("status")) not in {"active", "shared"}:
                        raise self.api_error("离职资产只能转交给在职人员或公用人员。")
                    self.scope.assert_org_access(context, target.get("orgId"))
                    target_cache[target_id] = target
            elif target_id > 0:
                raise self.api_error("只有转交他人时才能选择接收人员。")
            if action == "exception" and not note:
                raise self.api_error("异常待处理必须填写说明。")

            current = dict(current_by_key[key])
            current.update(
                {
                    "action": action,
                    "actionLabel": OFFBOARD_ACTION_LABELS[action],
                    "note": note,
                    "targetEmployeeId": str(target_id) if target_id > 0 else "",
                    "targetEmployeeNo": self.db.text(target.get("employeeNo")) if target else "",
                    "targetEmployeeName": self.db.text(target.get("name")) if target else "",
                }
            )
            if action == "recover" and current["itemType"] != "computer":
                active_allocations = current.get("activeAllocations") or []
                stock_adjusted_allocations = [
                    allocation
                    for allocation in active_allocations
                    if parse_bool(allocation.get("stockAdjusted"), False)
                ]
                stock_adjusted = parse_bool(current.get("stockAdjusted"), False) or bool(
                    stock_adjusted_allocations
                )
                if stock_adjusted and self.db.integer(current.get("modelId"), 0) <= 0 and not any(
                    self.db.integer(allocation.get("modelId"), 0) > 0
                    for allocation in stock_adjusted_allocations
                ):
                    raise self.conflict_error("已扣减库存的物资缺少库存型号，无法通过离职回收自动入库。")
                if any(
                    self.db.integer(allocation.get("modelId"), 0) <= 0
                    for allocation in stock_adjusted_allocations
                ):
                    raise self.conflict_error("离职回收记录缺少库存型号，无法按原库存批次入库。")
                if stock_adjusted:
                    source_warehouse_ids = sorted(
                        {
                            self.db.integer(value, 0)
                            for value in current.get("sourceWarehouseIds") or []
                            if self.db.integer(value, 0) > 0
                        }
                    )
                    if source_warehouse_ids:
                        for source_warehouse_id in source_warehouse_ids:
                            self._assert_warehouse_access(
                                context,
                                self._warehouse(source_warehouse_id, include_inactive=True),
                                "warehouse_management",
                            )
            if action == "recover":
                # Every recovery must name its destination warehouse, no matter
                # whether the item was deducted from stock: the destination is
                # recorded for traceability and used for stock recovery when the
                # item was issued from inventory.
                requested_warehouse_id = self.db.integer(
                    raw_item.get("recoveryWarehouseId") or raw_item.get("warehouseId"),
                    0,
                )
                if requested_warehouse_id <= 0:
                    raise self.api_error("选择回收时必须指定回收目标仓库。")
                target_warehouse = self._resolve_warehouse(
                    {"warehouseId": requested_warehouse_id},
                    context,
                    "employees",
                    require_explicit=True,
                )
                current["recoveryWarehouseId"] = self.db.text(target_warehouse.get("id"))
                current["recoveryWarehouseName"] = self.db.text(target_warehouse.get("name"))
            submitted_keys.append(key)
            normalized.append(current)

        current_keys = set(current_by_key)
        submitted_key_set = set(submitted_keys)
        if current_keys != submitted_key_set:
            raise self.api_error("当前名下资产或物资必须逐项处理后才能办理离职。")
        return normalized

    def offboard_employee(
        self,
        employee_id: object,
        payload: dict,
        context: dict,
        idempotency_key: str = "",
    ) -> dict:
        cached = self._idempotency_result("employee.offboard", idempotency_key, payload)
        if cached:
            return cached

        employee_id_int = self.db.integer(employee_id, 0)
        if employee_id_int <= 0:
            raise self.api_error("人员不存在。")
        permission_scope = self._permission_scope(context, "employees")
        if permission_scope not in {"all", "organization"}:
            raise self.forbidden_error("办理离职需要使用人员的全部数据或所属部门数据权限。")
        if self._actor_employee_id(context) == employee_id_int:
            raise self.conflict_error("当前登录账号不能办理自身绑定人员离职。")

        leave_date = self.db.text(payload.get("leaveDate")).strip()
        leave_reason = self.db.text(payload.get("leaveReason") or payload.get("leaveInfo")).strip()
        leave_remark = self.db.text(payload.get("leaveRemark")).strip()
        if not leave_date or not leave_reason or not leave_remark:
            raise self.api_error("离职日期、离职原因和备注不能为空。")
        try:
            datetime.strptime(leave_date, "%Y-%m-%d")
        except ValueError as exc:
            raise self.api_error("离职日期格式必须为 YYYY-MM-DD。") from exc
        if len(leave_reason) > 500 or len(leave_remark) > 500:
            raise self.api_error("离职原因和备注不能超过 500 个字符。")

        employee = self._offboarding_employee(employee_id_int)
        if self.db.text(employee.get("status")) == "left":
            raise self.conflict_error("该人员已经办理离职。")
        self.scope.assert_org_access(context, employee.get("orgId"))
        current_items = self._offboarding_items(employee_id_int)
        plan = self._normalize_offboarding_plan(employee_id_int, current_items, payload.get("items"), context)

        snapshot = []
        for item in plan:
            snapshot.append(
                {
                    "category": item.get("itemType"),
                    "label": self.db.text(item.get("label")),
                    "detail": self.db.text(item.get("detail")),
                    "quantity": self.db.integer(item.get("quantity"), 1),
                    "typeId": self.db.text(item.get("typeId")),
                    "typeName": self.db.text(item.get("typeName")),
                    "brandId": self.db.text(item.get("brandId")),
                    "modelId": self.db.text(item.get("modelId")),
                    "brand": self.db.text(item.get("brand")),
                    "model": self.db.text(item.get("model")),
                    "action": item.get("action"),
                    "actionLabel": item.get("actionLabel"),
                    "targetEmployeeId": item.get("targetEmployeeId"),
                    "targetEmployeeNo": item.get("targetEmployeeNo"),
                    "targetEmployeeName": item.get("targetEmployeeName"),
                    "sourceWarehouseIds": item.get("sourceWarehouseIds") or [],
                    "sourceWarehouseNames": item.get("sourceWarehouseNames") or [],
                    "recoveryWarehouseId": item.get("recoveryWarehouseId") or "",
                    "recoveryWarehouseName": item.get("recoveryWarehouseName") or "",
                    "handlingNote": item.get("note"),
                }
            )

        computer_ids = [self.db.integer(item.get("id"), 0) for item in plan if item.get("itemType") == "computer"]
        monitor_ids = [self.db.integer(item.get("id"), 0) for item in plan if item.get("itemType") == "monitor"]
        non_asset_ids = [self.db.integer(item.get("id"), 0) for item in plan if item.get("itemType") == "non_asset"]
        target_ids = [
            self.db.integer(item.get("targetEmployeeId"), 0)
            for item in plan
            if self.db.integer(item.get("targetEmployeeId"), 0) > 0
        ]
        recover_model_ids: list[int] = []
        for item in plan:
            if item.get("itemType") == "computer" or item.get("action") != "recover":
                continue
            active_allocations = item.get("activeAllocations") or []
            if active_allocations:
                recover_model_ids.extend(
                    self.db.integer(allocation.get("modelId"), 0)
                    for allocation in active_allocations
                    if parse_bool(allocation.get("stockAdjusted"), False)
                )
            elif parse_bool(item.get("stockAdjusted"), False):
                recover_model_ids.append(self.db.integer(item.get("modelId"), 0))

        computer_id_sql = self._sql_id_list(computer_ids)
        monitor_id_sql = self._sql_id_list(monitor_ids)
        non_asset_id_sql = self._sql_id_list(non_asset_ids)
        target_id_sql = self._sql_id_list(target_ids)
        recover_model_id_sql = self._sql_id_list(recover_model_ids)
        distinct_target_count = len({value for value in target_ids if value > 0})
        distinct_recover_model_count = len({value for value in recover_model_ids if value > 0})
        actor_id = self._actor_id(context)
        actor_sql = str(actor_id) if actor_id > 0 else "NULL"
        employee_name = self.db.text(employee.get("name"))
        employee_no = self.db.text(employee.get("employeeNo"))
        employee_label = f"{employee_name}（{employee_no}）" if employee_no else employee_name
        # 公用人员是占位使用人：办理“离职”等同于删除，不写入离职人员档案。
        shared_employee = self.db.text(employee.get("status")) == "shared"

        statements: list[str] = [
            "START TRANSACTION",
            "SET @processed_item_count = 0",
            "SET @archive_id = 0",
            f"""
            SELECT employee_id
            FROM employee
            WHERE employee_id = {employee_id_int}
              AND is_active = 1
            FOR UPDATE
            """,
            f"""
            SELECT assignment_id
            FROM computer_assignment
            WHERE employee_id = {employee_id_int}
              AND returned_at IS NULL
              AND assignment_status = 'active'
            FOR UPDATE
            """,
            f"""
            SELECT monitor_usage_id
            FROM employee_monitor_usage
            WHERE employee_id = {employee_id_int}
              AND is_active = 1
            FOR UPDATE
            """,
            f"""
            SELECT non_asset_usage_id
            FROM employee_non_asset_usage
            WHERE employee_id = {employee_id_int}
              AND is_active = 1
            FOR UPDATE
            """,
            f"""
            SELECT allocation_id
            FROM inventory_allocation_history
            WHERE employee_id = {employee_id_int}
              AND status = 'active'
            FOR UPDATE
            """,
        ]
        if distinct_target_count:
            statements.append(
                f"""
                SELECT employee_id
                FROM employee
                WHERE employee_id IN ({target_id_sql})
                  AND is_active = 1
                FOR UPDATE
                """
            )
        if distinct_recover_model_count:
            statements.append(
                f"""
                SELECT model_id
                FROM it_inventory_model
                WHERE model_id IN ({recover_model_id_sql})
                  AND is_active = 1
                FOR UPDATE
                """
            )

        statements.extend(
            [
                f"""
                SET @current_item_count = (
                  SELECT
                    (SELECT COUNT(*)
                     FROM computer_assignment
                     WHERE employee_id = {employee_id_int}
                       AND returned_at IS NULL
                       AND assignment_status = 'active')
                    +
                    (SELECT COUNT(*)
                     FROM employee_monitor_usage
                     WHERE employee_id = {employee_id_int}
                       AND is_active = 1)
                    +
                    (SELECT COUNT(*)
                     FROM employee_non_asset_usage
                     WHERE employee_id = {employee_id_int}
                       AND is_active = 1)
                )
                """,
                f"""
                SET @matched_item_count = (
                  SELECT
                    (SELECT COUNT(*)
                     FROM computer_assignment
                     WHERE employee_id = {employee_id_int}
                       AND returned_at IS NULL
                       AND assignment_status = 'active'
                       AND computer_id IN ({computer_id_sql}))
                    +
                    (SELECT COUNT(*)
                     FROM employee_monitor_usage
                     WHERE employee_id = {employee_id_int}
                       AND is_active = 1
                       AND monitor_usage_id IN ({monitor_id_sql}))
                    +
                    (SELECT COUNT(*)
                     FROM employee_non_asset_usage
                     WHERE employee_id = {employee_id_int}
                       AND is_active = 1
                       AND non_asset_usage_id IN ({non_asset_id_sql}))
                )
                """,
                f"""
                SET @offboard_allowed = IF(
                  (SELECT COUNT(*)
                   FROM employee
                   WHERE employee_id = {employee_id_int}
                     AND is_active = 1
                     AND employment_status <> 'left') = 1
                  AND @current_item_count = {len(plan)}
                  AND @matched_item_count = {len(plan)}
                  AND (SELECT COUNT(*)
                       FROM employee
                       WHERE employee_id IN ({target_id_sql})
                         AND is_active = 1
                         AND employment_status = 'active') = {distinct_target_count}
                  AND (SELECT COUNT(*)
                       FROM it_inventory_model
                       WHERE model_id IN ({recover_model_id_sql})
                         AND is_active = 1) = {distinct_recover_model_count},
                  1,
                  0
                )
                """,
            ]
        )

        for item in plan:
            item_type = self.db.text(item.get("itemType"))
            item_id = self.db.integer(item.get("id"), 0)
            quantity = max(1, self.db.integer(item.get("quantity"), 1))
            action = self.db.text(item.get("action"))
            handling_note = self.db.text(item.get("note"))

            if item_type == "computer":
                if action == "transfer":
                    target_id = self.db.integer(item.get("targetEmployeeId"), 0)
                    target_name = self.db.text(item.get("targetEmployeeName"))
                    note = self._offboard_note(f"离职办理转交给 {target_name}", handling_note)
                    statements.extend(
                        [
                            f"""
                            UPDATE computer_assignment
                            SET returned_at = CURRENT_TIMESTAMP,
                                assignment_status = 'returned',
                                notes = CONCAT_WS(' ', notes, {self.db.quote(note)})
                            WHERE computer_id = {item_id}
                              AND employee_id = {employee_id_int}
                              AND returned_at IS NULL
                              AND assignment_status = 'active'
                              AND @offboard_allowed = 1
                            """,
                            "SET @processed_item_count = @processed_item_count + ROW_COUNT()",
                            f"""
                            INSERT INTO computer_assignment_history (
                              computer_id, device_name, employee_id, employee_no, employee_name,
                              assigned_at, returned_at, assignment_status, notes, returned_by
                            )
                            SELECT
                              assignment.computer_id, asset.device_name, assignment.employee_id,
                              employee.employee_no, employee.employee_name, assignment.assigned_at,
                              CURRENT_TIMESTAMP, 'returned', assignment.notes, {actor_sql}
                            FROM computer_assignment assignment
                            JOIN computer_asset asset ON asset.computer_id = assignment.computer_id
                            JOIN employee ON employee.employee_id = assignment.employee_id
                            WHERE assignment.computer_id = {item_id}
                              AND assignment.employee_id = {employee_id_int}
                              AND assignment.returned_at IS NOT NULL
                              AND @offboard_allowed = 1
                            ORDER BY assignment.assignment_id DESC
                            LIMIT 1
                            ON DUPLICATE KEY UPDATE
                              returned_at = VALUES(returned_at),
                              assignment_status = VALUES(assignment_status),
                              notes = VALUES(notes),
                              returned_by = VALUES(returned_by)
                            """,
                            f"""
                            INSERT INTO computer_assignment (
                              computer_id, employee_id, assigned_at, assignment_status, notes
                            )
                            SELECT {item_id}, {target_id}, CURRENT_TIMESTAMP, 'active', {self.db.quote(note)}
                            FROM DUAL
                            WHERE @offboard_allowed = 1
                            """,
                            f"""
                            INSERT INTO computer_assignment_history (
                              computer_id, device_name, employee_id, employee_no, employee_name,
                              assigned_at, assignment_status, notes, assigned_by
                            )
                            SELECT
                              asset.computer_id, asset.device_name, employee.employee_id,
                              employee.employee_no, employee.employee_name, CURRENT_TIMESTAMP,
                              'active', {self.db.quote(note)}, {actor_sql}
                            FROM computer_asset asset
                            JOIN employee ON employee.employee_id = {target_id}
                            WHERE asset.computer_id = {item_id}
                              AND @offboard_allowed = 1
                            """,
                            f"""
                            UPDATE computer_asset
                            SET it_asset_status = 'in_use'
                            WHERE computer_id = {item_id}
                              AND @offboard_allowed = 1
                            """,
                        ]
                    )
                    continue

                next_status = "lost" if action == "exception" else "idle"
                note = self._offboard_note(
                    "离职办理异常待处理" if action == "exception" else "离职办理回收",
                    handling_note,
                )
                statements.extend(
                    [
                        f"""
                        UPDATE computer_assignment
                        SET returned_at = CURRENT_TIMESTAMP,
                            assignment_status = 'returned',
                            notes = CONCAT_WS(' ', notes, {self.db.quote(note)})
                        WHERE computer_id = {item_id}
                          AND employee_id = {employee_id_int}
                          AND returned_at IS NULL
                          AND assignment_status = 'active'
                          AND @offboard_allowed = 1
                        """,
                        "SET @processed_item_count = @processed_item_count + ROW_COUNT()",
                        f"""
                        INSERT INTO computer_assignment_history (
                          computer_id, device_name, employee_id, employee_no, employee_name,
                          assigned_at, returned_at, assignment_status, notes, returned_by
                        )
                        SELECT
                          assignment.computer_id, asset.device_name, assignment.employee_id,
                          employee.employee_no, employee.employee_name, assignment.assigned_at,
                          CURRENT_TIMESTAMP, 'returned', assignment.notes, {actor_sql}
                        FROM computer_assignment assignment
                        JOIN computer_asset asset ON asset.computer_id = assignment.computer_id
                        JOIN employee ON employee.employee_id = assignment.employee_id
                        WHERE assignment.computer_id = {item_id}
                          AND assignment.employee_id = {employee_id_int}
                          AND assignment.returned_at IS NOT NULL
                          AND @offboard_allowed = 1
                        ORDER BY assignment.assignment_id DESC
                        LIMIT 1
                        ON DUPLICATE KEY UPDATE
                          returned_at = VALUES(returned_at),
                          assignment_status = VALUES(assignment_status),
                          notes = VALUES(notes),
                          returned_by = VALUES(returned_by)
                        """,
                        f"""
                        UPDATE computer_asset
                        SET it_asset_status = {self.db.quote(next_status)}
                        WHERE computer_id = {item_id}
                          AND @offboard_allowed = 1
                        """,
                        f"""
                        INSERT INTO asset_status_history (
                          computer_id, previous_status, next_status, reason, changed_by
                        )
                        SELECT
                          {item_id}, {self.db.quote(self.db.text(item.get('status')) or 'in_use')},
                          {self.db.quote(next_status)}, {self.db.quote(note)}, {actor_sql}
                        FROM DUAL
                        WHERE @offboard_allowed = 1
                        """,
                    ]
                )
                continue

            usage_table = "employee_monitor_usage" if item_type == "monitor" else "employee_non_asset_usage"
            usage_pk = "monitor_usage_id" if item_type == "monitor" else "non_asset_usage_id"
            allocation_type = "monitor" if item_type == "monitor" else "non_asset"
            type_id_sql = self._nullable_id_sql(item.get("typeId"))
            brand_id_sql = self._nullable_id_sql(item.get("brandId"))
            model_id = self.db.integer(item.get("modelId"), 0)
            model_id_sql = self._nullable_id_sql(item.get("modelId"))
            stock_adjusted = 1 if parse_bool(item.get("stockAdjusted"), False) else 0
            type_name = self.db.text(item.get("typeName") or item.get("label")) or (
                "显示屏" if item_type == "monitor" else "非资产物资"
            )
            brand_name = self.db.text(item.get("brand"))
            model_name = self.db.text(item.get("model"))

            if action == "transfer":
                target_id = self.db.integer(item.get("targetEmployeeId"), 0)
                target_name = self.db.text(item.get("targetEmployeeName"))
                note = self._offboard_note(f"离职办理转交给 {target_name}", handling_note)
                allocation_groups: dict[int, dict[str, int]] = {}
                for allocation in item.get("activeAllocations") or []:
                    allocation_model_id = self.db.integer(allocation.get("modelId"), 0)
                    group = allocation_groups.setdefault(
                        allocation_model_id,
                        {"quantity": 0, "stockAdjusted": 0},
                    )
                    group["quantity"] += max(
                        1,
                        self.db.integer(allocation.get("quantity"), 1),
                    )
                    group["stockAdjusted"] = max(
                        group["stockAdjusted"],
                        1 if parse_bool(allocation.get("stockAdjusted"), False) else 0,
                    )
                if not allocation_groups:
                    allocation_groups[model_id] = {
                        "quantity": quantity,
                        "stockAdjusted": stock_adjusted,
                    }

                for allocation_model_id, group in sorted(allocation_groups.items()):
                    group_model_id_sql = (
                        str(allocation_model_id) if allocation_model_id > 0 else "NULL"
                    )
                    group_quantity = group["quantity"]
                    group_stock_adjusted = group["stockAdjusted"]
                    if item_type == "monitor":
                        statements.append(
                            f"""
                            INSERT INTO employee_monitor_usage (
                              employee_id, non_asset_type_id, inventory_brand_id, inventory_model_id,
                              display_name, model, quantity, stock_adjusted, notes
                            )
                            SELECT
                              {target_id}, {type_id_sql}, {brand_id_sql}, {group_model_id_sql},
                              {self.db.quote(brand_name)}, {self.db.quote(model_name)}, {group_quantity},
                              {group_stock_adjusted}, {self.db.quote(note)}
                            FROM DUAL
                            WHERE @offboard_allowed = 1
                            ON DUPLICATE KEY UPDATE
                              quantity = quantity + VALUES(quantity),
                              stock_adjusted = GREATEST(stock_adjusted, VALUES(stock_adjusted)),
                              inventory_brand_id = COALESCE(VALUES(inventory_brand_id), inventory_brand_id),
                              inventory_model_id = COALESCE(VALUES(inventory_model_id), inventory_model_id),
                              notes = CONCAT_WS(' ', notes, VALUES(notes))
                            """
                        )
                        target_usage_lookup = f"""
                        SELECT monitor_usage_id
                        INTO @target_usage_ref
                        FROM employee_monitor_usage
                        WHERE employee_id = {target_id}
                          AND display_name = {self.db.quote(brand_name)}
                          AND model = {self.db.quote(model_name)}
                          AND inventory_model_id <=> {group_model_id_sql}
                        LIMIT 1
                        """
                    else:
                        statements.append(
                            f"""
                            INSERT INTO employee_non_asset_usage (
                              employee_id, non_asset_type_id, inventory_brand_id, inventory_model_id,
                              brand, model, quantity, stock_adjusted, notes
                            )
                            SELECT
                              {target_id}, {type_id_sql}, {brand_id_sql}, {group_model_id_sql},
                              {self.db.quote(brand_name)}, {self.db.quote(model_name)}, {group_quantity},
                              {group_stock_adjusted}, {self.db.quote(note)}
                            FROM DUAL
                            WHERE @offboard_allowed = 1
                            ON DUPLICATE KEY UPDATE
                              quantity = quantity + VALUES(quantity),
                              stock_adjusted = GREATEST(stock_adjusted, VALUES(stock_adjusted)),
                              inventory_brand_id = COALESCE(VALUES(inventory_brand_id), inventory_brand_id),
                              inventory_model_id = COALESCE(VALUES(inventory_model_id), inventory_model_id),
                              notes = CONCAT_WS(' ', notes, VALUES(notes))
                            """
                        )
                        target_usage_lookup = f"""
                        SELECT non_asset_usage_id
                        INTO @target_usage_ref
                        FROM employee_non_asset_usage
                        WHERE employee_id = {target_id}
                          AND non_asset_type_id = {type_id_sql}
                          AND brand = {self.db.quote(brand_name)}
                          AND model = {self.db.quote(model_name)}
                          AND inventory_model_id <=> {group_model_id_sql}
                        LIMIT 1
                        """
                    statements.extend(
                        [
                            "SET @target_usage_ref = 0",
                            target_usage_lookup,
                            f"""
                            UPDATE inventory_allocation_history
                            SET employee_id = {target_id},
                                usage_record_id = @target_usage_ref,
                                notes = CONCAT_WS(' ', notes, {self.db.quote(note)})
                            WHERE allocation_type = {self.db.quote(allocation_type)}
                              AND employee_id = {employee_id_int}
                              AND usage_record_id = {item_id}
                              AND inventory_model_id <=> {group_model_id_sql}
                              AND status = 'active'
                              AND @offboard_allowed = 1
                              AND @target_usage_ref > 0
                            """,
                        ]
                    )
                statements.extend(
                    [
                        f"""
                        DELETE FROM {usage_table}
                        WHERE {usage_pk} = {item_id}
                          AND employee_id = {employee_id_int}
                          AND is_active = 1
                          AND @offboard_allowed = 1
                          AND (
                            SELECT COUNT(*)
                            FROM inventory_allocation_history
                            WHERE allocation_type = {self.db.quote(allocation_type)}
                              AND employee_id = {employee_id_int}
                              AND usage_record_id = {item_id}
                              AND status = 'active'
                          ) = 0
                        """,
                        "SET @processed_item_count = @processed_item_count + ROW_COUNT()",
                    ]
                )
                continue

            note = self._offboard_note(
                "离职办理异常待处理" if action == "exception" else "离职办理回收入库",
                handling_note,
            )
            target_status = "cancelled" if action == "exception" else "returned"
            recovery_warehouse_id = self.db.integer(item.get("recoveryWarehouseId"), 0)
            recovery_warehouse_id_sql = (
                str(recovery_warehouse_id) if recovery_warehouse_id > 0 else "NULL"
            )
            statements.append(
                f"""
                SET @active_allocation_count = (
                  SELECT COUNT(*)
                  FROM inventory_allocation_history
                  WHERE allocation_type = {self.db.quote(allocation_type)}
                    AND employee_id = {employee_id_int}
                    AND usage_record_id = {item_id}
                    AND status = 'active'
                )
                """
            )
            if action == "recover":
                statements.append(
                    self._recovery_catalog_sql(
                        type_id_sql=str(self.db.integer(item.get("typeId"), 0)),
                        brand_id_sql=str(self.db.integer(item.get("brandId"), 0)),
                        brand_name=brand_name,
                        model_name=model_name,
                        model_id_sql=str(model_id),
                        condition="@offboard_allowed = 1",
                    )
                )
                statements.extend(
                    [
                        f"""
                        INSERT INTO inventory_warehouse_stock (warehouse_id, model_id, quantity)
                        SELECT {recovery_warehouse_id_sql}, @recovery_model_id, {quantity}
                        FROM DUAL
                        WHERE @recovery_model_id > 0
                          AND @offboard_allowed = 1
                        ON DUPLICATE KEY UPDATE
                          quantity = quantity + VALUES(quantity)
                        """,
                        f"""
                        UPDATE it_inventory_model
                        SET quantity = quantity + {quantity}
                        WHERE model_id = @recovery_model_id
                          AND @offboard_allowed = 1
                        """,
                        f"""
                        INSERT INTO inventory_movement_log (
                          movement_direction, type_name, brand_name, model_name, quantity,
                          source_label, source_warehouse_id, target_label, target_warehouse_id,
                          note, related_employee_no, related_employee_name, trigger_action
                        )
                        SELECT
                          'increase',
                          COALESCE(type_row.type_name, {self.db.quote(type_name)}),
                          COALESCE(brand.brand_name, {self.db.quote(brand_name)}),
                          COALESCE(model.model_name, {self.db.quote(model_name)}),
                          {quantity},
                          {self.db.quote(employee_label)},
                          NULL,
                          warehouse.warehouse_name,
                          warehouse.warehouse_id,
                          {self.db.quote(note)},
                          {self.db.quote(employee_no)},
                          {self.db.quote(employee_name)},
                          'leave_recovery'
                        FROM inventory_warehouse warehouse
                        LEFT JOIN it_inventory_model model
                          ON model.model_id = @recovery_model_id
                        LEFT JOIN it_inventory_brand brand
                          ON brand.brand_id = model.brand_id
                        LEFT JOIN non_asset_type type_row
                          ON type_row.non_asset_type_id = model.non_asset_type_id
                        WHERE warehouse.warehouse_id = {recovery_warehouse_id_sql}
                          AND @recovery_model_id > 0
                          AND @offboard_allowed = 1
                        """,
                    ]
                )
            statements.extend(
                [
                    f"""
                    UPDATE inventory_allocation_history
                    SET status = {self.db.quote(target_status)},
                        returned_at = CURRENT_TIMESTAMP,
                        returned_by = {actor_sql},
                        warehouse_id = CASE
                          WHEN {1 if action == "recover" else 0} = 1
                            THEN {recovery_warehouse_id_sql}
                          ELSE warehouse_id
                        END,
                        notes = CONCAT_WS(' ', notes, {self.db.quote(note)})
                    WHERE allocation_type = {self.db.quote(allocation_type)}
                      AND employee_id = {employee_id_int}
                      AND usage_record_id = {item_id}
                      AND status = 'active'
                      AND @offboard_allowed = 1
                    """,
                    f"""
                    INSERT INTO inventory_allocation_history (
                      allocation_type, employee_id, non_asset_type_id, inventory_model_id, warehouse_id,
                      usage_record_id, quantity, stock_adjusted, status, issued_at,
                      returned_at, notes, issued_by, returned_by
                    )
                    SELECT
                      {self.db.quote(allocation_type)}, {employee_id_int}, {type_id_sql}, {model_id_sql},
                      {recovery_warehouse_id_sql if action == "recover" else "NULL"},
                      {item_id}, {quantity}, {stock_adjusted}, {self.db.quote(target_status)},
                      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, {self.db.quote(note)}, {actor_sql}, {actor_sql}
                    FROM DUAL
                    WHERE @offboard_allowed = 1
                      AND @active_allocation_count = 0
                    """,
                    f"""
                    DELETE FROM {usage_table}
                    WHERE {usage_pk} = {item_id}
                      AND employee_id = {employee_id_int}
                      AND is_active = 1
                      AND @offboard_allowed = 1
                    """,
                    "SET @processed_item_count = @processed_item_count + ROW_COUNT()",
                ]
            )

        statements.extend(
            [
                f"SET @offboard_success = IF(@offboard_allowed = 1 AND @processed_item_count = {len(plan)}, 1, 0)",
                f"""
                INSERT INTO left_employee_archive (
                  source_employee_ref, employee_no, employee_name, org_unit_id, org_path,
                  department, position_name, email, mobile, leave_date, leave_info,
                  leave_remark, device_snapshot
                )
                SELECT
                  CAST(employee_id AS CHAR),
                  employee_no,
                  employee_name,
                  org_unit_id,
                  {self.db.quote(self.db.text(employee.get('orgPath')))},
                  department,
                  position_name,
                  email,
                  mobile,
                  {self.db.quote(leave_date)},
                  {self.db.quote(leave_reason)},
                  {self.db.quote(leave_remark)},
                  {self.db.json_value(snapshot)}
                FROM employee
                WHERE employee_id = {employee_id_int}
                  AND @offboard_success = 1
                  AND {0 if shared_employee else 1} = 1
                """,
                f"SET @archive_id = IF(@offboard_success = 1 AND {0 if shared_employee else 1} = 1, LAST_INSERT_ID(), 0)",
                f"""
                UPDATE auth_session session
                JOIN user_account account
                  ON account.user_id = session.user_id
                 AND account.employee_id = {employee_id_int}
                SET session.revoked_at = CURRENT_TIMESTAMP
                WHERE session.revoked_at IS NULL
                  AND @offboard_success = 1
                """,
                f"""
                UPDATE user_account
                SET employee_id = NULL
                WHERE employee_id = {employee_id_int}
                  AND @offboard_success = 1
                """,
                "SET @unbound_account_count = ROW_COUNT()",
                f"""
                UPDATE employee
                SET employment_status = 'left'
                    {", is_active = 0" if shared_employee else ""}
                WHERE employee_id = {employee_id_int}
                  AND employment_status <> 'left'
                  AND @offboard_success = 1
                """,
                f"""
                INSERT INTO service_notification (
                  recipient_user_id, record_type, record_id, notification_type, title, content
                )
                SELECT
                  {actor_id}, 'system', @archive_id, 'employee_offboarded',
                  {self.db.quote('公用人员已删除' if shared_employee else '离职办理完成')},
                  {self.db.quote(
                      f'公用人员 {employee_label} 已删除，名下资产与物资已按清单处理。'
                      if shared_employee
                      else f'人员 {employee_label} 已完成离职办理，账号绑定已解除。'
                  )}
                FROM DUAL
                WHERE @offboard_success = 1
                  AND {actor_id} > 0
                """,
                self._conditional_audit_sql(
                    "employee_offboarded",
                    "employee",
                    self.db.quote(str(employee_id_int)),
                    employee_label,
                    (
                        f"公用人员 {employee_label} 已删除（占位人员，不进入离职人员档案）"
                        if shared_employee
                        else f"人员 {employee_label} 已完成受控离职办理"
                    ),
                    context,
                    "@offboard_success = 1",
                    {
                        "status": employee.get("status"),
                        "itemCount": len(plan),
                    },
                    {
                        "status": "left",
                        "isActive": 0 if shared_employee else 1,
                        "archived": not shared_employee,
                        "leaveDate": leave_date,
                        "itemCount": len(plan),
                        "unboundAccounts": "computed",
                    },
                ),
                """
                UPDATE app_state_revision
                SET revision = revision + 1
                WHERE revision_id = 1
                  AND @offboard_success = 1
                """,
                "SELECT @offboard_success, @archive_id, @processed_item_count, @unbound_account_count",
                "COMMIT",
            ]
        )
        movement_baseline = self.db.scalar(
            "SELECT COALESCE(MAX(movement_log_id), 0) FROM inventory_movement_log;"
        )
        output = self.db.execute(";\n".join(statements) + ";")
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        result = (lines[-1] if lines else "").split("\t")
        success = self.db.integer(result[0] if result else 0, 0)
        archive_id = self.db.integer(result[1] if len(result) > 1 else 0, 0)
        processed_items = self.db.integer(result[2] if len(result) > 2 else 0, 0)
        unbound_accounts = self.db.integer(result[3] if len(result) > 3 else 0, 0)
        if success != 1 or (archive_id <= 0 and not shared_employee):
            raise self.conflict_error("离职资产清单已变化，请刷新后重新办理。")

        response = {
            "archiveId": str(archive_id),
            "employeeId": str(employee_id_int),
            "status": "left",
            "sharedRemoved": shared_employee,
            "processedItems": processed_items,
            "unboundAccounts": unbound_accounts,
            "recoveryRecords": self._recovery_records_since(movement_baseline, ("leave_recovery",)),
            "unrecoveredItems": self._offboarding_unrecovered_items(plan),
        }
        self._store_idempotency_result("employee.offboard", idempotency_key, payload, response)
        return response

    def _recovery_records_since(
        self,
        movement_baseline: object,
        triggers: tuple[str, ...] = ("leave_recovery",),
    ) -> list[dict]:
        """Return the stock-recovery records written after a movement baseline."""
        trigger_sql = ", ".join(self.db.quote(trigger) for trigger in triggers)
        rows = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'movementLogId', CAST(movement_log_id AS CHAR),
              'typeName', type_name,
              'brandName', brand_name,
              'modelName', model_name,
              'quantity', quantity,
              'warehouseId', COALESCE(CAST(target_warehouse_id AS CHAR), ''),
              'warehouseName', target_label,
              'note', note,
              'triggerAction', trigger_action,
              'occurredAt', DATE_FORMAT(occurred_at, '%Y-%m-%d %H:%i:%s')
            )), JSON_ARRAY())
            FROM (
              SELECT movement_log_id, type_name, brand_name, model_name, quantity,
                     target_warehouse_id, target_label, note, trigger_action, occurred_at
              FROM inventory_movement_log
              WHERE movement_log_id > {self.db.integer(movement_baseline, 0)}
                AND trigger_action IN ({trigger_sql})
              ORDER BY movement_log_id
            ) AS ordered_recovery_records
            """,
            [],
        )
        return [dict(row) for row in (rows or [])]

    def _offboarding_unrecovered_items(self, plan: list[dict]) -> list[dict]:
        """Describe items that were not recovered into stock and why."""
        items: list[dict] = []
        for item in plan or []:
            action = self.db.text(item.get("action"))
            if action == "recover":
                continue
            target_name = self.db.text(item.get("targetEmployeeName"))
            note = self.db.text(item.get("note"))
            if action == "transfer":
                reason = f"已转交给 {target_name}" if target_name else "已转交他人"
            elif action == "exception":
                reason = f"异常待处理：{note}" if note else "异常待处理"
            else:
                reason = "未选择回收"
            items.append(
                {
                    "itemType": self.db.text(item.get("itemType")),
                    "label": self.db.text(item.get("label")),
                    "detail": self.db.text(item.get("detail")),
                    "quantity": self.db.integer(item.get("quantity"), 1),
                    "action": action,
                    "actionLabel": self.db.text(item.get("actionLabel")),
                    "targetEmployeeName": target_name,
                    "note": note,
                    "reason": reason,
                }
            )
        return items

    def add_relation(self, payload: dict, context: dict) -> dict:
        source_type = self.db.text(payload.get("sourceType"))
        target_type = self.db.text(payload.get("targetType"))
        relation_type = self.db.text(payload.get("relationType"))
        source_id = self.db.integer(payload.get("sourceId"), 0)
        target_id = self.db.integer(payload.get("targetId"), 0)
        if (
            source_type not in {"computer", "employee", "organization", "ticket"}
            or target_type not in {"computer", "employee", "organization", "ticket"}
            or relation_type not in {"depends_on", "connected_to", "assigned_to", "located_at", "related_to"}
            or source_id <= 0
            or target_id <= 0
            or (source_type == target_type and source_id == target_id)
        ):
            raise self.api_error("Invalid asset relation.")
        self._assert_relation_entity_access(source_type, source_id, context)
        self._assert_relation_entity_access(target_type, target_id, context)
        self.db.execute(
            f"""
            INSERT INTO asset_relation (
              source_entity_type, source_entity_id, relation_type,
              target_entity_type, target_entity_id, notes, created_by
            )
            VALUES (
              {self.db.quote(source_type)}, {source_id}, {self.db.quote(relation_type)},
              {self.db.quote(target_type)}, {target_id}, {self.db.quote(self.db.text(payload.get('notes')))},
              {self._actor_id(context)}
            )
            ON DUPLICATE KEY UPDATE
              notes = VALUES(notes),
              is_active = 1,
              updated_at = CURRENT_TIMESTAMP;
            """
        )
        return {"ok": True}

    def list_relations(self, entity_type: str, entity_id: object, context: dict) -> list[dict]:
        entity_id_int = self.db.integer(entity_id, 0)
        if entity_type not in {"computer", "employee", "organization", "ticket"} or entity_id_int <= 0:
            raise self.api_error("Invalid relation entity.")
        self._assert_relation_entity_access(entity_type, entity_id_int, context)
        rows = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(relation_id AS CHAR),
                  'sourceType', source_entity_type,
                  'sourceId', CAST(source_entity_id AS CHAR),
                  'relationType', relation_type,
                  'targetType', target_entity_type,
                  'targetId', CAST(target_entity_id AS CHAR),
                  'notes', notes
                )), JSON_ARRAY())
                FROM asset_relation
                WHERE is_active = 1
                  AND (
                    (source_entity_type = {self.db.quote(entity_type)} AND source_entity_id = {entity_id_int})
                    OR (target_entity_type = {self.db.quote(entity_type)} AND target_entity_id = {entity_id_int})
                  )
                """,
                [],
            )
            or []
        )
        visible: list[dict] = []
        for row in rows:
            try:
                self._assert_relation_entity_access(
                    self.db.text(row.get("sourceType")),
                    self.db.integer(row.get("sourceId"), 0),
                    context,
                )
                self._assert_relation_entity_access(
                    self.db.text(row.get("targetType")),
                    self.db.integer(row.get("targetId"), 0),
                    context,
                )
            except (self.forbidden_error, self.api_error):
                continue
            visible.append(row)
        return visible
