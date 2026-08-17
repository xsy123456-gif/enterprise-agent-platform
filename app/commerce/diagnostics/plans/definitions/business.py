"""The 15 v1 DiagnosticPlans (Phase 9).

Declarative, versioned plan definitions built on the Phase 5 plan framework and
the Phase 3-4 + Phase 6 definitions.  Plans reference metrics / policies /
rule sets / impact formulas / priority policies and capabilities *by name*;
they never inline thresholds, formulas, rules or tool implementation ids.

Each plan fetches source facts (current + baseline), computes derived metrics
(current + baseline), detects anomalies, then evaluates rules, estimates impact
and priority, and assembles the DiagnosticResult.
"""

from app.commerce.diagnostics.plans.schema import (
    STEP_ANOMALY_DETECT,
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


def _metric(sid, metric, inputs, result_name=None):
    params = {"metric": metric, "inputs": inputs}
    if result_name is not None:
        params["result_name"] = result_name
    return sid, STEP_METRIC_COMPUTE, params


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


def _factors():
    # All factors reference a single 0-1 drop-rate fact; weights/thresholds
    # live in the PriorityPolicy (not the plan).
    ref = "evidence:DROP_RATE"
    return {
        "severity": ref,
        "business_impact": ref,
        "urgency": ref,
        "confidence": ref,
        "actionability": ref,
    }


def _drop_rate_fact():
    return _fact("q_drop_rate", "DROP_RATE", "DROP_RATE")


# ── Fact/derived helpers (current + baseline) ───────────────

def _source_pair(prefix, metric, capability=CAP_METRICS):
    return [
        _fact(f"{prefix}q_{metric.lower()}", metric, metric, capability=capability),
        _fact(f"{prefix}q_{metric.lower()}_b", f"{metric}_B", f"{metric}_B",
              capability=capability),
    ]


def _derived_pair(prefix, metric, deps):
    specs = []
    for dep in deps:
        specs.extend(_source_pair(prefix, dep))
    specs.append(_metric(f"{prefix}_m_{metric.lower()}", metric,
                         {d: f"evidence:{d}" for d in deps}))
    specs.append(_metric(f"{prefix}_m_{metric.lower()}_b", metric,
                         {d: f"evidence:{d}_B" for d in deps},
                         result_name=f"{metric}_B"))
    return specs


def _src_anomaly(sid, metric, signal_code, domain, policy):
    return _anomaly(sid, f"evidence:{metric}", f"evidence:{metric}_B",
                    signal_code, domain, policy)


def _derived_anomaly(sid, metric, signal_code, domain, policy):
    return _anomaly(sid, f"metric:{metric}", f"metric:{metric}_B",
                    signal_code, domain, policy)


# ── S01/S02/S03: Store Operations ───────────────────────────

def store_health_scan():
    specs = [
        *_source_pair("s", "GMV"),
        *_source_pair("s", "ORDERS"),
        *_source_pair("s", "SESSIONS"),
        *_source_pair("s", "AVAILABLE_INVENTORY"),
        *_source_pair("s", "UNITS"),
        *_source_pair("s", "PERIOD_DAYS"),
        _metric("aov", "AOV", {"GMV": "evidence:GMV", "ORDERS": "evidence:ORDERS"}),
        _metric("aov_b", "AOV", {"GMV": "evidence:GMV_B", "ORDERS": "evidence:ORDERS_B"}, result_name="AOV_B"),
        _metric("cvr", "CVR", {"ORDERS": "evidence:ORDERS", "SESSIONS": "evidence:SESSIONS"}),
        _metric("cvr_b", "CVR", {"ORDERS": "evidence:ORDERS_B", "SESSIONS": "evidence:SESSIONS_B"}, result_name="CVR_B"),
        _metric("dos", "DAYS_OF_SUPPLY",
                {"AVAILABLE_INVENTORY": "evidence:AVAILABLE_INVENTORY",
                 "UNITS": "evidence:UNITS", "PERIOD_DAYS": "evidence:PERIOD_DAYS"}),
        _metric("dos_b", "DAYS_OF_SUPPLY",
                {"AVAILABLE_INVENTORY": "evidence:AVAILABLE_INVENTORY_B",
                 "UNITS": "evidence:UNITS_B", "PERIOD_DAYS": "evidence:PERIOD_DAYS_B"},
                result_name="DAYS_OF_SUPPLY_B"),
        _src_anomaly("gmv_anom", "GMV", "GMV_DROP", "sales", "commerce.sales.v1"),
        _src_anomaly("traffic_anom", "SESSIONS", "TRAFFIC_DROP", "sales", "commerce.sales.v1"),
        _derived_anomaly("cvr_anom", "CVR", "CVR_DROP", "conversion", "commerce.conversion.v1"),
        _derived_anomaly("dos_anom", "DAYS_OF_SUPPLY", "DAYS_OF_SUPPLY_LOW",
                         "inventory", "commerce.inventory.v1"),
        _drop_rate_fact(),
        _rule("rule", "commerce.sales.v1"),
        _assemble("assemble"),
    ]
    return _plan("store_health_scan", "store_performance_diagnosis", "sales", specs,
                 (CAP_METRICS,), ("GMV", "ORDERS", "SESSIONS"))


def gmv_decline_diagnosis():
    specs = [
        *_source_pair("s", "GMV"),
        *_source_pair("s", "ORDERS"),
        *_source_pair("s", "SESSIONS"),
        _metric("aov", "AOV", {"GMV": "evidence:GMV", "ORDERS": "evidence:ORDERS"}),
        _metric("aov_b", "AOV", {"GMV": "evidence:GMV_B", "ORDERS": "evidence:ORDERS_B"}, result_name="AOV_B"),
        _src_anomaly("gmv_anom", "GMV", "GMV_DROP", "sales", "commerce.sales.v1"),
        _src_anomaly("traffic_anom", "SESSIONS", "TRAFFIC_DROP", "sales", "commerce.sales.v1"),
        _derived_anomaly("aov_anom", "AOV", "AOV_DROP", "sales", "commerce.sales.v1"),
        _drop_rate_fact(),
        _rule("rule", "commerce.sales.v1"),
        _impact("impact", "est_revenue_loss",
                {"GMV_BASELINE": "evidence:GMV_B", "DROP_RATE": "evidence:DROP_RATE"}),
        _priority("priority", "commerce.priority.v1", _factors()),
        _assemble("assemble"),
    ]
    return _plan("gmv_decline_diagnosis", "store_performance_diagnosis", "sales", specs,
                 (CAP_METRICS,), ("GMV", "ORDERS", "SESSIONS"))


def conversion_decline_diagnosis():
    specs = [
        *_source_pair("s", "ORDERS"),
        *_source_pair("s", "SESSIONS"),
        *_source_pair("s", "GMV"),
        _fact("q_rating", "REVIEW_RATING", "REVIEW_RATING", capability=CAP_METRICS),
        _fact("q_price", "PRICE_INDEX", "PRICE_INDEX", capability=CAP_REVIEW),
        _fact("q_neg_review", "NEGATIVE_REVIEW_RATE", "NEGATIVE_REVIEW_RATE", capability=CAP_METRICS),
        _fact("q_neg_review_b", "NEGATIVE_REVIEW_RATE_B", "NEGATIVE_REVIEW_RATE_B", capability=CAP_METRICS),
        _metric("cvr", "CVR", {"ORDERS": "evidence:ORDERS", "SESSIONS": "evidence:SESSIONS"}),
        _metric("cvr_b", "CVR", {"ORDERS": "evidence:ORDERS_B", "SESSIONS": "evidence:SESSIONS_B"}, result_name="CVR_B"),
        _derived_anomaly("cvr_anom", "CVR", "CVR_DROP", "conversion", "commerce.conversion.v1"),
        _src_anomaly("negative_anom", "NEGATIVE_REVIEW_RATE", "NEGATIVE_REVIEW_RATE_RISE",
                     "review", "commerce.review.v1"),
        _drop_rate_fact(),
        _rule("rule", "commerce.conversion.v1"),
        _impact("impact", "est_revenue_loss",
                {"GMV_BASELINE": "evidence:GMV_B", "DROP_RATE": "evidence:DROP_RATE"}),
        _priority("priority", "commerce.priority.v1", _factors()),
        _assemble("assemble"),
    ]
    return _plan("conversion_decline_diagnosis", "store_performance_diagnosis", "conversion", specs,
                 (CAP_METRICS, CAP_REVIEW), ("ORDERS", "SESSIONS"))


# ── S04: Product Operations ─────────────────────────────────

def product_anomaly_diagnosis():
    specs = [
        *_source_pair("s", "UNITS"),
        *_source_pair("s", "ORDERS"),
        *_source_pair("s", "SESSIONS"),
        _metric("cvr", "CVR", {"ORDERS": "evidence:ORDERS", "SESSIONS": "evidence:SESSIONS"}),
        _metric("cvr_b", "CVR", {"ORDERS": "evidence:ORDERS_B", "SESSIONS": "evidence:SESSIONS_B"}, result_name="CVR_B"),
        _src_anomaly("units_anom", "UNITS", "UNITS_DROP", "sales", "commerce.sales.v1"),
        _derived_anomaly("cvr_anom", "CVR", "CVR_DROP", "conversion", "commerce.conversion.v1"),
        _drop_rate_fact(),
        _rule("rule", "commerce.sales.v1"),
        _assemble("assemble"),
    ]
    return _plan("product_anomaly_diagnosis", "product_performance_diagnosis", "sales", specs,
                 (CAP_METRICS,), ("UNITS", "ORDERS", "SESSIONS"))


def slow_moving_inventory():
    specs = [
        *_source_pair("s", "UNITS"),
        *_source_pair("s", "PERIOD_DAYS"),
        *_source_pair("s", "AVAILABLE_INVENTORY", capability=CAP_METRICS),
        _metric("velocity", "SALES_VELOCITY", {"UNITS": "evidence:UNITS", "PERIOD_DAYS": "evidence:PERIOD_DAYS"}),
        _metric("velocity_b", "SALES_VELOCITY", {"UNITS": "evidence:UNITS_B", "PERIOD_DAYS": "evidence:PERIOD_DAYS_B"}, result_name="SALES_VELOCITY_B"),
        _derived_anomaly("velocity_anom", "SALES_VELOCITY", "SLOW_MOVING", "inventory", "commerce.inventory.v1"),
        _drop_rate_fact(),
        _rule("rule", "commerce.inventory.v1"),
        _impact("impact", "inventory_capital_exposure",
                {"EXCESS_INVENTORY_VALUE": "evidence:AVAILABLE_INVENTORY"}),
        _priority("priority", "commerce.priority.v1", _factors()),
        _assemble("assemble"),
    ]
    return _plan("slow_moving_inventory", "inventory_risk_diagnosis", "inventory", specs,
                 (CAP_METRICS, CAP_INVENTORY), ("UNITS", "PERIOD_DAYS", "AVAILABLE_INVENTORY"))


# ── S06-S09: Advertising Operations ─────────────────────────

def advertising_health_scan():
    specs = [
        *_derived_pair("ctr", "CTR", ("CLICKS", "IMPRESSIONS")),
        *_derived_pair("roas", "ROAS", ("AD_SALES", "AD_SPEND")),
        *_derived_pair("cpc", "CPC", ("AD_SPEND", "CLICKS")),
        *_source_pair("s", "ORDERS"),
        *_source_pair("s", "SESSIONS"),
        _metric("cvr", "CVR", {"ORDERS": "evidence:ORDERS", "SESSIONS": "evidence:SESSIONS"}),
        _metric("cvr_b", "CVR", {"ORDERS": "evidence:ORDERS_B", "SESSIONS": "evidence:SESSIONS_B"}, result_name="CVR_B"),
        _derived_anomaly("roas_anom", "ROAS", "ROAS_DROP", "advertising", "commerce.advertising.v1"),
        _derived_anomaly("cpc_anom", "CPC", "CPC_RISE", "advertising", "commerce.advertising.v1"),
        _derived_anomaly("ctr_anom", "CTR", "CTR_DROP", "advertising", "commerce.advertising.v1"),
        _derived_anomaly("cvr_anom", "CVR", "CVR_DROP", "conversion", "commerce.conversion.v1"),
        _drop_rate_fact(),
        _rule("rule", "commerce.advertising.v1"),
        _assemble("assemble"),
    ]
    return _plan("advertising_health_scan", "advertising_performance_diagnosis", "advertising", specs,
                 (CAP_METRICS,), ("CLICKS", "IMPRESSIONS", "AD_SPEND", "AD_SALES"))


def roas_decline_diagnosis():
    specs = [
        *_derived_pair("roas", "ROAS", ("AD_SALES", "AD_SPEND")),
        *_derived_pair("cpc", "CPC", ("AD_SPEND", "CLICKS")),
        _derived_anomaly("roas_anom", "ROAS", "ROAS_DROP", "advertising", "commerce.advertising.v1"),
        _derived_anomaly("cpc_anom", "CPC", "CPC_RISE", "advertising", "commerce.advertising.v1"),
        _drop_rate_fact(),
        _rule("rule", "commerce.advertising.v1"),
        _impact("impact", "observed_ad_waste", {"WASTED_SPEND": "evidence:AD_SPEND"}),
        _priority("priority", "commerce.priority.v1", _factors()),
        _assemble("assemble"),
    ]
    return _plan("roas_decline_diagnosis", "advertising_performance_diagnosis", "advertising", specs,
                 (CAP_METRICS,), ("AD_SPEND", "AD_SALES", "CLICKS"))


def high_spend_low_conversion():
    specs = [
        *_source_pair("s", "AD_SPEND"),
        *_source_pair("s", "AD_CLICKS"),
        *_source_pair("s", "AD_ORDERS"),
        _metric("ad_cvr", "AD_CVR", {"AD_ORDERS": "evidence:AD_ORDERS", "AD_CLICKS": "evidence:AD_CLICKS"}),
        _metric("ad_cvr_b", "AD_CVR", {"AD_ORDERS": "evidence:AD_ORDERS_B", "AD_CLICKS": "evidence:AD_CLICKS_B"}, result_name="AD_CVR_B"),
        _src_anomaly("spend_anom", "AD_SPEND", "SPEND_RISE", "advertising", "commerce.advertising.v1"),
        _derived_anomaly("cvr_anom", "AD_CVR", "AD_CVR_DROP", "advertising", "commerce.advertising.v1"),
        _drop_rate_fact(),
        _rule("rule", "commerce.advertising.v1"),
        _impact("impact", "observed_ad_waste", {"WASTED_SPEND": "evidence:AD_SPEND"}),
        _priority("priority", "commerce.priority.v1", _factors()),
        _assemble("assemble"),
    ]
    return _plan("high_spend_low_conversion", "advertising_performance_diagnosis", "advertising", specs,
                 (CAP_METRICS,), ("AD_SPEND", "AD_CLICKS", "AD_ORDERS"))


def search_term_waste():
    specs = [
        *_source_pair("s", "SEARCH_TERM_SPEND", capability=CAP_ADVERTISING),
        _src_anomaly("waste_anom", "SEARCH_TERM_SPEND", "SEARCH_TERM_WASTE",
                     "advertising", "commerce.advertising.v1"),
        _drop_rate_fact(),
        _rule("rule", "commerce.advertising.v1"),
        _impact("impact", "observed_ad_waste", {"WASTED_SPEND": "evidence:SEARCH_TERM_SPEND"}),
        _priority("priority", "commerce.priority.v1", _factors()),
        _assemble("assemble"),
    ]
    return _plan("search_term_waste", "advertising_performance_diagnosis", "advertising", specs,
                 (CAP_ADVERTISING, CAP_METRICS), ("SEARCH_TERM_SPEND",))


# ── S10/S11: Inventory Operations ───────────────────────────

def stockout_risk():
    specs = [
        *_source_pair("s", "AVAILABLE_INVENTORY", capability=CAP_METRICS),
        *_source_pair("s", "UNITS"),
        *_source_pair("s", "PERIOD_DAYS"),
        _metric("dos", "DAYS_OF_SUPPLY",
                {"AVAILABLE_INVENTORY": "evidence:AVAILABLE_INVENTORY",
                 "UNITS": "evidence:UNITS", "PERIOD_DAYS": "evidence:PERIOD_DAYS"}),
        _metric("dos_b", "DAYS_OF_SUPPLY",
                {"AVAILABLE_INVENTORY": "evidence:AVAILABLE_INVENTORY_B",
                 "UNITS": "evidence:UNITS_B", "PERIOD_DAYS": "evidence:PERIOD_DAYS_B"},
                result_name="DAYS_OF_SUPPLY_B"),
        _derived_anomaly("dos_anom", "DAYS_OF_SUPPLY", "DAYS_OF_SUPPLY_LOW",
                         "inventory", "commerce.inventory.v1"),
        _fact("q_daily_revenue", "DAILY_REVENUE", "DAILY_REVENUE"),
        _fact("q_stockout_days", "STOCKOUT_DAYS", "STOCKOUT_DAYS"),
        _drop_rate_fact(),
        _rule("rule", "commerce.inventory.v1"),
        _impact("impact", "projected_stockout_loss",
                {"DAILY_REVENUE": "evidence:DAILY_REVENUE", "STOCKOUT_DAYS": "evidence:STOCKOUT_DAYS"}),
        _priority("priority", "commerce.priority.v1", _factors()),
        _assemble("assemble"),
    ]
    return _plan("stockout_risk", "inventory_risk_diagnosis", "inventory", specs,
                 (CAP_INVENTORY, CAP_METRICS), ("AVAILABLE_INVENTORY", "UNITS", "PERIOD_DAYS"))


def inventory_sales_imbalance():
    specs = [
        *_source_pair("s", "AVAILABLE_INVENTORY", capability=CAP_METRICS),
        *_source_pair("s", "UNITS"),
        *_source_pair("s", "PERIOD_DAYS"),
        _metric("velocity", "SALES_VELOCITY", {"UNITS": "evidence:UNITS", "PERIOD_DAYS": "evidence:PERIOD_DAYS"}),
        _metric("velocity_b", "SALES_VELOCITY", {"UNITS": "evidence:UNITS_B", "PERIOD_DAYS": "evidence:PERIOD_DAYS_B"}, result_name="SALES_VELOCITY_B"),
        _src_anomaly("inventory_anom", "AVAILABLE_INVENTORY", "INVENTORY_HIGH", "inventory", "commerce.inventory.v1"),
        _derived_anomaly("velocity_anom", "SALES_VELOCITY", "SLOW_MOVING", "inventory", "commerce.inventory.v1"),
        _drop_rate_fact(),
        _rule("rule", "commerce.inventory.v1"),
        _impact("impact", "inventory_capital_exposure",
                {"EXCESS_INVENTORY_VALUE": "evidence:AVAILABLE_INVENTORY"}),
        _priority("priority", "commerce.priority.v1", _factors()),
        _assemble("assemble"),
    ]
    return _plan("inventory_sales_imbalance", "inventory_risk_diagnosis", "inventory", specs,
                 (CAP_INVENTORY, CAP_METRICS), ("AVAILABLE_INVENTORY", "UNITS", "PERIOD_DAYS"))


# ── S12/S13: Review Operations ──────────────────────────────

def rating_deterioration():
    specs = [
        *_source_pair("s", "REVIEW_RATING", capability=CAP_METRICS),
        *_source_pair("s", "NEGATIVE_REVIEW_RATE", capability=CAP_METRICS),
        _src_anomaly("rating_anom", "REVIEW_RATING", "RATING_DROP", "review", "commerce.review.v1"),
        _src_anomaly("negative_anom", "NEGATIVE_REVIEW_RATE", "NEGATIVE_REVIEW_RATE_RISE",
                     "review", "commerce.review.v1"),
        _drop_rate_fact(),
        _rule("rule", "commerce.review.v1"),
        _priority("priority", "commerce.priority.v1", _factors()),
        _assemble("assemble"),
    ]
    return _plan("rating_deterioration", "review_issue_diagnosis", "review", specs,
                 (CAP_REVIEW, CAP_METRICS), ("REVIEW_RATING", "NEGATIVE_REVIEW_RATE"))


def emerging_product_issue():
    specs = [
        *_source_pair("s", "ISSUE_RATE", capability=CAP_REVIEW),
        _src_anomaly("issue_anom", "ISSUE_RATE", "EMERGING_ISSUE_RATE_RISE", "review", "commerce.review.v1"),
        _drop_rate_fact(),
        _rule("rule", "commerce.review.v1"),
        _priority("priority", "commerce.priority.v1", _factors()),
        _assemble("assemble"),
    ]
    return _plan("emerging_product_issue", "review_issue_diagnosis", "review", specs,
                 (CAP_REVIEW, CAP_METRICS), ("ISSUE_RATE",))


# ── S14: Product 360 ────────────────────────────────────────

def product_360():
    specs = [
        *_source_pair("s", "UNITS"),
        *_source_pair("s", "ORDERS"),
        *_source_pair("s", "SESSIONS"),
        *_source_pair("s", "GMV"),
        *_source_pair("s", "AD_SPEND"),
        *_source_pair("s", "AD_SALES"),
        *_source_pair("s", "REVIEW_RATING", capability=CAP_METRICS),
        _metric("cvr", "CVR", {"ORDERS": "evidence:ORDERS", "SESSIONS": "evidence:SESSIONS"}),
        _metric("cvr_b", "CVR", {"ORDERS": "evidence:ORDERS_B", "SESSIONS": "evidence:SESSIONS_B"}, result_name="CVR_B"),
        _metric("roas", "ROAS", {"AD_SALES": "evidence:AD_SALES", "AD_SPEND": "evidence:AD_SPEND"}),
        _metric("roas_b", "ROAS", {"AD_SALES": "evidence:AD_SALES_B", "AD_SPEND": "evidence:AD_SPEND_B"}, result_name="ROAS_B"),
        _src_anomaly("units_anom", "UNITS", "UNITS_DROP", "sales", "commerce.sales.v1"),
        _derived_anomaly("cvr_anom", "CVR", "CVR_DROP", "conversion", "commerce.conversion.v1"),
        _derived_anomaly("roas_anom", "ROAS", "ROAS_DROP", "advertising", "commerce.advertising.v1"),
        _src_anomaly("rating_anom", "REVIEW_RATING", "RATING_DROP", "review", "commerce.review.v1"),
        _drop_rate_fact(),
        _rule("rule", "commerce.conversion.v1"),
        _impact("impact", "est_revenue_loss",
                {"GMV_BASELINE": "evidence:GMV_B", "DROP_RATE": "evidence:DROP_RATE"}),
        _priority("priority", "commerce.priority.v1", _factors()),
        _assemble("assemble"),
    ]
    return _plan("product_360", "product_360_diagnosis", "sales", specs,
                 (CAP_METRICS, CAP_REVIEW),
                 ("UNITS", "ORDERS", "SESSIONS", "AD_SPEND", "AD_SALES", "REVIEW_RATING"))


# ── S15: Daily Operations Triage (aggregation/supervisor) ───

def daily_operations_scan():
    """Light aggregation/triage plan: surfaces cross-domain signals only.

    It does NOT re-implement the deep rule / impact / priority logic of the
    domain plans; the domain plans own that.  The triage just collects facts,
    computes a few key metrics and detects anomalies so the supervisor can
    route into the domain plans.
    """
    specs = [
        *_source_pair("s", "GMV"),
        *_source_pair("s", "ORDERS"),
        *_source_pair("s", "SESSIONS"),
        *_source_pair("s", "AD_SPEND"),
        *_source_pair("s", "AD_SALES"),
        *_source_pair("s", "AVAILABLE_INVENTORY", capability=CAP_METRICS),
        _metric("cvr", "CVR", {"ORDERS": "evidence:ORDERS", "SESSIONS": "evidence:SESSIONS"}),
        _metric("cvr_b", "CVR", {"ORDERS": "evidence:ORDERS_B", "SESSIONS": "evidence:SESSIONS_B"}, result_name="CVR_B"),
        _metric("roas", "ROAS", {"AD_SALES": "evidence:AD_SALES", "AD_SPEND": "evidence:AD_SPEND"}),
        _metric("roas_b", "ROAS", {"AD_SALES": "evidence:AD_SALES_B", "AD_SPEND": "evidence:AD_SPEND_B"}, result_name="ROAS_B"),
        _src_anomaly("gmv_anom", "GMV", "GMV_DROP", "sales", "commerce.sales.v1"),
        _derived_anomaly("cvr_anom", "CVR", "CVR_DROP", "conversion", "commerce.conversion.v1"),
        _derived_anomaly("roas_anom", "ROAS", "ROAS_DROP", "advertising", "commerce.advertising.v1"),
        _src_anomaly("inv_anom", "AVAILABLE_INVENTORY", "INVENTORY_HIGH", "inventory", "commerce.inventory.v1"),
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
