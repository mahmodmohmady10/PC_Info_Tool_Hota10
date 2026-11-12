from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FieldValue:
    value: Any = None
    source: str = "unknown"
    status: str = "unavailable"  # available, unavailable, unsupported, access_denied, error
    note: str = ""


@dataclass
class CollectionResult:
    section: str
    collected_at: str = field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
    status: str = "unavailable"
    fields: dict[str, FieldValue] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def add(self, name: str, value: Any, source: str, status: str = "available", note: str = "") -> None:
        self.fields[name] = FieldValue(value=value, source=source, status=status, note=note)

    def add_unavailable(self, name: str, source: str, status: str = "unavailable", note: str = "") -> None:
        self.fields[name] = FieldValue(value=None, source=source, status=status, note=note)

    def finalize(self) -> "CollectionResult":
        statuses = [item.status for item in self.fields.values()]
        if not statuses:
            self.status = "unavailable"
        elif any(s == "available" for s in statuses):
            self.status = "available"
        elif any(s == "error" for s in statuses):
            self.status = "error"
        else:
            self.status = statuses[0]
        return self
