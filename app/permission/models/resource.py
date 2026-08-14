"""Permission resource — the resource being acted upon."""

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class PermissionResource:
    resource_type: str
    resource_id: str
    tenant_id: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "attributes", dict(self.attributes or {}))
