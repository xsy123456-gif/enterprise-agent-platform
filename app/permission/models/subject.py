"""Permission subject — the authorization subject fact snapshot."""

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.permission.models.scope import PermissionScope


@dataclass(frozen=True)
class PermissionSubject:
    subject_id: str
    tenant_id: str
    roles: frozenset[str] = field(default_factory=frozenset)
    department_id: str | None = None
    position_id: str | None = None
    professional_level: str | None = None
    security_clearance: str | None = None
    scopes: PermissionScope = field(default_factory=PermissionScope)
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "roles", frozenset(self.roles or ()))
        object.__setattr__(self, "scopes", self.scopes or PermissionScope())
        object.__setattr__(self, "attributes", dict(self.attributes or {}))
