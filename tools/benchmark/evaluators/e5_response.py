"""E5 — Agent Response correctness (Phase 18.15).

Checks semantic anchors in the deterministic response: required facts present,
forbidden facts absent.  No exact-string matching; no LLM judge.
"""

from tools.benchmark.evaluators.base import assertion, not_applicable, result


def evaluate_e5(captured, spec):
    if not spec:
        return not_applicable("E5")
    assertions = []
    content = captured.get("content") or ""
    for fact in spec.get("required_facts", ()):
        present = fact in content
        assertions.append(assertion(f"required_fact:{fact}", True, present,
                                    present))
    for fact in spec.get("forbidden_facts", ()):
        leaked = fact in content
        assertions.append(assertion(f"forbidden_fact:{fact}", False, leaked,
                                    not leaked))
    return result("E5", all(a["passed"] for a in assertions), assertions)
