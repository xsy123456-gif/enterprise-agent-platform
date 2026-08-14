"""Organization — tenant-owned enterprise entity."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Organization:
    organization_id: str
    tenant_id: str
    name: str
    type: str = "company"
    status: str = "active"
