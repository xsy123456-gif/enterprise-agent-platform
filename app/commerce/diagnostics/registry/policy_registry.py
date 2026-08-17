"""DiagnosticPolicyRegistry — versioned DiagnosticPolicy definitions."""

from app.commerce.diagnostics.definitions.policies import DiagnosticPolicy
from app.commerce.diagnostics.registry.base import VersionedRegistry


class DiagnosticPolicyRegistry(VersionedRegistry):

    def __init__(self):
        super().__init__("diagnostic policy")

    def register(self, policy: DiagnosticPolicy):
        return super().register(policy.policy_id, policy.version, policy)

    def get(self, policy_id, version=None) -> DiagnosticPolicy:
        return super().get(policy_id, version)


__all__ = ["DiagnosticPolicyRegistry"]
