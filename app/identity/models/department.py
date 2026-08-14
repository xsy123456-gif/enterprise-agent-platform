"""Department — tenant-owned enterprise entity."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Department:
    department_id: str
    tenant_id: str
    name: str
    parent_department_id: str | None = None
