"""Skill execution tests: each skill runs deterministically (no LLM) and
returns a complete DiagnosticResult."""

import pytest

from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics.plans import FakeFactQueryExecutor
from app.commerce.skills import (
    SkillError,
    UnknownPlanForSkill,
    build_skill_system,
)

SUBJECT = SubjectRef("STORE", "JP01")
CAP_METRICS = "commerce.metrics.read"
CAP_REVIEW = "commerce.review.read"
CAP_INVENTORY = "commerce.inventory.read"
CAP_ADVERTISING = "commerce.advertising.read"


@pytest.fixture(scope="module")
def system():
    return build_skill_system()


def make_facts(*items):
    facts = {}
    for capability, resource, value in items:
        facts[(capability, resource, SUBJECT.id)] = {"records": [{"value": value}]}
    return facts


def _run(system, skill_id, facts, plan_id=None):
    return system.run(skill_id, SUBJECT, fact_executor=FakeFactQueryExecutor(facts),
                      plan_id=plan_id)


def test_store_performance_skill(engine_facts):
    result = engine_facts
    assert result.skill_id == "store_performance_diagnosis"
    assert result.plan_id == "store_health_scan"
    assert result.status == "COMPLETED"
    assert {s.signal_code for s in result.signals} >= {"GMV_DROP", "CVR_DROP"}


@pytest.fixture
def engine_facts(system):
    facts = make_facts(
        (CAP_METRICS, "GMV", 1000.0), (CAP_METRICS, "GMV_B", 2000.0),
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 40.0),
        (CAP_METRICS, "SESSIONS", 1000.0), (CAP_METRICS, "SESSIONS_B", 1000.0),
    )
    return _run(system, "store_performance_diagnosis", facts)


def test_product_performance_skill(system):
    facts = make_facts(
        (CAP_METRICS, "UNITS", 50.0), (CAP_METRICS, "UNITS_B", 100.0),
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 40.0),
        (CAP_METRICS, "SESSIONS", 1000.0), (CAP_METRICS, "SESSIONS_B", 1000.0),
    )
    result = _run(system, "product_performance_diagnosis", facts)
    assert result.plan_id == "product_anomaly_diagnosis"
    assert {s.signal_code for s in result.signals} >= {"UNITS_DROP", "CVR_DROP"}


def test_advertising_performance_skill(system):
    facts = make_facts(
        (CAP_METRICS, "CLICKS", 50.0), (CAP_METRICS, "CLICKS_B", 50.0),
        (CAP_METRICS, "IMPRESSIONS", 1000.0), (CAP_METRICS, "IMPRESSIONS_B", 1000.0),
        (CAP_METRICS, "AD_SPEND", 100.0), (CAP_METRICS, "AD_SPEND_B", 100.0),
        (CAP_METRICS, "AD_SALES", 200.0), (CAP_METRICS, "AD_SALES_B", 400.0),
    )
    result = _run(system, "advertising_performance_diagnosis", facts)
    assert result.plan_id == "advertising_health_scan"
    assert "ROAS_DROP" in {s.signal_code for s in result.signals}


def test_inventory_risk_skill(system):
    facts = make_facts(
        (CAP_INVENTORY, "AVAILABLE_INVENTORY", 30.0),
        (CAP_INVENTORY, "AVAILABLE_INVENTORY_B", 300.0),
        (CAP_METRICS, "UNITS", 100.0), (CAP_METRICS, "UNITS_B", 100.0),
        (CAP_METRICS, "PERIOD_DAYS", 10.0), (CAP_METRICS, "PERIOD_DAYS_B", 10.0),
        (CAP_METRICS, "DAILY_REVENUE", 1000.0), (CAP_METRICS, "STOCKOUT_DAYS", 3.0),
        (CAP_METRICS, "DROP_RATE", 0.8),
    )
    result = _run(system, "inventory_risk_diagnosis", facts)
    assert result.plan_id == "stockout_risk"
    assert {c.cause_code for c in result.causes} >= {"STOCKOUT_RISK"}


def test_review_issue_skill(system):
    facts = make_facts(
        (CAP_REVIEW, "REVIEW_RATING", 3.2), (CAP_REVIEW, "REVIEW_RATING_B", 4.5),
        (CAP_REVIEW, "NEGATIVE_REVIEW_RATE", 0.20),
        (CAP_REVIEW, "NEGATIVE_REVIEW_RATE_B", 0.05),
        (CAP_METRICS, "DROP_RATE", 0.3),
    )
    result = _run(system, "review_issue_diagnosis", facts)
    assert result.plan_id == "rating_deterioration"
    assert {c.cause_code for c in result.causes} >= {"PRODUCT_REPUTATION_DETERIORATION"}


def test_product_360_skill(system):
    facts = make_facts(
        (CAP_METRICS, "UNITS", 50.0), (CAP_METRICS, "UNITS_B", 100.0),
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 40.0),
        (CAP_METRICS, "SESSIONS", 1000.0), (CAP_METRICS, "SESSIONS_B", 1000.0),
        (CAP_METRICS, "GMV", 1000.0), (CAP_METRICS, "GMV_B", 2000.0),
        (CAP_METRICS, "AD_SPEND", 100.0), (CAP_METRICS, "AD_SPEND_B", 100.0),
        (CAP_METRICS, "AD_SALES", 200.0), (CAP_METRICS, "AD_SALES_B", 400.0),
        (CAP_REVIEW, "REVIEW_RATING", 3.2), (CAP_REVIEW, "REVIEW_RATING_B", 4.5),
        (CAP_METRICS, "DROP_RATE", 0.5),
    )
    result = _run(system, "product_360_diagnosis", facts)
    assert result.plan_id == "product_360"
    assert {s.signal_code for s in result.signals} >= {
        "UNITS_DROP", "CVR_DROP", "ROAS_DROP", "RATING_DROP",
    }


def test_daily_operations_triage_skill(system):
    facts = make_facts(
        (CAP_METRICS, "GMV", 1000.0), (CAP_METRICS, "GMV_B", 2000.0),
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 40.0),
        (CAP_METRICS, "SESSIONS", 1000.0), (CAP_METRICS, "SESSIONS_B", 1000.0),
        (CAP_METRICS, "AD_SPEND", 100.0), (CAP_METRICS, "AD_SPEND_B", 100.0),
        (CAP_METRICS, "AD_SALES", 200.0), (CAP_METRICS, "AD_SALES_B", 400.0),
        (CAP_INVENTORY, "AVAILABLE_INVENTORY", 30.0),
        (CAP_INVENTORY, "AVAILABLE_INVENTORY_B", 300.0),
    )
    result = _run(system, "daily_operations_triage", facts)
    assert result.plan_id == "daily_operations_scan"
    assert {s.signal_code for s in result.signals} >= {
        "GMV_DROP", "CVR_DROP", "ROAS_DROP", "INVENTORY_HIGH",
    }


def test_skill_selects_explicit_plan(system):
    facts = make_facts(
        (CAP_METRICS, "GMV", 1000.0), (CAP_METRICS, "GMV_B", 2000.0),
        (CAP_METRICS, "ORDERS", 20.0), (CAP_METRICS, "ORDERS_B", 20.0),
        (CAP_METRICS, "SESSIONS", 1000.0), (CAP_METRICS, "SESSIONS_B", 1000.0),
        (CAP_METRICS, "DROP_RATE", 0.5),
    )
    result = _run(system, "store_performance_diagnosis", facts,
                  plan_id="gmv_decline_diagnosis")
    assert result.plan_id == "gmv_decline_diagnosis"


def test_skill_rejects_unsupported_plan(system):
    with pytest.raises(UnknownPlanForSkill):
        _run(system, "product_performance_diagnosis", {},
             plan_id="gmv_decline_diagnosis")


def test_skill_requires_subject(system):
    from app.commerce.skills.models import SkillInput
    from app.commerce.skills.skill import Skill
    definition = system.skill_registry.get("store_performance_diagnosis")
    skill = Skill(definition, system.plan_registry, system.compile_context)
    with pytest.raises(SkillError):
        skill.execute(SkillInput(subject=None), fact_executor=FakeFactQueryExecutor())


def test_skill_requires_fact_executor(system):
    with pytest.raises(SkillError):
        system.run("store_performance_diagnosis", SUBJECT, fact_executor=None)
