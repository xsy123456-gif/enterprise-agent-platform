"""E2 — Metric & Signal correctness (Phase 18.15).

Compares the signals the diagnostic surfaced (from the deterministic response)
against the expected signal set.
"""

from tools.benchmark.evaluators.base import assertion, not_applicable, result


def evaluate_e2(captured, spec):
    if not spec or not spec.get("signals"):
        return not_applicable("E2")
    expected_signals = spec.get("signals", {})
    observed_signals = set(captured.get("signals", ()))
    assertions = []
    for signal in expected_signals:
        present = signal in observed_signals
        assertions.append(assertion(f"signal:{signal}", True, present, present))
    return result("E2", all(a["passed"] for a in assertions), assertions)
