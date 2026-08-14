"""AccessContext builder.

Assembles a validated ``AccessContext`` from a ``UserIdentity`` and its
resolved tenant-owned entities, then stamps the deterministic
``identity_version``.
"""

from dataclasses import replace

from app.identity.context.access_context import AccessContext
from app.identity.models.scope import BusinessScope


def _union(*collections):
    return tuple(sorted({item for collection in collections for item in collection}))


def merge_scopes(scopes) -> BusinessScope:
    if not scopes:
        return BusinessScope(scope_id="", tenant_id="")
    return BusinessScope(
        scope_id="",
        tenant_id=scopes[0].tenant_id,
        stores=_union(*(s.stores for s in scopes)),
        regions=_union(*(s.regions for s in scopes)),
        channels=_union(*(s.channels for s in scopes)),
        brands=_union(*(s.brands for s in scopes)),
        products=_union(*(s.products for s in scopes)),
        business_units=_union(*(s.business_units for s in scopes)),
    )


class AccessContextBuilder:
    """Build an AccessContext from resolved identity facts."""

    def build(
        self,
        user,
        organization,
        department,
        position,
        level_id,
        roles,
        scopes,
    ) -> AccessContext:
        context = AccessContext(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            organization_id=organization.organization_id,
            department_id=department.department_id,
            position_id=position.position_id,
            professional_level=level_id,
            roles=tuple(sorted(role.role_id for role in roles)),
            business_scope=merge_scopes(scopes),
            security_clearance=user.security_clearance,
            attributes=dict(user.attributes),
        )
        version = context.stable_identity_version()
        return replace(context, identity_version=version)
