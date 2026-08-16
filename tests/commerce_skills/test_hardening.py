"""Phase 10 Final Gate Hardening tests."""

import pytest

from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics.plans import (
    FakeFactQueryExecutor,
    TrustedExecutionContext,
)
from app.commerce.diagnostics.plans import DiagnosticPlanRegistry
from app.commerce.skills import (
    SKILL_ACTIVE,
    SKILL_DRAFT,
    SKILL_VALIDATED,
    SkillDefinition,
    SkillRegistry,
    SkillResult,
    SkillValidationError,
    build_skill_system,
)
from app.commerce.skills.definitions import build_business_skill_definitions
from app.commerce.skills.system import _build_compile_context

SUBJECT = SubjectRef("STORE", "JP01")
CAP_METRICS = "commerce.metrics.read"


@pytest.fixture(scope="module")
def system():
    return build_skill_system()


# ── 1. Skill capability model ───────────────────────────────

def test_skill_capabilities_are_union_of_plan_capabilities(system):
    for definition in build_business_skill_definitions():
        plan_caps = set()
        for plan_id in definition.plan_ids:
            plan_caps.update(
                system.plan_registry.get_definition(plan_id).required_capabilities
            )
        assert set(definition.required_capabilities) == plan_caps, definition.skill_id


def test_skill_rejects_unknown_capability():
    registry = SkillRegistry()
    with pytest.raises(SkillValidationError):
        registry.register(SkillDefinition(
            skill_id="x", version="1.0", domain="sales", description="x",
            plan_ids=("store_health_scan",), default_plan_id="store_health_scan",
            required_capabilities=("commerce.nonexistent.read",),
        ))


def test_skill_rejects_inconsistent_capabilities(system):
    registry = SkillRegistry(plan_registry=system.plan_registry)
    definition = SkillDefinition(
        skill_id="x", version="1.0", domain="sales", description="x",
        plan_ids=("store_health_scan",), default_plan_id="store_health_scan",
        required_capabilities=("commerce.review.read",),  # wrong: store scan needs metrics
    )
    registry.register(definition)
    with pytest.raises(SkillValidationError):
        registry.validate("x")


# ── 2. Trusted context isolation ────────────────────────────

def test_skill_input_cannot_carry_security_fields():
    from app.commerce.skills.models import SkillInput
    inp = SkillInput(subject=SUBJECT)
    assert not hasattr(inp, "tenant_id")
    assert not hasattr(inp, "principal_id")
    assert not hasattr(inp, "scope")
    assert not hasattr(inp, "scopes")
    assert not hasattr(inp, "permission")
    assert not hasattr(inp, "permissions")


def test_trusted_context_is_passed_through(system):
    executor = FakeFactQueryExecutor({
        (CAP_METRICS, "GMV", "JP01"): {"records": [{"value": 1000.0}]},
        (CAP_METRICS, "GMV_B", "JP01"): {"records": [{"value": 2000.0}]},
        (CAP_METRICS, "ORDERS", "JP01"): {"records": [{"value": 20.0}]},
        (CAP_METRICS, "ORDERS_B", "JP01"): {"records": [{"value": 40.0}]},
        (CAP_METRICS, "SESSIONS", "JP01"): {"records": [{"value": 1000.0}]},
        (CAP_METRICS, "SESSIONS_B", "JP01"): {"records": [{"value": 1000.0}]},
    })
    trusted = TrustedExecutionContext(tenant_id="company_A", principal_id="u1")
    system.run("store_performance_diagnosis", SUBJECT, fact_executor=executor,
               trusted_context=trusted)
    # The fact executor only ever saw the injected trusted context.
    assert executor.last_trusted_context.tenant_id == "company_A"
    assert executor.last_trusted_context.principal_id == "u1"


# ── 3. SkillResult contract ─────────────────────────────────

def test_skill_result_contract(system):
    executor = FakeFactQueryExecutor({
        (CAP_METRICS, "GMV", "JP01"): {"records": [{"value": 1000.0}]},
        (CAP_METRICS, "GMV_B", "JP01"): {"records": [{"value": 2000.0}]},
        (CAP_METRICS, "ORDERS", "JP01"): {"records": [{"value": 20.0}]},
        (CAP_METRICS, "ORDERS_B", "JP01"): {"records": [{"value": 40.0}]},
        (CAP_METRICS, "SESSIONS", "JP01"): {"records": [{"value": 1000.0}]},
        (CAP_METRICS, "SESSIONS_B", "JP01"): {"records": [{"value": 1000.0}]},
    })
    result = system.run("store_performance_diagnosis", SUBJECT, fact_executor=executor)
    assert isinstance(result, SkillResult)
    assert result.skill_id == "store_performance_diagnosis"
    assert result.skill_version == "1.0"
    assert result.plan_id == "store_health_scan"
    assert result.plan_version == "1.0"
    assert result.diagnostic_result is not None
    assert result.execution_id


# ── 4. Skill lifecycle ──────────────────────────────────────

def test_skill_lifecycle(system):
    registry = system.skill_registry
    assert registry.status("store_performance_diagnosis") == SKILL_ACTIVE


def test_lifecycle_draft_validated_active():
    compile_context = _build_compile_context()
    plan_registry = DiagnosticPlanRegistry(compile_context)
    registry = SkillRegistry(plan_registry=plan_registry)
    registry.register(SkillDefinition(
        skill_id="x", version="1.0", domain="sales", description="x",
        plan_ids=(), default_plan_id="",
    ))
    assert registry.status("x") == SKILL_DRAFT
    registry.validate("x")
    assert registry.status("x") == SKILL_VALIDATED
    registry.activate("x")
    assert registry.status("x") == SKILL_ACTIVE


def test_active_skill_requires_active_plan():
    # A skill bound to a registered-but-not-ACTIVE plan cannot activate.
    compile_context = _build_compile_context()
    plan_registry = DiagnosticPlanRegistry(compile_context)
    from app.commerce.diagnostics.plans.definitions.business import (
        build_business_plan_definitions,
    )
    plan = next(p for p in build_business_plan_definitions()
                if p.plan_id == "store_health_scan")
    plan_registry.register(plan)  # registered, NOT activated
    registry = SkillRegistry(plan_registry=plan_registry)
    definition = SkillDefinition(
        skill_id="y", version="1.0", domain="sales", description="y",
        plan_ids=("store_health_scan",), default_plan_id="store_health_scan",
        required_capabilities=(CAP_METRICS,),
    )
    registry.register(definition)
    registry.validate("y")  # plan definition exists + consistency OK
    from app.commerce.diagnostics.errors import UnknownDefinitionError
    with pytest.raises(UnknownDefinitionError):
        registry.activate("y")  # bound plan is not ACTIVE


def test_disable_blocks_active_skill():
    compile_context = _build_compile_context()
    plan_registry = DiagnosticPlanRegistry(compile_context)
    registry = SkillRegistry(plan_registry=plan_registry)
    definition = SkillDefinition(
        skill_id="z", version="1.0", domain="sales", description="z",
        plan_ids=(), default_plan_id="",
    )
    registry.register(definition)
    registry.validate("z")
    registry.activate("z")
    assert registry.get_active_skill("z") is not None
    registry.disable("z")
    from app.commerce.skills.errors import SkillNotActiveError
    with pytest.raises(SkillNotActiveError):
        registry.get_active_skill("z")


# ── 5. Skill replay ─────────────────────────────────────────

def _deterministic_fields(diagnostic):
    return (
        diagnostic.status,
        tuple(sorted((s.signal_code, s.status, s.direction)
                     for s in diagnostic.signals)),
        tuple(sorted((c.cause_code, c.causal_role, c.support_level)
                     for c in diagnostic.causes)),
        tuple(sorted((i.classification, i.impact_type, i.value)
                     for i in diagnostic.impacts)),
        diagnostic.priority.level if diagnostic.priority else None,
    )


def test_skill_replay_deterministic(system):
    facts = {
        (CAP_METRICS, "GMV", "JP01"): {"records": [{"value": 1000.0}]},
        (CAP_METRICS, "GMV_B", "JP01"): {"records": [{"value": 2000.0}]},
        (CAP_METRICS, "ORDERS", "JP01"): {"records": [{"value": 20.0}]},
        (CAP_METRICS, "ORDERS_B", "JP01"): {"records": [{"value": 20.0}]},
        (CAP_METRICS, "SESSIONS", "JP01"): {"records": [{"value": 1000.0}]},
        (CAP_METRICS, "SESSIONS_B", "JP01"): {"records": [{"value": 1000.0}]},
        (CAP_METRICS, "DROP_RATE", "JP01"): {"records": [{"value": 0.5}]},
    }
    first = system.run("store_performance_diagnosis", SUBJECT,
                       fact_executor=FakeFactQueryExecutor(facts),
                       plan_id="gmv_decline_diagnosis")
    second = system.run("store_performance_diagnosis", SUBJECT,
                        fact_executor=FakeFactQueryExecutor(facts),
                        plan_id="gmv_decline_diagnosis")
    assert first.skill_version == second.skill_version == "1.0"
    assert first.plan_version == second.plan_version == "1.0"
    assert _deterministic_fields(first.diagnostic_result) == \
        _deterministic_fields(second.diagnostic_result)
