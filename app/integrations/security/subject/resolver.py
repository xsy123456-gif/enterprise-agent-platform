"""Trusted subject resolver — TrustedPrincipal -> PermissionSubject (fail-closed)."""

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
