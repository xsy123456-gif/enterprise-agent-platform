"""Allowed + Denied E2E chains with zero-invocation assertions."""

from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics import MetricDefinitionRegistry
from app.commerce.diagnostics.plans import (
    CompileContext,
    PlanDefinition,
    PlanExecutor,
    StepDefinition,
    STEP_FACT_QUERY,
    STEP_RESULT_ASSEMBLE,
)
from app.commerce.diagnostics.plans.ports import FactQuerySpec


def _spec(resource, store_id):
    return FactQuerySpec(
        query_id="q1", capability="commerce.metrics.read", resource=resource,
        subject=SubjectRef("STORE", store_id),
    )


# ── Capability / binding registrations ──────────────────────

def test_six_capabilities_registered(surface):
    ids = {c.capability_id for c in surface.capabilities}
    assert ids == {
        "commerce.store.read", "commerce.catalog.read", "commerce.metrics.read",
        "commerce.inventory.read", "commerce.review.read", "commerce.advertising.read",
    }


def test_six_tools_registered(surface):
    names = set(surface.tools)
    assert names == {
        "store.get", "catalog.query", "metric.query",
        "inventory.query", "review.query", "advertising.query",
    }


def test_six_bindings(surface):
    assert {(b.capability_id, b.tool_name) for b in surface.bindings} == {
        ("commerce.store.read", "store.get"),
        ("commerce.catalog.read", "catalog.query"),
        ("commerce.metrics.read", "metric.query"),
        ("commerce.inventory.read", "inventory.query"),
        ("commerce.review.read", "review.query"),
        ("commerce.advertising.read", "advertising.query"),
    }


# ── Allowed E2E ─────────────────────────────────────────────

def test_allowed_e2e(surface, counting_repository, trusted_u001):
    result = surface.fact_executor.execute(_spec("GMV", "JP01"), trusted_u001)
    assert result.quality == "VALID"
    assert result.records
    assert result.records[0]["metric_name"] == "GMV"
    assert result.provenance is not None
    assert counting_repository.query_count == 1


# ── Denied E2E (scope) ──────────────────────────────────────

def test_denied_e2e_scope(surface, counting_repository, trusted_u001):
    result = surface.fact_executor.execute(_spec("GMV", "US01"), trusted_u001)
    assert result.records == ()
    assert counting_repository.query_count == 0


# ── Denied E2E (department) ─────────────────────────────────

def test_denied_e2e_department(surface, counting_repository, trusted_u006):
    # U006 is finance, which the execution policy does not authorize.
    result = surface.fact_executor.execute(_spec("GMV", "JP01"), trusted_u006)
    assert result.records == ()
    assert counting_repository.query_count == 0


# ── Denied E2E (DERIVED metric) ─────────────────────────────

def test_denied_e2e_derived_metric(surface, counting_repository, trusted_u001):
    result = surface.fact_executor.execute(_spec("ROAS", "JP01"), trusted_u001)
    assert result.records == ()
    assert counting_repository.query_count == 0


# ── Full-plan Denied E2E (zero evidence) ────────────────────

def test_full_plan_denied_e2e(surface, counting_repository, trusted_u001):
    plan = PlanDefinition(
        plan_id="denied_mini", version="1.0", domain="conversion",
        required_capabilities=("commerce.metrics.read",),
        steps=(
            StepDefinition("q", STEP_FACT_QUERY,
                           {"capability": "commerce.metrics.read", "resource": "GMV",
                            "evidence_code": "GMV"}, next=("assemble",)),
            StepDefinition("assemble", STEP_RESULT_ASSEMBLE, {}),
        ),
    )
    compile_context = CompileContext(metric_registry=MetricDefinitionRegistry())
    from app.commerce.diagnostics.plans.registry import DiagnosticPlanRegistry
    registry = DiagnosticPlanRegistry(compile_context)
    registry.register(plan)
    registry.activate(plan.plan_id)
    state = PlanExecutor().execute(
        registry.get_active_ir(plan.plan_id), compile_context, surface.fact_executor,
        SubjectRef("STORE", "US01"), trusted_context=trusted_u001,
    )
    assert state.evidence == []
    assert counting_repository.query_count == 0


def test_full_plan_allowed_e2e(surface, counting_repository, trusted_u001):
    plan = PlanDefinition(
        plan_id="allowed_mini", version="1.0", domain="conversion",
        required_capabilities=("commerce.metrics.read",),
        steps=(
            StepDefinition("q", STEP_FACT_QUERY,
                           {"capability": "commerce.metrics.read", "resource": "GMV",
                            "evidence_code": "GMV"}, next=("assemble",)),
            StepDefinition("assemble", STEP_RESULT_ASSEMBLE, {}),
        ),
    )
    compile_context = CompileContext(metric_registry=MetricDefinitionRegistry())
    from app.commerce.diagnostics.plans.registry import DiagnosticPlanRegistry
    registry = DiagnosticPlanRegistry(compile_context)
    registry.register(plan)
    registry.activate(plan.plan_id)
    state = PlanExecutor().execute(
        registry.get_active_ir(plan.plan_id), compile_context, surface.fact_executor,
        SubjectRef("STORE", "JP01"), trusted_context=trusted_u001,
    )
    assert len(state.evidence) >= 1
    assert state.evidence[0].provenance is not None
    assert counting_repository.query_count == 1


# ── Bypass / safety ─────────────────────────────────────────

def test_spec_cannot_override_tenant(surface, counting_repository, trusted_u001):
    spec = FactQuerySpec(
        query_id="q", capability="commerce.metrics.read", resource="GMV",
        subject=SubjectRef("STORE", "JP01"),
        params={"tenant_id": "evil_tenant", "store_id": "JP01"},
    )
    result = surface.fact_executor.execute(spec, trusted_u001)
    assert result.quality == "VALID"
    # The tenant actually queried is the trusted tenant, never the spec's.
    assert result.records[0]["tenant_id"] == "company_A"


def test_fact_executor_has_no_direct_repository(surface):
    # The production adapter only talks to ToolRunner; it has no QueryService
    # or Repository handle to bypass the governance chain.
    assert not hasattr(surface.fact_executor, "query_service")
    assert not hasattr(surface.fact_executor, "repository")
