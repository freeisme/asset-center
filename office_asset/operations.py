from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from .sql import SqlGateway


QUALITY_SEVERITY_LABELS = {
    "high": "高",
    "medium": "中",
    "low": "低",
}
QUALITY_RULE_LABELS = {
    "computer_assigned_to_inactive_employee": "设备分配给非在职人员",
    "computer_missing_identity": "办公终端缺少唯一标识",
    "resolved_ticket_missing_resolution": "已解决工单缺少解决方案",
}
QUALITY_ENTITY_TYPE_LABELS = {
    "computer": "办公终端",
    "itil_ticket": "工单",
}
QUALITY_STATUS_LABELS = {
    "open": "待处理",
    "resolved": "已解决",
    "ignored": "已忽略",
}


@dataclass
class SyncService:
    db: SqlGateway
    api_error: type[Exception]
    conflict_error: type[Exception]

    def _validate_record(self, entity_type: str, action: str, data: dict) -> list[str]:
        errors: list[str] = []
        if entity_type not in {"organization", "employee", "computer"}:
            errors.append("entityType must be organization, employee or computer")
        if action not in {"upsert", "disable"}:
            errors.append("action must be upsert or disable")
        if not isinstance(data, dict):
            errors.append("data must be an object")
            return errors
        if action == "disable":
            return errors
        if entity_type == "organization":
            if not self.db.text(data.get("code")):
                errors.append("organization code is required")
            if not self.db.text(data.get("name")):
                errors.append("organization name is required")
        elif entity_type == "employee":
            if not self.db.text(data.get("employeeNo")):
                errors.append("employeeNo is required")
            if not self.db.text(data.get("name")):
                errors.append("employee name is required")
        elif entity_type == "computer":
            if not self.db.text(data.get("deviceName")):
                errors.append("deviceName is required")
            if not self.db.text(data.get("deviceType")):
                errors.append("deviceType is required")
        return errors

    def stage(self, payload: dict, context: dict) -> dict:
        source_code = self.db.text(payload.get("sourceCode"))
        source = self.db.scalar(
            f"SELECT COUNT(*) FROM sync_source WHERE source_code = {self.db.quote(source_code)} AND is_active = 1;"
        )
        if source != 1:
            raise self.api_error("Sync source does not exist or is inactive.")
        records = payload.get("records")
        if not isinstance(records, list) or not records:
            raise self.api_error("Sync staging requires at least one record.")
        if len(records) > 5000:
            raise self.api_error("A sync run cannot contain more than 5000 records.")

        run_id = str(uuid.uuid4())
        valid_count = 0
        invalid_count = 0
        rows: list[str] = []
        canonical_records: list[dict] = []
        for item in records:
            if not isinstance(item, dict):
                raise self.api_error("Every sync record must be an object.")
            entity_type = self.db.text(item.get("entityType"))
            external_id = self.db.text(item.get("externalId"))
            action = self.db.text(item.get("action")) or "upsert"
            data = item.get("data")
            if not external_id:
                raise self.api_error("Every sync record requires an externalId.")
            errors = self._validate_record(entity_type, action, data)
            validation_status = "valid" if not errors else "invalid"
            valid_count += 1 if not errors else 0
            invalid_count += 1 if errors else 0
            canonical_records.append(
                {
                    "entityType": entity_type,
                    "externalId": external_id,
                    "action": action,
                    "data": data,
                }
            )
            rows.append(
                "("
                + ", ".join(
                    [
                        self.db.quote(run_id),
                        self.db.quote(entity_type),
                        self.db.quote(external_id),
                        self.db.quote(action),
                        self.db.json_value(data),
                        self.db.quote(validation_status),
                        self.db.json_value(errors) if errors else "NULL",
                    ]
                )
                + ")"
            )
        payload_hash = hashlib.sha256(
            json.dumps(canonical_records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.db.execute(
            f"""
            START TRANSACTION;
            INSERT INTO sync_run (
              sync_run_id, source_code, status, source_reference, payload_hash,
              records_total, records_valid, records_invalid, requested_by
            )
            VALUES (
              {self.db.quote(run_id)}, {self.db.quote(source_code)}, 'validated',
              {self.db.quote(self.db.text(payload.get('sourceReference')))},
              {self.db.quote(payload_hash)}, {len(canonical_records)}, {valid_count}, {invalid_count},
              {self.db.integer(context.get('id'), 0)}
            );
            INSERT INTO sync_staging_record (
              sync_run_id, entity_type, external_id, requested_action, payload,
              validation_status, validation_errors
            )
            VALUES {", ".join(rows)};
            COMMIT;
            """
        )
        return self.get_run(run_id)

    def get_run(self, run_id: object) -> dict:
        run_id_text = self.db.text(run_id)
        run = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', sync_run_id,
              'sourceCode', source_code,
              'status', status,
              'sourceReference', source_reference,
              'recordsTotal', records_total,
              'recordsValid', records_valid,
              'recordsInvalid', records_invalid,
              'recordsApplied', records_applied,
              'errorSummary', error_summary,
              'startedAt', CAST(started_at AS CHAR),
              'completedAt', COALESCE(CAST(completed_at AS CHAR), '')
            )
            FROM sync_run
            WHERE sync_run_id = {self.db.quote(run_id_text)}
            """,
            None,
        )
        if not run:
            raise self.api_error("Sync run does not exist.")
        records = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', CAST(staging_id AS CHAR),
              'entityType', entity_type,
              'externalId', external_id,
              'action', requested_action,
              'data', payload,
              'validationStatus', validation_status,
              'validationErrors', COALESCE(validation_errors, JSON_ARRAY()),
              'targetEntityId', COALESCE(CAST(target_entity_id AS CHAR), '')
            )), JSON_ARRAY())
            FROM sync_staging_record
            WHERE sync_run_id = {self.db.quote(run_id_text)}
            ORDER BY staging_id
            """,
            [],
        )
        result = dict(run)
        result["records"] = records or []
        return result

    def list_runs(self) -> list[dict]:
        return list(
            self.db.json(
                """
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', sync_run_id,
                  'sourceCode', source_code,
                  'status', status,
                  'recordsTotal', records_total,
                  'recordsValid', records_valid,
                  'recordsInvalid', records_invalid,
                  'recordsApplied', records_applied,
                  'startedAt', CAST(started_at AS CHAR),
                  'completedAt', COALESCE(CAST(completed_at AS CHAR), '')
                )), JSON_ARRAY())
                FROM (
                  SELECT *
                  FROM sync_run
                  ORDER BY started_at DESC
                  LIMIT 100
                ) recent_runs
                """,
                [],
            )
            or []
        )

    def _mapped_target(self, source_code: str, entity_type: str, external_id: str) -> int:
        return self.db.scalar(
            f"""
            SELECT COALESCE(target_entity_id, 0)
            FROM sync_entity_mapping
            WHERE source_code = {self.db.quote(source_code)}
              AND entity_type = {self.db.quote(entity_type)}
              AND external_id = {self.db.quote(external_id)}
            """
        )

    def _save_mapping(self, source_code: str, entity_type: str, external_id: str, target_id: int) -> str:
        return f"""
        INSERT INTO sync_entity_mapping (
          source_code, entity_type, external_id, target_entity_id, last_synced_at
        )
        VALUES (
          {self.db.quote(source_code)}, {self.db.quote(entity_type)},
          {self.db.quote(external_id)}, {target_id}, CURRENT_TIMESTAMP
        )
        ON DUPLICATE KEY UPDATE
          target_entity_id = VALUES(target_entity_id),
          last_synced_at = VALUES(last_synced_at);
        """

    def _apply_organization(self, source_code: str, external_id: str, action: str, data: dict) -> int:
        target_id = self._mapped_target(source_code, "organization", external_id)
        if action == "disable":
            if target_id:
                self.db.execute(f"UPDATE org_unit SET is_active = 0 WHERE org_unit_id = {target_id};")
            return target_id
        code = self.db.text(data.get("code")).upper()
        name = self.db.text(data.get("name"))
        parent_code = self.db.text(data.get("parentCode"))
        parent_sql = (
            f"(SELECT org_unit_id FROM org_unit WHERE org_code = {self.db.quote(parent_code)} AND is_active = 1 LIMIT 1)"
            if parent_code
            else "NULL"
        )
        if target_id:
            self.db.execute(
                f"""
                UPDATE org_unit
                SET org_code = {self.db.quote(code)},
                    org_name = {self.db.quote(name)},
                    parent_org_unit_id = {parent_sql},
                    is_active = 1
                WHERE org_unit_id = {target_id};
                """
            )
        else:
            output = self.db.execute(
                f"""
                INSERT INTO org_unit (org_code, org_name, parent_org_unit_id)
                VALUES ({self.db.quote(code)}, {self.db.quote(name)}, {parent_sql})
                ON DUPLICATE KEY UPDATE
                  org_unit_id = LAST_INSERT_ID(org_unit_id),
                  org_name = VALUES(org_name),
                  parent_org_unit_id = VALUES(parent_org_unit_id),
                  is_active = 1;
                SELECT LAST_INSERT_ID();
                """
            )
            target_id = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        self.db.execute(self._save_mapping(source_code, "organization", external_id, target_id))
        return target_id

    def _apply_employee(self, source_code: str, external_id: str, action: str, data: dict) -> int:
        target_id = self._mapped_target(source_code, "employee", external_id)
        if action == "disable":
            if target_id:
                self.db.execute(
                    f"UPDATE employee SET employment_status = 'inactive', is_active = 0 WHERE employee_id = {target_id};"
                )
            return target_id
        employee_no = self.db.text(data.get("employeeNo"))
        name = self.db.text(data.get("name"))
        org_code = self.db.text(data.get("orgCode"))
        org_sql = (
            f"(SELECT org_unit_id FROM org_unit WHERE org_code = {self.db.quote(org_code)} AND is_active = 1 LIMIT 1)"
            if org_code
            else "NULL"
        )
        if target_id:
            self.db.execute(
                f"""
                UPDATE employee
                SET employee_no = {self.db.quote(employee_no)},
                    employee_name = {self.db.quote(name)},
                    org_unit_id = {org_sql},
                    department = {self.db.quote(self.db.text(data.get('department')))},
                    position_name = {self.db.quote(self.db.text(data.get('position')))},
                    email = {self.db.quote(self.db.text(data.get('email')))},
                    mobile = {self.db.quote(self.db.text(data.get('mobile')))},
                    employment_status = 'active',
                    is_active = 1
                WHERE employee_id = {target_id};
                """
            )
        else:
            output = self.db.execute(
                f"""
                INSERT INTO employee (
                  employee_no, employee_name, org_unit_id, department, position_name, email, mobile,
                  employment_status, is_active
                )
                VALUES (
                  {self.db.quote(employee_no)}, {self.db.quote(name)}, {org_sql},
                  {self.db.quote(self.db.text(data.get('department')))},
                  {self.db.quote(self.db.text(data.get('position')))},
                  {self.db.quote(self.db.text(data.get('email')))},
                  {self.db.quote(self.db.text(data.get('mobile')))},
                  'active', 1
                )
                ON DUPLICATE KEY UPDATE
                  employee_id = LAST_INSERT_ID(employee_id),
                  employee_name = VALUES(employee_name),
                  org_unit_id = VALUES(org_unit_id),
                  department = VALUES(department),
                  position_name = VALUES(position_name),
                  email = VALUES(email),
                  mobile = VALUES(mobile),
                  employment_status = 'active',
                  is_active = 1;
                SELECT LAST_INSERT_ID();
                """
            )
            target_id = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        self.db.execute(self._save_mapping(source_code, "employee", external_id, target_id))
        return target_id

    def _apply_computer(self, source_code: str, external_id: str, action: str, data: dict) -> int:
        target_id = self._mapped_target(source_code, "computer", external_id)
        if action == "disable":
            if target_id:
                self.db.execute(f"UPDATE computer_asset SET is_active = 0 WHERE computer_id = {target_id};")
            return target_id
        device_name = self.db.text(data.get("deviceName"))
        org_code = self.db.text(data.get("orgCode"))
        org_sql = (
            f"(SELECT org_unit_id FROM org_unit WHERE org_code = {self.db.quote(org_code)} AND is_active = 1 LIMIT 1)"
            if org_code
            else "NULL"
        )
        status = self.db.text(data.get("status")) or "idle"
        if status not in {"in_use", "idle", "repair", "retired", "lost"}:
            status = "idle"
        if target_id:
            self.db.execute(
                f"""
                UPDATE computer_asset
                SET device_name = {self.db.quote(device_name)},
                    org_unit_id = {org_sql},
                    device_type = {self.db.quote(self.db.text(data.get('deviceType')))},
                    brand = {self.db.quote(self.db.text(data.get('brand')))},
                    model = {self.db.quote(self.db.text(data.get('model')))},
                    fixed_asset_code = {self.db.quote(self.db.text(data.get('fixedAssetCode')))},
                    sn_st = {self.db.quote(self.db.text(data.get('snSt')))},
                    location = {self.db.quote(self.db.text(data.get('location')))},
                    it_asset_status = {self.db.quote(status)},
                    is_active = 1
                WHERE computer_id = {target_id};
                """
            )
        else:
            output = self.db.execute(
                f"""
                INSERT INTO computer_asset (
                  device_name, org_unit_id, device_type, brand, model, fixed_asset_code,
                  sn_st, location, it_asset_status, is_active
                )
                VALUES (
                  {self.db.quote(device_name)}, {org_sql},
                  {self.db.quote(self.db.text(data.get('deviceType')))},
                  {self.db.quote(self.db.text(data.get('brand')))},
                  {self.db.quote(self.db.text(data.get('model')))},
                  {self.db.quote(self.db.text(data.get('fixedAssetCode')))},
                  {self.db.quote(self.db.text(data.get('snSt')))},
                  {self.db.quote(self.db.text(data.get('location')))},
                  {self.db.quote(status)}, 1
                )
                ON DUPLICATE KEY UPDATE
                  computer_id = LAST_INSERT_ID(computer_id),
                  org_unit_id = VALUES(org_unit_id),
                  device_type = VALUES(device_type),
                  brand = VALUES(brand),
                  model = VALUES(model),
                  fixed_asset_code = VALUES(fixed_asset_code),
                  sn_st = VALUES(sn_st),
                  location = VALUES(location),
                  it_asset_status = VALUES(it_asset_status),
                  is_active = 1;
                SELECT LAST_INSERT_ID();
                """
            )
            target_id = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        self.db.execute(self._save_mapping(source_code, "computer", external_id, target_id))
        return target_id

    def _record_apply_sql(self, source_code: str, record: dict, actor_name: str) -> str:
        entity_type = self.db.text(record.get("entityType"))
        external_id = self.db.text(record.get("externalId"))
        action = self.db.text(record.get("action")) or "upsert"
        data = record.get("data") or {}
        staging_id = self.db.integer(record.get("id"), 0)
        if entity_type not in {"organization", "employee", "computer"} or action not in {"upsert", "disable"}:
            raise self.api_error("The staged record is not valid.")

        mapping_sql = f"""
        SET @sync_target_id = COALESCE((
          SELECT target_entity_id
          FROM sync_entity_mapping
          WHERE source_code = {self.db.quote(source_code)}
            AND entity_type = {self.db.quote(entity_type)}
            AND external_id = {self.db.quote(external_id)}
          LIMIT 1
        ), 0);
        """

        if entity_type == "organization":
            if action == "disable":
                body = """
                UPDATE org_unit
                SET is_active = 0
                WHERE org_unit_id = @sync_target_id AND @sync_can_apply = 1;
                """
            else:
                code = self.db.text(data.get("code")).upper()
                name = self.db.text(data.get("name"))
                parent_code = self.db.text(data.get("parentCode"))
                parent_sql = (
                    f"(SELECT org_unit_id FROM org_unit WHERE org_code = {self.db.quote(parent_code)} "
                    "AND is_active = 1 LIMIT 1)"
                    if parent_code
                    else "NULL"
                )
                body = f"""
                SET @sync_inserted_id = 0;
                INSERT INTO org_unit (org_code, org_name, parent_org_unit_id)
                SELECT {self.db.quote(code)}, {self.db.quote(name)}, {parent_sql}
                FROM DUAL
                WHERE @sync_target_id = 0 AND @sync_can_apply = 1
                ON DUPLICATE KEY UPDATE
                  org_unit_id = LAST_INSERT_ID(org_unit_id),
                  org_name = VALUES(org_name),
                  parent_org_unit_id = VALUES(parent_org_unit_id),
                  is_active = 1;
                SET @sync_inserted_id = LAST_INSERT_ID();
                SET @sync_target_id = IF(@sync_target_id = 0, @sync_inserted_id, @sync_target_id);
                UPDATE org_unit
                SET org_code = {self.db.quote(code)},
                    org_name = {self.db.quote(name)},
                    parent_org_unit_id = {parent_sql},
                    is_active = 1
                WHERE org_unit_id = @sync_target_id AND @sync_can_apply = 1;
                """
        elif entity_type == "employee":
            if action == "disable":
                body = """
                UPDATE employee
                SET employment_status = 'inactive', is_active = 0
                WHERE employee_id = @sync_target_id AND @sync_can_apply = 1;
                """
            else:
                employee_no = self.db.text(data.get("employeeNo"))
                name = self.db.text(data.get("name"))
                org_code = self.db.text(data.get("orgCode"))
                org_sql = (
                    f"(SELECT org_unit_id FROM org_unit WHERE org_code = {self.db.quote(org_code)} "
                    "AND is_active = 1 LIMIT 1)"
                    if org_code
                    else "NULL"
                )
                body = f"""
                SET @sync_inserted_id = 0;
                INSERT INTO employee (
                  employee_no, employee_name, org_unit_id, department, position_name, email, mobile,
                  employment_status, is_active
                )
                SELECT
                  {self.db.quote(employee_no)}, {self.db.quote(name)}, {org_sql},
                  {self.db.quote(self.db.text(data.get('department')))},
                  {self.db.quote(self.db.text(data.get('position')))},
                  {self.db.quote(self.db.text(data.get('email')))},
                  {self.db.quote(self.db.text(data.get('mobile')))}, 'active', 1
                FROM DUAL
                WHERE @sync_target_id = 0 AND @sync_can_apply = 1
                ON DUPLICATE KEY UPDATE
                  employee_id = LAST_INSERT_ID(employee_id),
                  employee_name = VALUES(employee_name),
                  org_unit_id = VALUES(org_unit_id),
                  department = VALUES(department),
                  position_name = VALUES(position_name),
                  email = VALUES(email),
                  mobile = VALUES(mobile),
                  employment_status = 'active',
                  is_active = 1;
                SET @sync_inserted_id = LAST_INSERT_ID();
                SET @sync_target_id = IF(@sync_target_id = 0, @sync_inserted_id, @sync_target_id);
                UPDATE employee
                SET employee_no = {self.db.quote(employee_no)},
                    employee_name = {self.db.quote(name)},
                    org_unit_id = {org_sql},
                    department = {self.db.quote(self.db.text(data.get('department')))},
                    position_name = {self.db.quote(self.db.text(data.get('position')))},
                    email = {self.db.quote(self.db.text(data.get('email')))},
                    mobile = {self.db.quote(self.db.text(data.get('mobile')))},
                    employment_status = 'active',
                    is_active = 1
                WHERE employee_id = @sync_target_id AND @sync_can_apply = 1;
                """
        else:
            if action == "disable":
                body = """
                UPDATE computer_asset
                SET is_active = 0
                WHERE computer_id = @sync_target_id AND @sync_can_apply = 1;
                """
            else:
                device_name = self.db.text(data.get("deviceName"))
                org_code = self.db.text(data.get("orgCode"))
                org_sql = (
                    f"(SELECT org_unit_id FROM org_unit WHERE org_code = {self.db.quote(org_code)} "
                    "AND is_active = 1 LIMIT 1)"
                    if org_code
                    else "NULL"
                )
                status = self.db.text(data.get("status")) or "idle"
                if status not in {"in_use", "idle", "repair", "retired", "lost"}:
                    status = "idle"
                body = f"""
                SET @sync_inserted_id = 0;
                INSERT INTO computer_asset (
                  device_name, org_unit_id, device_type, brand, model, fixed_asset_code,
                  sn_st, location, it_asset_status, is_active
                )
                SELECT
                  {self.db.quote(device_name)}, {org_sql},
                  {self.db.quote(self.db.text(data.get('deviceType')))},
                  {self.db.quote(self.db.text(data.get('brand')))},
                  {self.db.quote(self.db.text(data.get('model')))},
                  {self.db.quote(self.db.text(data.get('fixedAssetCode')))},
                  {self.db.quote(self.db.text(data.get('snSt')))},
                  {self.db.quote(self.db.text(data.get('location')))},
                  {self.db.quote(status)}, 1
                FROM DUAL
                WHERE @sync_target_id = 0 AND @sync_can_apply = 1
                ON DUPLICATE KEY UPDATE
                  computer_id = LAST_INSERT_ID(computer_id),
                  org_unit_id = VALUES(org_unit_id),
                  device_type = VALUES(device_type),
                  brand = VALUES(brand),
                  model = VALUES(model),
                  fixed_asset_code = VALUES(fixed_asset_code),
                  sn_st = VALUES(sn_st),
                  location = VALUES(location),
                  it_asset_status = VALUES(it_asset_status),
                  is_active = 1;
                SET @sync_inserted_id = LAST_INSERT_ID();
                SET @sync_target_id = IF(@sync_target_id = 0, @sync_inserted_id, @sync_target_id);
                UPDATE computer_asset
                SET device_name = {self.db.quote(device_name)},
                    org_unit_id = {org_sql},
                    device_type = {self.db.quote(self.db.text(data.get('deviceType')))},
                    brand = {self.db.quote(self.db.text(data.get('brand')))},
                    model = {self.db.quote(self.db.text(data.get('model')))},
                    fixed_asset_code = {self.db.quote(self.db.text(data.get('fixedAssetCode')))},
                    sn_st = {self.db.quote(self.db.text(data.get('snSt')))},
                    location = {self.db.quote(self.db.text(data.get('location')))},
                    it_asset_status = {self.db.quote(status)},
                    is_active = 1
                WHERE computer_id = @sync_target_id AND @sync_can_apply = 1;
                """

        return f"""
        {mapping_sql}
        {body}
        INSERT INTO sync_entity_mapping (
          source_code, entity_type, external_id, target_entity_id, last_synced_at
        )
        SELECT
          {self.db.quote(source_code)}, {self.db.quote(entity_type)},
          {self.db.quote(external_id)}, @sync_target_id, CURRENT_TIMESTAMP
        FROM DUAL
        WHERE @sync_target_id > 0 AND @sync_can_apply = 1
        ON DUPLICATE KEY UPDATE
          target_entity_id = VALUES(target_entity_id),
          last_synced_at = VALUES(last_synced_at);
        UPDATE sync_staging_record
        SET validation_status = 'applied',
            target_entity_id = NULLIF(@sync_target_id, 0),
            applied_at = CURRENT_TIMESTAMP
        WHERE staging_id = {staging_id} AND @sync_can_apply = 1;
        INSERT INTO audit_log (
          action_type, entity_type, entity_id, entity_name, summary, actor, source
        )
        SELECT
          'sync_applied', {self.db.quote(entity_type)}, CAST(@sync_target_id AS CHAR),
          {self.db.quote(external_id)},
          {self.db.quote(f'Sync {action} applied from {source_code}')},
          {self.db.quote(actor_name)}, 'sync'
        FROM DUAL
        WHERE @sync_target_id > 0 AND @sync_can_apply = 1;
        """

    def apply(self, run_id: object, context: dict) -> dict:
        run = self.get_run(run_id)
        if self.db.text(run.get("status")) in {"applied", "cancelled", "failed"}:
            raise self.conflict_error("This sync run cannot be applied again.")
        if self.db.integer(run.get("recordsInvalid"), 0) > 0:
            raise self.conflict_error("Fix or cancel invalid staged records before applying this sync run.")
        source_code = self.db.text(run.get("sourceCode"))
        valid_records = [
            item for item in run.get("records", []) if self.db.text(item.get("validationStatus")) == "valid"
        ]
        if not valid_records:
            raise self.conflict_error("This sync run has no valid staged records to apply.")
        record_sql = "\n".join(
            self._record_apply_sql(source_code, record, self.db.text(context.get("username")) or "sync")
            for record in valid_records
        )
        try:
            output = self.db.execute(
                f"""
                START TRANSACTION;
                SELECT status INTO @sync_run_status
                FROM sync_run
                WHERE sync_run_id = {self.db.quote(self.db.text(run_id))}
                FOR UPDATE;
                SET @sync_can_apply = IF(@sync_run_status = 'validated', 1, 0);
                {record_sql}
                UPDATE sync_run
                SET status = 'applied',
                    records_applied = {len(valid_records)},
                    completed_at = CURRENT_TIMESTAMP,
                    error_summary = ''
                WHERE sync_run_id = {self.db.quote(self.db.text(run_id))}
                  AND @sync_can_apply = 1;
                SELECT @sync_can_apply;
                COMMIT;
                """
            )
        except Exception as exc:
            self.db.execute(
                f"""
                UPDATE sync_run
                SET status = 'failed',
                    error_summary = {self.db.quote(str(exc)[:1000])},
                    completed_at = CURRENT_TIMESTAMP
                WHERE sync_run_id = {self.db.quote(self.db.text(run_id))};
                """
            )
            raise
        applied = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        if applied != 1:
            raise self.conflict_error("This sync run was already changed by another request.")
        return self.get_run(run_id)


@dataclass
class DataQualityService:
    db: SqlGateway
    api_error: type[Exception]

    def _actor_name(self, context: dict) -> str:
        return self.db.text(context.get("username")) or "web"

    def _label(self, labels: dict[str, str], value: object) -> str:
        code = self.db.text(value)
        return labels.get(code, code)

    def _upsert_issue(self, issue: dict) -> None:
        fingerprint = hashlib.sha256(
            f"{issue['rule']}:{issue['entityType']}:{issue.get('entityId') or ''}".encode("utf-8")
        ).hexdigest()
        self.db.execute(
            f"""
            INSERT INTO data_quality_issue (
              fingerprint, rule_code, severity, entity_type, entity_id, title, details,
              status, first_detected_at, last_detected_at
            )
            VALUES (
              {self.db.quote(fingerprint)}, {self.db.quote(issue['rule'])},
              {self.db.quote(issue['severity'])}, {self.db.quote(issue['entityType'])},
              {"NULL" if not issue.get('entityId') else self.db.integer(issue.get('entityId'), 0)},
              {self.db.quote(issue['title'])}, {self.db.json_value(issue.get('details') or {})},
              'open', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON DUPLICATE KEY UPDATE
              severity = VALUES(severity),
              title = VALUES(title),
              details = VALUES(details),
              status = 'open',
              last_detected_at = CURRENT_TIMESTAMP,
              resolved_at = NULL,
              resolved_by = NULL,
              resolution_result = NULL;
            """
        )

    def run(self) -> dict:
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        checks = [
            """
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'entityId', asset.computer_id,
              'title', CONCAT('设备已分配给非在职人员：', asset.device_name),
              'details', JSON_OBJECT('employeeId', employee.employee_id, 'employeeStatus', employee.employment_status)
            )), JSON_ARRAY())
            FROM computer_asset asset
            JOIN computer_assignment assignment
              ON assignment.computer_id = asset.computer_id
             AND assignment.returned_at IS NULL
             AND assignment.assignment_status = 'active'
            JOIN employee ON employee.employee_id = assignment.employee_id
            WHERE asset.is_active = 1
              AND (employee.is_active = 0 OR employee.employment_status <> 'active')
            """,
            """
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'entityId', computer_id,
              'title', CONCAT('办公终端缺少序列号和固定资产编号：', device_name),
              'details', JSON_OBJECT('deviceName', device_name)
            )), JSON_ARRAY())
            FROM computer_asset
            WHERE is_active = 1
              AND COALESCE(sn_st, '') = ''
              AND COALESCE(fixed_asset_code, '') = ''
            """,
            """
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'entityId', ticket_id,
              'title', CONCAT('已解决工单缺少解决方案：', ticket_number),
              'details', JSON_OBJECT('ticketNumber', ticket_number)
            )), JSON_ARRAY())
            FROM itil_ticket
            WHERE status = 'resolved'
              AND COALESCE(TRIM(resolution), '') = ''
            """,
        ]
        rules = [
            ("computer_assigned_to_inactive_employee", "high", "computer"),
            ("computer_missing_identity", "medium", "computer"),
            ("resolved_ticket_missing_resolution", "medium", "itil_ticket"),
        ]
        detected = 0
        for sql, (rule_code, severity, entity_type) in zip(checks, rules):
            rows = self.db.json(sql, []) or []
            for row in rows:
                self._upsert_issue(
                    {
                        "rule": rule_code,
                        "severity": severity,
                        "entityType": entity_type,
                        "entityId": row.get("entityId"),
                        "title": self.db.text(row.get("title")),
                        "details": row.get("details") or {},
                    }
                )
                detected += 1
        rule_sql = ", ".join(self.db.quote(rule[0]) for rule in rules)
        self.db.execute(
            f"""
            UPDATE data_quality_issue
            SET status = 'resolved',
                resolved_at = CURRENT_TIMESTAMP
            WHERE status = 'open'
              AND rule_code IN ({rule_sql})
              AND last_detected_at < {self.db.quote(started_at)};
            """
        )
        return {"issuesDetected": detected}

    def list_issues(self, status: str = "open") -> list[dict]:
        if status not in {"open", "resolved", "ignored", "all"}:
            raise self.api_error("不支持的数据质量问题状态。")
        condition = "" if status == "all" else f"WHERE issue.status = {self.db.quote(status)}"
        issues = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(issue.issue_id AS CHAR),
                  'ruleCode', issue.rule_code,
                  'severity', issue.severity,
                  'entityType', issue.entity_type,
                  'entityId', COALESCE(CAST(issue.entity_id AS CHAR), ''),
                  'title', issue.title,
                  'details', COALESCE(issue.details, JSON_OBJECT()),
                  'status', issue.status,
                  'firstDetectedAt', CAST(issue.first_detected_at AS CHAR),
                  'lastDetectedAt', CAST(issue.last_detected_at AS CHAR),
                  'resolvedAt', COALESCE(CAST(issue.resolved_at AS CHAR), ''),
                  'resolutionResult', COALESCE(issue.resolution_result, '')
                )), JSON_ARRAY())
                FROM (
                  SELECT *
                  FROM data_quality_issue issue
                  {condition}
                  ORDER BY FIELD(severity, 'high', 'medium', 'low'), last_detected_at DESC
                  LIMIT 500
                ) issue
                """,
                [],
            )
            or []
        )
        for issue in issues:
            issue["severityLabel"] = self._label(QUALITY_SEVERITY_LABELS, issue.get("severity"))
            issue["ruleLabel"] = self._label(QUALITY_RULE_LABELS, issue.get("ruleCode"))
            issue["entityTypeLabel"] = self._label(QUALITY_ENTITY_TYPE_LABELS, issue.get("entityType"))
            issue["statusLabel"] = self._label(QUALITY_STATUS_LABELS, issue.get("status"))
        return issues

    def resolve(self, issue_id: object, payload: dict, context: dict, ignored: bool = False) -> dict:
        issue_id_int = self.db.integer(issue_id, 0)
        if issue_id_int <= 0:
            raise self.api_error("数据质量问题不存在。")
        resolution_result = self.db.text(payload.get("resolutionResult")).strip()
        if not ignored and not resolution_result:
            raise self.api_error("请填写处理结果后再解决问题。")
        if len(resolution_result) > 2000:
            raise self.api_error("处理结果不能超过 2000 个字符。")
        issue = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'ruleCode', rule_code,
              'title', title,
              'status', status,
              'resolutionResult', COALESCE(resolution_result, '')
            )
            FROM data_quality_issue
            WHERE issue_id = {issue_id_int}
            """,
            None,
        )
        if not issue:
            raise self.api_error("数据质量问题不存在。")
        if self.db.text(issue.get("status")) != "open":
            raise self.api_error("数据质量问题已经处理，无需重复提交。")

        status = "ignored" if ignored else "resolved"
        actor_id = self.db.integer(context.get("id"), 0)
        statements = [
            "START TRANSACTION",
            f"""
            UPDATE data_quality_issue
            SET status = {self.db.quote(status)},
                resolved_at = CURRENT_TIMESTAMP,
                resolved_by = {actor_id if actor_id > 0 else "NULL"},
                resolution_result = {self.db.quote(resolution_result) if not ignored else "NULL"}
            WHERE issue_id = {issue_id_int}
              AND status = 'open'
            """,
            "SET @quality_issue_changed = ROW_COUNT()",
        ]
        if not ignored:
            statements.append(
                f"""
                INSERT INTO audit_log (
                  action_type, entity_type, entity_id, entity_name,
                  old_value, new_value, summary, actor, source
                )
                SELECT
                  'data_quality_issue_resolved',
                  'data_quality_issue',
                  {self.db.quote(str(issue_id_int))},
                  {self.db.quote(self.db.text(issue.get("title")) or f"数据质量问题 #{issue_id_int}")},
                  {self.db.json_value({"status": "open", "ruleCode": self.db.text(issue.get("ruleCode"))})},
                  {self.db.json_value({"status": "resolved", "resolutionResult": resolution_result})},
                  {self.db.quote(f"数据质量问题已解决：{self._label(QUALITY_RULE_LABELS, issue.get('ruleCode'))}。")},
                  {self.db.quote(self._actor_name(context))},
                  'api'
                FROM DUAL
                WHERE @quality_issue_changed = 1
                """
            )
        statements.extend(["COMMIT", "SELECT @quality_issue_changed"])
        output = self.db.execute(";\n".join(statement.strip() for statement in statements) + ";")
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        changed = self.db.integer(lines[-1] if lines else 0, 0)
        if changed != 1:
            raise self.api_error("数据质量问题已经被其他操作处理。")
        return {
            "id": str(issue_id_int),
            "status": status,
            "statusLabel": self._label(QUALITY_STATUS_LABELS, status),
            "resolutionResult": resolution_result,
        }
