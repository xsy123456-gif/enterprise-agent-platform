"""Authentication port + principal model (Phase 18.12)."""

from dataclasses import dataclass, field
from typing import Protocol

from app.core.time import utc_now


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """The result of Credential -> Principal (NOT Principal -> Permission).

    Only carries the authenticated identity; roles / permissions / scope /
    department come from the IdentityService, never from the token.
    """

    principal_id: str
    auth_source: str = "auth"
    credential_type: str = "bearer"
    authenticated_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.principal_id:
            raise ValueError("principal_id is required")


class AuthenticationProvider(Protocol):
    def authenticate(self, authorization_header) -> AuthenticatedPrincipal:
        """Map an Authorization header to an AuthenticatedPrincipal.

        Raises ``ApiError`` (401) when missing or invalid.
        """
        ...


__all__ = ["AuthenticatedPrincipal", "AuthenticationProvider"]
