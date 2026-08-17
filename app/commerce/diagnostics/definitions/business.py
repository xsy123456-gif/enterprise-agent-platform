"""Business knowledge definitions for the v1 DiagnosticPlans (Phase 9).

These are the versioned domain definitions the plans *reference by name* — the
plans never inline thresholds, formulas, rules, impact expressions or priority
weights.  Rules map signals to causes with causal role + support level.
"""

from app.commerce.diagnostics.definitions.impact import ImpactFormula
from app.commerce.diagnostics.definitions.policies import DiagnosticPolicy
from app.commerce.diagnostics.definitions.priority import PriorityPolicy
from app.commerce.diagnostics.definitions.rules import (
    Rule,
    RuleCondition,
    RuleConsequent,
    RuleSet,
)

_VERSION = "1.0"

# ── Diagnostic policies (per domain) ────────────────────────

def build_business_diagnostic_policies():
    return [
        DiagnosticPolicy(
            policy_id="commerce.sales.v1", version=_VERSION, domain="sales",
            min_baseline_volume=0.0, min_sample_size=0,
            warning_relative_change=0.10, abnormal_relative_change=0.20,
            critical_relative_change=0.40,
        ),
        DiagnosticPolicy(
            policy_id="commerce.conversion.v1", version=_VERSION, domain="conversion",
            min_baseline_volume=0.0001, min_sample_size=0,
            warning_relative_change=0.10, abnormal_relative_change=0.20,
            critical_relative_change=0.40,
        ),
        DiagnosticPolicy(
            policy_id="commerce.advertising.v1", version=_VERSION, domain="advertising",
            min_baseline_volume=0.0, min_sample_size=0,
            warning_relative_change=0.15, abnormal_relative_change=0.25,
            critical_relative_change=0.50,
        ),
        DiagnosticPolicy(
            policy_id="commerce.inventory.v1", version=_VERSION, domain="inventory",
            min_baseline_volume=0.0, min_sample_size=0,
            warning_relative_change=0.10, abnormal_relative_change=0.20,
            critical_relative_change=0.40,
        ),
        DiagnosticPolicy(
            policy_id="commerce.review.v1", version=_VERSION, domain="review",
            min_baseline_volume=0.0, min_sample_size=0,
            warning_relative_change=0.05, abnormal_relative_change=0.10,
            critical_relative_change=0.25,
        ),
    ]


# ── Rule sets (per domain) ──────────────────────────────────

def _rule(rule_id, antecedents, consequent):
    return Rule(rule_id=rule_id, version=_VERSION,
                antecedents=tuple(antecedents), consequent=consequent)


def build_business_rule_sets():
    return [
        RuleSet(rule_set_id="commerce.sales.v1", version=_VERSION, domain="sales", rules=[
            _rule("gmv_traffic_decline", [RuleCondition("GMV_DROP", "ABNORMAL", "DOWN"),
                                          RuleCondition("TRAFFIC_DROP", "ABNORMAL", "DOWN")],
                  RuleConsequent("TRAFFIC_DECLINE", "PRIMARY", "CONFIRMED",
                                 required_evidence=("SESSIONS",))),
            _rule("gmv_product_mix_shift", [RuleCondition("AOV_DROP", "ABNORMAL", "DOWN")],
                  RuleConsequent("PRODUCT_MIX_SHIFT", "PRIMARY", "SUPPORTED")),
        ]),
        RuleSet(rule_set_id="commerce.conversion.v1", version=_VERSION, domain="conversion", rules=[
            _rule("cvr_price_increase", [RuleCondition("CVR_DROP", "ABNORMAL", "DOWN")],
                  RuleConsequent("PRICE_INCREASE", "PRIMARY", "CONFIRMED",
                                 required_evidence=("PRICE_INDEX",))),
            _rule("cvr_review_deterioration", [RuleCondition("CVR_DROP", "ABNORMAL", "DOWN"),
                                               RuleCondition("NEGATIVE_REVIEW_RATE_RISE", "WARNING", "UP")],
                  RuleConsequent("PRODUCT_REPUTATION_DETERIORATION", "CONTRIBUTING", "POSSIBLE",
                                 required_evidence=("REVIEW_RATING",),
                                 contradicting_evidence=("PRICE_INDEX",))),
        ]),
        RuleSet(rule_set_id="commerce.advertising.v1", version=_VERSION, domain="advertising", rules=[
            _rule("roas_cpc_increase", [RuleCondition("ROAS_DROP", "ABNORMAL", "DOWN"),
                                        RuleCondition("CPC_RISE", "ABNORMAL", "UP")],
                  RuleConsequent("TRAFFIC_COST_INCREASE", "PRIMARY", "CONFIRMED",
                                 required_evidence=("CPC",))),
            _rule("roas_product_conversion", [RuleCondition("ROAS_DROP", "ABNORMAL", "DOWN"),
                                              RuleCondition("CVR_DROP", "ABNORMAL", "DOWN")],
                  RuleConsequent("PRODUCT_CONVERSION_DETERIORATION", "PRIMARY", "SUPPORTED",
                                 required_evidence=("AD_CVR",))),
            _rule("search_term_waste", [RuleCondition("SEARCH_TERM_WASTE", "ABNORMAL")],
                  RuleConsequent("IRRELEVANT_SEARCH_TERM_SPEND", "PRIMARY", "CONFIRMED",
                                 required_evidence=("SEARCH_TERM_SPEND",))),
        ]),
        RuleSet(rule_set_id="commerce.inventory.v1", version=_VERSION, domain="inventory", rules=[
            _rule("stockout_risk", [RuleCondition("DAYS_OF_SUPPLY_LOW", "ABNORMAL", "DOWN")],
                  RuleConsequent("STOCKOUT_RISK", "PRIMARY", "CONFIRMED",
                                 required_evidence=("AVAILABLE_INVENTORY",))),
            _rule("slow_moving", [RuleCondition("SLOW_MOVING", "ABNORMAL")],
                  RuleConsequent("SLOW_MOVING_INVENTORY", "PRIMARY", "SUPPORTED",
                                 required_evidence=("SALES_VELOCITY",))),
        ]),
        RuleSet(rule_set_id="commerce.review.v1", version=_VERSION, domain="review", rules=[
            _rule("rating_deterioration", [RuleCondition("RATING_DROP", "ABNORMAL", "DOWN")],
                  RuleConsequent("PRODUCT_REPUTATION_DETERIORATION", "PRIMARY", "SUPPORTED",
                                 required_evidence=("REVIEW_RATING",))),
            _rule("emerging_quality_issue", [RuleCondition("EMERGING_ISSUE_RATE_RISE", "ABNORMAL", "UP")],
                  RuleConsequent("EMERGING_PRODUCT_QUALITY_ISSUE", "PRIMARY", "SUPPORTED",
                                 required_evidence=("ISSUE_RATE",))),
        ]),
    ]


# ── Impact formulas ─────────────────────────────────────────

def build_business_impact_formulas():
    return [
        ImpactFormula(
            formula_id="est_revenue_loss", version=_VERSION, impact_type="REVENUE_LOSS",
            classification="ESTIMATED", unit="currency",
            expression="GMV_BASELINE * DROP_RATE", dependencies=("GMV_BASELINE", "DROP_RATE"),
        ),
        ImpactFormula(
            formula_id="observed_ad_waste", version=_VERSION, impact_type="WASTED_AD_SPEND",
            classification="OBSERVED", unit="currency",
            expression="WASTED_SPEND * 1", dependencies=("WASTED_SPEND",),
        ),
        ImpactFormula(
            formula_id="inventory_capital_exposure", version=_VERSION,
            impact_type="INVENTORY_CAPITAL_EXPOSURE", classification="ESTIMATED", unit="currency",
            expression="EXCESS_INVENTORY_VALUE * 1", dependencies=("EXCESS_INVENTORY_VALUE",),
        ),
        ImpactFormula(
            formula_id="projected_stockout_loss", version=_VERSION,
            impact_type="STOCKOUT_LOSS", classification="PROJECTED", unit="currency",
            expression="DAILY_REVENUE * STOCKOUT_DAYS", dependencies=("DAILY_REVENUE", "STOCKOUT_DAYS"),
        ),
    ]


# ── Priority policy ─────────────────────────────────────────

def build_business_priority_policy():
    return PriorityPolicy(policy_id="commerce.priority.v1", version=_VERSION)


__all__ = [
    "build_business_diagnostic_policies",
    "build_business_rule_sets",
    "build_business_impact_formulas",
    "build_business_priority_policy",
]
