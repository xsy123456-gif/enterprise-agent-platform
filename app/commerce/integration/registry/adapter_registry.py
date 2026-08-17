"""Versioned adapter registry (Phase 12.9.2).

Adapters are versioned so old raw data can still be replayed against the exact
adapter version that produced it.
"""

from app.commerce.diagnostics.registry.base import VersionedRegistry


class AdapterRegistry(VersionedRegistry):
    """Versioned adapter classes keyed by ``(adapter_id, version)``."""

    def __init__(self):
        super().__init__("adapter")

    def register_class(self, adapter_id, version, adapter_cls):
        return super().register(adapter_id, version, adapter_cls)

    def build(self, adapter_id, version=None, **kwargs):
        adapter_cls = self.get(adapter_id, version)
        resolved = version or self.active_version(adapter_id)
        kwargs.setdefault("version", resolved)
        return adapter_cls(**kwargs)


__all__ = ["AdapterRegistry"]
