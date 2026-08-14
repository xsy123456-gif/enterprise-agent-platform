"""Identity subsystem errors.

Platform-facing only.  Provider-native errors (yaml parse, file IO) are mapped
to these before leaving the Identity boundary.
"""


class IdentityError(Exception):
    """Base class for all Identity subsystem errors."""


class IdentityNotFoundError(IdentityError):
    """A referenced identity entity (user/organization/...) does not exist."""


class IdentityValidationError(IdentityError):
    """Identity data failed validation (invalid reference, cross-tenant, ...)."""


class IdentityProviderError(IdentityError):
    """The identity provider failed to read or resolve data."""


class IdentityUnavailableError(IdentityError):
    """The identity system cannot produce an AccessContext."""
