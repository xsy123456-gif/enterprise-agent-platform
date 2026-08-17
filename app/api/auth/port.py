"""Authentication provider port re-export (Phase 18.12)."""

from app.api.auth.models import AuthenticatedPrincipal, AuthenticationProvider

__all__ = ["AuthenticatedPrincipal", "AuthenticationProvider"]
