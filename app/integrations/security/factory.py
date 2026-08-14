"""Execution security integration composition.

This is the anti-corruption layer where Identity, Permission and Governance are
combined into the trusted execution security chain.
"""

from dataclasses import dataclass

from app.integrations.security.admission.agent import AgentAdmissionController
from app.integrations.security.config import SecurityIntegrationConfig
from app.integrations.security.context.carrier import (
    InMemoryPrincipalContextCarrier,
    PrincipalContextCarrierPort,
)
from app.integrations.security.lifecycle.authorization_adapter import (
    PermissionLifecycleAuthorizationAdapter,
)
from app.integrations.security.subject.resolver import TrustedSubjectResolver
from app.integrations.security.tools.security_gate import ExecutionSecurityGate


@dataclass(frozen=True)
class SecurityIntegration:
    resolver: TrustedSubjectResolver
    admission: AgentAdmissionController
    tool_gate: ExecutionSecurityGate
    lifecycle_authorization: PermissionLifecycleAuthorizationAdapter
    carrier: PrincipalContextCarrierPort
    config: SecurityIntegrationConfig


def build_security_integration(
    identity_service,
    permission_service,
    governance_gate=None,
    carrier: PrincipalContextCarrierPort | None = None,
    config: SecurityIntegrationConfig | None = None,
) -> SecurityIntegration:
    config = config or SecurityIntegrationConfig()
    resolver = TrustedSubjectResolver(identity_service)
    admission = AgentAdmissionController(resolver, permission_service)
    tool_gate = ExecutionSecurityGate(
        resolver, permission_service, governance_gate
    )
    lifecycle = PermissionLifecycleAuthorizationAdapter(resolver, permission_service)
    carrier = carrier or InMemoryPrincipalContextCarrier()
    return SecurityIntegration(
        resolver=resolver,
        admission=admission,
        tool_gate=tool_gate,
        lifecycle_authorization=lifecycle,
        carrier=carrier,
        config=config,
    )
