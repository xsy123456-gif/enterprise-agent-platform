"""Production security configuration validation (Phase 18.7).

Production must fail-closed: no AllowAll governance, no AllowAll memory
authorization, no local principal fallback.  Startup validation raises
``ApplicationStartupError`` (APPLICATION_STARTUP_FAILED) rather than silently
running an insecure platform.
"""

from app.runtime.governance.gate import AllowAllGovernancePolicy
from app.memory.ports.authorization import AllowAllMemoryAuthorizationProvider

PRODUCTION = "production"
PRINCIPAL_EXTERNAL = "external"
PRINCIPAL_LOCAL = "local"


class ApplicationStartupError(RuntimeError):
    """The application failed secure-configuration validation at startup."""


class SecurityConfigValidator:

    def __init__(self, environment, governance_policy=None,
                 memory_authorization=None, principal_source=PRINCIPAL_LOCAL):
        self.environment = (environment or "").lower()
        self.governance_policy = governance_policy
        self.memory_authorization = memory_authorization
        self.principal_source = principal_source

    def violations(self):
        problems = []
        if self.environment != PRODUCTION:
            return problems
        if isinstance(self.governance_policy, AllowAllGovernancePolicy):
            problems.append("production must not use AllowAllGovernancePolicy")
        if isinstance(self.memory_authorization,
                      AllowAllMemoryAuthorizationProvider):
            problems.append(
                "production must not use AllowAllMemoryAuthorizationProvider"
            )
        if self.principal_source == PRINCIPAL_LOCAL:
            problems.append(
                "production must not fall back to a local principal source"
            )
        return problems

    def assert_secure(self):
        problems = self.violations()
        if problems:
            raise ApplicationStartupError(
                "APPLICATION_STARTUP_FAILED: " + "; ".join(problems)
            )
        return self


__all__ = [
    "SecurityConfigValidator",
    "ApplicationStartupError",
    "PRODUCTION",
    "PRINCIPAL_EXTERNAL",
    "PRINCIPAL_LOCAL",
]
