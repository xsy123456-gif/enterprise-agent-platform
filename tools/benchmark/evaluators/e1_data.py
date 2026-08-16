"""E1 — Data / Ingestion correctness (Phase 18.15).

Verifies the facts the agent observed are correct: required entity present, and
(where connectors are exercised) the provider request log reflects the expected
provider/store scope.
"""

from tools.benchmark.evaluators.base import assertion, not_applicable, result


def evaluate_e1(captured, spec):
    if not spec:
        return not_applicable("E1")
    assertions = []
    required_entity = spec.get("required_entity")
    if required_entity:
        seen = captured.get("observed_entities", ())
        assertions.append(assertion("required_entity", required_entity,
                                    list(seen), required_entity in seen))
    # provider request scope (only when connectors are part of the scenario)
    forbidden_providers = spec.get("forbidden_providers", ())
    for provider in forbidden_providers:
        called = provider in captured.get("providers_called", ())
        assertions.append(assertion(f"forbidden_provider:{provider}", False,
                                    called, not called))
    return result("E1", all(a["passed"] for a in assertions), assertions)
