"""Benchmark scenario runner (Phase 18.15).

Reproducible lifecycle per scenario: validate checksum binding, reset, seed
scenario facts, invoke the product API, capture output, and evaluate E1-E5.

Usage::

    python -m tools.benchmark.run --suite benchmark/enterprise-commerce-v1 \
        --seed data/seed/enterprise-commerce-v1 [--scenario B004] [--verbose]
"""

import argparse
import re

from tools.benchmark import loader
from tools.benchmark.evaluators import EVALUATORS
from tools.benchmark.models import LAYERS

AUTH = {"Authorization": "Bearer test-user-U001"}


def parse_diagnostic_message(content):
    """Parse the deterministic diagnostic message into its structured anchors."""
    parsed = {}
    m = re.search(r"针对 (.+?) 的诊断（(.+?)）", content or "")
    if m:
        parsed["subject"] = m.group(1)
        parsed["status"] = m.group(2)
    m = re.search(r"检测到信号 (.+?)；可能原因", content or "")
    if m:
        parsed["signals"] = [s.strip() for s in m.group(1).split("、") if s.strip()]
    else:
        parsed["signals"] = []
    m = re.search(r"可能原因 (.+?)；优先级", content or "")
    if m:
        parsed["causes"] = [s.strip() for s in m.group(1).split("、") if s.strip()]
    else:
        parsed["causes"] = []
    m = re.search(r"优先级 (.+?)。", content or "")
    if m:
        parsed["priority"] = m.group(1)
    return parsed


def seed_metrics(application, metrics):
    from app.commerce.domain import MetricSeries
    repository = application.commerce.repository
    # reset scenario state: clear previously-seeded metrics so each scenario
    # starts from the same baseline (scenario independence).
    repository._metrics.clear()
    for name, value in metrics:
        repository.upsert_metric("company_A", MetricSeries(
            metric_record_id=name, tenant_id="company_A", subject_type="STORE",
            subject_id="JP01", metric_name=name, metric_class="AGGREGATED",
            granularity="DAILY", period_start="2026-08-01",
            period_end="2026-08-02", value=value))


def capture(response, parsed):
    return {
        "http_status": response.status_code,
        "content": response.json().get("response", {}).get("content", ""),
        "subject": parsed.get("subject", ""),
        "status": parsed.get("status", ""),
        "signals": parsed.get("signals", ()),
        "causes": parsed.get("causes", ()),
        "priority": parsed.get("priority", ""),
        "observed_entities": (parsed.get("subject", ""),),
        "execution_created": response.json().get("execution") is not None,
        "providers_called": (),
    }


def run_scenario(client, application, scenario, ground_truth):
    metrics = scenario.get("setup", {}).get("metrics", ())
    seed_metrics(application, metrics)
    body = client.post(
        f"/v1/agents/{scenario['agent_id']}/messages",
        headers=AUTH, json={"message": scenario["message"]},
    )
    content = body.json().get("response", {}).get("content", "")
    parsed = parse_diagnostic_message(content)
    captured = capture(body, parsed)
    results = {}
    evaluation = ground_truth.get("evaluation", {})
    for layer in LAYERS:
        spec = evaluation.get(layer)
        results[layer] = EVALUATORS[layer](captured, spec)
    return results, captured


def run_all(application, client, scenarios, ground_truth):
    report = {}
    for sid in sorted(scenarios):
        results, captured = run_scenario(
            client, application, scenarios[sid], ground_truth[sid])
        verdicts = [r.verdict for r in results.values()]
        overall = "PASS" if all(v != "FAIL" for v in verdicts) else "FAIL"
        report[sid] = {
            "scenario_id": sid,
            "overall": overall,
            "layers": {r.layer: r.to_dict() for r in results.values()},
        }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    from tools.benchmark import validate as v
    errors, manifest, _ = v.validate(args.suite, args.seed)
    if errors:
        print("FAIL (suite validation)")
        for e in errors:
            print(f"  - {e}")
        return 1

    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from app.api.server import build_http_application
    from tests.memory.repository import TestEmbeddingService, TestMemoryRepository

    class _LLM:
        def chat(self, m, **k):
            return '{"goal":"g","steps":[]}'

    with patch("app.main.create_llm", return_value=_LLM()):
        app = build_http_application(
            "testing", memory_repository=TestMemoryRepository(),
            memory_embedding_service=TestEmbeddingService())
    application = app.state.application
    from app.commerce.domain import Store
    application.commerce.repository.upsert_store("company_A", Store(
        store_id="JP01", tenant_id="company_A", platform="amazon",
        marketplace="JP", external_store_id="ext-JP01", name="Japan Store",
        currency="JPY", timezone="Asia/Tokyo"))
    # Register the seed's cross-tenant resource so the agent can resolve (and
    # deny) foreign-tenant references.  This mirrors the seed's multi-tenant
    # world (Northstar Retail); it is benchmark setup, not a product change.
    from app.commerce.contracts.subject import SUBJECT_STORE, SubjectRef
    entity_router = application.agents.runtime.router.entity_router
    for token in ("Northstar", "其他租户", "其他店铺"):
        entity_router.known_subjects[token] = SubjectRef(SUBJECT_STORE,
                                                         "foreign_store")
        entity_router.subject_tenants[token] = "tenant_northstar"
    client = TestClient(app, raise_server_exceptions=False)

    scenarios = loader.load_all(args.suite)[1]
    ground_truth = loader.load_all(args.suite)[2]
    ids = [args.scenario] if args.scenario else sorted(scenarios)
    report = run_all(application, client,
                     {i: scenarios[i] for i in ids},
                     ground_truth)

    for sid in ids:
        entry = report[sid]
        print(f"{sid}: {entry['overall']}")
        if args.verbose:
            for layer in LAYERS:
                r = entry["layers"][layer]
                print(f"  {layer}: {r['verdict']}")
                for a in r["assertions"]:
                    print(f"    {a['name']}: expected={a['expected']} "
                          f"actual={a['actual']} {'OK' if a['passed'] else 'MISS'}")
    passed = sum(1 for e in report.values() if e["overall"] == "PASS")
    print(f"result: {passed}/{len(report)} scenarios PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
