"""IdentityService — the single public Identity API."""

from app.identity.context.access_context import AccessContext
from app.identity.context.builder import AccessContextBuilder
from app.identity.models.user import UserIdentity
from app.identity.ports.provider import IdentityProviderPort
from app.identity.validation.validator import IdentityValidator


class IdentityService:
    """Resolves a subject into a trusted, validated ``AccessContext``.

    Identity only answers "who is this user"; it never decides what the user
    may do.
    """

    def __init__(
        self,
        provider: IdentityProviderPort,
        validator: IdentityValidator | None = None,
        builder: AccessContextBuilder | None = None,
    ):
        if provider is None:
            raise ValueError("IdentityService requires an IdentityProviderPort")
        self.provider = provider
        self.validator = validator or IdentityValidator()
        self.builder = builder or AccessContextBuilder()

    def get_identity(self, user_id: str) -> UserIdentity:
        user = self.provider.get_user(user_id)
        self.validator.validate_user(user)
        return user

    def build_access_context(self, user_id: str) -> AccessContext:
        user = self.provider.get_user(user_id)
        organization = self.provider.get_organization(user.organization_id)
        department = self.provider.get_department(user.department_id)
        position = self.provider.get_position(user.position_id)
        roles = self.provider.get_roles(user.role_ids)
        scopes = self.provider.get_scopes(user.scope_ids)
        self.validator.validate_resolved(
            user, organization, department, position, roles, scopes
        )
        return self.builder.build(
            user,
            organization,
            department,
            position,
            user.professional_level_id,
            roles,
            scopes,
        )
