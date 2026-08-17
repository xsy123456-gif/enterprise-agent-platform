"""Phase 18.15.7b/d orchestration tests: deterministic plan selection + merge."""

import pytest

from app.commerce.contracts.subject import SubjectRef
from app.commerce.skills.system import build_skill_system


class _Facts:
    def __init__(self, facts):
        self.facts = dict(facts)
        self.last_context = None

    def execute(self, spec, trusted_context):
        self.last_context = trusted_context
        key = (spec.capability, spec.resource,
               spec.subject.id if spec.subject else None)
        entry = self.facts.get(key)
        if entry is None:
            from app.commerce.diagnostics.plans.ports import (
                FACT_QUALITY_INSUFFICIENT, FactQueryResult)
            return FactQueryResult(query_id=spec.query_id, records=(),
                                   quality=FACT_QUALITY_INSUFFICIENT)
        from app.commerce.diagnostics.plans.ports import FactQueryResult
        return FactQueryResult(query_id=spec.query_id,
                               records=tuple(dict(r) for r in entry.get("records", ())),
                               quality=entry.get("quality", "VALID"))


def _metric_facts(items):
    facts = {}
    for name, value in items:
        facts[("commerce.metrics.read", name, "JP01")] = {
            "records": [{"value": value}]}
    return facts


def test_conversion_signal_selects_conversion_plan():
    system = build_skill_system()
    # Traffic stable, conversion down -> CVR_DROP -> conversion plan.
    facts = _Facts(_metric_facts([
        ("GMV", 1200.0), ("GMV_B", 2000.0), ("ORDERS", 24.0), ("ORDERS_B", 40.0),
        ("SESSIONS", 2000.0), ("SESSIONS_B", 2000.0),
    ]))
    result = system.diagnose(
        "store_performance_diagnosis", SubjectRef("STORE", "JP01"),
        fact_executor=facts)
    causes = {c.cause_code for c in result.diagnostic_result.causes}
    assert "PRICE_INCREASE" in causes


def test_inventory_signal_selects_stockout_plan():
    system = build_skill_system()
    facts = _Facts(_metric_facts([
        ("GMV", 1000.0), ("GMV_B", 2000.0), ("ORDERS", 20.0), ("ORDERS_B", 40.0),
        ("SESSIONS", 1000.0), ("SESSIONS_B", 2000.0),
        ("AVAILABLE_INVENTORY", 30.0), ("AVAILABLE_INVENTORY_B", 300.0),
        ("UNITS", 100.0), ("UNITS_B", 100.0),
        ("PERIOD_DAYS", 10.0), ("PERIOD_DAYS_B", 10.0),
    ]))
    result = system.diagnose(
        "store_performance_diagnosis", SubjectRef("STORE", "JP01"),
        fact_executor=facts)
    causes = {c.cause_code for c in result.diagnostic_result.causes}
    assert "TRAFFIC_DECLINE" in causes
    assert "STOCKOUT_RISK" in causes


def test_normal_store_produces_no_false_cause():
    system = build_skill_system()
    facts = _Facts(_metric_facts([
        ("GMV", 2000.0), ("GMV_B", 2000.0), ("ORDERS", 40.0), ("ORDERS_B", 40.0),
        ("SESSIONS", 2000.0), ("SESSIONS_B", 2000.0),
        ("AVAILABLE_INVENTORY", 200.0), ("AVAILABLE_INVENTORY_B", 200.0),
        ("UNITS", 40.0), ("UNITS_B", 40.0),
        ("PERIOD_DAYS", 7.0), ("PERIOD_DAYS_B", 7.0),
    ]))
    result = system.diagnose(
        "store_performance_diagnosis", SubjectRef("STORE", "JP01"),
        fact_executor=facts)
    real = {c.cause_code for c in result.diagnostic_result.causes} - {"UNKNOWN"}
    assert real == set()
