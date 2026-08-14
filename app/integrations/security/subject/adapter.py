"""Identity AccessContext -> PermissionSubject adapter (explicit, no inference)."""

from app.permission.models.scope import PermissionScope, ScopeGrant
from app.permission.models.subject import PermissionSubject

SCOPE_MAPPING = {
    "stores": "business.store",
    "regions": "geo.region",
    "channels": "commerce.channel",
    "brands": "catalog.brand",
    "products": "catalog.product",
    "business_units": "organization.business_unit",
}


class IdentityPermissionSubjectAdapter:
    """Map an Identity AccessContext to a PermissionSubject.

    Explicit, one-to-one, no inference: never derives roles from P-level,
    permissions from department, or scope from position.
    """

    def adapt(self, access_context) -> PermissionSubject:
        return PermissionSubject(
            subject_id=access_context.user_id,
            tenant_id=access_context.tenant_id,
            roles=frozenset(access_context.roles),
            department_id=access_context.department_id,
            position_id=access_context.position_id,
            professional_level=access_context.professional_level,
            security_clearance=access_context.security_clearance,
            scopes=self._adapt_scope(access_context.business_scope),
            attributes=dict(access_context.attributes),
        )

    def _adapt_scope(self, business_scope) -> PermissionScope:
        grants = []
        for field, dimension in SCOPE_MAPPING.items():
            values = tuple(getattr(business_scope, field, ()) or ())
            if values:
                grants.append(ScopeGrant(dimension, frozenset(values)))
        return PermissionScope(tuple(grants))
