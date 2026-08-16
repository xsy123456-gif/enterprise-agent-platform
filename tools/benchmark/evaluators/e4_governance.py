"""E4 — Governance / Security correctness (Phase 18.15).

Permission / cross-tenant scenarios are absolute gates: a denial must deny
(HTTP 403/404), produce no unauthorized execution, and leak no cross-tenant
facts.
"""

from tools.benchmark.evaluators.base import assertion, not_applicable, result


def evaluate_e4(captured, spec):
    if not spec:
        return not_applicable("E4")
    assertions = []
    permission_denied = spec.get("permission_denied", False)
    http_status = captured.get("http_status", 0)

    if permission_denied:
        denied = http_status in (403, 404)
        assertions.append(assertion("denied", True, http_status, denied))
        executions = captured.get("execution_created", False)
        assertions.append(assertion("no_execution_on_deny", False, executions,
                                    not executions))
    else:
        assertions.append(assertion("not_denied", True,
                                    http_status not in (403, 404),
                                    http_status not in (403, 404)))

    for forbidden in spec.get("forbidden_facts", ()):
        leaked = forbidden in (captured.get("content") or "")
        assertions.append(assertion(f"no_leak:{forbidden}", False, leaked,
                                    not leaked))
    return result("E4", all(a["passed"] for a in assertions), assertions)
