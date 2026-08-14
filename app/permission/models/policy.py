"""Permission policy — the declarative authorization rule."""

from dataclasses import dataclass, field

from app.permission.models.condition import ConditionNode


@dataclass(frozen=True)
class PolicyScope:
    type: str  # "platform" | "tenant"
    tenant_id: str | None = None


@dataclass(frozen=True)
class ResourceMatch:
    type: str  # "any" | "ids"
    ids: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self):
        object.__setattr__(self, "ids", frozenset(self.ids or ()))


@dataclass(frozen=True)
class PolicyTarget:
    resource_types: frozenset[str] = field(default_factory=frozenset)
    resource_match: ResourceMatch = field(default_factory=lambda: ResourceMatch("any"))
    actions: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self):
        object.__setattr__(self, "resource_types", frozenset(self.resource_types or ()))
        object.__setattr__(self, "actions", frozenset(self.actions or ()))


@dataclass(frozen=True)
class PermissionPolicy:
    policy_id: str
    version: int
    status: str  # "active" | "disabled"
    scope: PolicyScope
    effect: str  # "allow" | "deny"
    target: PolicyTarget
    condition: ConditionNode | None = None
