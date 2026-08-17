"""Canonical commerce storage errors."""

from app.commerce.contracts.errors import CommerceError


class CommerceStorageError(CommerceError):
    """A canonical commerce store operation failed."""


class TenantIsolationViolation(CommerceStorageError):
    """A cross-tenant write was attempted (fail-closed)."""


class ExternalIdentityConflict(CommerceStorageError):
    """The same external key maps to a different canonical id (fail-closed).

    The existing mapping is left unchanged.
    """


__all__ = [
    "CommerceStorageError",
    "TenantIsolationViolation",
    "ExternalIdentityConflict",
]
