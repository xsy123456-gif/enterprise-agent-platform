"""E3 — Diagnostic correctness (Phase 18.15).

Checks the diagnostic conclusion against frozen cause semantics: expected state,
primary cause (exact frozen cause id), acceptable secondary causes, and
forbidden causes (must NOT be asserted).
"""

from tools.benchmark.evaluators.base import assertion, not_applicable, result

_NO_CAUSE = frozenset({"", "无", "UNKNOWN"})


def _real_causes(causes):
    return [c for c in causes if c not in _NO_CAUSE]


def evaluate_e3(captured, spec):
    if not spec:
        return not_applicable("E3")
    assertions = []
    causes = captured.get("causes", ())
    status = captured.get("status", "")
    expected_state = spec.get("expected_state")
    primary = spec.get("primary_cause")

    if primary:
        assertions.append(assertion("primary_cause", primary, list(causes),
                                    primary in causes))
    else:
        # expected no real cause (NORMAL / INSUFFICIENT_DATA)
        real = _real_causes(causes)
        assertions.append(assertion("no_unsupported_cause", [], real,
                                    not real))

    for forbidden in spec.get("forbidden_causes", ()):
        present = forbidden in causes
        assertions.append(assertion(f"forbidden_cause:{forbidden}", False,
                                    present, not present))

    for acceptable in spec.get("acceptable_secondary_causes", ()):
        if acceptable in causes:
            break
    else:
        if spec.get("acceptable_secondary_causes"):
            assertions.append(assertion("secondary_cause_covered",
                                        spec["acceptable_secondary_causes"],
                                        list(causes), False))

    if expected_state == "INSUFFICIENT_DATA":
        assertions.append(assertion("insufficient_data_state", True,
                                    status == "INSUFFICIENT_DATA",
                                    status == "INSUFFICIENT_DATA"))

    return result("E3", all(a["passed"] for a in assertions), assertions)
