import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from app.events.bus import EventBus
from app.events.models import Event
from app.memory.api.models import MemoryEventRequest, MemoryRetrieveRequest
from app.memory.factory import build_memory_system
from app.memory.governance.policy import MemoryAccessDenied, MemoryGovernancePolicy
from app.memory.models.event import MemoryEventStatus
from app.memory.models.identity import MemoryIdentity
from app.memory.models.item import MemoryItemStatus
from app.memory.models.scope import MemoryScope
from app.memory.pipeline.write.extractor import LLMMemoryExtractor, StructuredMemoryExtractor
from tests.memory_repository import TestEmbeddingService, TestMemoryRepository


class StubLLM:
    def chat(self, messages, **kwargs):
        return "compressed memory context"


class ExtractionLLM:
    def chat(self, messages, **kwargs):
        return json.dumps([{
            "type": "customer", "entity_id": "Customer A", "attribute": "budget",
            "content": {"amount": 1000000}, "confidence": 0.9,
            "business_value": 0.9, "stability": 0.8,
            "explicitness": 1.0, "future_usefulness": 0.9,
        }])


def candidate(content, confidence=0.9, **metadata):
    return {
        "type": "customer", "entity_id": "Customer A", "attribute": "budget",
        "content": content, "confidence": confidence,
        "business_value": 0.9, "stability": 0.8,
        "explicitness": 1.0, "future_usefulness": 0.9,
        "metadata": metadata,
    }


class MemorySystemTest(unittest.TestCase):
    def build(self, governance=None):
        bus = EventBus()
        service, consumer, adapter, audit = build_memory_system(
            StubLLM(), bus, extractor=StructuredMemoryExtractor(),
            async_mode=False, governance=governance,
            repository=TestMemoryRepository(),
            embedding_service=TestEmbeddingService(),
        )
        return service, consumer, adapter, audit, bus

    def request(self, value, confidence=0.9, **metadata):
        return MemoryEventRequest(
            trace_id="trace-1", task_id="task-1", agent_id="sales_agent",
            user_id="user-1", tenant_id="tenant-1", department_id="sales",
            event_type="response.completed", input={"query": "customer budget"},
            output={"answer": "done"}, tool_results=[],
            metadata={"memory_candidates": [candidate(value, confidence, **metadata)]},
        )

    def retrieve_request(self, **overrides):
        values = {
            "user_id": "user-1", "agent_id": "sales_agent",
            "tenant_id": "tenant-1", "department_id": "sales",
            "query": "customer budget", "types": ["customer"],
            "limit": 10, "trace_id": "read-1",
        }
        values.update(overrides)
        return MemoryRetrieveRequest(**values)

    def test_submit_processes_event_and_retrieve_returns_public_context(self):
        service, consumer, _, audit, _ = self.build()
        with redirect_stdout(StringIO()):
            response = service.submit(self.request({"amount": 1000000}))
            context = service.retrieve(self.retrieve_request())

        self.assertTrue(response.accepted)
        self.assertEqual(MemoryEventStatus.PROCESSED, consumer.repository.get_event(response.event_id).status)
        self.assertEqual(
            "completed",
            consumer.repository.processing_tasks[response.event_id]["status"],
        )
        self.assertEqual("compressed memory context", context.summary)
        self.assertEqual(1, len(context.references))
        self.assertFalse(hasattr(context.references[0], "embedding"))
        self.assertEqual(1, len(audit.query("memory.created", "sales_agent")))
        stored = consumer.repository.get_item(context.references[0].memory_id)
        self.assertEqual([1.0, 0.0, 0.0], stored.embedding)
        self.assertEqual("test-embedding", stored.embedding_model)
        self.assertEqual("test", stored.embedding_version)
        self.assertEqual(3, stored.embedding_dimension)

    def test_exact_duplicate_merges_without_new_version(self):
        service, consumer, _, _, _ = self.build()
        with redirect_stdout(StringIO()):
            service.submit(self.request({"amount": 1000000}))
            service.submit(self.request({"amount": 1000000}))
        versions = consumer.repository.list_versions(
            MemoryScope("tenant-1", "user-1", "sales_agent", "sales"),
            MemoryIdentity("customer", "customer_a", "budget"),
        )
        self.assertEqual(1, len(versions))

    def test_changed_fact_creates_replacement_version(self):
        service, consumer, _, _, _ = self.build()
        with redirect_stdout(StringIO()):
            service.submit(self.request({"amount": 1000000}, confidence=0.8))
            service.submit(self.request({"amount": 1200000}, confidence=0.9))
        versions = consumer.repository.list_versions(
            MemoryScope("tenant-1", "user-1", "sales_agent", "sales"),
            MemoryIdentity("customer", "customer_a", "budget"),
        )
        self.assertEqual([1, 2], [item.version for item in versions])
        self.assertEqual(MemoryItemStatus.REPLACED, versions[0].status)
        self.assertEqual(versions[1].id, versions[0].replaced_by_id)

    def test_conflict_preserves_active_history(self):
        service, consumer, _, _, _ = self.build()
        with redirect_stdout(StringIO()):
            service.submit(self.request({"amount": 1000000}))
            service.submit(self.request({"amount": 800000}, conflict=True))
        versions = consumer.repository.list_versions(
            MemoryScope("tenant-1", "user-1", "sales_agent", "sales"),
            MemoryIdentity("customer", "customer_a", "budget"),
        )
        self.assertEqual(MemoryItemStatus.ACTIVE, versions[0].status)
        self.assertEqual(MemoryItemStatus.CONFLICT, versions[1].status)

    def test_conflict_then_replacement_keeps_one_active_head(self):
        service, consumer, _, _, _ = self.build()
        with redirect_stdout(StringIO()):
            service.submit(self.request({"amount": 100}, confidence=0.9))
            service.submit(self.request({"amount": 80}, confidence=0.8, conflict=True))
            service.submit(self.request({"amount": 120}, confidence=0.95))
        scope = MemoryScope("tenant-1", "user-1", "sales_agent", "sales")
        identity = MemoryIdentity("customer", "customer_a", "budget")
        versions = consumer.repository.list_versions(scope, identity)
        self.assertEqual([1, 2, 3], [item.version for item in versions])
        self.assertEqual(
            [MemoryItemStatus.REPLACED, MemoryItemStatus.CONFLICT,
             MemoryItemStatus.ACTIVE],
            [item.status for item in versions],
        )
        self.assertEqual(versions[2].id, versions[0].replaced_by_id)
        self.assertEqual(versions[2].id, consumer.repository.find_active_head(
            scope, identity
        ).id)

    def test_conflict_then_lower_confidence_fact_still_compares_with_active(self):
        service, consumer, _, _, _ = self.build()
        with redirect_stdout(StringIO()):
            service.submit(self.request({"amount": 100}, confidence=0.9))
            service.submit(self.request({"amount": 80}, confidence=0.8, conflict=True))
            service.submit(self.request({"amount": 70}, confidence=0.7))
        scope = MemoryScope("tenant-1", "user-1", "sales_agent", "sales")
        identity = MemoryIdentity("customer", "customer_a", "budget")
        versions = consumer.repository.list_versions(scope, identity)
        self.assertEqual(
            [MemoryItemStatus.ACTIVE, MemoryItemStatus.CONFLICT,
             MemoryItemStatus.CONFLICT],
            [item.status for item in versions],
        )
        self.assertEqual(versions[0].id, consumer.repository.find_active_head(
            scope, identity
        ).id)

    def test_governance_denies_read_and_write(self):
        deny_read = MemoryGovernancePolicy(read_rule=lambda request: False)
        service, _, _, audit, _ = self.build(deny_read)
        with redirect_stdout(StringIO()), self.assertRaises(MemoryAccessDenied):
            service.retrieve(self.retrieve_request())
        self.assertEqual(1, len(audit.query("memory.read.denied")))

        deny_write = MemoryGovernancePolicy(write_rule=lambda event, item: False)
        service, consumer, _, audit, _ = self.build(deny_write)
        with redirect_stdout(StringIO()):
            response = service.submit(self.request({"amount": 1000000}))
        self.assertEqual(MemoryEventStatus.FAILED, consumer.repository.get_event(response.event_id).status)
        self.assertEqual(
            "failed",
            consumer.repository.processing_tasks[response.event_id]["status"],
        )
        self.assertEqual(0, len(consumer.repository.items))
        self.assertEqual(1, len(audit.query("memory.failed")))

    def test_response_event_enters_memory_pipeline_without_runtime_save(self):
        service, consumer, _, _, bus = self.build()
        event = Event("response.completed", {
            "trace_id": "trace", "task_id": "task", "agent_id": "sales_agent",
            "user_id": "user-1", "tenant_id": "tenant-1", "department_id": "sales",
            "input": "customer budget", "output": "recorded", "tool_results": [],
            "metadata": {"memory_candidates": [candidate({"amount": 1000000})]},
        })
        with redirect_stdout(StringIO()):
            bus.publish(event)
        self.assertEqual(1, len(consumer.repository.events))
        self.assertEqual(1, len(consumer.repository.items))

    def test_llm_extractor_extracts_candidates_without_persistence_decision(self):
        service, consumer, _, _, _ = self.build()
        event_request = self.request({"amount": 1})
        response = service.submit(event_request)
        event = consumer.repository.get_event(response.event_id)
        extracted = LLMMemoryExtractor(ExtractionLLM()).extract(event)
        self.assertEqual("customer:Customer A:budget", extracted[0].memory_key)


if __name__ == "__main__":
    unittest.main()
