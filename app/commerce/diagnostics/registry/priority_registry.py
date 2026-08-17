"""PriorityPolicyRegistry — versioned PriorityPolicy definitions."""

from app.commerce.diagnostics.definitions.priority import PriorityPolicy
from app.commerce.diagnostics.registry.base import VersionedRegistry


class PriorityPolicyRegistry(VersionedRegistry):

    def __init__(self):
        super().__init__("priority policy")

    def register(self, policy: PriorityPolicy):
        return super().register(policy.policy_id, policy.version, policy)

    def get(self, policy_id, version=None) -> PriorityPolicy:
        return super().get(policy_id, version)


__all__ = ["PriorityPolicyRegistry"]
