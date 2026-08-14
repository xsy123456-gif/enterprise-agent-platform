"""ExecutionSecurityGate — Permission-first then Governance, Runtime-compatible.

Implements the Runtime GovernanceGate-compatible ``check(request)`` interface so
the frozen Runtime needs no changes.  Order: Permission -> Governance.
"""

from dataclasses import dataclass

from app.integrations.security.models.trusted_principal import TrustedPrincipal
from app.permission.models.decision import Decision
from app.permission.models.environment import PermissionEnvironment
from app.permission.models.request import PermissionRequest
from app.permission.models.resource import PermissionResource
from app.runtime.governance.gate import GovernanceDecision, GovernanceResult


@dataclass(frozen=True)
class _DenyDecision:
    value: str = GovernanceDecision.DENY.value


class LocalTrustedPrincipalProvider:
    """Development/testing: derive a TrustedPrincipal from the Application-layer
    user_id carried on the tool request (never from LLM output)."""

    def from_request(self, request) -> TrustedPrincipal:
        principal_id = getattr(request, "user_id", None)
        if not principal_id:
            raise ValueError("request has no principal (user_id)")
        return TrustedPrincipal(principal_id=principal_id, source="local")


class ExecutionSecurityGate:
    def __init__(
        self,
        subject_resolver,
        permission_service,
        governance_gate,
        principal_provider=None,
    ):
        self.subject_resolver = subject_resolver
        self.permission_service = permission_service
        self.governance_gate = governance_gate
        self.principal_provider = principal_provider or LocalTrustedPrincipalProvider()

    def check(self, request):
        try:
            principal = self.principal_provider.from_request(request)
            subject = self.subject_resolver.resolve(principal)
        except Exception as error:
            return False, GovernanceResult(
                GovernanceDecision.DENY, f"principal resolution failed: {error}"
            )

        request_tenant = getattr(request, "tenant_id", None)
        if request_tenant and request_tenant != subject.tenant_id:
            return False, GovernanceResult(
                GovernanceDecision.DENY, "tenant mismatch"
            )

        tool_name = getattr(request, "tool_name", None) or "tool"
        resource = PermissionResource(
            resource_type="tool",
            resource_id=tool_name,
            tenant_id=subject.tenant_id,
            attributes={
                "agent_id": getattr(request, "agent_id", None),
                "capability": getattr(request, "capability", None),
            },
        )
        permission_request = PermissionRequest(
            request_id=getattr(request, "request_id", None) or "sec",
            subject=subject,
            resource=resource,
            action="execute",
            environment=PermissionEnvironment(),
        )
        decision = self.permission_service.evaluate(permission_request)
        if decision.decision is Decision.DENY:
            return False, GovernanceResult(
                GovernanceDecision.DENY, f"permission {decision.reason_code.value}"
            )

        # Permission ALLOW -> Governance.
        return self.governance_gate.check(request)
