"""Phase 12.9.2 Registry tests."""

import pytest

from app.commerce.integration.connectors.base import BaseConnector
from app.commerce.integration.adapters.base import BaseAdapter
from app.commerce.integration.registry import AdapterRegistry, ConnectorRegistry
from app.commerce.diagnostics.errors import UnknownDefinitionVersionError


class _ConnectorV1(BaseConnector):
    connector_id = "demo"

    def _fetch(self, request):
        return None


class _ConnectorV2(BaseConnector):
    connector_id = "demo"

    def _fetch(self, request):
        return None


class _AdapterV1(BaseAdapter):
    adapter_id = "demo"

    def adapt(self, envelope):
        return []


class _AdapterV2(BaseAdapter):
    adapter_id = "demo"

    def adapt(self, envelope):
        return []


def test_connector_registry_versioned():
    registry = ConnectorRegistry()
    registry.register_class("amazon_sp_api", "1.0", _ConnectorV1)
    registry.register_class("amazon_sp_api", "1.1", _ConnectorV2)
    # first registered version becomes active
    assert registry.active_version("amazon_sp_api") == "1.0"
    v1 = registry.build("amazon_sp_api")
    assert isinstance(v1, _ConnectorV1)
    assert v1.version == "1.0"
    v2 = registry.build("amazon_sp_api", version="1.1")
    assert isinstance(v2, _ConnectorV2)
    assert v2.version == "1.1"


def test_connector_registry_unknown_version():
    registry = ConnectorRegistry()
    registry.register_class("amazon_sp_api", "1.0", _ConnectorV1)
    with pytest.raises(UnknownDefinitionVersionError):
        registry.build("amazon_sp_api", version="9.9")


def test_adapter_registry_versioned():
    registry = AdapterRegistry()
    registry.register_class("amazon_listing_adapter", "1.0", _AdapterV1)
    registry.register_class("amazon_listing_adapter", "1.1", _AdapterV2)
    v1 = registry.build("amazon_listing_adapter", tenant_id="company_A")
    assert isinstance(v1, _AdapterV1)
    assert v1.version == "1.0"
    v2 = registry.build("amazon_listing_adapter", version="1.1", tenant_id="company_A")
    assert isinstance(v2, _AdapterV2)


def test_registry_activate_promotes_explicitly():
    registry = ConnectorRegistry()
    registry.register_class("amazon_sp_api", "1.0", _ConnectorV1)
    registry.register_class("amazon_sp_api", "1.1", _ConnectorV2)
    registry.activate("amazon_sp_api", "1.1")
    assert registry.active_version("amazon_sp_api") == "1.1"
    assert isinstance(registry.build("amazon_sp_api"), _ConnectorV2)
