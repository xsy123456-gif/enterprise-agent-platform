"""Trusted subject resolver — TrustedPrincipal -> PermissionSubject (fail-closed)."""

from app.integrations.security.errors import TrustedPrincipalResolutionError
from app.integrations.security.models.trusted_principal import TrustedPrincipal
from app.integrations.security.subject.adapter import (
    IdentityPermissionSubjectAdapter,
)


class TrustedSubjectResolver:
    """Resolve a TrustedPrincipal into a current PermissionSubject.

    Identity resolution failures (unknown/inactive/suspended user, provider
    error) propagate; callers must treat them as DENY, never fall back.
    """

    def __init__(self, identity_service, adapter=None):
        if identity_service is None:
            raise ValueError("TrustedSubjectResolver requires an IdentityService")
        self.identity_service = identity_service
        self.adapter = adapter or IdentityPermissionSubjectAdapter()

    def resolve(self, principal: TrustedPrincipal):
        access_context = self.identity_service.build_access_context(
            principal.principal_id
        )
        return self.adapter.adapt(access_context)


class PrincipalResolver:
    """Dispatch human principals to Identity, system principals to the system
    registry.  Both paths produce a PermissionSubject."""

    def __init__(self, human_resolver: TrustedSubjectResolver, system_resolver=None):
        self.human_resolver = human_resolver
        self.system_resolver = system_resolver

    def resolve(self, principal: TrustedPrincipal):
        if principal.source == "system":
            if self.system_resolver is None:
                raise TrustedPrincipalResolutionError(
                    "no system principal resolver configured"
                )
            return self.system_resolver.resolve(principal)
        return self.human_resolver.resolve(principal)
