"""Composition wiring tests: Identity/Permission/Security assembled."""

from pathlib import Path
from unittest.mock import patch

from app.identity import build_identity
from app.identity.providers.local_file import LocalFileIdentityProvider
from app.integrations.security import build_security_integration
from app.permission import PermissionConfig, build_permission
from app.runtime.governance.gate import AllowAllGovernancePolicy, GovernanceGate

ROOT = Path(__file__).resolve().parents[2]


def test_security_integration_assembly():
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
    assert sec.resolver is not None
    assert sec.admission is not None
    assert sec.tool_gate is not None
    assert sec.lifecycle_authorization is not None
    assert sec.carrier is not None


def test_build_application_wires_security_components():
    from app.main import build_application
    from tests.memory.repository import TestEmbeddingService, TestMemoryRepository

    class StubLLM:
        def chat(self, messages, **kwargs):
            return (
                '{"goal":"g","steps":['
                '{"step_id":"1","capability":"customer_analysis","dependencies":[]}]}'
            )

    with patch("app.main.create_llm", return_value=StubLLM()):
        app = build_application(
            memory_repository=TestMemoryRepository(),
            memory_embedding_service=TestEmbeddingService(),
        )
    assert app.identity is not None
    assert app.permission is not None
    assert app.security is not None
    assert app.runtime is not None
