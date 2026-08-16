"""Phase 12.8 Hardening + Employee scenario E2E."""

import pytest

from app.commerce.agents import (
    RESPONSE_DIAGNOSTIC,
    AgentDefinition,
    AgentManifest,
    AgentRequest,
    AgentSkillBinding,
    build_employee_agent_runtime,
)
from app.commerce.contracts.subject import SUBJECT_STORE, SubjectRef
from app.commerce.diagnostics.plans import FakeFactQueryExecutor
from app.commerce.diagnostics.plans.ports import TrustedExecutionContext
from app.commerce.skills import build_skill_system

SUBJECT = SubjectRef(SUBJECT_STORE, "JP01")
TRUSTED = TrustedExecutionContext(tenant_id="company_A", principal_id="U001",
                                  scopes=("business.store:JP01",))
CAP_METRICS = "commerce.metrics.read"


@pytest.fixture(scope="module")
def system():
    return build_skill_system()


def _definition():
    return AgentDefinition(
        agent_id="commerce_operations_agent", version="1.0",
        name="Commerce Operations Employee", description="ops", domain="commerce",
    )


def _manifest():
    return AgentManifest(
        agent_id="commerce_operations_agent", version="1.0",
        description="AI assistant for ecommerce operators",
        skills=("store_performance_diagnosis", "advertising_performance_diagnosis",
                "inventory_risk_diagnosis"),
        default_skill="store_performance_diagnosis",
        required_capabilities=(CAP_METRICS,),
    )


def _bindings():
    return [
        AgentSkillBinding(
            agent_id="commerce_operations_agent",
            skill_id="store_performance_diagnosis", skill_version="1.0",
            priority=80, routing_examples=("销量", "GMV", "转化率", "巡检")),
        AgentSkillBinding(
            agent_id="commerce_operations_agent",
            skill_id="advertising_performance_diagnosis", skill_version="1.0",
            priority=90, routing_examples=("广告", "ROAS", "ACOS")),
        AgentSkillBinding(
            agent_id="commerce_operations_agent",
            skill_id="inventory_risk_diagnosis", skill_version="1.0",
            priority=70, routing_examples=("库存", "缺货", "滞销")),
    ]


def _facts():
    facts = {}
    for capability, resource, value in [
        (CAP_METRICS, "GMV", 1000.0), (CAP_METRICS, "GMV_B", 2000.0),
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 40.0),
        (CAP_METRICS, "SESSIONS", 1000.0), (CAP_METRICS, "SESSIONS_B", 1000.0),
    ]:
        facts[(capability, resource, SUBJECT.id)] = {"records": [{"value": value}]}
    return facts


def _agent(system, **kwargs):
    return build_employee_agent_runtime(
        _definition(), _manifest(), system, _bindings(),
        known_subjects={"JP01": SUBJECT}, **kwargs,
    )


# ── Employee scenario E2E ───────────────────────────────────

def test_employee_scenario_e2e(system):
    agent = _agent(system)
    executor = FakeFactQueryExecutor(_facts())
    response = agent.handle(
        AgentRequest(request_id="r1", message="JP01最近销量下降原因？"),
        TRUSTED, executor,
    )
    assert response.response_type == RESPONSE_DIAGNOSTIC
    assert response.diagnostic_result is not None
    signals = {s.signal_code for s in response.diagnostic_result.signals}
    assert "GMV_DROP" in signals
    assert "STORE:JP01" in response.message


def test_e2e_advertising_route(system):
    agent = _agent(system)
    executor = FakeFactQueryExecutor(_facts())
    response = agent.handle(
        AgentRequest(request_id="r1", message="JP01广告ROAS下降"),
        TRUSTED, executor,
    )
    assert response.response_type == RESPONSE_DIAGNOSTIC
    assert response.diagnostic_result.plan_id == "advertising_health_scan"


# ── Replay ──────────────────────────────────────────────────

def test_replay_deterministic_conclusions(system):
    agent = _agent(system)
    first = agent.handle(
        AgentRequest(request_id="r1", message="JP01销量下降"), TRUSTED,
        FakeFactQueryExecutor(_facts()))
    second = agent.handle(
        AgentRequest(request_id="r2", message="JP01销量下降"), TRUSTED,
        FakeFactQueryExecutor(_facts()))
    assert {s.signal_code for s in first.diagnostic_result.signals} == \
           {s.signal_code for s in second.diagnostic_result.signals}
    assert {c.cause_code for c in first.diagnostic_result.causes} == \
           {c.cause_code for c in second.diagnostic_result.causes}


# ── Security ────────────────────────────────────────────────

def test_request_cannot_override_tenant(system):
    agent = _agent(system)
    executor = FakeFactQueryExecutor(_facts())
    # The request carries no identity; the injected trusted context is the only
    # source of tenant/principal, and it reaches the fact executor verbatim.
    request = AgentRequest.from_dict({
        "request_id": "r1", "message": "JP01销量下降",
        "tenant_id": "evil_tenant", "principal_id": "hacker", "scope": "all",
    })
    agent.handle(request, TRUSTED, executor)
    assert executor.last_trusted_context.tenant_id == "company_A"
    assert executor.last_trusted_context.principal_id == "U001"


def test_agent_has_no_direct_repository_access(system):
    agent = _agent(system)
    assert not hasattr(agent, "repository")
    assert not hasattr(agent, "query_service")
    assert not hasattr(agent, "tools")


# ── Performance: rule match skips LLM ───────────────────────

def test_rule_match_does_not_invoke_llm(system):
    def explosive_llm(base, diagnostic):
        raise AssertionError("LLM should not be called for rule-matched input")
    agent = _agent(system, llm=explosive_llm)
    response = agent.handle(
        AgentRequest(request_id="r1", message="JP01销量下降"), TRUSTED,
        FakeFactQueryExecutor(_facts()))
    assert response.response_type == RESPONSE_DIAGNOSTIC
