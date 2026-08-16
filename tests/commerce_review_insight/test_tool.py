"""Phase 11.5 Tool Integration tests (review_insight.query)."""

import pytest

from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics.plans.ports import FactQuerySpec
from app.commerce.domain import Listing, Review, ReviewInsight, Store
from app.commerce.platform import CAPABILITY_TOOL, build_commerce_tool_surface
from app.commerce.query.service import CommerceQueryService
from app.commerce.repositories.inmemory import InMemoryCommerceRepository
from app.commerce.tools import ReviewInsightQueryTool
from app.commerce.trusted_context import (
    project_trusted_context,
    reset_trusted_context,
    set_trusted_context,
)
from app.permission.models.scope import PermissionScope, ScopeGrant
from app.permission.models.subject import PermissionSubject


class CountingRepository(InMemoryCommerceRepository):
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


def _seed(repo):
    repo.upsert_store("company_A", Store(
        store_id="JP01", tenant_id="company_A", platform="amazon", marketplace="JP",
        external_store_id="ext-JP01", name="JP", currency="JPY", timezone="Asia/Tokyo",
    ))
    repo.upsert_store("company_A", Store(
        store_id="US01", tenant_id="company_A", platform="amazon", marketplace="US",
        external_store_id="ext-US01", name="US", currency="USD", timezone="America/New_York",
    ))
    repo.upsert_listing("company_A", Listing(
        listing_id="listing_1", tenant_id="company_A", store_id="JP01",
        platform="amazon", external_listing_id="B0",
    ))
    repo.upsert_review("company_A", Review(
        review_id="rev1", tenant_id="company_A", store_id="JP01",
        listing_id="listing_1", platform="amazon", external_review_id="R1",
        rating=2.0, content="battery died",
    ))
    repo.upsert_review_insight("company_A", ReviewInsight(
        review_insight_id="ri1", review_id="rev1", sentiment="negative",
        issues=("BATTERY_FAILURE",), topics=("battery",), confidence=0.91,
        severity="high", extractor_id="review_extractor", extractor_version="1.0",
        model_provider="deepseek", model_version="v3", prompt_version="2",
        knowledge_policy_version="kp1", knowledge_context_version="kc1",
    ))


@pytest.fixture
def repo():
    repository = CountingRepository()
    _seed(repository)
    repository.query_count = 0
    return repository


@pytest.fixture
def query_service(repo):
    return CommerceQueryService(repo)


@pytest.fixture
def tool(query_service):
    return ReviewInsightQueryTool(query_service)


@pytest.fixture
def trusted_jp():
    subject = PermissionSubject(
        subject_id="U001", tenant_id="company_A",
        roles=frozenset({"product_operator"}),
        scopes=PermissionScope((ScopeGrant("business.store", frozenset({"JP01"})),)),
    )
    return project_trusted_context(subject, {})


def _execute(tool, arguments, trusted):
    token = set_trusted_context(trusted)
    try:
        return tool.execute(arguments)
    finally:
        reset_trusted_context(token)


# ── Allowed query returns AI facts + provenance ─────────────

def test_allowed_query_by_review_returns_provenance(tool, trusted_jp):
    result = _execute(tool, {"store_id": "JP01", "review_id": "rev1"}, trusted_jp)
    insight = result.data[0]
    assert insight.review_insight_id == "ri1"
    assert insight.issues == ("BATTERY_FAILURE",)
    assert insight.topics == ("battery",)
    assert insight.confidence == 0.91
    assert insight.severity == "high"
    assert insight.extractor_id == "review_extractor"
    assert insight.extractor_version == "1.0"
    assert insight.model_provider == "deepseek"
    assert insight.model_version == "v3"
    assert insight.prompt_version == "2"
    assert insight.knowledge_policy_version == "kp1"
    assert insight.knowledge_context_version == "kc1"


def test_allowed_query_by_listing(tool, trusted_jp):
    result = _execute(tool, {"store_id": "JP01", "listing_id": "listing_1"}, trusted_jp)
    assert result.data[0].review_insight_id == "ri1"


# ── AI facts only: no raw content, no business analysis ─────

def test_insight_exposes_no_raw_content_or_business_analysis(tool, trusted_jp):
    result = _execute(tool, {"store_id": "JP01", "review_id": "rev1"}, trusted_jp)
    data = result.data[0].to_dict()
    for forbidden in ("content", "title", "cause", "impact", "priority",
                      "recommendation", "action"):
        assert forbidden not in data


# ── STRICT scope denial before any canonical query ──────────

def test_scope_denied_before_query(tool, repo, trusted_jp):
    result = _execute(tool, {"store_id": "US01", "review_id": "rev1"}, trusted_jp)
    assert result.code == "PERMISSION_DENIED"
    assert repo.query_count == 0


def test_scope_denied_zero_invocation_via_surface(query_service, repo, trusted_jp):
    surface = build_commerce_tool_surface(query_service)
    spec = FactQuerySpec(
        query_id="q", capability="commerce.review_insight.read", resource="",
        subject=SubjectRef("STORE", "US01"), params={"review_id": "rev1"},
    )
    result = surface.fact_executor.execute(spec, trusted_jp)
    assert result.error == "PERMISSION_DENIED"
    assert result.records == ()
    assert repo.query_count == 0


# ── Capability / binding registration ───────────────────────

def test_capability_and_binding_registered(query_service):
    surface = build_commerce_tool_surface(query_service)
    assert "review_insight.query" in surface.tools
    cap_ids = {c.capability_id for c in surface.capabilities}
    assert "commerce.review_insight.read" in cap_ids
    assert CAPABILITY_TOOL["commerce.review_insight.read"] == "review_insight.query"


def test_fact_executor_returns_ai_facts(query_service, trusted_jp):
    surface = build_commerce_tool_surface(query_service)
    spec = FactQuerySpec(
        query_id="q", capability="commerce.review_insight.read", resource="",
        subject=SubjectRef("STORE", "JP01"), params={"review_id": "rev1"},
    )
    result = surface.fact_executor.execute(spec, trusted_jp)
    assert result.error is None
    assert result.records
    record = result.records[0]
    assert record["review_insight_id"] == "ri1"
    assert record["issues"] == ["BATTERY_FAILURE"]
    assert record["extractor_id"] == "review_extractor"
    assert record["model_provider"] == "deepseek"
    assert "cause" not in record and "impact" not in record and "priority" not in record
