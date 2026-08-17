"""Platform-common versioned registry (Phase 18.6).

The generic ``(id, version) -> item`` registry used by Commerce diagnostics AND
the Platform registries.  Commerce re-exports this; no Platform module imports
versioning from Commerce.
"""

from app.core.errors import (
    DuplicateDefinitionError,
    UnknownDefinitionError,
    UnknownDefinitionVersionError,
)


class VersionedRegistry:
    """Generic ``(id, version) -> item`` registry with active-version tracking."""

    def __init__(self, kind):
        self.kind = kind
        self._items = {}
        self._active = {}

    def register(self, key, version, item):
        if (key, version) in self._items:
            raise DuplicateDefinitionError(
                f"{self.kind} {key!r} version {version!r} is already defined"
            )
        self._items[(key, version)] = item
        if key not in self._active:
            self._active[key] = version
        return item

    def get(self, key, version=None):
        if version is None:
            active = self._active.get(key)
            if active is None:
                raise UnknownDefinitionError(f"{self.kind} {key!r} is not defined")
            return self._items[(key, active)]
        item = self._items.get((key, version))
        if item is None:
            if key not in self._active:
                raise UnknownDefinitionError(f"{self.kind} {key!r} is not defined")
            raise UnknownDefinitionVersionError(
                f"{self.kind} {key!r} has no version {version!r}"
            )
        return item

    def activate(self, key, version):
        item = self._items.get((key, version))
        if item is None:
            raise UnknownDefinitionVersionError(
                f"{self.kind} {key!r} has no version {version!r}"
            )
        self._active[key] = version
        return item

    def active_version(self, key):
        return self._active.get(key)

    def versions(self, key):
        return sorted(version for (k, version) in self._items if k == key)

    def has(self, key):
        return key in self._active

    def list_items(self):
        return sorted(self._items.values(), key=lambda i: (self._id(i), i.version))

    def __len__(self):
        return len(self._items)

    def __contains__(self, key):
        return key in self._active

    @staticmethod
    def _id(item):
        return item.policy_id if hasattr(item, "policy_id") else (
            item.rule_set_id if hasattr(item, "rule_set_id") else (
                item.formula_id if hasattr(item, "formula_id") else getattr(item, "id", "")
            )
        )


__all__ = ["VersionedRegistry"]
