"""Enterprise integration registry (Phase 16.5)."""

from app.core.versioning import VersionedRegistry


class EnterpriseIntegrationRegistry(VersionedRegistry):

    def __init__(self):
        super().__init__("integration")

    def register_class(self, connector_id, version, connector_cls):
        return super().register(connector_id, version, connector_cls)

    def build(self, connector_id, version=None, **kwargs):
        connector_cls = self.get(connector_id, version)
        resolved = version or self.active_version(connector_id)
        kwargs["version"] = resolved
        return connector_cls(**kwargs)


__all__ = ["EnterpriseIntegrationRegistry"]
