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
    MemoryReadGrant,
)
from app.memory.models.scope import MemoryScope


class MemoryBoundaryArchitectureTest(unittest.TestCase):
    def test_memory_package_has_no_platform_reverse_dependencies(self):
        forbidden = (
            "app.runtime", "app.agents", "app.orchestration", "app.manifest",
            "app.events", "app.audit", "app.main",
        )
        root = Path(__file__).parents[2] / "app" / "memory"
        imports = []
        for path in root.rglob("*.py"):
            if path.name.startswith("test_"):
                continue
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
        root = Path(__file__).parents[2]
        self.assertTrue((root / "app/integrations/memory/runtime_adapter.py").exists())
        self.assertTrue((root / "app/integrations/memory/event_bus_bridge.py").exists())
        self.assertTrue((root / "app/memory/worker/event_worker.py").exists())
        self.assertFalse((root / "app/memory/adapter/runtime.py").exists())
        self.assertFalse((root / "app/memory/consumer/event_consumer.py").exists())

    def test_service_has_fixed_submit_contract_without_consumer_attachment(self):
        from app.memory.api.service import MemoryService
        self.assertFalse(hasattr(MemoryService, "attach_consumer"))

    def test_contract_cleanup_removes_legacy_requests_and_duplicate_domain_event(self):
        from app.memory.api import models
        from app.memory import events
        from app.memory.models import event as event_model
        self.assertFalse(hasattr(models, "MemoryEventRequest"))
        self.assertFalse(hasattr(models, "LegacyMemoryEventRequest"))
        self.assertFalse(hasattr(event_model, "MemoryDomainEvent"))
        self.assertTrue(hasattr(events, "MemoryDomainEvent"))

    def test_public_memory_system_is_data_plane_only(self):
        from app.memory.factory import MemorySystem
        self.assertFalse(hasattr(MemorySystem, "client"))
        self.assertFalse(hasattr(MemorySystem, "control"))
        self.assertFalse(hasattr(MemorySystem, "drain"))
        self.assertTrue(callable(MemorySystem.read))
        self.assertTrue(callable(MemorySystem.write))
        self.assertFalse(hasattr(MemorySystem, "retrieve"))
        self.assertFalse(hasattr(MemorySystem, "submit"))

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
        self.assertEqual("tenant", retrieve.scope.tenant_id)

    def test_factory_requires_explicit_authorization_provider(self):
        with self.assertRaisesRegex(ValueError, "authorization_provider"):
            build_memory_system(repository=object(), embedding_service=object())

    def test_allow_all_provider_is_explicit(self):
        provider = AllowAllMemoryAuthorizationProvider()
        self.assertIsNotNone(provider.authorize_read(None, None, []))

    def test_specific_grant_constrains_empty_requested_types(self):
        grant = MemoryReadGrant(frozenset({"customer"}))
        self.assertEqual(frozenset({"customer"}), grant.effective_types([]))
        with self.assertRaises(PermissionError):
            grant.effective_types(["profile"])
        with self.assertRaises(PermissionError):
            MemoryReadGrant.deny_all().effective_types([])


if __name__ == "__main__":
    unittest.main()
