"""Versioned SyncDefinitionRegistry."""

from app.commerce.diagnostics.registry.base import VersionedRegistry
from app.commerce.ingestion.models import SyncDefinition


class SyncDefinitionRegistry(VersionedRegistry):
    """Versioned sync definitions keyed by ``(sync_id, version)``."""

    def __init__(self):
        super().__init__("sync definition")

    def register(self, definition: SyncDefinition):
        return super().register(definition.sync_id, definition.version, definition)

    def get(self, sync_id, version=None) -> SyncDefinition:
        return super().get(sync_id, version)


__all__ = ["SyncDefinitionRegistry"]
