"""User identity — the enterprise identity subject.

``UserIdentity`` references other tenant-owned entities by id; it never inlines
them.  ``security_clearance`` is an identity fact (see clearance.py).
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class UserIdentity:
    user_id: str
    tenant_id: str
    name: str
    status: str
    organization_id: str
    department_id: str
    position_id: str
    professional_level_id: str
    role_ids: tuple[str, ...] = ()
    scope_ids: tuple[str, ...] = ()
    security_clearance: str = "internal"
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "role_ids", tuple(self.role_ids or ()))
        object.__setattr__(self, "scope_ids", tuple(self.scope_ids or ()))
        object.__setattr__(self, "attributes", dict(self.attributes or {}))
