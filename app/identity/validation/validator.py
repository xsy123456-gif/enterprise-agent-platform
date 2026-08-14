"""Identity validation — fail-closed.

Rejects invalid references, cross-tenant ownership violations, invalid
clearance/level, and non-active user status.  Fail-closed by default.
"""

from app.identity.errors import IdentityValidationError
from app.identity.models.clearance import SecurityClearance
from app.identity.models.level import ProfessionalLevel

_ACTIVE_STATUSES = {"active"}


class IdentityValidator:
    def __init__(self, fail_closed=True):
        self.fail_closed = fail_closed

    def validate_user(self, user) -> None:
        if user.status not in _ACTIVE_STATUSES:
            raise IdentityValidationError(
                f"user {user.user_id} is not active: {user.status}"
            )
        if user.professional_level_id not in ProfessionalLevel.values():
            raise IdentityValidationError(
                f"unknown professional level: {user.professional_level_id}"
            )
        if user.security_clearance not in SecurityClearance.values():
            raise IdentityValidationError(
                f"invalid security clearance: {user.security_clearance}"
            )

    def assert_tenant_owned(self, user, entity, kind: str) -> None:
        if getattr(entity, "tenant_id", None) != user.tenant_id:
            raise IdentityValidationError(
                f"cross-tenant reference: user {user.user_id} (tenant "
                f"{user.tenant_id}) references {kind} of tenant "
                f"{getattr(entity, 'tenant_id', None)!r}"
            )

    def validate_resolved(self, user, organization, department, position,
                          roles, scopes) -> None:
        self.validate_user(user)
        self.assert_tenant_owned(user, organization, "organization")
        self.assert_tenant_owned(user, department, "department")
        self.assert_tenant_owned(user, position, "position")
        for role in roles:
            self.assert_tenant_owned(user, role, "role")
        for scope in scopes:
            self.assert_tenant_owned(user, scope, "scope")
