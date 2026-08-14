"""Execution security integration layer.

The only place where Identity / Permission / Governance are combined.  Identity
and Permission cores never import this package.
"""

from app.integrations.security.admission.agent import AgentAdmissionController
from app.integrations.security.config import SecurityIntegrationConfig
from app.integrations.security.context.carrier import (
    InMemoryPrincipalContextCarrier,
    PrincipalContextCarrierPort,
)
from app.integrations.security.errors import (
    SecurityContextError,
    SecurityIntegrationError,
    TrustedPrincipalResolutionError,
)
from app.integrations.security.factory import SecurityIntegration, build_security_integration
from app.integrations.security.lifecycle.authorization_adapter import (
    PermissionLifecycleAuthorizationAdapter,
)
from app.integrations.security.models.execution_context import (
    ExecutionPrincipalBinding,
    ExecutionSecurityContext,
)
from app.integrations.security.models.trusted_principal import TrustedPrincipal
from app.integrations.security.subject.adapter import (
    IdentityPermissionSubjectAdapter,
    SCOPE_MAPPING,
)
from app.integrations.security.subject.resolver import TrustedSubjectResolver
from app.integrations.security.tools.security_gate import (
    ExecutionSecurityGate,
    LocalTrustedPrincipalProvider,
)

__all__ = [
    "SecurityIntegration",
    "build_security_integration",
    "SecurityIntegrationConfig",
    "TrustedPrincipal",
    "ExecutionPrincipalBinding",
    "ExecutionSecurityContext",
    "IdentityPermissionSubjectAdapter",
    "SCOPE_MAPPING",
    "TrustedSubjectResolver",
    "AgentAdmissionController",
    "ExecutionSecurityGate",
    "LocalTrustedPrincipalProvider",
    "PermissionLifecycleAuthorizationAdapter",
    "PrincipalContextCarrierPort",
    "InMemoryPrincipalContextCarrier",
    "SecurityIntegrationError",
    "TrustedPrincipalResolutionError",
    "SecurityContextError",
]
