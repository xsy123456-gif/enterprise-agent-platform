import os
import unittest
import uuid
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO

from app.events.bus import EventBus
from app.main import build_runtime
from app.memory.api.models import MemoryEventRequest, MemoryRetrieveRequest
from app.memory.factory import build_memory_system
from app.memory.models.event import MemoryEvent, MemoryEventStatus
from app.memory.models.item import MemoryItem, MemoryItemStatus
from app.memory.pipeline.write.extractor import StructuredMemoryExtractor
from app.memory.storage.postgres import create_postgres_repository
from app.runtime.context import AgentContext
from tests.memory_repository import TestEmbeddingService


class StubLLM:
    def chat(self, messages, **kwargs):
        return "postgres memory context"


class RuntimeMemoryLLM:
    def __init__(self):
        self.observed_memory = False

    def chat(self, messages, **kwargs):
        system = messages[0].get("content", "")
        if system.startswith("You are a memory fact extractor"):
            return (
                '[{"type":"customer","entity_id":"customer_A",'
                '"attribute":"industry","content":"新能源",'
                '"confidence":0.9,"business_value":0.9,"stability":0.9,'
                '"explicitness":0.9,"future_usefulness":0.9}]'
            )
        if system.startswith("Compress supplied memory facts"):
            return "historical customer memory"
        if any("historical customer memory" in str(message) for message in messages):
            self.observed_memory = True
        return '{"type":"finish","output":"done"}'


@unittest.skipUnless(
    os.getenv("MEMORY_TEST_DATABASE_URL"),
    "MEMORY_TEST_DATABASE_URL is not configured",
)
class PostgresMemoryIntegrationTest(unittest.TestCase):
    DIMENSION = int(os.getenv("MEMORY_TEST_EMBEDDING_DIMENSION", "1024"))

    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["MEMORY_TEST_DATABASE_URL"]
        cls.repository = create_postgres_repository(
            cls.dsn, embedding_dimension=cls.DIMENSION, initialize=True
        )

    def setUp(self):
        self.suffix = uuid.uuid4().hex
        self.user_id = f"memory-test-{self.suffix}"
        self.tenant_id = f"memory-test-{self.suffix}"

    def tearDown(self):
        with self.repository.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM memory_access_logs WHERE user_id=%s", (self.user_id,)
                )
                cursor.execute(
                    "DELETE FROM memory_relations WHERE source_id IN "
                    "(SELECT id FROM memory_items WHERE user_id=%s) OR target_id IN "
                    "(SELECT id FROM memory_items WHERE user_id=%s)",
                    (self.user_id, self.user_id),
                )
                cursor.execute(
                    "DELETE FROM memory_processing_tasks WHERE event_id IN "
                    "(SELECT event_id FROM memory_events WHERE user_id=%s)",
                    (self.user_id,),
                )
                cursor.execute("DELETE FROM memory_items WHERE user_id=%s", (self.user_id,))
                cursor.execute("DELETE FROM memory_events WHERE user_id=%s", (self.user_id,))

    def make_item(self, key, content, embedding, version=1, status=MemoryItemStatus.ACTIVE,
                  replaces_id=None):
        return MemoryItem(
            memory_key=key, type="customer", content=content,
            embedding=embedding, importance=0.9, confidence=0.9,
            source="integration-test", tenant_id=self.tenant_id,
            department_id="test", user_id=self.user_id,
            agent_id="sales_agent", version=version, status=status,
            replaces_id=replaces_id,
        )

    def retrieve_request(self, query="customer", limit=10):
        return MemoryRetrieveRequest(
            user_id=self.user_id, agent_id="sales_agent",
            tenant_id=self.tenant_id, department_id="test",
            query=query, limit=limit, trace_id=self.suffix,
        )

    def vector(self, primary, secondary=None):
        vector = [0.0] * self.DIMENSION
        vector[primary] = 1.0 if secondary is None else secondary[0]
        if secondary is not None:
            vector[secondary[1]] = secondary[2]
        return vector

    def test_connection_schema_extension_and_vector_index(self):
        self.assertGreaterEqual(self.repository.healthcheck(), 160000)
        state = self.repository.validate_schema()
        self.assertEqual(self.DIMENSION, state["embedding_dimension"])
        self.assertTrue(state["pgvector_version"])
        self.assertEqual("memory_items_embedding_hnsw_idx", state["vector_index"])
        self.assertTrue({
            "memory_events", "memory_items", "memory_relations",
            "memory_access_logs", "memory_processing_tasks",
        }.issubset(state["tables"]))

    def test_embedding_dimension_mismatch_fails_at_startup(self):
        with self.assertRaisesRegex(RuntimeError, "dimension mismatch"):
            create_postgres_repository(
                self.dsn, embedding_dimension=self.DIMENSION + 1,
                initialize=False,
            )

    def test_event_create_query_and_status_update(self):
        event = MemoryEvent(
            trace_id=self.suffix, task_id=self.suffix, agent_id="sales_agent",
            user_id=self.user_id, tenant_id=self.tenant_id,
            department_id="test", event_type="response.completed",
            input={"query": "customer"}, output={"answer": "done"},
            tool_results=[], metadata={},
        )
        self.repository.save_event(event)
        stored = self.repository.get_event(event.event_id)
        self.assertEqual(MemoryEventStatus.RECEIVED, stored.status)
        stored.status = MemoryEventStatus.PROCESSED
        stored.processed_at = datetime.now(timezone.utc)
        self.repository.update_event(stored)
        self.assertEqual(
            MemoryEventStatus.PROCESSED,
            self.repository.get_event(event.event_id).status,
        )

    def test_item_versions_replace_conflict_and_relations(self):
        key = f"customer:{self.suffix}:budget"
        first = self.make_item(key, {"amount": 100}, self.vector(0))
        self.repository.create_item(first, relations=[(self.suffix, "DERIVED_FROM")])
        second = self.make_item(
            key, {"amount": 120}, self.vector(0, (0.9, 1, 0.1)), version=2,
            replaces_id=first.id,
        )
        self.repository.create_item(second, relations=[(first.id, "REPLACES")])
        conflict = self.make_item(
            key, {"amount": 80}, self.vector(0, (0.8, 1, 0.2)), version=3,
            status=MemoryItemStatus.CONFLICT,
        )
        self.repository.create_item(
            conflict, relations=[(first.id, "CONFLICT_WITH")]
        )
        self.repository.create_relation(second.id, self.suffix, "MERGED_FROM")

        versions = self.repository.list_versions(
            key, self.tenant_id, self.user_id, "sales_agent"
        )
        self.assertEqual([1, 2, 3], [item.version for item in versions])
        self.assertEqual(MemoryItemStatus.REPLACED, versions[0].status)
        self.assertEqual(second.id, versions[0].replaced_by_id)
        self.assertEqual(
            {"REPLACES", "DERIVED_FROM", "MERGED_FROM", "CONFLICT_WITH"},
            {relation["relation_type"] for relation in self.repository.list_relations()},
        )

    def test_sql_retrieve_writes_access_log_without_realtime_counter(self):
        item = self.make_item(
            f"customer:{self.suffix}:industry", "新能源", self.vector(0)
        )
        self.repository.create_item(item)
        bus = EventBus()
        service, _, _, _ = build_memory_system(
            StubLLM(), bus, repository=self.repository,
            extractor=StructuredMemoryExtractor(), async_mode=False,
            embedding_service=TestEmbeddingService(dimension=self.DIMENSION),
        )
        with redirect_stdout(StringIO()):
            context = service.retrieve(self.retrieve_request("industry"))
        self.assertEqual([item.id], [reference.memory_id for reference in context.references])
        self.assertEqual(0, self.repository.get_item(item.id).access_count)
        with self.repository.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT query FROM memory_access_logs WHERE memory_id=%s", (item.id,)
                )
                self.assertEqual("industry", cursor.fetchone()[0])

    def test_write_pipeline_persists_embedding_metadata(self):
        bus = EventBus()
        service, _, _, _ = build_memory_system(
            StubLLM(), bus, repository=self.repository,
            extractor=StructuredMemoryExtractor(), async_mode=False,
            embedding_service=TestEmbeddingService(dimension=self.DIMENSION),
        )
        request = MemoryEventRequest(
            trace_id=self.suffix, task_id=self.suffix, agent_id="sales_agent",
            user_id=self.user_id, tenant_id=self.tenant_id, department_id="test",
            event_type="response.completed", input={}, output={}, tool_results=[],
            metadata={"memory_candidates": [{
                "type": "customer", "entity_id": self.suffix,
                "attribute": "semantic", "content": "customer semantic fact",
                "confidence": 0.9, "business_value": 0.9, "stability": 0.9,
                "explicitness": 0.9, "future_usefulness": 0.9,
            }]},
        )
        with redirect_stdout(StringIO()):
            service.submit(request)
        stored = self.repository.find_latest(
            f"customer:{self.suffix}:semantic", self.tenant_id,
            self.user_id, "sales_agent",
        )
        self.assertEqual(self.vector(0), stored.embedding)
        self.assertEqual("test-embedding", stored.embedding_model)
        self.assertEqual("test", stored.embedding_version)
        self.assertEqual(self.DIMENSION, stored.embedding_dimension)

    def test_vector_search_returns_real_similarity_order(self):
        close = self.make_item(
            f"customer:{self.suffix}:close", "close", self.vector(0)
        )
        far = self.make_item(
            f"customer:{self.suffix}:far", "far", self.vector(1)
        )
        self.repository.create_item(close)
        self.repository.create_item(far)
        results = self.repository.search(
            self.retrieve_request(limit=2),
            query_embedding=self.vector(0, (0.99, 1, 0.01)),
        )
        self.assertEqual(close.id, results[0][0].id)
        self.assertGreater(results[0][1], results[1][1])
        self.assertGreater(results[0][1], 0.99)

    def test_runtime_event_persists_then_next_request_retrieves(self):
        llm = RuntimeMemoryLLM()
        runtime, _, _ = build_runtime(
            llm=llm, memory_repository=self.repository,
            memory_embedding_service=TestEmbeddingService(dimension=self.DIMENSION),
        )
        lifecycle = runtime.lifecycle_service
        lifecycle.request_review("sales_agent", "0.2")
        lifecycle.approve("sales_agent", "0.2")
        lifecycle.activate("sales_agent", "0.2")

        def state():
            return AgentContext(
                task="analyze customer A", user_id=self.user_id, role="sales",
                agent_name="sales_agent", tenant_id=self.tenant_id,
                department_id="test",
            )

        with redirect_stdout(StringIO()):
            self.assertEqual("done", runtime.run(state()))
            runtime.memory_consumer.drain()
            self.assertEqual("done", runtime.run(state()))
            runtime.memory_consumer.drain()

        self.assertTrue(llm.observed_memory)
        with self.repository.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM memory_events WHERE user_id=%s", (self.user_id,)
                )
                self.assertEqual(2, cursor.fetchone()[0])
                cursor.execute(
                    "SELECT count(*) FROM memory_items WHERE user_id=%s", (self.user_id,)
                )
                self.assertEqual(1, cursor.fetchone()[0])


if __name__ == "__main__":
    unittest.main()
