"""Execution security integration composition.

This is the anti-corruption layer where Identity, Permission and Governance are
combined into the trusted execution security chain.
"""

from dataclasses import dataclass, field

from app.integrations.security.admission.agent import AgentAdmissionController
from app.integrations.security.config import SecurityIntegrationConfig
from app.integrations.security.context.carrier import (
    InMemoryPrincipalContextCarrier,
    PrincipalContextCarrierPort,
)
from app.integrations.security.lifecycle.authorization_adapter import (
    PermissionLifecycleAuthorizationAdapter,
)
from app.integrations.security.subject.resolver import (
    PrincipalResolver,
    TrustedSubjectResolver,
)
from app.integrations.security.subject.system_resolver import (
    SystemPrincipalDefinition,
    SystemPrincipalResolver,
    TrustedSystemPrincipalRegistry,
)
from app.integrations.security.tools.security_gate import (
    ExecutionSecurityGate,
    LocalTrustedPrincipalProvider,
)


def default_system_principals():
    return [
        SystemPrincipalDefinition(
            principal_id="platform.bootstrap",
            tenant_id="company_A",
            roles=frozenset({"platform_bootstrap"}),
        ),
    ]


@dataclass(frozen=True)
class SecurityIntegration:
    resolver: PrincipalResolver
    admission: AgentAdmissionController
    tool_gate: ExecutionSecurityGate
    lifecycle_authorization: PermissionLifecycleAuthorizationAdapter
    carrier: PrincipalContextCarrierPort
    config: SecurityIntegrationConfig
    system_registry: TrustedSystemPrincipalRegistry = field(
        default_factory=TrustedSystemPrincipalRegistry
    )


def build_security_integration(
    identity_service,
    permission_service,
    governance_gate=None,
    carrier: PrincipalContextCarrierPort | None = None,
    config: SecurityIntegrationConfig | None = None,
    system_principals=None,
) -> SecurityIntegration:
    config = config or SecurityIntegrationConfig()
    system_registry = TrustedSystemPrincipalRegistry(
        system_principals if system_principals is not None else default_system_principals()
    )
    resolver = PrincipalResolver(
        TrustedSubjectResolver(identity_service),
        SystemPrincipalResolver(system_registry),
    )
    admission = AgentAdmissionController(resolver, permission_service)
    principal_provider = LocalTrustedPrincipalProvider(
        allow_local=(config.principal_source != "external_required")
    )
    tool_gate = ExecutionSecurityGate(
        resolver, permission_service, governance_gate,
        principal_provider=principal_provider,
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
        system_registry=system_registry,
    )
