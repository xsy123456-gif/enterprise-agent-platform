"""Phase 18.15.8 authoring-consistency tests (independent of the product)."""

import os

from tools.benchmark import loader
from tests.business_world.conftest import SEED_ROOT

SUITE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "benchmark", "enterprise-commerce-v1")

# Frozen signal IDs (v1): referenced by rule sets + anomaly steps.
FROZEN_SIGNALS = frozenset({
    "GMV_DROP", "TRAFFIC_DROP", "AOV_DROP", "CVR_DROP",
    "NEGATIVE_REVIEW_RATE_RISE", "ROAS_DROP", "CPC_RISE", "SEARCH_TERM_WASTE",
    "DAYS_OF_SUPPLY_LOW", "SLOW_MOVING", "RATING_DROP",
    "EMERGING_ISSUE_RATE_RISE", "UNITS_DROP", "CTR_DROP", "SPEND_RISE",
    "AD_CVR_DROP", "INVENTORY_HIGH",
})

DIAGNOSTIC = {"B004", "B005", "B006", "B007", "B008", "B009", "B010", "B011",
              "B012", "B013", "B014", "B020"}


def _metrics(scenario_id):
    scenario = loader.load_scenario(SUITE, scenario_id)
    return dict(scenario["setup"]["metrics"])


def _cvr(current, baseline):
    orders = current["ORDERS"]; sessions = current["SESSIONS"]
    orders_b = baseline["ORDERS_B"]; sessions_b = baseline["SESSIONS_B"]
    return orders / sessions, orders_b / sessions_b


def test_b011_seed_satisfies_frozen_conversion_abnormal_threshold():
    facts = _metrics("B011")
    cvr, cvr_b = _cvr(facts, facts)
    change = (cvr - cvr_b) / cvr_b
    # frozen commerce.conversion.v1 ABNORMAL threshold = 20%
    assert change <= -0.20, f"B011 conversion change {change:.2%} not ABNORMAL"


def test_b014_seed_contains_days_of_supply_base_facts():
    facts = _metrics("B014")
    for name in ("UNITS", "UNITS_B", "PERIOD_DAYS", "PERIOD_DAYS_B",
                 "AVAILABLE_INVENTORY", "AVAILABLE_INVENTORY_B"):
        assert name in facts, f"B014 missing base fact {name}"


def test_diagnostic_scenarios_have_e2_expectations():
    gt = loader.load_all(SUITE)[2]
    for sid in DIAGNOSTIC:
        e2 = gt[sid]["evaluation"].get("E2")
        assert e2 and e2.get("signals"), f"{sid} E2 signal spec is empty"


def test_e2_ground_truth_uses_frozen_signal_ids():
    gt = loader.load_all(SUITE)[2]
    for sid in DIAGNOSTIC:
        signals = gt[sid]["evaluation"]["E2"]["signals"]
        for signal in signals:
            assert signal in FROZEN_SIGNALS, f"{sid} uses unknown signal {signal!r}"


def test_normal_controls_are_not_marked_abnormal():
    gt = loader.load_all(SUITE)[2]
    for sid in ("B001", "B002", "B003"):
        e3 = gt[sid]["evaluation"]["E3"]
        assert e3["expected_state"] == "NORMAL"
        assert e3.get("primary_cause") is None
