"""Enterprise Identity Foundation.

A black-box identity-facts service: reads an enterprise subject from a
replaceable provider and outputs a trusted ``AccessContext``.  It does NOT do
authentication, authorization, or know any other platform domain.
"""

from app.identity.api.service import IdentityService
from app.identity.config import IdentityConfig
from app.identity.context.access_context import AccessContext
from app.identity.context.builder import AccessContextBuilder
from app.identity.errors import (
    IdentityError,
    IdentityNotFoundError,
    IdentityProviderError,
    IdentityUnavailableError,
    IdentityValidationError,
)
from app.identity.factory import IdentitySystem, build_identity
from app.identity.models import (
    BusinessScope,
    Department,
    Organization,
    Position,
    ProfessionalLevel,
    Role,
    SecurityClearance,
    UserIdentity,
)
from app.identity.ports.provider import IdentityProviderPort

__all__ = [
    "IdentityService",
    "IdentityConfig",
    "IdentitySystem",
    "build_identity",
    "AccessContext",
    "AccessContextBuilder",
    "UserIdentity",
    "Organization",
    "Department",
    "Position",
    "ProfessionalLevel",
    "Role",
    "BusinessScope",
    "SecurityClearance",
    "IdentityProviderPort",
    "IdentityError",
    "IdentityNotFoundError",
    "IdentityValidationError",
    "IdentityProviderError",
    "IdentityUnavailableError",
]
