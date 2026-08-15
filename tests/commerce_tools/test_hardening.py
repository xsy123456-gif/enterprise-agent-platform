"""Phase 6 Final Gate Hardening tests."""

from dataclasses import replace

import pytest

from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics.plans import (
    CompileContext,
    FactQueryExecutionError,
    PlanDefinition,
    PlanExecutor,
    StepDefinition,
    STEP_FACT_QUERY,
    STEP_RESULT_ASSEMBLE,
    STOP_UNSUPPORTED,
)
from app.commerce.diagnostics.plans.ports import FactQuerySpec
from app.commerce.trusted_context import (
    current_trusted_context,
    reset_trusted_context,
    set_trusted_context,
    project_trusted_context,
)
from app.permission.models.subject import PermissionSubject
from app.permission.models.scope import PermissionScope, ScopeGrant


def _spec(capability, resource, store_id):
    return FactQuerySpec(
        query_id="q", capability=capability, resource=resource,
        subject=SubjectRef("STORE", store_id),
    )


# ── 1. FactQuery typed error propagation ────────────────────

def test_permission_denied_is_typed_error_not_insufficient(surface, trusted_u001):
    result = surface.fact_executor.execute(_spec("commerce.metrics.read", "GMV", "US01"),
                                           trusted_u001)
    assert result.error == "PERMISSION_DENIED"
    assert result.records == ()
    # NOT data insufficiency.
    assert result.quality != "INSUFFICIENT"


def test_invalid_request_is_typed_error(surface, trusted_u001):
    result = surface.fact_executor.execute(_spec("commerce.metrics.read", "ROAS", "JP01"),
                                           trusted_u001)
    assert result.error == "INVALID_REQUEST"


def test_subject_not_found_is_typed_error(surface, trusted_u001):
    spec = FactQuerySpec(
        query_id="q", capability="commerce.store.read", resource="",
        subject=None,
        params={"platform": "amazon", "external_store_id": "ext-NOPE"},
    )
    result = surface.fact_executor.execute(spec, trusted_u001)
    assert result.error == "SUBJECT_NOT_FOUND"


# ── 2. PERMISSION_DENIED final behavior ─────────────────────

def test_permission_denied_propagates_as_execution_error(surface, trusted_u001):
    plan = PlanDefinition(
        plan_id="denied_prop", version="1.0", domain="conversion",
        required_capabilities=("commerce.metrics.read",),
        steps=(
            StepDefinition("q", STEP_FACT_QUERY,
                           {"capability": "commerce.metrics.read", "resource": "GMV",
                            "evidence_code": "GMV"},
                           on_failure="STOP", next=("assemble",)),
            StepDefinition("assemble", STEP_RESULT_ASSEMBLE, {}),
        ),
    )
    from app.commerce.diagnostics.registry.metric_registry import MetricDefinitionRegistry
    from app.commerce.diagnostics.plans.registry import DiagnosticPlanRegistry
    ctx = CompileContext(metric_registry=MetricDefinitionRegistry())
    registry = DiagnosticPlanRegistry(ctx)
    registry.register(plan)
    registry.activate(plan.plan_id)
    state = PlanExecutor().execute(
        registry.get_active_ir(plan.plan_id), ctx, surface.fact_executor,
        SubjectRef("STORE", "US01"), trusted_context=trusted_u001,
    )
    # The typed execution error halts the plan (STOP), NOT data insufficiency.
    assert state.evidence == []
    assert state.outcome == STOP_UNSUPPORTED
    assert any("PERMISSION_DENIED" in e for e in state.errors)


# ── 3. TrustedExecutionContext permissions fix ──────────────

def test_permissions_are_not_derived_from_roles():
    subject = PermissionSubject(
        subject_id="U001", tenant_id="company_A", roles=frozenset({"product_operator"}),
        scopes=PermissionScope((ScopeGrant("business.store", frozenset({"JP01"})),)),
    )
    trusted = project_trusted_context(subject, {})
    assert trusted.permissions == ()
    assert "business.store:JP01" in trusted.scopes


# ── 4. Capability-specific authorization ────────────────────

def test_metrics_allowed_but_review_denied(surface, counting_repository, trusted_u003):
    metrics = surface.fact_executor.execute(
        _spec("commerce.metrics.read", "GMV", "JP01"), trusted_u003,
    )
    assert metrics.records  # advertising dept may read metrics
    review = surface.fact_executor.execute(
        _spec("commerce.review.read", "", "JP01"), trusted_u003,
    )
    assert review.error == "PERMISSION_DENIED"
    assert review.records == ()


# ── 5. AdPromotedItem support ───────────────────────────────

def test_advertising_query_ad_promoted_item(surface, trusted_u001):
    tool = surface.tools["advertising.query"]
    token = set_trusted_context(trusted_u001)
    try:
        result = tool.execute({"subject_type": "AD_PROMOTED_ITEM", "ad_id": "ad1",
                               "store_id": "JP01"})
    finally:
        reset_trusted_context(token)
    assert result.data[0].ad_id == "ad1"
    assert result.data[0].listing_id == "listing_1"
    # AdPromotedItem links Ad -> Listing, never writes sku_id onto Ad.
    from app.commerce.domain import Ad
    assert not hasattr(Ad(ad_id="x", ad_group_id="g", external_ad_id="e"), "sku_id")


# ── 6. Denied zero-invocation counters ──────────────────────

def test_denied_zero_invocation(surface, counting_repository, trusted_u001):
    tool = surface.tools["metric.query"]
    original = tool._query
    tool.business_calls = 0

    def wrapped(*args, **kwargs):
        tool.business_calls += 1
        return original(*args, **kwargs)

    tool._query = wrapped
    try:
        result = surface.fact_executor.execute(
            _spec("commerce.metrics.read", "GMV", "US01"), trusted_u001,
        )
    finally:
        tool._query = original

    assert result.error == "PERMISSION_DENIED"
    assert tool.business_calls == 0           # Tool business execution = 0
    assert counting_repository.query_count == 0  # QueryService/Repository = 0
    assert result.records == ()              # Evidence = 0


# ── 7. Audit allow/deny assertions ──────────────────────────

def test_audit_allow_metadata(surface, trusted_u001):
    surface.audit.logs.clear()
    surface.fact_executor.execute(_spec("commerce.metrics.read", "GMV", "JP01"),
                                  trusted_u001)
    allow = [log for log in surface.audit.logs if log["action"] == "allow"]
    assert allow
    entry = allow[0]
    assert entry["tool"] == "metric.query"
    assert entry["capability"] == "commerce.metrics.read"
    assert entry["principal_id"] == "U001"
    assert entry["tenant_id"] == "company_A"
    assert entry["trace_id"]
    assert entry["execution_id"]
    assert entry["subject"]["id"] == "JP01"


def test_audit_deny_recorded_before_query(surface, counting_repository, trusted_u001):
    surface.audit.logs.clear()
    surface.fact_executor.execute(_spec("commerce.metrics.read", "GMV", "US01"),
                                  trusted_u001)
    deny = [log for log in surface.audit.logs if log["action"] == "deny"]
    assert deny
    assert deny[0]["tool"] == "metric.query"
    assert deny[0]["capability"] == "commerce.metrics.read"
    assert counting_repository.query_count == 0


# ── 8. External store resolution security ───────────────────

def test_external_resolution_resolves_then_scope_then_read(surface, trusted_u001):
    tool = surface.tools["store.get"]
    token = set_trusted_context(trusted_u001)
    try:
        allowed = tool.execute({"platform": "amazon", "external_store_id": "ext-JP01"})
        denied = tool.execute({"platform": "amazon", "external_store_id": "ext-US01"})
    finally:
        reset_trusted_context(token)
    assert allowed.data[0].store_id == "JP01"
    assert denied.code == "PERMISSION_DENIED"


# ── 9. Pagination + ReviewInsight ───────────────────────────

def test_catalog_pagination_contracts(surface, trusted_u001):
    tool = surface.tools["catalog.query"]
    token = set_trusted_context(trusted_u001)
    try:
        page1 = tool.execute({"subject_type": "PRODUCT", "page": {"limit": 2}})
        page2 = tool.execute({"subject_type": "PRODUCT", "page": {"limit": 2, "cursor": page1.page.next_cursor}})
    finally:
        reset_trusted_context(token)
    assert page1.page.returned_count == 2
    assert page1.page.has_more is True
    assert page1.page.next_cursor is not None
    ids1 = {p.product_id for p in page1.data}
    ids2 = {p.product_id for p in page2.data}
    assert not (ids1 & ids2)  # deterministic, no overlap


def test_catalog_pagination_malformed_cursor(surface, trusted_u001):
    tool = surface.tools["catalog.query"]
    token = set_trusted_context(trusted_u001)
    try:
        result = tool.execute({"subject_type": "PRODUCT", "page": {"limit": 2, "cursor": "opaque-not-a-number"}})
    finally:
        reset_trusted_context(token)
    # Malformed cursor is treated as offset 0 (fail-safe first page).
    assert result.page.returned_count == 2


def test_review_query_returns_insight_with_provenance(surface, trusted_u001):
    tool = surface.tools["review.query"]
    token = set_trusted_context(trusted_u001)
    try:
        result = tool.execute({"subject_type": "REVIEW_INSIGHT", "review_id": "rev1",
                               "store_id": "JP01"})
    finally:
        reset_trusted_context(token)
    assert result.data[0].review_insight_id == "ri1"
    assert result.data[0].model_provider == "openai"
    assert result.data[0].model_version == "gpt-4o"
    assert result.data[0].extractor_version == "1.0"
    assert result.data[0].confidence == 0.92


def test_review_query_insight_does_not_leak_raw(surface, trusted_u001):
    tool = surface.tools["review.query"]
    token = set_trusted_context(trusted_u001)
    try:
        result = tool.execute({"subject_type": "REVIEW", "listing_id": "listing_1",
                               "store_id": "JP01"})
    finally:
        reset_trusted_context(token)
    assert "content" not in result.data[0]
    assert "title" not in result.data[0]
