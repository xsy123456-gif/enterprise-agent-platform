import os
import unittest
import uuid
from contextlib import redirect_stdout
from io import StringIO

from app.events.bus import EventBus
from app.memory.api.models import MemoryEventRequest, MemoryRetrieveRequest
from app.memory.factory import build_memory_system
from app.memory.pipeline.write.extractor import StructuredMemoryExtractor
from app.memory.storage.postgres import create_postgres_repository


class StubLLM:
    def chat(self, messages, **kwargs):
        return "postgres memory context"


@unittest.skipUnless(
    os.getenv("MEMORY_TEST_DATABASE_URL"),
    "MEMORY_TEST_DATABASE_URL is not configured",
)
class PostgresMemoryIntegrationTest(unittest.TestCase):
    def test_postgres_repository_persists_and_retrieves(self):
        dsn = os.environ["MEMORY_TEST_DATABASE_URL"]
        repository = create_postgres_repository(dsn, initialize=True)
        suffix = uuid.uuid4().hex
        user_id = f"memory-test-{suffix}"
        bus = EventBus()
        service, _, _, _ = build_memory_system(
            StubLLM(), bus, repository=repository,
            extractor=StructuredMemoryExtractor(), async_mode=False,
        )
        request = MemoryEventRequest(
            trace_id=suffix, task_id=suffix, agent_id="sales_agent",
            user_id=user_id, tenant_id="memory-test", department_id="test",
            event_type="response.completed", input={"query": "customer budget"},
            output={"answer": "done"}, tool_results=[],
            metadata={"memory_candidates": [{
                "type": "customer", "entity_id": suffix, "attribute": "budget",
                "content": {"amount": 100}, "confidence": 0.9,
                "business_value": 0.9, "stability": 0.9,
                "explicitness": 0.9, "future_usefulness": 0.9,
            }]},
        )
        with redirect_stdout(StringIO()):
            response = service.submit(request)
            context = service.retrieve(MemoryRetrieveRequest(
                user_id=user_id, agent_id="sales_agent", tenant_id="memory-test",
                department_id="test", query="customer budget", trace_id=suffix,
            ))

        self.assertTrue(response.accepted)
        self.assertEqual(1, len(context.references))


if __name__ == "__main__":
    unittest.main()
