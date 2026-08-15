"""Version governance for the four Phase 4 definition registries."""

import pytest

from app.commerce.diagnostics import (
    DiagnosticPolicy,
    DiagnosticPolicyRegistry,
    ImpactFormula,
    ImpactFormulaRegistry,
    PriorityPolicy,
    PriorityPolicyRegistry,
    Rule,
    RuleSet,
    RuleSetRegistry,
)
from app.commerce.diagnostics.errors import (
    DuplicateDefinitionError,
    UnknownDefinitionVersionError,
)


def test_policy_registry_version_coexistence():
    registry = DiagnosticPolicyRegistry()
    registry.register(DiagnosticPolicy(policy_id="commerce.anomaly.v1", version="1.0"))
    registry.register(DiagnosticPolicy(policy_id="commerce.anomaly.v1", version="2.0"))
    assert set(registry.versions("commerce.anomaly.v1")) == {"1.0", "2.0"}
    assert registry.active_version("commerce.anomaly.v1") == "1.0"
    assert registry.get("commerce.anomaly.v1", "2.0").version == "2.0"


def test_policy_registry_duplicate_rejected():
    registry = DiagnosticPolicyRegistry()
    registry.register(DiagnosticPolicy(policy_id="p", version="1.0"))
    with pytest.raises(DuplicateDefinitionError):
        registry.register(DiagnosticPolicy(policy_id="p", version="1.0"))


def test_policy_registry_activate():
    registry = DiagnosticPolicyRegistry()
    registry.register(DiagnosticPolicy(policy_id="p", version="1.0"))
    registry.register(DiagnosticPolicy(policy_id="p", version="2.0"))
    registry.activate("p", "2.0")
    assert registry.get("p").version == "2.0"
    with pytest.raises(UnknownDefinitionVersionError):
        registry.get("p", "9.0")


def test_ruleset_registry_version_coexistence():
    registry = RuleSetRegistry()
    registry.register(RuleSet(rule_set_id="commerce.conversion.v1", version="1.0"))
    registry.register(RuleSet(rule_set_id="commerce.conversion.v1", version="2.0"))
    assert set(registry.versions("commerce.conversion.v1")) == {"1.0", "2.0"}
    assert registry.get("commerce.conversion.v1", "1.0").version == "1.0"


def test_impact_registry_version_coexistence():
    registry = ImpactFormulaRegistry()
    registry.register(ImpactFormula(formula_id="est_revenue_loss", version="1.0",
                                    impact_type="ESTIMATED", classification="REVENUE_LOSS",
                                    expression="X * 1", dependencies=("X",)))
    registry.register(ImpactFormula(formula_id="est_revenue_loss", version="2.0",
                                    impact_type="ESTIMATED", classification="REVENUE_LOSS",
                                    expression="X * 2", dependencies=("X",)))
    assert set(registry.versions("est_revenue_loss")) == {"1.0", "2.0"}


def test_priority_registry_version_coexistence():
    registry = PriorityPolicyRegistry()
    registry.register(PriorityPolicy(policy_id="commerce.priority.v1", version="1.0"))
    registry.register(PriorityPolicy(policy_id="commerce.priority.v1", version="2.0"))
    assert set(registry.versions("commerce.priority.v1")) == {"1.0", "2.0"}
    assert registry.active_version("commerce.priority.v1") == "1.0"
