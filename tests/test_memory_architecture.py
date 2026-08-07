import ast
from pathlib import Path
import unittest

from app.memory.api.models import (
    MemoryObservation, MemoryPrincipal, MemoryRetrieveRequest, MemorySource,
    MemorySubmitRequest,
)
from app.memory.factory import build_memory_system
from app.memory.ports.authorization import (
    AllowAllMemoryAuthorizationProvider, DenyByDefaultMemoryAuthorizationProvider,
)
from app.memory.models.scope import MemoryScope


class MemoryBoundaryArchitectureTest(unittest.TestCase):
    def test_memory_package_has_no_platform_reverse_dependencies(self):
        forbidden = (
            "app.runtime", "app.agents", "app.orchestration", "app.manifest",
            "app.events", "app.audit", "app.main",
        )
        root = Path(__file__).parents[1] / "app" / "memory"
        imports = []
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
        self.assertFalse(
            [name for name in imports if name.startswith(forbidden)], imports
        )

    def test_platform_adapters_are_outside_memory_core(self):
        root = Path(__file__).parents[1]
        self.assertTrue((root / "app/integrations/memory/runtime_adapter.py").exists())
        self.assertTrue((root / "app/integrations/memory/event_bus_bridge.py").exists())
        self.assertTrue((root / "app/memory/worker/event_worker.py").exists())
        self.assertFalse((root / "app/memory/adapter/runtime.py").exists())
        self.assertFalse((root / "app/memory/consumer/event_consumer.py").exists())

    def test_service_has_fixed_submit_contract_without_consumer_attachment(self):
        from app.memory.api.service import MemoryService
        self.assertFalse(hasattr(MemoryService, "attach_consumer"))

    def test_authorization_is_not_implicitly_allow_all(self):
        provider = DenyByDefaultMemoryAuthorizationProvider()
        with self.assertRaises(PermissionError):
            provider.authorize_ingest(None, None, None)

    def test_submit_contract_contains_memory_owned_boundary_fields(self):
        request = MemorySubmitRequest(
            principal=MemoryPrincipal("subject", "tenant", "user", "agent"),
            scope=MemoryScope("tenant", "user", "agent"),
            idempotency_key="source-1",
            source=MemorySource("human_input", "source-1"),
            observations=[MemoryObservation("user_input", "hello")],
        )
        self.assertEqual("human_input", request.source.kind)
        self.assertEqual("source-1", request.idempotency_key)
        retrieve = MemoryRetrieveRequest(
            principal=request.principal, scope=request.scope, query="hello"
        )
        self.assertEqual("tenant", retrieve.tenant_id)

    def test_factory_requires_explicit_authorization_provider(self):
        with self.assertRaisesRegex(ValueError, "authorization_provider"):
            build_memory_system(repository=object(), embedding_service=object())

    def test_allow_all_provider_is_explicit(self):
        provider = AllowAllMemoryAuthorizationProvider()
        self.assertIsNotNone(provider.authorize_read(None, None, []))


if __name__ == "__main__":
    unittest.main()
