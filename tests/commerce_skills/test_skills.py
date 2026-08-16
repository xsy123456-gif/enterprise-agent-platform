"""Skill registry + definition tests."""

import pytest

from app.commerce.skills import (
    SkillDefinition,
    SkillRegistry,
    build_business_skill_definitions,
    build_skill_system,
)
from app.commerce.diagnostics.errors import DuplicateDefinitionError

EXPECTED_SKILLS = {
    "store_performance_diagnosis",
    "product_performance_diagnosis",
    "advertising_performance_diagnosis",
    "inventory_risk_diagnosis",
    "review_issue_diagnosis",
    "product_360_diagnosis",
    "daily_operations_triage",
}

PLAN_MAPPING = {
    "store_performance_diagnosis": {"store_health_scan", "gmv_decline_diagnosis",
                                    "conversion_decline_diagnosis"},
    "product_performance_diagnosis": {"product_anomaly_diagnosis"},
    "advertising_performance_diagnosis": {"advertising_health_scan",
                                          "roas_decline_diagnosis",
                                          "high_spend_low_conversion",
                                          "search_term_waste"},
    "inventory_risk_diagnosis": {"stockout_risk", "slow_moving_inventory",
                                 "inventory_sales_imbalance"},
    "review_issue_diagnosis": {"rating_deterioration", "emerging_product_issue"},
    "product_360_diagnosis": {"product_360"},
    "daily_operations_triage": {"daily_operations_scan"},
}


def test_seven_skills_defined():
    definitions = build_business_skill_definitions()
    assert {d.skill_id for d in definitions} == EXPECTED_SKILLS
    assert len(definitions) == 7


def test_skill_plan_mapping():
    definitions = build_business_skill_definitions()
    by_id = {d.skill_id: d for d in definitions}
    for skill_id, plans in PLAN_MAPPING.items():
        assert set(by_id[skill_id].plan_ids) == plans
        assert by_id[skill_id].default_plan_id in plans


def test_skills_are_versioned():
    definitions = build_business_skill_definitions()
    for d in definitions:
        assert d.version == "1.0"
        assert d.description  # a clear business goal is required


def test_skill_registry_version_coexistence():
    registry = SkillRegistry()
    registry.register(SkillDefinition(
        skill_id="store_performance_diagnosis", version="1.0", domain="sales",
        description="store diagnosis", plan_ids=("store_health_scan",),
        default_plan_id="store_health_scan",
    ))
    registry.register(SkillDefinition(
        skill_id="store_performance_diagnosis", version="2.0", domain="sales",
        description="store diagnosis v2", plan_ids=("store_health_scan",),
        default_plan_id="store_health_scan",
    ))
    assert set(registry.versions("store_performance_diagnosis")) == {"1.0", "2.0"}
    assert registry.get("store_performance_diagnosis").version == "1.0"
    assert registry.get("store_performance_diagnosis", "2.0").version == "2.0"


def test_skill_registry_duplicate_rejected():
    registry = SkillRegistry()
    registry.register(SkillDefinition(
        skill_id="x", version="1.0", domain="sales", description="x",
        plan_ids=(), default_plan_id="",
    ))
    with pytest.raises(DuplicateDefinitionError):
        registry.register(SkillDefinition(
            skill_id="x", version="1.0", domain="sales", description="x",
            plan_ids=(), default_plan_id="",
        ))


def test_skill_system_wires_plans_and_skills():
    system = build_skill_system()
    assert set(system.skills) == EXPECTED_SKILLS
    # all 15 plans are registered + activated.
    for plan_id in {
        p for plans in PLAN_MAPPING.values() for p in plans
    }:
        assert system.plan_registry.get_active_ir(plan_id).checksum
