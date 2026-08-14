"""Durable principal binding + concurrent context isolation tests."""

import threading

from app.integrations.security import (
    ExecutionPrincipalBinding,
    InMemoryPrincipalContextCarrier,
    TrustedPrincipal,
)


def test_binding_survives_bind_get_remove():
    carrier = InMemoryPrincipalContextCarrier()
    binding = ExecutionPrincipalBinding(
        principal_id="U003", tenant_id="company_A",
        identity_version_at_admission="v1", security_context_id="sc1",
    )
    carrier.bind("E001", binding)
    assert carrier.get("E001") == binding
    carrier.remove("E001")
    assert carrier.get("E001") is None


def test_resume_re_resolves_principal():
    # On resume, the binding yields the principal id; identity is re-resolved
    # by the security gate (never a stale authorization snapshot).
    carrier = InMemoryPrincipalContextCarrier()
    carrier.bind("E001", ExecutionPrincipalBinding(
        principal_id="U003", tenant_id="company_A",
    ))
    binding = carrier.get("E001")
    principal = TrustedPrincipal(binding.principal_id)
    assert principal.principal_id == "U003"


def test_concurrent_context_isolation():
    carrier = InMemoryPrincipalContextCarrier()
    errors = []

    def worker(index):
        try:
            for _ in range(500):
                execution_id = f"E{index}"
                binding = ExecutionPrincipalBinding(
                    principal_id=f"U{index}", tenant_id=f"tenant_{index}",
                )
                carrier.bind(execution_id, binding)
                got = carrier.get(execution_id)
                assert got.principal_id == f"U{index}", "principal bleed"
                assert got.tenant_id == f"tenant_{index}", "tenant bleed"
        except AssertionError as error:
            errors.append(str(error))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
