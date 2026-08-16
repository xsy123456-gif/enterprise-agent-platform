"""Versioned connector registry (Phase 12.9.2).

Connectors are versioned because external APIs change.  The registry stores
connector *classes* (not instances) — a connector instance is tenant- and
credential-scoped, so it is built per sync run.
"""

from app.commerce.diagnostics.registry.base import VersionedRegistry


class ConnectorRegistry(VersionedRegistry):
    """Versioned connector classes keyed by ``(connector_id, version)``."""

    def __init__(self):
        super().__init__("connector")

    def register_class(self, connector_id, version, connector_cls):
        return super().register(connector_id, version, connector_cls)

    def build(self, connector_id, version=None, **kwargs):
        connector_cls = self.get(connector_id, version)
        resolved = version or self.active_version(connector_id)
        kwargs["version"] = resolved
        return connector_cls(**kwargs)


__all__ = ["ConnectorRegistry"]
