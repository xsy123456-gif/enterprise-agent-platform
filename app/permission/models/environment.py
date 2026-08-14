"""Permission environment — the evaluation environment fact snapshot."""

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class PermissionEnvironment:
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "attributes", dict(self.attributes or {}))
