"""Platform-common error hierarchy (Phase 18.6).

``ApplicationError`` is the root of the error tree; Commerce and Platform both
inherit from it (CommerceError -> ApplicationError, PlatformError ->
ApplicationError).  The versioning errors are generic platform errors, so they
live here (not in Commerce).
"""


class ApplicationError(Exception):
    """Root of all application errors."""


class DuplicateDefinitionError(ApplicationError):
    """A versioned definition was registered more than once under (id, version)."""


class UnknownDefinitionError(ApplicationError):
    """A versioned definition id is not registered."""


class UnknownDefinitionVersionError(ApplicationError):
    """A versioned definition id has no such version."""


__all__ = [
    "ApplicationError",
    "DuplicateDefinitionError",
    "UnknownDefinitionError",
    "UnknownDefinitionVersionError",
]
