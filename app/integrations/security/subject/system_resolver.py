"""System principal resolution.

A system principal (bootstrap / scheduler / migration worker) is a first-class
principal, NOT a bypass.  It resolves to a PermissionSubject from a trusted
registry and is still governed by Permission policies.
"""

from dataclasses import dataclass, field

from app.integrations.security.errors import TrustedPrincipalResolutionError
from app.integrations.security.models.trusted_principal import TrustedPrincipal
from app.permission.models.scope import PermissionScope, ScopeGrant
from app.permission.models.subject import PermissionSubject


@dataclass(frozen=True)
class SystemPrincipalDefinition:
    principal_id: str
    tenant_id: str
    roles: frozenset[str] = field(default_factory=frozenset)
    scopes: tuple[ScopeGrant, ...] = ()
    attributes: dict = field(default_factory=dict)
    status: str = "active"

    def __post_init__(self):
        object.__setattr__(self, "roles", frozenset(self.roles or ()))
        object.__setattr__(self, "scopes", tuple(self.scopes or ()))
        object.__setattr__(self, "attributes", dict(self.attributes or {}))


class TrustedSystemPrincipalRegistry:
    def __init__(self, definitions=None):
        self._definitions: dict[str, SystemPrincipalDefinition] = {}
        for definition in definitions or []:
            self.register(definition)

    def register(self, definition: SystemPrincipalDefinition):
        self._definitions[definition.principal_id] = definition
        return definition

    def get(self, principal_id: str):
        return self._definitions.get(principal_id)


class SystemPrincipalResolver:
    def __init__(self, registry: TrustedSystemPrincipalRegistry):
        self.registry = registry

    def resolve(self, principal: TrustedPrincipal) -> PermissionSubject:
        definition = self.registry.get(principal.principal_id)
        if definition is None or definition.status != "active":
            raise TrustedPrincipalResolutionError(
                f"unknown or inactive system principal: {principal.principal_id}"
            )
        return PermissionSubject(
            subject_id=definition.principal_id,
            tenant_id=definition.tenant_id,
            roles=frozenset(definition.roles),
            scopes=PermissionScope(tuple(definition.scopes)),
            attributes=dict(definition.attributes),
        )
