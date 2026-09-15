from __future__ import annotations

from dataclasses import dataclass

from .sql import SqlGateway, parse_bool


@dataclass
class OrganizationScopeService:
    db: SqlGateway
    forbidden: type[Exception]

    def _requires_organization_scope(self, context: dict) -> bool:
        """Return whether the permission checked for this request is org-scoped."""
        scopes = context.get("_permissionScopes")
        if not isinstance(scopes, dict):
            return False
        return any(self.db.text(scope) == "organization" for scope in scopes.values())

    def scoped_org_ids(self, context: dict) -> set[int] | None:
        if parse_bool(context.get("isSuperAdmin")):
            return None
        user_id = self.db.integer(context.get("id"), 0)
        if user_id <= 0:
            raise self.forbidden("Invalid user context.")

        scopes = self.db.json(
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

        org_rows = self.db.json(
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
            parent_id = self.db.integer(row.get("parentId"), 0)
            children.setdefault(parent_id, []).append(self.db.integer(row.get("id"), 0))

        allowed: set[int] = set()
        for scope in scopes or []:
            root_id = self.db.integer(scope.get("orgId"), 0)
            if root_id <= 0:
                continue
            allowed.add(root_id)
            if not parse_bool(scope.get("includeDescendants")):
                continue
            queue = list(children.get(root_id, []))
            while queue:
                current = queue.pop()
                if current in allowed:
                    continue
                allowed.add(current)
                queue.extend(children.get(current, []))
        return allowed

    def permitted_org_ids(self, context: dict) -> set[int] | None:
        """Return a concrete org allowlist only for an organization-scoped request."""
        if not self._requires_organization_scope(context):
            return None
        return self.scoped_org_ids(context)

    def ancestor_org_ids(self, org_unit_id: object | None) -> list[int]:
        """Return an active organization and its active ancestors, nearest first."""
        current_id = self.db.integer(org_unit_id, 0)
        if current_id <= 0:
            return []

        rows = self.db.json(
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
        parents = {
            self.db.integer(row.get("id"), 0): self.db.integer(row.get("parentId"), 0)
            for row in rows or []
            if self.db.integer(row.get("id"), 0) > 0
        }
        if current_id not in parents:
            return []

        ancestors: list[int] = []
        visited: set[int] = set()
        while current_id > 0 and current_id not in visited:
            if current_id not in parents:
                break
            visited.add(current_id)
            ancestors.append(current_id)
            current_id = parents[current_id]
        return ancestors

    def assert_org_access(self, context: dict, org_unit_id: object | None) -> None:
        org_id = self.db.integer(org_unit_id, 0)
        allowed = self.permitted_org_ids(context)
        if org_id <= 0:
            if allowed is not None:
                raise self.forbidden("This account is not authorized to access an unassigned organization.")
            return
        if allowed is not None and org_id not in allowed:
            raise self.forbidden("You are not authorized to access this organization.")

    def assert_computer_access(self, context: dict, computer_id: object) -> None:
        computer_id_int = self.db.integer(computer_id, 0)
        if computer_id_int <= 0:
            raise self.forbidden("Invalid computer identifier.")
        org_id = self.db.scalar(
            f"SELECT COALESCE(org_unit_id, 0) FROM computer_asset WHERE computer_id = {computer_id_int};"
        )
        self.assert_org_access(context, org_id)

    def get_user_scopes(self, user_id: object) -> list[dict]:
        user_id_int = self.db.integer(user_id, 0)
        if user_id_int <= 0:
            return []
        return list(
            self.db.json(
                f"""
                SELECT COALESCE(JSON_ARRAYAGG(JSON_OBJECT(
                  'id', scope_id,
                  'orgId', org_unit_id,
                  'includeDescendants', include_descendants
                )), JSON_ARRAY())
                FROM user_org_scope
                WHERE user_id = {user_id_int}
                """,
                [],
            )
            or []
        )

    def replace_user_scopes(self, user_id: object, scopes: list[dict]) -> list[dict]:
        user_id_int = self.db.integer(user_id, 0)
        if user_id_int <= 0:
            raise ValueError("Invalid user identifier.")
        values: list[str] = []
        for item in scopes:
            org_id = self.db.integer(item.get("orgId"), 0)
            if org_id <= 0:
                raise ValueError("Every organization scope requires an organization.")
            values.append(
                f"({user_id_int}, {org_id}, {1 if parse_bool(item.get('includeDescendants', True), True) else 0})"
            )
        statements = [
            "START TRANSACTION",
            f"DELETE FROM user_org_scope WHERE user_id = {user_id_int}",
        ]
        if values:
            statements.append(
                "INSERT INTO user_org_scope (user_id, org_unit_id, include_descendants) VALUES "
                + ", ".join(values)
            )
        statements.append("COMMIT")
        self.db.execute(";\n".join(statements) + ";")
        return self.get_user_scopes(user_id_int)
