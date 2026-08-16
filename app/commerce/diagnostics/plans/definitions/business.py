"""The 15 v1 DiagnosticPlans (Phase 9).

Declarative, versioned plan definitions built on the Phase 5 plan framework and
the Phase 3-4 + Phase 6 definitions.  Plans reference metrics / policies /
rule sets / impact formulas / priority policies and capabilities *by name*;
they never inline thresholds, formulas, rules or tool implementation ids.
"""

from app.commerce.diagnostics.plans.schema import (
    STEP_ANOMALY_DETECT,
    STEP_DATA_QUALITY_GATE,
    STEP_FACT_QUERY,
    STEP_IMPACT_ESTIMATE,
    STEP_METRIC_COMPUTE,
    STEP_PRIORITY_EVALUATE,
    STEP_RESULT_ASSEMBLE,
    STEP_RULE_EVALUATE,
    PlanDefinition,
    StepDefinition,
)

_VERSION = "1.0"

CAP_METRICS = "commerce.metrics.read"
CAP_INVENTORY = "commerce.inventory.read"
CAP_REVIEW = "commerce.review.read"
CAP_ADVERTISING = "commerce.advertising.read"
CAP_CATALOG = "commerce.catalog.read"


def _fact(sid, resource, code, capability=CAP_METRICS):
    return sid, STEP_FACT_QUERY, {
        "capability": capability, "resource": resource, "evidence_code": code,
    }


def _metric(sid, metric, inputs):
    return sid, STEP_METRIC_COMPUTE, {"metric": metric, "inputs": inputs}


def _anomaly(sid, metric, baseline_metric, signal_code, domain, policy):
    return sid, STEP_ANOMALY_DETECT, {
        "policy": policy, "metric": metric, "baseline_metric": baseline_metric,
        "signal_code": signal_code, "domain": domain,
    }


def _rule(sid, rule_set):
    return sid, STEP_RULE_EVALUATE, {"rule_set": rule_set}


def _impact(sid, formula, inputs):
    return sid, STEP_IMPACT_ESTIMATE, {"formula": formula, "inputs": inputs}


def _priority(sid, policy, factors):
    return sid, STEP_PRIORITY_EVALUATE, {"policy": policy, "factors": factors}


def _assemble(sid):
    return sid, STEP_RESULT_ASSEMBLE, {}


def _chain(specs):
    steps = []
    for index, (sid, typ, params) in enumerate(specs):
        nxt = (specs[index + 1][0],) if index < len(specs) - 1 else ()
        steps.append(StepDefinition(sid, typ, params, next=nxt))
    return steps


def _plan(plan_id, skill_id, domain, specs, capabilities, evidence):
    return PlanDefinition(
        plan_id=plan_id, version=_VERSION, domain=domain,
        skill_id=skill_id, skill_version=_VERSION,
        required_capabilities=tuple(capabilities),
        required_evidence=tuple(evidence),
        steps=tuple(_chain(specs)),
    )


def _factors(magnitude_ref):
    return {
        "severity": magnitude_ref,
        "business_impact": magnitude_ref,
        "urgency": magnitude_ref,
        "confidence": "evidence:CONFIDENCE",
        "actionability": "evidence:ACTIONABILITY",
    }


# ── S01/S02/S03: Store Operations ───────────────────────────

def store_health_scan():
    specs = [
        _fact("q_gmv", "GMV", "GMV"),
        _fact("q_orders", "ORDERS", "ORDERS"),
        _fact("q_sessions", "SESSIONS", "SESSIONS"),
        _metric("aov", "AOV", {"GMV": "evidence:GMV", "ORDERS": "evidence:ORDERS"}),
        _metric("cvr", "CVR", {"ORDERS": "evidence:ORDERS", "SESSIONS": "evidence:SESSIONS"}),
        _anomaly("gmv_anom", "evidence:GMV", "evidence:GMV_B", "GMV_DROP", "sales", "commerce.sales.v1"),
        _anomaly("cvr_anom", "metric:cvr", "metric:cvr_b", "CVR_DROP", "conversion", "commerce.conversion.v1"),
        _rule("rule", "commerce.sales.v1"),
        _assemble("assemble"),
    ]
    return _plan("store_health_scan", "store_performance_diagnosis", "sales", specs,
                 (CAP_METRICS,), ("GMV", "ORDERS", "SESSIONS"))


def gmv_decline_diagnosis():
    specs = [
        _fact("q_gmv", "GMV", "GMV"),
        _fact("q_orders", "ORDERS", "ORDERS"),
        _fact("q_sessions", "SESSIONS", "SESSIONS"),
        _metric("aov", "AOV", {"GMV": "evidence:GMV", "ORDERS": "evidence:ORDERS"}),
        _anomaly("gmv_anom", "evidence:GMV", "evidence:GMV_B", "GMV_DROP", "sales", "commerce.sales.v1"),
        _anomaly("aov_anom", "metric:aov", "metric:aov_b", "AOV_DROP", "sales", "commerce.sales.v1"),
        _rule("rule", "commerce.sales.v1"),
        _impact("impact", "est_revenue_loss",
                {"GMV_BASELINE": "evidence:GMV_B", "DROP_RATE": "evidence:DROP_RATE"}),
        _priority("priority", "commerce.priority.v1", _factors("evidence:GMV")),
        _assemble("assemble"),
    ]
    return _plan("gmv_decline_diagnosis", "store_performance_diagnosis", "sales", specs,
                 (CAP_METRICS,), ("GMV", "ORDERS", "SESSIONS"))


def conversion_decline_diagnosis():
    specs = [
        _fact("q_orders", "ORDERS", "ORDERS"),
        _fact("q_sessions", "SESSIONS", "SESSIONS"),
        _fact("q_rating", "REVIEW_RATING", "REVIEW_RATING", capability=CAP_REVIEW),
        _metric("cvr", "CVR", {"ORDERS": "evidence:ORDERS", "SESSIONS": "evidence:SESSIONS"}),
        _anomaly("cvr_anom", "metric:cvr", "metric:cvr_b", "CVR_DROP", "conversion", "commerce.conversion.v1"),
        _rule("rule", "commerce.conversion.v1"),
        _impact("impact", "est_revenue_loss",
                {"GMV_BASELINE": "evidence:GMV_B", "DROP_RATE": "evidence:DROP_RATE"}),
        _priority("priority", "commerce.priority.v1", _factors("evidence:ORDERS")),
        _assemble("assemble"),
    ]
    return _plan("conversion_decline_diagnosis", "store_performance_diagnosis", "conversion", specs,
                 (CAP_METRICS, CAP_REVIEW), ("ORDERS", "SESSIONS"))


# ── S04: Product Operations ─────────────────────────────────

def product_anomaly_diagnosis():
    specs = [
        _fact("q_units", "UNITS", "UNITS"),
        _fact("q_orders", "ORDERS", "ORDERS"),
        _fact("q_sessions", "SESSIONS", "SESSIONS"),
        _metric("cvr", "CVR", {"ORDERS": "evidence:ORDERS", "SESSIONS": "evidence:SESSIONS"}),
        _anomaly("units_anom", "evidence:UNITS", "evidence:UNITS_B", "UNITS_DROP", "sales", "commerce.sales.v1"),
        _anomaly("cvr_anom", "metric:cvr", "metric:cvr_b", "CVR_DROP", "conversion", "commerce.conversion.v1"),
        _rule("rule", "commerce.sales.v1"),
        _assemble("assemble"),
    ]
    return _plan("product_anomaly_diagnosis", "product_performance_diagnosis", "sales", specs,
                 (CAP_METRICS,), ("UNITS", "ORDERS", "SESSIONS"))


def slow_moving_inventory():
    specs = [
        _fact("q_velocity", "SALES_VELOCITY", "SALES_VELOCITY"),
        _fact("q_inventory", "AVAILABLE_INVENTORY", "AVAILABLE_INVENTORY", capability=CAP_INVENTORY),
        _anomaly("velocity_anom", "evidence:SALES_VELOCITY", "evidence:SALES_VELOCITY_B",
                 "SLOW_MOVING", "inventory", "commerce.inventory.v1"),
        _rule("rule", "commerce.inventory.v1"),
        _impact("impact", "inventory_capital_exposure",
                {"EXCESS_INVENTORY_VALUE": "evidence:AVAILABLE_INVENTORY"}),
        _priority("priority", "commerce.priority.v1", _factors("evidence:AVAILABLE_INVENTORY")),
        _assemble("assemble"),
    ]
    return _plan("slow_moving_inventory", "inventory_risk_diagnosis", "inventory", specs,
                 (CAP_METRICS, CAP_INVENTORY), ("SALES_VELOCITY", "AVAILABLE_INVENTORY"))


# ── S06-S09: Advertising Operations ─────────────────────────

def advertising_health_scan():
    specs = [
        _fact("q_clicks", "CLICKS", "CLICKS"),
        _fact("q_impressions", "IMPRESSIONS", "IMPRESSIONS"),
        _fact("q_spend", "AD_SPEND", "AD_SPEND"),
        _fact("q_sales", "AD_SALES", "AD_SALES"),
        _metric("ctr", "CTR", {"CLICKS": "evidence:CLICKS", "IMPRESSIONS": "evidence:IMPRESSIONS"}),
        _metric("cpc", "CPC", {"AD_SPEND": "evidence:AD_SPEND", "CLICKS": "evidence:CLICKS"}),
        _metric("roas", "ROAS", {"AD_SALES": "evidence:AD_SALES", "AD_SPEND": "evidence:AD_SPEND"}),
        _metric("acos", "ACOS", {"AD_SPEND": "evidence:AD_SPEND", "AD_SALES": "evidence:AD_SALES"}),
        _anomaly("roas_anom", "metric:roas", "metric:roas_b", "ROAS_DROP", "advertising", "commerce.advertising.v1"),
        _anomaly("ctr_anom", "metric:ctr", "metric:ctr_b", "CTR_DROP", "advertising", "commerce.advertising.v1"),
        _rule("rule", "commerce.advertising.v1"),
        _assemble("assemble"),
    ]
    return _plan("advertising_health_scan", "advertising_performance_diagnosis", "advertising", specs,
                 (CAP_METRICS,), ("CLICKS", "IMPRESSIONS", "AD_SPEND", "AD_SALES"))


def roas_decline_diagnosis():
    specs = [
        _fact("q_spend", "AD_SPEND", "AD_SPEND"),
        _fact("q_sales", "AD_SALES", "AD_SALES"),
        _fact("q_clicks", "CLICKS", "CLICKS"),
        _metric("roas", "ROAS", {"AD_SALES": "evidence:AD_SALES", "AD_SPEND": "evidence:AD_SPEND"}),
        _metric("cpc", "CPC", {"AD_SPEND": "evidence:AD_SPEND", "CLICKS": "evidence:CLICKS"}),
        _anomaly("roas_anom", "metric:roas", "metric:roas_b", "ROAS_DROP", "advertising", "commerce.advertising.v1"),
        _anomaly("cpc_anom", "metric:cpc", "metric:cpc_b", "CPC_RISE", "advertising", "commerce.advertising.v1"),
        _rule("rule", "commerce.advertising.v1"),
        _impact("impact", "observed_ad_waste", {"WASTED_SPEND": "evidence:AD_SPEND"}),
        _priority("priority", "commerce.priority.v1", _factors("evidence:AD_SPEND")),
        _assemble("assemble"),
    ]
    return _plan("roas_decline_diagnosis", "advertising_performance_diagnosis", "advertising", specs,
                 (CAP_METRICS,), ("AD_SPEND", "AD_SALES", "CLICKS"))


def high_spend_low_conversion():
    specs = [
        _fact("q_spend", "AD_SPEND", "AD_SPEND"),
        _fact("q_clicks", "CLICKS", "CLICKS"),
        _fact("q_orders", "AD_ORDERS", "AD_ORDERS"),
        _metric("ad_cvr", "AD_CVR", {"AD_ORDERS": "evidence:AD_ORDERS", "AD_CLICKS": "evidence:AD_CLICKS"}),
        _anomaly("spend_anom", "evidence:AD_SPEND", "evidence:AD_SPEND_B", "SPEND_RISE", "advertising", "commerce.advertising.v1"),
        _anomaly("cvr_anom", "metric:ad_cvr", "metric:ad_cvr_b", "AD_CVR_DROP", "advertising", "commerce.advertising.v1"),
        _rule("rule", "commerce.advertising.v1"),
        _impact("impact", "observed_ad_waste", {"WASTED_SPEND": "evidence:AD_SPEND"}),
        _priority("priority", "commerce.priority.v1", _factors("evidence:AD_SPEND")),
        _assemble("assemble"),
    ]
    return _plan("high_spend_low_conversion", "advertising_performance_diagnosis", "advertising", specs,
                 (CAP_METRICS,), ("AD_SPEND", "CLICKS", "AD_ORDERS"))


def search_term_waste():
    specs = [
        _fact("q_term_spend", "SEARCH_TERM_SPEND", "SEARCH_TERM_SPEND", capability=CAP_ADVERTISING),
        _fact("q_orders", "AD_ORDERS", "AD_ORDERS"),
        _anomaly("waste_anom", "evidence:SEARCH_TERM_SPEND", "evidence:SEARCH_TERM_SPEND_B",
                 "SEARCH_TERM_WASTE", "advertising", "commerce.advertising.v1"),
        _rule("rule", "commerce.advertising.v1"),
        _impact("impact", "observed_ad_waste", {"WASTED_SPEND": "evidence:SEARCH_TERM_SPEND"}),
        _priority("priority", "commerce.priority.v1", _factors("evidence:SEARCH_TERM_SPEND")),
        _assemble("assemble"),
    ]
    return _plan("search_term_waste", "advertising_performance_diagnosis", "advertising", specs,
                 (CAP_ADVERTISING, CAP_METRICS), ("SEARCH_TERM_SPEND",))


# ── S10/S11: Inventory Operations ───────────────────────────

def stockout_risk():
    specs = [
        _fact("q_inventory", "AVAILABLE_INVENTORY", "AVAILABLE_INVENTORY", capability=CAP_INVENTORY),
        _fact("q_units", "UNITS", "UNITS"),
        _fact("q_period", "PERIOD_DAYS", "PERIOD_DAYS"),
        _metric("velocity", "SALES_VELOCITY", {"UNITS": "evidence:UNITS", "PERIOD_DAYS": "evidence:PERIOD_DAYS"}),
        _metric("dos", "DAYS_OF_SUPPLY", {"AVAILABLE_INVENTORY": "evidence:AVAILABLE_INVENTORY",
                                          "SALES_VELOCITY": "evidence:SALES_VELOCITY"}),
        _anomaly("dos_anom", "metric:dos", "metric:dos_b", "DAYS_OF_SUPPLY_LOW", "inventory", "commerce.inventory.v1"),
        _rule("rule", "commerce.inventory.v1"),
        _impact("impact", "projected_stockout_loss",
                {"DAILY_REVENUE": "evidence:DAILY_REVENUE", "STOCKOUT_DAYS": "evidence:STOCKOUT_DAYS"}),
        _priority("priority", "commerce.priority.v1", _factors("evidence:AVAILABLE_INVENTORY")),
        _assemble("assemble"),
    ]
    return _plan("stockout_risk", "inventory_risk_diagnosis", "inventory", specs,
                 (CAP_INVENTORY, CAP_METRICS), ("AVAILABLE_INVENTORY", "UNITS", "PERIOD_DAYS"))


def inventory_sales_imbalance():
    specs = [
        _fact("q_inventory", "AVAILABLE_INVENTORY", "AVAILABLE_INVENTORY", capability=CAP_INVENTORY),
        _fact("q_units", "UNITS", "UNITS"),
        _fact("q_period", "PERIOD_DAYS", "PERIOD_DAYS"),
        _metric("velocity", "SALES_VELOCITY", {"UNITS": "evidence:UNITS", "PERIOD_DAYS": "evidence:PERIOD_DAYS"}),
        _anomaly("inventory_anom", "evidence:AVAILABLE_INVENTORY", "evidence:AVAILABLE_INVENTORY_B",
                 "INVENTORY_HIGH", "inventory", "commerce.inventory.v1"),
        _anomaly("velocity_anom", "metric:velocity", "metric:velocity_b",
                 "SLOW_MOVING", "inventory", "commerce.inventory.v1"),
        _rule("rule", "commerce.inventory.v1"),
        _impact("impact", "inventory_capital_exposure",
                {"EXCESS_INVENTORY_VALUE": "evidence:AVAILABLE_INVENTORY"}),
        _priority("priority", "commerce.priority.v1", _factors("evidence:AVAILABLE_INVENTORY")),
        _assemble("assemble"),
    ]
    return _plan("inventory_sales_imbalance", "inventory_risk_diagnosis", "inventory", specs,
                 (CAP_INVENTORY, CAP_METRICS), ("AVAILABLE_INVENTORY", "UNITS", "PERIOD_DAYS"))


# ── S12/S13: Review Operations ──────────────────────────────

def rating_deterioration():
    specs = [
        _fact("q_rating", "REVIEW_RATING", "REVIEW_RATING", capability=CAP_REVIEW),
        _fact("q_negative", "NEGATIVE_REVIEW_RATE", "NEGATIVE_REVIEW_RATE", capability=CAP_REVIEW),
        _anomaly("rating_anom", "evidence:REVIEW_RATING", "evidence:REVIEW_RATING_B",
                 "RATING_DROP", "review", "commerce.review.v1"),
        _anomaly("negative_anom", "evidence:NEGATIVE_REVIEW_RATE", "evidence:NEGATIVE_REVIEW_RATE_B",
                 "NEGATIVE_REVIEW_RATE_RISE", "review", "commerce.review.v1"),
        _rule("rule", "commerce.review.v1"),
        _priority("priority", "commerce.priority.v1", _factors("evidence:REVIEW_RATING")),
        _assemble("assemble"),
    ]
    return _plan("rating_deterioration", "review_issue_diagnosis", "review", specs,
                 (CAP_REVIEW,), ("REVIEW_RATING", "NEGATIVE_REVIEW_RATE"))


def emerging_product_issue():
    specs = [
        _fact("q_issue_rate", "ISSUE_RATE", "ISSUE_RATE", capability=CAP_REVIEW),
        _fact("q_rating", "REVIEW_RATING", "REVIEW_RATING", capability=CAP_REVIEW),
        _anomaly("issue_anom", "evidence:ISSUE_RATE", "evidence:ISSUE_RATE_B",
                 "EMERGING_ISSUE_RATE_RISE", "review", "commerce.review.v1"),
        _rule("rule", "commerce.review.v1"),
        _priority("priority", "commerce.priority.v1", _factors("evidence:ISSUE_RATE")),
        _assemble("assemble"),
    ]
    return _plan("emerging_product_issue", "review_issue_diagnosis", "review", specs,
                 (CAP_REVIEW,), ("ISSUE_RATE",))


# ── S14: Product 360 ────────────────────────────────────────

def product_360():
    specs = [
        _fact("q_units", "UNITS", "UNITS"),
        _fact("q_orders", "ORDERS", "ORDERS"),
        _fact("q_sessions", "SESSIONS", "SESSIONS"),
        _fact("q_spend", "AD_SPEND", "AD_SPEND"),
        _fact("q_sales", "AD_SALES", "AD_SALES"),
        _fact("q_rating", "REVIEW_RATING", "REVIEW_RATING", capability=CAP_REVIEW),
        _fact("q_inventory", "AVAILABLE_INVENTORY", "AVAILABLE_INVENTORY", capability=CAP_INVENTORY),
        _metric("cvr", "CVR", {"ORDERS": "evidence:ORDERS", "SESSIONS": "evidence:SESSIONS"}),
        _metric("roas", "ROAS", {"AD_SALES": "evidence:AD_SALES", "AD_SPEND": "evidence:AD_SPEND"}),
        _anomaly("units_anom", "evidence:UNITS", "evidence:UNITS_B", "UNITS_DROP", "sales", "commerce.sales.v1"),
        _anomaly("cvr_anom", "metric:cvr", "metric:cvr_b", "CVR_DROP", "conversion", "commerce.conversion.v1"),
        _anomaly("roas_anom", "metric:roas", "metric:roas_b", "ROAS_DROP", "advertising", "commerce.advertising.v1"),
        _anomaly("rating_anom", "evidence:REVIEW_RATING", "evidence:REVIEW_RATING_B", "RATING_DROP", "review", "commerce.review.v1"),
        _rule("rule", "commerce.conversion.v1"),
        _impact("impact", "est_revenue_loss",
                {"GMV_BASELINE": "evidence:GMV_B", "DROP_RATE": "evidence:DROP_RATE"}),
        _priority("priority", "commerce.priority.v1", _factors("evidence:UNITS")),
        _assemble("assemble"),
    ]
    return _plan("product_360", "product_360_diagnosis", "sales", specs,
                 (CAP_METRICS, CAP_REVIEW, CAP_INVENTORY),
                 ("UNITS", "ORDERS", "SESSIONS", "AD_SPEND", "AD_SALES", "REVIEW_RATING"))


# ── S15: Daily Operations Triage ────────────────────────────

def daily_operations_scan():
    specs = [
        _fact("q_gmv", "GMV", "GMV"),
        _fact("q_orders", "ORDERS", "ORDERS"),
        _fact("q_sessions", "SESSIONS", "SESSIONS"),
        _fact("q_spend", "AD_SPEND", "AD_SPEND"),
        _fact("q_sales", "AD_SALES", "AD_SALES"),
        _fact("q_inventory", "AVAILABLE_INVENTORY", "AVAILABLE_INVENTORY", capability=CAP_INVENTORY),
        _metric("cvr", "CVR", {"ORDERS": "evidence:ORDERS", "SESSIONS": "evidence:SESSIONS"}),
        _metric("roas", "ROAS", {"AD_SALES": "evidence:AD_SALES", "AD_SPEND": "evidence:AD_SPEND"}),
        _anomaly("gmv_anom", "evidence:GMV", "evidence:GMV_B", "GMV_DROP", "sales", "commerce.sales.v1"),
        _anomaly("cvr_anom", "metric:cvr", "metric:cvr_b", "CVR_DROP", "conversion", "commerce.conversion.v1"),
        _anomaly("roas_anom", "metric:roas", "metric:roas_b", "ROAS_DROP", "advertising", "commerce.advertising.v1"),
        _anomaly("inv_anom", "evidence:AVAILABLE_INVENTORY", "evidence:AVAILABLE_INVENTORY_B",
                 "INVENTORY_HIGH", "inventory", "commerce.inventory.v1"),
        _rule("rule", "commerce.sales.v1"),
        _priority("priority", "commerce.priority.v1", _factors("evidence:GMV")),
        _assemble("assemble"),
    ]
    return _plan("daily_operations_scan", "daily_operations_triage", "sales", specs,
                 (CAP_METRICS, CAP_INVENTORY),
                 ("GMV", "ORDERS", "SESSIONS", "AD_SPEND", "AD_SALES", "AVAILABLE_INVENTORY"))


def build_business_plan_definitions():
    """Return the 15 v1 DiagnosticPlans as a list of PlanDefinition."""
    return [
        store_health_scan(),
        gmv_decline_diagnosis(),
        conversion_decline_diagnosis(),
        product_anomaly_diagnosis(),
        slow_moving_inventory(),
        advertising_health_scan(),
        roas_decline_diagnosis(),
        high_spend_low_conversion(),
        search_term_waste(),
        stockout_risk(),
        inventory_sales_imbalance(),
        rating_deterioration(),
        emerging_product_issue(),
        product_360(),
        daily_operations_scan(),
    ]


__all__ = ["build_business_plan_definitions"]
