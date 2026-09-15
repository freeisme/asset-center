from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from datetime import datetime

from .scope import OrganizationScopeService
from .sql import SqlGateway, parse_bool


TICKET_TRANSITIONS = {
    "new": {"assigned", "in_progress", "cancelled"},
    "assigned": {"in_progress", "pending", "resolved", "cancelled"},
    "in_progress": {"pending", "resolved", "cancelled"},
    "pending": {"in_progress", "resolved", "cancelled"},
    "resolved": {"closed", "in_progress"},
    "closed": set(),
    "cancelled": set(),
}


def priority_from(impact: str, urgency: str) -> str:
    if impact == "high" and urgency == "high":
        return "high"
    if impact == "low" and urgency == "low":
        return "low"
    return "medium"


@dataclass
class TicketService:
    db: SqlGateway
    scope: OrganizationScopeService
    api_error: type[Exception]
    conflict_error: type[Exception]
    forbidden_error: type[Exception]
    service: Any | None = None

    def _actor_id(self, context: dict) -> int:
        return self.db.integer(context.get("id"), 0)

    def _actor_name(self, context: dict) -> str:
        return self.db.text(context.get("username")) or "web"

    def _actor_employee_id(self, context: dict) -> int:
        employee = context.get("employee") if isinstance(context.get("employee"), dict) else {}
        return self.db.integer(employee.get("employeeId"), 0)

    def _ticket_row(self, ticket_id: object) -> dict:
        ticket_id_int = self.db.integer(ticket_id, 0)
        ticket = self.db.json(
            f"""
            SELECT JSON_OBJECT(
              'id', CAST(ticket.ticket_id AS CHAR),
              'number', ticket.ticket_number,
              'type', ticket.ticket_type,
              'title', ticket.title,
              'description', ticket.description,
              'status', ticket.status,
              'impact', ticket.impact,
              'urgency', ticket.urgency,
              'priority', ticket.priority,
              'source', ticket.source,
              'requesterEmployeeId', COALESCE(CAST(ticket.requester_employee_id AS CHAR), ''),
              'requesterName', COALESCE(requester.employee_name, ''),
              'orgId', COALESCE(CAST(ticket.org_unit_id AS CHAR), ''),
              'orgName', COALESCE(org.org_name, ''),
              'assignedToUserId', COALESCE(CAST(ticket.assigned_to_user_id AS CHAR), ''),
              'assignedToName', COALESCE(assignee.display_name, ''),
              'createdByUserId', COALESCE(CAST(ticket.created_by AS CHAR), ''),
              'relatedComputerId', COALESCE(CAST(ticket.related_computer_id AS CHAR), ''),
              'relatedComputerName', COALESCE(computer.device_name, ''),
              'resolution', COALESCE(ticket.resolution, ''),
              'resolvedAt', COALESCE(CAST(ticket.resolved_at AS CHAR), ''),
              'closedAt', COALESCE(CAST(ticket.closed_at AS CHAR), ''),
              'createdAt', CAST(ticket.created_at AS CHAR),
              'updatedAt', CAST(ticket.updated_at AS CHAR),
              'formId', COALESCE(CAST(extension.form_id AS CHAR), ''),
              'formCode', COALESCE(form.form_code, ''),
              'formName', COALESCE(form.form_name, ''),
              'customFields', COALESCE(extension.custom_fields, JSON_OBJECT()),
              'slaPolicyId', COALESCE(CAST(extension.sla_policy_id AS CHAR), ''),
              'slaDueAt', COALESCE(CAST(extension.resolution_due_at AS CHAR), ''),
              'slaState', CASE
                WHEN extension.resolution_due_at IS NULL THEN 'not_configured'
                WHEN ticket.status IN ('closed', 'cancelled') THEN 'stopped'
                WHEN CURRENT_TIMESTAMP > extension.resolution_due_at THEN 'breached'
                ELSE 'running'
              END,
              'slaRemainingMinutes', CASE
                WHEN extension.resolution_due_at IS NULL THEN NULL
                ELSE TIMESTAMPDIFF(MINUTE, CURRENT_TIMESTAMP, extension.resolution_due_at)
              END,
              'approvalStatus', COALESCE(extension.approval_status, 'not_required')
            )
            FROM itil_ticket ticket
            LEFT JOIN employee requester ON requester.employee_id = ticket.requester_employee_id
            LEFT JOIN org_unit org ON org.org_unit_id = ticket.org_unit_id
            LEFT JOIN user_account assignee ON assignee.user_id = ticket.assigned_to_user_id
            LEFT JOIN computer_asset computer ON computer.computer_id = ticket.related_computer_id
            LEFT JOIN service_ticket_extension extension ON extension.ticket_id = ticket.ticket_id
            LEFT JOIN service_form form ON form.form_id = extension.form_id
            WHERE ticket.ticket_id = {ticket_id_int}
            """,
            None,
        )
        if not ticket:
            raise self.api_error("Ticket does not exist.")
        return dict(ticket)

    def _assert_ticket_access(self, context: dict, ticket: dict) -> None:
        self.scope.assert_org_access(context, ticket.get("orgId"))
        scope = self.db.text((context.get("_permissionScopes") or {}).get("tickets")) or "all"
        actor_id = self._actor_id(context)
        if scope == "assigned" and self.db.integer(ticket.get("assignedToUserId"), 0) != actor_id:
            raise self.forbidden_error("You can only access tickets assigned to you.")
        if scope in {"own", "submitted"} and self.db.integer(ticket.get("createdByUserId"), 0) != actor_id:
            raise self.forbidden_error("You can only access tickets submitted by you.")

    def list_tickets(self, context: dict, filters: dict[str, list[str]]) -> list[dict]:
        conditions = ["1 = 1"]
        status = self.db.text((filters.get("status") or [""])[0])
        ticket_type = self.db.text((filters.get("type") or [""])[0])
        mine = self.db.text((filters.get("mine") or [""])[0])
        if status:
            if status not in TICKET_TRANSITIONS:
                raise self.api_error("Unsupported ticket status filter.")
            conditions.append(f"ticket.status = {self.db.quote(status)}")
        if ticket_type:
            if ticket_type not in {"incident", "request"}:
                raise self.api_error("Unsupported ticket type filter.")
            conditions.append(f"ticket.ticket_type = {self.db.quote(ticket_type)}")
        if mine == "1":
            conditions.append(f"ticket.assigned_to_user_id = {self._actor_id(context)}")
        scope = self.db.text((context.get("_permissionScopes") or {}).get("tickets")) or "all"
        if scope == "assigned":
            conditions.append(f"ticket.assigned_to_user_id = {self._actor_id(context)}")
        elif scope in {"own", "submitted"}:
            conditions.append(f"ticket.created_by = {self._actor_id(context)}")
        records = list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', CAST(ticket.ticket_id AS CHAR),
                  'number', ticket.ticket_number,
                  'type', ticket.ticket_type,
                  'title', ticket.title,
                  'status', ticket.status,
                  'impact', ticket.impact,
                  'urgency', ticket.urgency,
                  'priority', ticket.priority,
                  'requesterName', COALESCE(requester.employee_name, ''),
                  'orgId', COALESCE(CAST(ticket.org_unit_id AS CHAR), ''),
                  'orgName', COALESCE(org.org_name, ''),
                  'assignedToName', COALESCE(assignee.display_name, ''),
                  'relatedComputerName', COALESCE(computer.device_name, ''),
                  'createdAt', CAST(ticket.created_at AS CHAR),
                  'updatedAt', CAST(ticket.updated_at AS CHAR),
                  'slaDueAt', COALESCE(CAST(extension.resolution_due_at AS CHAR), ''),
                  'slaState', CASE
                    WHEN extension.resolution_due_at IS NULL THEN 'not_configured'
                    WHEN ticket.status IN ('closed', 'cancelled') THEN 'stopped'
                    WHEN CURRENT_TIMESTAMP > extension.resolution_due_at THEN 'breached'
                    ELSE 'running'
                  END,
                  'slaRemainingMinutes', CASE
                    WHEN extension.resolution_due_at IS NULL THEN NULL
                    ELSE TIMESTAMPDIFF(MINUTE, CURRENT_TIMESTAMP, extension.resolution_due_at)
                  END,
                  'approvalStatus', COALESCE(extension.approval_status, 'not_required')
                )), JSON_ARRAY())
                FROM (
                  SELECT ticket.*
                  FROM itil_ticket ticket
                  WHERE {" AND ".join(conditions)}
                  ORDER BY
                    FIELD(ticket.status, 'new', 'assigned', 'in_progress', 'pending', 'resolved', 'closed', 'cancelled'),
                    FIELD(ticket.priority, 'high', 'medium', 'low'),
                    ticket.updated_at DESC,
                    ticket.ticket_id DESC
                  LIMIT 500
                ) ticket
                LEFT JOIN employee requester ON requester.employee_id = ticket.requester_employee_id
                LEFT JOIN org_unit org ON org.org_unit_id = ticket.org_unit_id
                LEFT JOIN user_account assignee ON assignee.user_id = ticket.assigned_to_user_id
                LEFT JOIN computer_asset computer ON computer.computer_id = ticket.related_computer_id
                LEFT JOIN service_ticket_extension extension ON extension.ticket_id = ticket.ticket_id
                """,
                [],
            )
            or []
        )
        allowed = self.scope.permitted_org_ids(context)
        if allowed is None:
            return records
        return [item for item in records if self.db.integer(item.get("orgId"), 0) in allowed]

    def get_ticket(self, ticket_id: object, context: dict) -> dict:
        ticket = self._ticket_row(ticket_id)
        self._assert_ticket_access(context, ticket)
        history = self.db.json(
            f"""
            SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
              'id', CAST(history.history_id AS CHAR),
              'entryType', history.entry_type,
              'content', history.content,
              'oldValues', COALESCE(history.old_values, JSON_OBJECT()),
              'newValues', COALESCE(history.new_values, JSON_OBJECT()),
              'isPublic', history.is_public,
              'createdBy', COALESCE(user.display_name, ''),
              'createdAt', CAST(history.created_at AS CHAR)
            )), JSON_ARRAY())
            FROM (
              SELECT *
              FROM itil_ticket_history
              WHERE ticket_id = {self.db.integer(ticket_id, 0)}
              ORDER BY history_id ASC
            ) history
            LEFT JOIN user_account user ON user.user_id = history.created_by
            """,
            [],
        )
        ticket["history"] = history or []
        return ticket

    def create_ticket(self, payload: dict, context: dict) -> dict:
        ticket_type = self.db.text(payload.get("type")) or "incident"
        if ticket_type not in {"incident", "request"}:
            raise self.api_error("Ticket type must be incident or request.")
        title = self.db.text(payload.get("title"))
        description = self.db.text(payload.get("description"))
        if not title or not description:
            raise self.api_error("Ticket title and description are required.")
        impact = self.db.text(payload.get("impact")) or "medium"
        urgency = self.db.text(payload.get("urgency")) or "medium"
        source = self.db.text(payload.get("source")) or "portal"
        if impact not in {"low", "medium", "high"} or urgency not in {"low", "medium", "high"}:
            raise self.api_error("Unsupported impact or urgency.")
        if source not in {"portal", "phone", "email", "monitoring", "import"}:
            raise self.api_error("Unsupported ticket source.")
        requester_id = self.db.integer(payload.get("requesterEmployeeId"), 0)
        org_id = self.db.integer(payload.get("orgId"), 0)
        scope = self.db.text((context.get("_permissionScopes") or {}).get("tickets")) or "all"
        actor_employee_id = self._actor_employee_id(context)
        if scope in {"own", "submitted"}:
            if actor_employee_id <= 0:
                raise self.forbidden_error(
                    "A ticket submitter must bind an employee identity before submitting tickets."
                )
            if requester_id and requester_id != actor_employee_id:
                raise self.forbidden_error("You can only submit tickets for your bound employee identity.")
            requester_id = actor_employee_id
        if requester_id:
            requester = self.db.json(
                f"""
                SELECT JSON_OBJECT(
                  'orgId', COALESCE(org_unit_id, 0),
                  'status', employment_status
                )
                FROM employee
                WHERE employee_id = {requester_id} AND is_active = 1
                """,
                None,
            )
            if not requester:
                raise self.api_error("Requester employee does not exist.")
            requester_org_id = self.db.integer(requester.get("orgId"), 0)
            if org_id and requester_org_id and org_id != requester_org_id:
                raise self.api_error("Requester employee and ticket organization do not match.")
            if not org_id:
                org_id = requester_org_id
        self.scope.assert_org_access(context, org_id)
        computer_id = self.db.integer(payload.get("relatedComputerId"), 0)
        if computer_id:
            computer = self.db.json(
                f"""
                SELECT JSON_OBJECT('orgId', COALESCE(org_unit_id, 0))
                FROM computer_asset
                WHERE computer_id = {computer_id} AND is_active = 1
                """,
                None,
            )
            if not computer:
                raise self.api_error("Related computer does not exist.")
            self.scope.assert_org_access(context, computer.get("orgId"))
            if not org_id:
                org_id = self.db.integer(computer.get("orgId"), 0)
        priority = priority_from(impact, urgency)
        extension = (
            self.service.ticket_extension_values(payload, priority, context)
            if self.service is not None
            else {"formId": 0, "customFields": {}, "sla": {}}
        )
        output = self.db.execute(
            f"""
            START TRANSACTION;
            INSERT INTO itil_ticket (
              ticket_type, title, description, status, impact, urgency, priority, source,
              requester_employee_id, org_unit_id, related_computer_id, created_by
            )
            VALUES (
              {self.db.quote(ticket_type)}, {self.db.quote(title)}, {self.db.quote(description)},
              'new', {self.db.quote(impact)}, {self.db.quote(urgency)}, {self.db.quote(priority)},
              {self.db.quote(source)},
              {"NULL" if requester_id <= 0 else requester_id},
              {"NULL" if org_id <= 0 else org_id},
              {"NULL" if computer_id <= 0 else computer_id},
              {self._actor_id(context)}
            );
            SET @ticket_id = LAST_INSERT_ID();
            UPDATE itil_ticket
            SET ticket_number = CONCAT(
              {"'INC'" if ticket_type == 'incident' else "'REQ'"},
              '-', DATE_FORMAT(CURRENT_DATE, '%Y'), '-', LPAD(@ticket_id, 6, '0')
            )
            WHERE ticket_id = @ticket_id;
            INSERT INTO itil_ticket_history (
              ticket_id, entry_type, content, new_values, created_by
            )
            VALUES (
              @ticket_id, 'created', 'Ticket created',
              JSON_OBJECT('status', 'new', 'priority', {self.db.quote(priority)}),
              {self._actor_id(context)}
            );
            SELECT @ticket_id;
            COMMIT;
            """
        )
        ticket_id = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        created = self._ticket_row(ticket_id)
        if self.service is not None:
            self.service.save_ticket_extension(ticket_id, extension)
            self.service.start_approval("ticket", ticket_id, context)
            self.service.notify_record_change(
                "ticket",
                ticket_id,
                "新建工单",
                f"工单 {created.get('number') or ticket_id} 已创建。",
            )
        self.db.execute(
            f"""
            INSERT INTO audit_log (
              action_type, entity_type, entity_id, entity_name, summary, actor, source
            )
            VALUES (
              'ticket_created', 'itil_ticket', {self.db.quote(str(ticket_id))},
              {self.db.quote(self.db.text(created.get('number')))}, '工单已创建',
              {self.db.quote(self._actor_name(context))}, 'api'
            );
            """
        )
        return {"ticket": self.get_ticket(ticket_id, context)}

    def transition_ticket(self, ticket_id: object, payload: dict, context: dict) -> dict:
        ticket = self._ticket_row(ticket_id)
        self._assert_ticket_access(context, ticket)
        current_status = self.db.text(ticket.get("status"))
        next_status = self.db.text(payload.get("status"))
        if next_status not in TICKET_TRANSITIONS.get(current_status, set()):
            raise self.conflict_error(f"Invalid ticket transition: {current_status} -> {next_status}.")
        approval_status = self.db.text(ticket.get("approvalStatus")) or "not_required"
        if approval_status == "pending" and next_status != "cancelled":
            raise self.conflict_error("This ticket is waiting for approval and cannot be processed yet.")
        if approval_status == "rejected" and next_status != "cancelled":
            raise self.conflict_error("This ticket was rejected and can only be cancelled.")
        has_assignee_update = "assignedToUserId" in payload
        assignee_id = self.db.integer(payload.get("assignedToUserId"), 0)
        if has_assignee_update and assignee_id:
            account = self.db.scalar(
                f"SELECT COUNT(*) FROM user_account WHERE user_id = {assignee_id} AND is_active = 1;"
            )
            if account != 1:
                raise self.api_error("Assigned operator does not exist.")
        assignee_sql = "NULL" if assignee_id <= 0 else str(assignee_id)
        current_assignee_id = self.db.integer(ticket.get("assignedToUserId"), 0)
        history_assignee_sql = (
            assignee_sql
            if has_assignee_update
            else ("NULL" if current_assignee_id <= 0 else str(current_assignee_id))
        )
        resolution = self.db.text(payload.get("resolution"))
        if next_status == "resolved" and not resolution:
            raise self.api_error("A resolution is required before resolving a ticket.")
        note = self.db.text(payload.get("note"))
        ticket_id_int = self.db.integer(ticket_id, 0)
        values = [f"status = {self.db.quote(next_status)}"]
        if has_assignee_update:
            values.append(f"assigned_to_user_id = {assignee_sql}")
        if next_status == "resolved":
            values.extend(
                [
                    f"resolution = {self.db.quote(resolution)}",
                    "resolved_at = CURRENT_TIMESTAMP",
                    "closed_at = NULL",
                ]
            )
        elif next_status == "closed":
            values.append("closed_at = CURRENT_TIMESTAMP")
        elif next_status == "in_progress":
            values.extend(["resolved_at = NULL", "closed_at = NULL"])
        output = self.db.execute(
            f"""
            START TRANSACTION;
            UPDATE itil_ticket
            SET {", ".join(values)}
            WHERE ticket_id = {ticket_id_int}
              AND status = {self.db.quote(current_status)};
            SET @changed_count = ROW_COUNT();
            INSERT INTO itil_ticket_history (
              ticket_id, entry_type, content, old_values, new_values, created_by
            )
            SELECT
              {ticket_id_int},
              {"'resolution'" if next_status == 'resolved' else "'status_change'"},
              {self.db.quote(note or f"Status changed to {next_status}")},
              JSON_OBJECT('status', {self.db.quote(current_status)}),
              JSON_OBJECT('status', {self.db.quote(next_status)}, 'assignedToUserId', {history_assignee_sql}),
              {self._actor_id(context)}
            FROM DUAL
            WHERE @changed_count = 1;
            SELECT @changed_count;
            COMMIT;
            """
        )
        changed_count = self.db.integer(output.splitlines()[-1] if output else 0, 0)
        if changed_count != 1:
            raise self.conflict_error("Ticket changed by another request. Reload and try again.")
        if self.service is not None:
            self.service.notify_record_change(
                "ticket",
                ticket_id_int,
                "工单状态更新",
                f"工单状态已更新为 {next_status}。",
            )
        return {"ticket": self.get_ticket(ticket_id_int, context)}

    def add_note(self, ticket_id: object, payload: dict, context: dict) -> dict:
        ticket = self._ticket_row(ticket_id)
        self._assert_ticket_access(context, ticket)
        content = self.db.text(payload.get("content"))
        if not content:
            raise self.api_error("Ticket note cannot be empty.")
        is_public = 1 if parse_bool(payload.get("isPublic"), True) else 0
        self.db.execute(
            f"""
            START TRANSACTION;
            INSERT INTO itil_ticket_history (
              ticket_id, entry_type, content, is_public, created_by
            )
            VALUES (
              {self.db.integer(ticket_id, 0)}, 'note', {self.db.quote(content)},
              {is_public}, {self._actor_id(context)}
            );
            UPDATE itil_ticket
            SET updated_at = CURRENT_TIMESTAMP
            WHERE ticket_id = {self.db.integer(ticket_id, 0)};
            COMMIT;
            """
        )
        return {"ticket": self.get_ticket(ticket_id, context)}
