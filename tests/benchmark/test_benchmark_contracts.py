"""Benchmark contract + evaluator unit tests (Phase 18.15).

Each evaluator has a known PASS and a known FAIL (mutant) case, so evaluators
cannot silently always-pass.
"""

import os

from tools.benchmark import loader, validate
from tools.benchmark.evaluators import evaluate_e3, evaluate_e4, evaluate_e5
from tools.benchmark.models import frozen_cause_codes

from tests.business_world.conftest import SEED_ROOT

SUITE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "benchmark", "enterprise-commerce-v1")


def test_frozen_cause_catalog_is_populated():
    assert frozen_cause_codes() >= {"TRAFFIC_DECLINE", "STOCKOUT_RISK"}


def test_benchmark_validates_against_seed_checksum():
    errors, manifest, ids = validate.validate(SUITE, SEED_ROOT)
    assert errors == []
    assert len(ids) == 20
    assert manifest["benchmark_version"] == "1.0.1"


def test_scenarios_have_no_answer_fields():
    scenarios = loader.load_all(SUITE)[1]
    for sid, scenario in scenarios.items():
        for forbidden in ("expected_cause", "ground_truth", "primary_cause"):
            assert forbidden not in scenario


def test_e3_passes_on_correct_cause():
    captured = {"causes": ["TRAFFIC_DECLINE"], "status": "COMPLETED"}
    spec = {"expected_state": "ABNORMAL", "primary_cause": "TRAFFIC_DECLINE",
            "forbidden_causes": ["STOCKOUT_RISK"]}
    assert evaluate_e3(captured, spec).verdict == "PASS"


def test_e3_fails_on_wrong_cause():
    captured = {"causes": ["STOCKOUT_RISK"], "status": "COMPLETED"}
    spec = {"expected_state": "ABNORMAL", "primary_cause": "TRAFFIC_DECLINE",
            "forbidden_causes": ["STOCKOUT_RISK"]}
    assert evaluate_e3(captured, spec).verdict == "FAIL"


def test_e3_fails_on_forbidden_cause():
    captured = {"causes": ["TRAFFIC_DECLINE", "STOCKOUT_RISK"],
               "status": "COMPLETED"}
    spec = {"expected_state": "ABNORMAL", "primary_cause": "TRAFFIC_DECLINE",
            "forbidden_causes": ["STOCKOUT_RISK"]}
    assert evaluate_e3(captured, spec).verdict == "FAIL"


def test_e4_fails_on_cross_tenant_leak():
    captured = {"http_status": 200, "execution_created": True,
                "content": "Northstar 的数据如下..."}
    spec = {"permission_denied": True, "forbidden_facts": ["Northstar"]}
    assert evaluate_e4(captured, spec).verdict == "FAIL"


def test_e4_passes_on_denial():
    captured = {"http_status": 403, "execution_created": False, "content": ""}
    spec = {"permission_denied": True, "forbidden_facts": ["Northstar"]}
    assert evaluate_e4(captured, spec).verdict == "PASS"


def test_e5_checks_required_facts():
    captured = {"content": "针对 STORE:JP01 的诊断（COMPLETED）"}
    spec = {"required_facts": ["STORE:JP01"]}
    assert evaluate_e5(captured, spec).verdict == "PASS"
    captured = {"content": "针对 STORE:JP02 的诊断"}
    assert evaluate_e5(captured, spec).verdict == "FAIL"
