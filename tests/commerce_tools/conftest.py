"""Shared fixtures for Commerce Read Tools + E2E tests."""

from pathlib import Path

import pytest

from app.commerce.diagnostics import build_core_metric_registry
from app.commerce.domain import (
    Ad,
    AdGroup,
    AdPromotedItem,
    Campaign,
    InventorySnapshot,
    Listing,
    MetricSeries,
    Product,
    Review,
    ReviewInsight,
    SKU,
    Store,
)
from app.commerce.platform import build_commerce_tool_surface
from app.commerce.query.service import CommerceQueryService
from app.commerce.repositories.inmemory import InMemoryCommerceRepository
from app.commerce.trusted_context import project_trusted_context
from app.identity import build_identity
from app.identity.providers.local_file import LocalFileIdentityProvider
from app.integrations.security import build_security_integration
from app.integrations.security.models.trusted_principal import TrustedPrincipal
from app.permission import PermissionConfig, build_permission
from app.runtime.governance.gate import AllowAllGovernancePolicy, GovernanceGate

ROOT = Path(__file__).resolve().parents[2]


class CountingRepository(InMemoryCommerceRepository):
    """In-memory repository that counts every canonical read."""

    def __init__(self):
        super().__init__()
        self.query_count = 0

    def __getattribute__(self, name):
        attr = object.__getattribute__(self, name)
        if name.startswith(("get_", "list_", "query_", "find_")) and callable(attr):
            def wrapper(*args, **kwargs):
                object.__setattr__(
                    self, "query_count",
                    object.__getattribute__(self, "query_count") + 1,
                )
                return attr(*args, **kwargs)
            return wrapper
        return attr


@pytest.fixture
def identity():
    return build_identity(
        provider=LocalFileIdentityProvider(str(ROOT / "data" / "identity"))
    )


@pytest.fixture
def permission():
    perm = build_permission(
        config=PermissionConfig(policy_root=str(ROOT / "data" / "permission" / "policies"))
    )
    perm.runtime.start()
    return perm


@pytest.fixture
def security(identity, permission):
    return build_security_integration(
        identity_service=identity.service,
        permission_service=permission.service,
        governance_gate=GovernanceGate(AllowAllGovernancePolicy()),
    )


def _seed(repository):
    repository.upsert_store("company_A", Store(
        store_id="JP01", tenant_id="company_A", platform="amazon", marketplace="JP",
        external_store_id="ext-JP01", name="Japan Store 01", currency="JPY",
        timezone="Asia/Tokyo",
    ))
    repository.upsert_store("company_A", Store(
        store_id="US01", tenant_id="company_A", platform="amazon", marketplace="US",
        external_store_id="ext-US01", name="US Store 01", currency="USD",
        timezone="America/New_York",
    ))
    for i in range(1, 6):
        repository.upsert_product("company_A", Product(
            product_id=f"product_{i}", tenant_id="company_A",
            title=f"Product {i}", brand="Acme",
        ))
    repository.upsert_sku("company_A", SKU(
        sku_id="sku_1", tenant_id="company_A", product_id="product_1",
        merchant_sku="SKU-1",
    ))
    repository.upsert_listing("company_A", Listing(
        listing_id="listing_1", tenant_id="company_A", store_id="JP01",
        platform="amazon", external_listing_id="B0ABC", title="Wireless Mouse",
    ))
    repository.upsert_metric("company_A", MetricSeries(
        metric_record_id="gmv", tenant_id="company_A", subject_type="STORE",
        subject_id="JP01", metric_name="GMV", metric_class="AGGREGATED",
        granularity="DAILY", period_start="2026-08-01", period_end="2026-08-02",
        value=12345.6, unit="JPY",
    ))
    repository.upsert_metric("company_A", MetricSeries(
        metric_record_id="orders", tenant_id="company_A", subject_type="STORE",
        subject_id="JP01", metric_name="ORDERS", metric_class="AGGREGATED",
        granularity="DAILY", period_start="2026-08-01", period_end="2026-08-02",
        value=40.0,
    ))
    repository.append_inventory_snapshot("company_A", InventorySnapshot(
        inventory_snapshot_id="inv1", tenant_id="company_A", store_id="JP01",
        sku_id="sku_1", available_quantity=100, snapshot_at="2026-08-01T00:00:00+00:00",
        source_metadata={"source": "amazon"},
    ))
    repository.upsert_review("company_A", Review(
        review_id="rev1", tenant_id="company_A", store_id="JP01", listing_id="listing_1",
        platform="amazon", external_review_id="R1", rating=4.0, content="good product",
    ))
    repository.upsert_review_insight("company_A", ReviewInsight(
        review_insight_id="ri1", review_id="rev1", sentiment="positive",
        model_provider="openai", model_version="gpt-4o", extractor_version="1.0",
        confidence=0.92,
    ))
    repository.upsert_campaign("company_A", Campaign(
        campaign_id="campaign_1", tenant_id="company_A", store_id="JP01",
        platform="amazon", external_campaign_id="C1", name="SP Main",
    ))
    repository.upsert_ad_group("company_A", AdGroup(
        ad_group_id="ag1", campaign_id="campaign_1", external_ad_group_id="AG1",
        name="Group", targeting_type="KEYWORD",
    ))
    repository.upsert_ad("company_A", Ad(
        ad_id="ad1", ad_group_id="ag1", external_ad_id="AD1",
    ))
    repository.upsert_ad_promoted_item("company_A", AdPromotedItem(
        ad_promoted_item_id="api1", ad_id="ad1", listing_id="listing_1",
    ))


@pytest.fixture
def counting_repository():
    repo = CountingRepository()
    _seed(repo)
    repo.query_count = 0
    return repo


@pytest.fixture
def query_service(counting_repository):
    return CommerceQueryService(counting_repository)


@pytest.fixture
def metric_registry():
    return build_core_metric_registry()


@pytest.fixture
def surface(query_service, metric_registry, security):
    return build_commerce_tool_surface(
        query_service, metric_registry=metric_registry,
        governance_gate=security.tool_gate,
    )


def trusted_for(security, principal_id):
    subject = security.resolver.resolve(
        TrustedPrincipal(principal_id=principal_id, source="local")
    )
    return project_trusted_context(subject, {"trace_id": "t1", "execution_id": "e1"})


@pytest.fixture
def trusted_u001(security):
    return trusted_for(security, "U001")


@pytest.fixture
def trusted_u003(security):
    return trusted_for(security, "U003")


@pytest.fixture
def trusted_u006(security):
    return trusted_for(security, "U006")


__all__ = [
    "ROOT", "CountingRepository", "identity", "permission", "security",
    "counting_repository", "query_service", "metric_registry", "surface",
    "trusted_u001", "trusted_u003", "trusted_u006", "trusted_for",
]
