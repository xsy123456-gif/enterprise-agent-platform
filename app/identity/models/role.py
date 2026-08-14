"""Role — tenant-owned enterprise entity (future RBAC grouping).

A role is an identity fact; whether it grants a permission is decided by the
Permission layer, not by Identity.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    role_id: str
    tenant_id: str
    name: str = ""
