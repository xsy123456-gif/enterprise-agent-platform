"""Canonical commerce storage errors."""

from app.commerce.contracts.errors import CommerceError


class CommerceStorageError(CommerceError):
    """A canonical commerce store operation failed."""


class TenantIsolationViolation(CommerceStorageError):
    """A cross-tenant write was attempted (fail-closed)."""


__all__ = ["CommerceStorageError", "TenantIsolationViolation"]
