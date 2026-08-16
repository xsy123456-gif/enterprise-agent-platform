"""Integration sync runtime (Phase 12.9.6).

Wires the integration connector/adapter (resolved from versioned registries with
tenant-scoped credentials) into the frozen Phase 7 ``SyncCoordinator``.  The
coordinator does the actual fetch -> land -> map -> stage -> publish -> events
pipeline; this runtime only resolves and binds the external boundary pieces.
"""

from app.commerce.ingestion.coordinator import SyncCoordinator
from app.commerce.ingestion.events import SyncEvents
from app.commerce.ingestion.infra import (
    Quarantine,
    RawLanding,
    SyncLock,
    SyncStateStore,
)
from app.commerce.ingestion.publish import PublishManager, Staging
from app.commerce.ingestion.registry import SyncDefinitionRegistry


class IntegrationSyncRuntime:

    def __init__(self, connector_registry, adapter_registry, credential_provider,
                 secret_provider, repository, identity_map=None, event_bus=None):
        self.connector_registry = connector_registry
        self.adapter_registry = adapter_registry
        self.credential_provider = credential_provider
        self.secret_provider = secret_provider
        self.repository = repository
        self.identity_map = identity_map
        self.event_bus = event_bus

    def run(self, sync_definition, binding, trace_id=None):
        connector_cls = self.connector_registry.get(
            binding.connector_id,
            binding.connector_version or None,
        )
        provider = getattr(connector_cls, "provider", binding.connector_id)
        credential = self.credential_provider.resolve(sync_definition.tenant_id,
                                                      provider)

        connector = self.connector_registry.build(
            binding.connector_id,
            version=binding.connector_version or None,
            credential=credential,
            secret_provider=self.secret_provider,
            **binding.connector_config,
        )
        adapter = self.adapter_registry.build(
            binding.adapter_id,
            version=binding.adapter_version or None,
            tenant_id=sync_definition.tenant_id,
            store_id=sync_definition.store_id,
        )

        registry = SyncDefinitionRegistry()
        registry.register(sync_definition)
        coordinator = SyncCoordinator(
            registry=registry,
            connectors={sync_definition.connector_id: connector},
            adapters={sync_definition.adapter_id: adapter},
            landing=RawLanding(),
            quarantine=Quarantine(),
            staging=Staging(self.repository),
            publish=PublishManager(self.repository, self.identity_map),
            lock=SyncLock(),
            state_store=SyncStateStore(),
            events=SyncEvents(event_bus=self.event_bus),
        )
        return coordinator.run(sync_definition.sync_id, trace_id=trace_id)


__all__ = ["IntegrationSyncRuntime"]
