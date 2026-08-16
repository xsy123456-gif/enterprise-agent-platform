"""Authentication package (Phase 18.12)."""

from app.api.auth.models import AuthenticatedPrincipal, AuthenticationProvider
from app.api.auth.test_provider import TestAuthenticationProvider
from app.api.auth.dev_provider import DevAuthenticationProvider

__all__ = [
    "AuthenticatedPrincipal",
    "AuthenticationProvider",
    "TestAuthenticationProvider",
    "DevAuthenticationProvider",
]
