from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


def parse_bool(value: object | None, default: bool = False) -> bool:
    """Parse booleans from JSON and form payloads consistently."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    return default


@dataclass(frozen=True)
class SqlGateway:
    execute: Callable[[str], str]
    query_json: Callable[[str, object | None], object | None]
    quote: Callable[[object | None], str]
    text: Callable[[object | None], str]
    integer: Callable[[object | None, int], int]

    def json(self, sql: str, default: object | None = None) -> object | None:
        return self.query_json(sql, default)

    def scalar(self, sql: str, default: int = 0) -> int:
        return self.integer(self.execute(sql).strip(), default)

    def one_id(self, sql: str) -> int:
        output = self.execute(sql)
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if not lines:
            return 0
        return self.integer(lines[-1], 0)

    def json_value(self, value: Any) -> str:
        import json

        return self.quote(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
