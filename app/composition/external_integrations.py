"""External integration wiring (Phase 18.13.4).

Wires the HTTP connectors (Amazon / TikTok / SAP / Salesforce / NetSuite) and
their adapters into versioned registries, together with simulation credential +
secret providers.  This is *composition only*: it injects config (base URLs,
scope, credentials), never hardcodes a token inside a connector, and is only
activated when ``EXTERNAL_INTEGRATION_MODE=simulation`` is explicitly set (never
by default in production).
"""

import os
from dataclasses import dataclass, field
from types import SimpleNamespace

from app.commerce.integration.adapters import (
    AmazonAdapter,
    NetSuiteAdapter,
    SapAdapter,
    TikTokAdapter,
)
from app.commerce.integration.connectors import (
    AmazonHttpConnector,
    NetSuiteHttpConnector,
    SalesforceHttpConnector,
    SapHttpConnector,
    TikTokHttpConnector,
)
from app.commerce.integration.credentials.models import Credential, SecretReference
from app.commerce.integration.credentials.provider import (
    InMemoryCredentialProvider,
    InMemorySecretProvider,
)
from app.commerce.integration.registry import AdapterRegistry, ConnectorRegistry
from app.commerce.integration.sync import ConnectorBinding, IntegrationSyncRuntime


@dataclass(frozen=True)
class SimulationConnectorConfig:
    amazon_base_url: str = "http://127.0.0.1:9101"
    tiktok_base_url: str = "http://127.0.0.1:9102"
    sap_base_url: str = "http://127.0.0.1:9103"
    salesforce_base_url: str = "http://127.0.0.1:9104"
    netsuite_base_url: str = "http://127.0.0.1:9105"
    amazon_scope: dict = field(default_factory=lambda: {"seller_id": "store-001"})
    tiktok_scope: dict = field(default_factory=lambda: {"shop_id": "shop-001"})
    sap_scope: dict = field(default_factory=lambda: {"plant": "PL01",
                                                     "company_code": "CC01"})
    netsuite_scope: dict = field(default_factory=lambda: {"subsidiary": "SUB-001"})
    tenant_id: str = "company_A"

    @classmethod
    def from_env(cls):
        env = os.getenv
        return cls(
            amazon_base_url=env("AMAZON_API_BASE_URL", "http://127.0.0.1:9101"),
            tiktok_base_url=env("TIKTOK_API_BASE_URL", "http://127.0.0.1:9102"),
            sap_base_url=env("SAP_API_BASE_URL", "http://127.0.0.1:9103"),
            salesforce_base_url=env("SALESFORCE_API_BASE_URL",
                                    "http://127.0.0.1:9104"),
            netsuite_base_url=env("NETSUITE_API_BASE_URL", "http://127.0.0.1:9105"),
        )


def _secret(name):
    return SecretReference(reference_id=f"sim/{name}/token")


def _build_registries(config):
    connectors = ConnectorRegistry()
    connectors.register_class("amazon_sp_api", "1.0", AmazonHttpConnector)
    connectors.register_class("tiktok_shop", "1.0", TikTokHttpConnector)
    connectors.register_class("sap_erp", "1.0", SapHttpConnector)
    connectors.register_class("salesforce_crm", "1.0", SalesforceHttpConnector)
    connectors.register_class("netsuite_erp", "1.0", NetSuiteHttpConnector)

    adapters = AdapterRegistry()
    adapters.register_class("amazon_adapter", "1.0", AmazonAdapter)
    adapters.register_class("tiktok_adapter", "1.0", TikTokAdapter)
    adapters.register_class("sap_adapter", "1.0", SapAdapter)
    adapters.register_class("netsuite_adapter", "1.0", NetSuiteAdapter)
    return connectors, adapters


def _build_credentials(config):
    tenant = config.tenant_id
    credentials = InMemoryCredentialProvider([
        Credential(credential_id=f"{provider}-sim", tenant_id=tenant,
                   provider=provider, secret_ref=_secret(provider))
        for provider in ("amazon", "tiktok", "sap", "salesforce", "netsuite")
    ])
    secrets = InMemorySecretProvider({
        "sim/amazon/token": "sim-amazon-key",
        "sim/tiktok/token": "sim-tiktok-key",
        "sim/sap/token": "sim-sap-key",
        "sim/salesforce/token": "sim-salesforce-key",
        "sim/netsuite/token": "sim-netsuite-key",
    })
    return credentials, secrets


def _default_bindings(config):
    def binding(sync_id, connector_id, adapter_id, base_url, scope):
        return ConnectorBinding(
            sync_id=sync_id, connector_id=connector_id, adapter_id=adapter_id,
            connector_config={"base_url": base_url, "scope": scope},
        )

    return [
        binding("amazon_listing_sync", "amazon_sp_api", "amazon_adapter",
                config.amazon_base_url, config.amazon_scope),
        binding("tiktok_product_sync", "tiktok_shop", "tiktok_adapter",
                config.tiktok_base_url, config.tiktok_scope),
        binding("sap_material_sync", "sap_erp", "sap_adapter",
                config.sap_base_url, config.sap_scope),
        binding("netsuite_item_sync", "netsuite_erp", "netsuite_adapter",
                config.netsuite_base_url, config.netsuite_scope),
    ]


def build_simulation_external_integrations(environment=None, config=None,
                                           repository=None, identity_map=None,
                                           event_bus=None):
    config = config or SimulationConnectorConfig.from_env()
    connectors, adapters = _build_registries(config)
    credentials, secrets = _build_credentials(config)
    runtime = None
    if repository is not None:
        runtime = IntegrationSyncRuntime(
            connectors, adapters, credentials, secrets, repository,
            identity_map=identity_map, event_bus=event_bus,
        )
    return SimpleNamespace(
        config=config,
        connector_registry=connectors,
        adapter_registry=adapters,
        credential_provider=credentials,
        secret_provider=secrets,
        sync_runtime=runtime,
        default_bindings=_default_bindings(config),
        mode="simulation",
    )


__all__ = [
    "SimulationConnectorConfig",
    "build_simulation_external_integrations",
]
