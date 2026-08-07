import unittest

from app.memory.api.models import (
    MemoryObservation, MemoryPrincipal, MemoryRetrieveRequest, MemorySource,
    MemorySubmitRequest,
)
from app.memory.factory import build_memory_system
from app.memory.models.identity import MemoryIdentity
from app.memory.models.item import MemoryItemStatus
from app.memory.models.scope import MemoryScope
from app.memory.pipeline.write.extractor import StructuredMemoryExtractor
from app.memory.ports.authorization import AllowAllMemoryAuthorizationProvider
from tests.memory_repository import TestEmbeddingService, TestMemoryRepository


def candidate(content, confidence=0.9, type_id="customer", **metadata):
    return {
        "type": type_id, "entity_id": "Customer A", "attribute": "budget",
        "content": content, "confidence": confidence,
        "business_value": 0.9, "stability": 0.8,
        "explicitness": 1.0, "future_usefulness": 0.9,
        "metadata": metadata,
    }


class StubLLM:
    def chat(self, messages, **kwargs):
        return "compressed memory context"


class MemorySystemTest(unittest.TestCase):
    def setUp(self):
        self.repository = TestMemoryRepository()
        self.scope = MemoryScope("tenant-1", "user-1", "sales_agent", "sales")
        self.principal = MemoryPrincipal("user-1", "tenant-1", "user-1", "sales_agent")
        self.system = build_memory_system(
            repository=self.repository, embedding_service=TestEmbeddingService(),
            extractor=StructuredMemoryExtractor(), text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
            async_mode=False,
        )

    def submit_request(self, value, confidence=0.9, observations=None):
        return MemorySubmitRequest(
            principal=self.principal, scope=self.scope,
            idempotency_key=f"source-{len(self.repository.events)}",
            source=MemorySource("workflow_result", f"task-{len(self.repository.events)}"),
            observations=observations or [MemoryObservation("business_fact", value)],
            metadata={"memory_candidates": [candidate(value, confidence)]},
            trace_id="trace-1",
        )

    def retrieve_request(self, types=None):
        return MemoryRetrieveRequest(
            principal=self.principal, scope=self.scope, query="customer budget",
            types=types or ["customer"], trace_id="read-1",
        )

    def test_submit_processes_generic_observations_and_retrieves_context(self):
        response = self.system.submit(self.submit_request({"amount": 1000000}))
        self.system._worker.process_once()
        self.assertEqual("processed", self.repository.get_event(response.event_id).status)
        context = self.system.retrieve(self.retrieve_request())
        self.assertEqual("compressed memory context", context.summary)
        self.assertEqual(1, len(context.references))

    def test_unknown_observation_is_preserved_for_extractor(self):
        request = self.submit_request(
            {"amount": 1},
            observations=[MemoryObservation("crm_snapshot", {"segment": "A"})],
        )
        response = self.system.submit(request)
        self.system._worker.process_once()
        event = self.repository.get_event(response.event_id)
        self.assertEqual("crm_snapshot", event.observations[0].kind)
        self.assertEqual({"segment": "A"}, event.observations[0].content)

    def test_changed_fact_creates_replacement_version(self):
        self.system.submit(self.submit_request({"amount": 100}, confidence=0.8))
        self.system._worker.process_once()
        self.system.submit(self.submit_request({"amount": 120}, confidence=0.9))
        self.system._worker.process_once()
        versions = self.repository.list_versions(
            self.scope, MemoryIdentity("customer", "customer_a", "budget")
        )
        self.assertEqual([1, 2], [item.version for item in versions])
        self.assertEqual(MemoryItemStatus.REPLACED, versions[0].status)

    def test_exact_duplicate_merges_without_new_version(self):
        self.system.submit(self.submit_request({"amount": 100}))
        self.system._worker.process_once()
        self.system.submit(self.submit_request({"amount": 100}))
        self.system._worker.process_once()
        versions = self.repository.list_versions(
            self.scope, MemoryIdentity("customer", "customer_a", "budget")
        )
        self.assertEqual(1, len(versions))

    def test_system_has_no_public_service_or_control_bypass(self):
        self.assertFalse(hasattr(self.system, "client"))
        self.assertFalse(hasattr(self.system, "control"))

    def test_specific_read_grant_limits_empty_type_query(self):
        class CustomerOnlyAuthorization:
            def authorize_ingest(self, principal, scope, source):
                return None

            def authorize_read(self, principal, scope, requested_types):
                from app.memory.ports.authorization import MemoryReadGrant
                return MemoryReadGrant(frozenset({"customer"}))

            def authorize_write_candidate(self, principal, scope, candidate_type):
                return None

        repository = TestMemoryRepository()
        system = build_memory_system(
            repository=repository, embedding_service=TestEmbeddingService(),
            extractor=StructuredMemoryExtractor(), text_model=StubLLM(),
            authorization_provider=CustomerOnlyAuthorization(), async_mode=False,
        )
        for type_id in ("customer", "profile"):
            request = MemorySubmitRequest(
                self.principal, self.scope, f"{type_id}-source",
                MemorySource("test", type_id), [MemoryObservation("fact", type_id)],
                metadata={"memory_candidates": [candidate(type_id, type_id=type_id)]},
            )
            system.submit(request)
            system._worker.process_once()
        context = system.retrieve(MemoryRetrieveRequest(
            self.principal, self.scope, query="", types=[]
        ))
        self.assertEqual(["customer"], [reference.type for reference in context.references])


if __name__ == "__main__":
    unittest.main()
