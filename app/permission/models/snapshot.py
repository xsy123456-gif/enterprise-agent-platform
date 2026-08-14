"""Policy snapshot — immutable, validated, canonicalized policy set."""

from dataclasses import dataclass

from app.permission.models.policy import PermissionPolicy


@dataclass(frozen=True)
class PolicySnapshot:
    policy_set_version: str
    policies: tuple[PermissionPolicy, ...]

    def __post_init__(self):
        object.__setattr__(self, "policies", tuple(self.policies or ()))
