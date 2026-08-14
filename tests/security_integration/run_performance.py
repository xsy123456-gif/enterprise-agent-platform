"""Execution security chain performance measurement (report only).

Run manually::

    python -m tests.security_integration.run_performance
"""

import json
import time
from pathlib import Path

from app.identity import build_identity
from app.identity.providers.local_file import LocalFileIdentityProvider
from app.integrations.security import TrustedPrincipal, build_security_integration
from app.permission import PermissionConfig, build_permission
from app.runtime.governance.gate import AllowAllGovernancePolicy, GovernanceGate

ROOT = Path(__file__).resolve().parents[2]


def _percentiles(samples):
    ordered = sorted(samples)
    n = len(ordered)
    return {
        "p50": round(ordered[int(n * 0.50)] * 1000, 2),
        "p95": round(ordered[min(int(n * 0.95), n - 1)] * 1000, 2),
        "p99": round(ordered[min(int(n * 0.99), n - 1)] * 1000, 2),
    }


def main():
    identity = build_identity(
        provider=LocalFileIdentityProvider(str(ROOT / "data" / "identity"))
    )
    permission = build_permission(
        config=PermissionConfig(policy_root=str(ROOT / "data" / "permission" / "policies"))
    )
    permission.runtime.start()
    sec = build_security_integration(
        identity_service=identity.service,
        permission_service=permission.service,
        governance_gate=GovernanceGate(AllowAllGovernancePolicy()),
    )

    principal = TrustedPrincipal("U001")
    resolve_samples, admission_samples, gate_samples = [], [], []

    for _ in range(50):
        t = time.perf_counter()
        sec.resolver.resolve(principal)
        resolve_samples.append(time.perf_counter() - t)

        t = time.perf_counter()
        sec.admission.admit(principal, "sales_agent", "0.2", "company_A")
        admission_samples.append(time.perf_counter() - t)

        from types import SimpleNamespace
        req = SimpleNamespace(user_id="U001", tenant_id="company_A",
                              tool_name="crm_query", agent_id="sales_agent",
                              execution_id="e1", request_id="r1")
        t = time.perf_counter()
        sec.tool_gate.check(req)
        gate_samples.append(time.perf_counter() - t)

    report = {
        "identity_resolve_ms": _percentiles(resolve_samples),
        "agent_admission_ms": _percentiles(admission_samples),
        "tool_security_gate_ms": _percentiles(gate_samples),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
