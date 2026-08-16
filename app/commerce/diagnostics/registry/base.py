"""Versioned definition registry base.

``VersionedRegistry`` now lives in ``app.core.versioning`` (platform-common);
Commerce re-exports it here for backward compatibility.  Identity is
``(id, version)``, the first version becomes active, later versions never
auto-activate, and ``activate`` promotes explicitly.
"""

from app.core.versioning import VersionedRegistry  # noqa: F401

__all__ = ["VersionedRegistry"]
