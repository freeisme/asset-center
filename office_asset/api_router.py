from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import ParseResult

from .asset_service import AssetService
from .inspection import InspectionService
from .operations import DataQualityService, SyncService
from .scope import OrganizationScopeService
from .sql import SqlGateway
from .service_management import ServiceManagementService
from .tickets import TicketService


@dataclass(frozen=True)
class ApiDependencies:
    db: SqlGateway
    api_error: type[Exception]
    conflict_error: type[Exception]
    forbidden_error: type[Exception]
    require_auth: Callable[[object], dict]
    require_role: Callable[..., None]
    require_permission: Callable[[dict, str, str], None]
    require_csrf: Callable[[object, dict], None]


class DomainApiRouter:
    def __init__(self, deps: ApiDependencies) -> None:
        self.deps = deps
        self.scope = OrganizationScopeService(deps.db, deps.forbidden_error)
        self.assets = AssetService(
            deps.db,
            self.scope,
            deps.api_error,
            deps.conflict_error,
            deps.forbidden_error,
        )
        self.service = ServiceManagementService(
            deps.db,
            self.scope,
            deps.api_error,
            deps.conflict_error,
            deps.forbidden_error,
        )
        self.tickets = TicketService(
            deps.db,
            self.scope,
            deps.api_error,
            deps.conflict_error,
            deps.forbidden_error,
            self.service,
        )
        self.sync = SyncService(deps.db, deps.api_error, deps.conflict_error)
        self.quality = DataQualityService(deps.db, deps.api_error)
        self.inspection = InspectionService(
            deps.db,
            self.scope,
            deps.api_error,
            deps.conflict_error,
            deps.forbidden_error,
        )

    def _authenticated(self, handler: object) -> dict:
        return self.deps.require_auth(handler)

    def _read_context(self, handler: object, module_code: str, action_code: str = "view") -> dict:
        context = self._authenticated(handler)
        self.deps.require_permission(context, module_code, action_code)
        return context

    def _write_context(self, handler: object, module_code: str, action_code: str) -> dict:
        context = self._read_context(handler, module_code, action_code)
        self.deps.require_csrf(handler, context)
        return context

    def _inventory_read_context(self, handler: object) -> dict:
        context = self._read_context(handler, "inventory_operations")
        self.deps.require_permission(context, "warehouse_management", "view")
        return context

    def _inventory_write_context(self, handler: object, action_code: str) -> dict:
        context = self._write_context(handler, "inventory_operations", action_code)
        self.deps.require_permission(context, "warehouse_management", "view")
        return context

    def _idempotency_key(self, handler: object) -> str:
        headers = getattr(handler, "headers", None)
        return str(headers.get("Idempotency-Key", "") if headers else "").strip()

    def _payload(self, handler: object) -> dict:
        return getattr(handler, "read_json")()

    def dispatch(self, handler: object, parsed: ParseResult, params: dict[str, list[str]]) -> bool:
        path = parsed.path.rstrip("/") or "/"
        method = str(getattr(handler, "command", "GET")).upper()
        send_json = getattr(handler, "send_json")

        if path == "/api/tickets" and method == "GET":
            send_json({"tickets": self.tickets.list_tickets(self._read_context(handler, "tickets"), params)})
            return True
        if path == "/api/tickets" and method == "POST":
            context = self._write_context(handler, "tickets", "create")
            send_json(self.tickets.create_ticket(self._payload(handler), context), status=201)
            return True
        if path.startswith("/api/tickets/"):
            parts = path.split("/")
            if len(parts) == 4 and method == "GET":
                send_json({"ticket": self.tickets.get_ticket(parts[3], self._read_context(handler, "tickets"))})
                return True
            if len(parts) == 5 and parts[4] == "notes" and method == "POST":
                context = self._write_context(handler, "tickets", "update")
                send_json(self.tickets.add_note(parts[3], self._payload(handler), context))
                return True
            if len(parts) == 5 and parts[4] == "transitions" and method == "POST":
                context = self._write_context(handler, "tickets", "update")
                send_json(self.tickets.transition_ticket(parts[3], self._payload(handler), context))
                return True

        if path == "/api/service/forms" and method == "GET":
            record_type = str((params.get("recordType") or [""])[0])
            for_submission = str((params.get("forSubmission") or [""])[0]) == "1"
            if for_submission:
                module_code = {"ticket": "tickets", "change": "changes", "problem": "problems"}.get(record_type)
                if not module_code:
                    raise self.deps.api_error("recordType is required for submission forms.")
                context = self._read_context(handler, module_code)
                send_json({"forms": self.service.list_forms_for_submission(record_type, context)})
            else:
                context = self._read_context(handler, "forms")
                send_json({"forms": self.service.list_forms(record_type, context)})
            return True
        if path == "/api/service/forms" and method == "POST":
            context = self._write_context(handler, "forms", "create")
            send_json({"form": self.service.create_form(self._payload(handler), context)}, status=201)
            return True
        if path.startswith("/api/service/forms/"):
            parts = path.split("/")
            form_id = parts[4] if len(parts) > 4 else ""
            if len(parts) == 6 and parts[5] == "permissions" and method == "GET":
                context = self._read_context(handler, "forms", "update")
                self.service.assert_form_permission(form_id, context, "update")
                send_json({"permissions": self.service.list_form_permissions(form_id)})
                return True
            if len(parts) == 6 and parts[5] == "permissions" and method == "PUT":
                context = self._write_context(handler, "forms", "update")
                send_json(
                    {
                        "permissions": self.service.replace_form_permissions(
                            form_id,
                            self._payload(handler).get("permissions"),
                            context,
                        )
                    }
                )
                return True
            if method == "GET":
                context = self._read_context(handler, "forms")
                self.service.assert_form_permission(form_id, context, "view")
                send_json({"form": self.service.get_form(form_id)})
                return True
            if method == "PUT":
                context = self._write_context(handler, "forms", "update")
                self.service.assert_form_permission(form_id, context, "update")
                send_json({"form": self.service.update_form(form_id, self._payload(handler), context)})
                return True

        if path == "/api/changes" and method == "GET":
            send_json({"changes": self.service.list_changes(self._read_context(handler, "changes"))})
            return True
        if path == "/api/changes" and method == "POST":
            context = self._write_context(handler, "changes", "create")
            payload = self._payload(handler)
            if self.deps.db.integer(payload.get("relatedTicketId"), 0):
                self.deps.require_permission(context, "tickets", "view")
            send_json({"change": self.service.create_change(payload, context)}, status=201)
            return True
        if path.startswith("/api/changes/"):
            parts = path.split("/")
            if len(parts) == 4 and method == "GET":
                context = self._read_context(handler, "changes")
                change = self.service._change_row(parts[3])
                self.service._assert_record_access(context, "changes", change)
                send_json({"change": change})
                return True
            if len(parts) == 5 and parts[4] == "transitions" and method == "POST":
                context = self._write_context(handler, "changes", "update")
                send_json({"change": self.service.transition_change(parts[3], self._payload(handler), context)})
                return True

        if path == "/api/problems" and method == "GET":
            send_json({"problems": self.service.list_problems(self._read_context(handler, "problems"))})
            return True
        if path == "/api/problems" and method == "POST":
            context = self._write_context(handler, "problems", "create")
            payload = self._payload(handler)
            if self.deps.db.integer(payload.get("relatedTicketId"), 0):
                self.deps.require_permission(context, "tickets", "view")
            send_json({"problem": self.service.create_problem(payload, context)}, status=201)
            return True
        if path.startswith("/api/problems/"):
            parts = path.split("/")
            if len(parts) == 4 and method == "GET":
                context = self._read_context(handler, "problems")
                problem = self.service._problem_row(parts[3])
                self.service._assert_record_access(context, "problems", problem)
                send_json({"problem": problem})
                return True
            if len(parts) == 5 and parts[4] == "transitions" and method == "POST":
                context = self._write_context(handler, "problems", "update")
                send_json({"problem": self.service.transition_problem(parts[3], self._payload(handler), context)})
                return True

        if path == "/api/knowledge" and method == "GET":
            send_json({"articles": self.service.list_articles(params, self._read_context(handler, "knowledge"))})
            return True
        if path == "/api/knowledge" and method == "POST":
            context = self._write_context(handler, "knowledge", "create")
            send_json({"article": self.service.create_article(self._payload(handler), context)}, status=201)
            return True
        if path.startswith("/api/knowledge/"):
            parts = path.split("/")
            if len(parts) == 4 and method == "GET":
                context = self._read_context(handler, "knowledge")
                article = self.service.article(parts[3])
                self.service.assert_article_read_access(article, context)
                send_json({"article": article})
                return True
            if len(parts) == 4 and method == "PUT":
                context = self._write_context(handler, "knowledge", "update")
                send_json({"article": self.service.update_article(parts[3], self._payload(handler), context)})
                return True
            if len(parts) == 5 and parts[4] == "transitions" and method == "POST":
                context = self._write_context(handler, "knowledge", "approve")
                send_json({"article": self.service.transition_article(parts[3], self._payload(handler), context)})
                return True

        if path == "/api/sla/policies" and method == "GET":
            self._read_context(handler, "sla")
            send_json({"policies": self.service.list_sla_policies()})
            return True
        if path == "/api/sla/policies" and method == "POST":
            context = self._write_context(handler, "sla", "create")
            send_json({"policy": self.service.save_sla_policy(self._payload(handler), context)}, status=201)
            return True
        if path.startswith("/api/sla/policies/") and method == "PUT":
            context = self._write_context(handler, "sla", "update")
            policy_id = path.split("/")[-1]
            send_json({"policy": self.service.save_sla_policy(self._payload(handler), context, policy_id)})
            return True

        if path == "/api/approval-workflows" and method == "GET":
            self._read_context(handler, "approvals")
            send_json({"workflows": self.service.list_workflows()})
            return True
        if path == "/api/approval-workflows" and method == "POST":
            context = self._write_context(handler, "approvals", "create")
            send_json({"workflow": self.service.save_workflow(self._payload(handler), context)}, status=201)
            return True
        if path.startswith("/api/approval-workflows/") and method == "PUT":
            context = self._write_context(handler, "approvals", "update")
            workflow_id = path.split("/")[-1]
            send_json({"workflow": self.service.save_workflow(self._payload(handler), context, workflow_id)})
            return True
        if path == "/api/approvals" and method == "GET":
            send_json({"approvals": self.service.list_approvals(self._read_context(handler, "approvals"))})
            return True
        if path.startswith("/api/approvals/") and path.endswith("/decision") and method == "POST":
            context = self._write_context(handler, "approvals", "approve")
            approval_id = path.split("/")[-2]
            send_json({"approval": self.service.decide_approval(approval_id, self._payload(handler), context)})
            return True

        if path == "/api/notifications" and method == "GET":
            send_json({"notifications": self.service.list_notifications(self._read_context(handler, "notifications"))})
            return True
        if path.startswith("/api/notifications/") and path.endswith("/read") and method == "POST":
            context = self._write_context(handler, "notifications", "update")
            notification_id = path.split("/")[-2]
            send_json(self.service.mark_notification_read(notification_id, context))
            return True

        if path == "/api/inventory/warehouses" and method == "GET":
            send_json(
                {"warehouses": self.assets.list_warehouses(self._read_context(handler, "warehouse_management"))}
            )
            return True
        if path == "/api/inventory/warehouses" and method == "POST":
            context = self._write_context(handler, "warehouse_management", "create")
            send_json(self.assets.save_warehouse(None, self._payload(handler), context), status=201)
            return True
        if path.startswith("/api/inventory/warehouses/"):
            parts = path.split("/")
            if len(parts) == 6 and parts[5] == "stock" and method == "GET":
                context = self._read_context(handler, "warehouse_management")
                send_json({"stock": self.assets.list_warehouse_stock(parts[4], context)})
                return True
            if len(parts) == 5 and method == "PUT":
                context = self._write_context(handler, "warehouse_management", "update")
                send_json(self.assets.save_warehouse(parts[4], self._payload(handler), context))
                return True
            if len(parts) == 5 and method == "DELETE":
                context = self._write_context(handler, "warehouse_management", "delete")
                send_json(self.assets.delete_warehouse(parts[4], context))
                return True
        if path == "/api/inventory/transfers" and method == "POST":
            context = self._inventory_write_context(handler, "update")
            self.deps.require_permission(context, "warehouse_management", "create")
            send_json(
                self.assets.transfer_inventory(
                    self._payload(handler), context, self._idempotency_key(handler)
                ),
                status=201,
            )
            return True

        if path == "/api/inventory/allocations" and method == "GET":
            active_only = str((params.get("status") or ["active"])[0]) != "all"
            send_json({"allocations": self.assets.list_allocations(self._inventory_read_context(handler), active_only)})
            return True
        if path == "/api/inventory/allocations" and method == "POST":
            context = self._inventory_write_context(handler, "create")
            send_json(
                self.assets.allocate_inventory(
                    self._payload(handler), context, self._idempotency_key(handler)
                ),
                status=201,
            )
            return True
        if path.startswith("/api/inventory/allocations/") and path.endswith("/return") and method == "POST":
            allocation_id = path.split("/")[-2]
            context = self._inventory_write_context(handler, "update")
            send_json(
                self.assets.return_inventory(
                    allocation_id, self._payload(handler), context, self._idempotency_key(handler)
                )
            )
            return True
        if path.startswith("/api/inventory/usage/") and path.endswith("/return") and method == "POST":
            parts = path.split("/")
            if len(parts) != 7 or parts[3] != "usage" or parts[6] != "return":
                raise self.deps.api_error("Invalid inventory usage return path.")
            allocation_type, usage_record_id = parts[4], parts[5]
            context = self._inventory_write_context(handler, "update")
            send_json(
                self.assets.return_usage_inventory(
                    allocation_type,
                    usage_record_id,
                    self._payload(handler),
                    context,
                    self._idempotency_key(handler),
                )
            )
            return True
        if path.startswith("/api/inventory/usage/") and path.endswith("/scrap") and method == "POST":
            parts = path.split("/")
            if len(parts) != 7 or parts[3] != "usage" or parts[6] != "scrap":
                raise self.deps.api_error("Invalid inventory usage scrap path.")
            allocation_type, usage_record_id = parts[4], parts[5]
            context = self._write_context(handler, "scrap_management", "create")
            self.deps.require_permission(context, "inventory_operations", "view")
            send_json(
                self.assets.scrap_inventory_usage(
                    allocation_type,
                    usage_record_id,
                    self._payload(handler),
                    context,
                    self._idempotency_key(handler),
                ),
                status=201,
            )
            return True
        if path == "/api/inventory/receipts" and method == "POST":
            context = self._inventory_write_context(handler, "create")
            send_json(
                self.assets.receive_inventory(
                    self._payload(handler), context, self._idempotency_key(handler)
                ),
                status=201,
            )
            return True
        if path == "/api/inventory/adjustments" and method == "POST":
            context = self._inventory_write_context(handler, "update")
            send_json(
                self.assets.adjust_inventory(
                    self._payload(handler), context, self._idempotency_key(handler)
                )
            )
            return True
        if path.startswith("/api/inventory/movement-logs/") and path.endswith("/note-corrections") and method == "POST":
            parts = path.split("/")
            if len(parts) != 6 or parts[3] != "movement-logs" or parts[5] != "note-corrections":
                raise self.deps.api_error("Invalid inventory movement note correction path.")
            context = self._inventory_write_context(handler, "update")
            send_json(
                self.assets.add_inventory_movement_note_correction(
                    parts[4], self._payload(handler), context
                ),
                status=201,
            )
            return True

        if path == "/api/scrap-reasons" and method == "GET":
            context = self._read_context(handler, "scrap_management")
            send_json({"reasons": self.assets.list_scrap_reasons(context)})
            return True
        if path == "/api/scrap-records" and method == "GET":
            context = self._read_context(handler, "scrap_management")
            kind = str((params.get("kind") or [""])[0])
            limit = str((params.get("limit") or ["500"])[0])
            send_json({"records": self.assets.list_scrap_records(context, kind, limit)})
            return True
        if path.startswith("/api/scrap-records/") and method == "GET":
            parts = path.split("/")
            if len(parts) != 4 or not parts[3]:
                raise self.deps.api_error("Invalid scrap record path.")
            context = self._read_context(handler, "scrap_management")
            send_json({"record": self.assets.get_scrap_record(parts[3], context)})
            return True

        # 巡检管理：机房、弱电间、机柜、巡检模板与巡检任务。
        if path == "/api/inspection/sites" and method == "GET":
            context = self._read_context(handler, "inspection_management")
            send_json({"sites": self.inspection.list_sites(context, params)})
            return True
        if path == "/api/inspection/sites" and method == "POST":
            context = self._write_context(handler, "inspection_management", "create")
            send_json(self.inspection.create_site(self._payload(handler), context), status=201)
            return True
        if path.startswith("/api/inspection/sites/") and method == "PUT":
            site_id = path.split("/")[-1]
            context = self._write_context(handler, "inspection_management", "update")
            send_json(self.inspection.update_site(site_id, self._payload(handler), context))
            return True

        if path == "/api/inspection/racks" and method == "GET":
            context = self._read_context(handler, "inspection_management")
            send_json({"racks": self.inspection.list_racks(context, params)})
            return True
        if path == "/api/inspection/racks" and method == "POST":
            context = self._write_context(handler, "inspection_management", "create")
            send_json(self.inspection.create_rack(self._payload(handler), context), status=201)
            return True
        if path.startswith("/api/inspection/racks/") and method == "PUT":
            rack_id = path.split("/")[-1]
            context = self._write_context(handler, "inspection_management", "update")
            send_json(self.inspection.update_rack(rack_id, self._payload(handler), context))
            return True

        if path == "/api/inspection/templates" and method == "GET":
            context = self._read_context(handler, "inspection_management")
            send_json({"templates": self.inspection.list_templates(context)})
            return True
        if path == "/api/inspection/templates" and method == "POST":
            context = self._write_context(handler, "inspection_management", "create")
            send_json(self.inspection.create_template(self._payload(handler), context), status=201)
            return True
        if path.startswith("/api/inspection/templates/"):
            template_id = path.split("/")[-1]
            if method == "GET":
                context = self._read_context(handler, "inspection_management")
                send_json({"template": self.inspection.get_template(template_id, context)})
                return True
            if method == "PUT":
                context = self._write_context(handler, "inspection_management", "update")
                send_json(self.inspection.update_template(template_id, self._payload(handler), context))
                return True

        if path == "/api/inspection/tasks" and method == "GET":
            context = self._read_context(handler, "inspection_management")
            send_json({"tasks": self.inspection.list_tasks(context, params)})
            return True
        if path == "/api/inspection/tasks" and method == "POST":
            context = self._write_context(handler, "inspection_management", "create")
            send_json(
                self.inspection.start_task(
                    self._payload(handler),
                    context,
                    self._idempotency_key(handler),
                ),
                status=201,
            )
            return True
        if path.startswith("/api/inspection/tasks/"):
            parts = path.split("/")
            if len(parts) == 8 and parts[5] == "items" and parts[7] == "check" and method == "POST":
                context = self._write_context(handler, "inspection_management", "update")
                send_json(
                    self.inspection.check_item(
                        parts[4],
                        parts[6],
                        self._payload(handler),
                        context,
                    )
                )
                return True
            if len(parts) == 6 and parts[5] == "submit" and method == "POST":
                context = self._write_context(handler, "inspection_management", "update")
                send_json(self.inspection.submit_task(parts[4], self._payload(handler), context))
                return True
            if len(parts) == 6 and parts[5] == "void" and method == "POST":
                context = self._write_context(handler, "inspection_management", "delete")
                send_json(self.inspection.void_task(parts[4], self._payload(handler), context))
                return True
            if len(parts) == 5 and method == "GET":
                context = self._read_context(handler, "inspection_management")
                send_json({"task": self.inspection.get_task(parts[4], context)})
                return True

        if path.startswith("/api/computers/") and path.endswith("/movement-history") and method == "GET":
            computer_id = path.split("/")[-2]
            context = self._read_context(handler, "it_assets")
            send_json({"events": self.assets.computer_movement_history(computer_id, context)})
            return True
        if path.startswith("/api/computers/") and path.endswith("/assignments") and method == "POST":
            computer_id = path.split("/")[-2]
            context = self._write_context(handler, "inventory_operations", "create")
            send_json(
                self.assets.assign_computer(
                    computer_id, self._payload(handler), context, self._idempotency_key(handler)
                ),
                status=201,
            )
            return True
        if path.startswith("/api/computers/") and path.endswith("/assignments/return") and method == "POST":
            computer_id = path.split("/")[-3]
            context = self._write_context(handler, "inventory_operations", "update")
            send_json(
                self.assets.return_computer(
                    computer_id, self._payload(handler), context, self._idempotency_key(handler)
                )
            )
            return True
        if path.startswith("/api/computers/") and path.endswith("/scrap") and method == "POST":
            computer_id = path.split("/")[-2]
            context = self._write_context(handler, "scrap_management", "create")
            self.deps.require_permission(context, "it_assets", "view")
            send_json(
                self.assets.scrap_computer(
                    computer_id, self._payload(handler), context, self._idempotency_key(handler)
                ),
                status=201,
            )
            return True

        if path.startswith("/api/employees/") and path.endswith("/offboard") and method == "POST":
            parts = path.split("/")
            if len(parts) != 5 or parts[2] != "employees" or parts[4] != "offboard":
                raise self.deps.api_error("Invalid employee offboarding path.")
            context = self._write_context(handler, "employees", "update")
            self.deps.require_permission(context, "warehouse_management", "view")
            send_json(
                self.assets.offboard_employee(
                    parts[3], self._payload(handler), context, self._idempotency_key(handler)
                )
            )
            return True
        if path.startswith("/api/employees/") and path.endswith("/offboarding-preview") and method == "GET":
            parts = path.split("/")
            if len(parts) != 5 or parts[2] != "employees" or parts[4] != "offboarding-preview":
                raise self.deps.api_error("Invalid employee offboarding preview path.")
            context = self._read_context(handler, "employees", "update")
            self.deps.require_permission(context, "warehouse_management", "view")
            send_json(self.assets.offboarding_preview(parts[3], context))
            return True

        if path.startswith("/api/resources/"):
            parts = path.split("/")
            resource_modules = {
                "computer": "it_assets",
                "employee": "employees",
                "organization": "organizations",
                "inventory-type": "inventory_catalog",
                "inventory-brand": "inventory_catalog",
                "inventory-model": "inventory_catalog",
            }
            resource_type = parts[3] if len(parts) >= 4 else ""
            module_code = resource_modules.get(resource_type)
            if not module_code:
                return False
            if len(parts) == 4 and method == "POST":
                context = self._write_context(handler, module_code, "create")
                send_json(self.assets.save_resource(parts[3], None, self._payload(handler), context), status=201)
                return True
            if len(parts) == 5 and method == "PUT":
                context = self._write_context(handler, module_code, "update")
                send_json(self.assets.save_resource(parts[3], parts[4], self._payload(handler), context))
                return True

        if path == "/api/relations" and method == "GET":
            context = self._read_context(handler, "organizations")
            entity_type = str((params.get("entityType") or [""])[0])
            entity_id = str((params.get("entityId") or [""])[0])
            send_json({"relations": self.assets.list_relations(entity_type, entity_id, context)})
            return True
        if path == "/api/relations" and method == "POST":
            context = self._write_context(handler, "organizations", "create")
            send_json(self.assets.add_relation(self._payload(handler), context), status=201)
            return True

        if path == "/api/sync-runs" and method == "GET":
            self._read_context(handler, "sync")
            send_json({"runs": self.sync.list_runs()})
            return True
        if path == "/api/sync-runs" and method == "POST":
            context = self._write_context(handler, "sync", "create")
            send_json({"run": self.sync.stage(self._payload(handler), context)}, status=201)
            return True
        if path.startswith("/api/sync-runs/") and path.endswith("/apply") and method == "POST":
            context = self._write_context(handler, "sync", "approve")
            run_id = path.split("/")[-2]
            send_json({"run": self.sync.apply(run_id, context)})
            return True
        if path.startswith("/api/sync-runs/") and method == "GET":
            self._read_context(handler, "sync")
            send_json({"run": self.sync.get_run(path.split("/")[-1])})
            return True

        if path == "/api/data-quality/issues" and method == "GET":
            self._read_context(handler, "quality")
            status = str((params.get("status") or ["open"])[0])
            send_json({"issues": self.quality.list_issues(status)})
            return True
        if path == "/api/data-quality/run" and method == "POST":
            self._write_context(handler, "quality", "update")
            send_json(self.quality.run())
            return True
        if path.startswith("/api/data-quality/issues/") and path.endswith("/resolve") and method == "POST":
            context = self._write_context(handler, "quality", "approve")
            issue_id = path.split("/")[-2]
            send_json(self.quality.resolve(issue_id, self._payload(handler), context, ignored=False))
            return True
        if path.startswith("/api/data-quality/issues/") and path.endswith("/ignore") and method == "POST":
            context = self._write_context(handler, "quality", "approve")
            issue_id = path.split("/")[-2]
            send_json(self.quality.resolve(issue_id, self._payload(handler), context, ignored=True))
            return True

        if path.startswith("/api/user-org-scopes/"):
            user_id = path.split("/")[-1]
            if method == "GET":
                self._read_context(handler, "user_management", "view")
                send_json({"scopes": self.scope.get_user_scopes(user_id)})
                return True
            if method == "PUT":
                self._write_context(handler, "user_management", "update")
                payload = self._payload(handler)
                scopes = payload.get("scopes")
                if not isinstance(scopes, list):
                    raise self.deps.api_error("scopes must be an array.")
                send_json({"scopes": self.scope.replace_user_scopes(user_id, scopes)})
                return True

        return False
