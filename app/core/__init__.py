"""Platform-common core primitives (Phase 18.6).

``app.core`` is the bottom-most application foundation: time, error hierarchy
and versioned registry.  Both Platform and Commerce depend on it; it depends on
nothing application-specific.
"""

from app.core.errors import (
    ApplicationError,
    DuplicateDefinitionError,
    UnknownDefinitionError,
    UnknownDefinitionVersionError,
)
from app.core.time import utc_now
from app.core.versioning import VersionedRegistry

__all__ = [
    "utc_now",
    "ApplicationError",
    "DuplicateDefinitionError",
    "UnknownDefinitionError",
    "UnknownDefinitionVersionError",
    "VersionedRegistry",
]
