import os
import unittest
import uuid
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from threading import Barrier, Lock, Thread

from psycopg.errors import UniqueViolation

from app.memory.errors import ConcurrentMemoryWrite
from app.memory.api.models import (
    MemoryObservation, MemoryPrincipal, MemoryRetrieveRequest, MemorySource,
    MemorySubmitRequest,
)
from app.memory.embedding.models import EmbeddingSpace
from app.memory.factory import build_memory_system
from app.memory.models.event import MemoryEvent, MemoryEventStatus
from app.memory.models.identity import MemoryIdentity
from app.memory.models.item import MemoryItem, MemoryItemStatus
from app.memory.models.scope import MemoryScope
from app.memory.pipeline.write.extractor import StructuredMemoryExtractor
from app.memory.ports.authorization import AllowAllMemoryAuthorizationProvider
from app.memory.storage.postgres import create_postgres_repository
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
    TEST_SPACE_ID = EmbeddingSpace("test", "test", "1", DIMENSION).space_id

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
                  replaces_id=None, department_id="test", space_id=None):
        type_id, entity_id, attribute = key.split(":", 2)
        return MemoryItem(
            memory_key=key, type=type_id, entity_id=entity_id,
            attribute=attribute, content=content,
            embedding=embedding, importance=0.9, confidence=0.9,
            embedding_space_id=space_id or self.TEST_SPACE_ID,
            embedding_provider="test", embedding_model="test", embedding_version="1",
            embedding_dimension=self.DIMENSION,
            source="integration-test", tenant_id=self.tenant_id,
            department_id=department_id, user_id=self.user_id,
            agent_id="sales_agent", version=version, status=status,
            replaces_id=replaces_id,
        )

    def retrieve_request(self, query="customer", limit=10):
        scope = self.scope()
        return MemoryRetrieveRequest(
            principal=MemoryPrincipal(
                self.user_id, self.tenant_id, self.user_id, "sales_agent"
            ),
            scope=scope,
            query=query, limit=limit, trace_id=self.suffix,
        )

    def vector(self, primary, secondary=None):
        vector = [0.0] * self.DIMENSION
        vector[primary] = 1.0 if secondary is None else secondary[0]
        if secondary is not None:
            vector[secondary[1]] = secondary[2]
        return vector

    def scope(self, department_id="test"):
        return MemoryScope(
            self.tenant_id, self.user_id, "sales_agent", department_id
        )

    def identity(self, entity_id=None, attribute="budget"):
        return MemoryIdentity("customer", entity_id or self.suffix, attribute)

    def test_connection_schema_extension_and_vector_index(self):
        self.assertGreaterEqual(self.repository.healthcheck(), 160000)
        state = self.repository.validate_schema()
        self.assertEqual(self.DIMENSION, state["embedding_dimension"])
        self.assertTrue(state["pgvector_version"])
        self.assertEqual("memory_items_embedding_hnsw_idx", state["vector_index"])
        self.assertEqual("memory_items_active_head_uidx", state["active_head_index"])
        self.assertEqual(
            "memory_items_scope_identity_version_uidx", state["version_index"]
        )
        self.assertTrue({
            "memory_events", "memory_items", "memory_relations",
            "memory_access_logs", "memory_processing_tasks",
        }.issubset(state["tables"]))

    def test_validate_schema_fails_when_version_identity_index_is_missing(self):
        with self.repository.connection_factory(register_types=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DROP INDEX memory_items_scope_identity_version_uidx")
        try:
            with self.assertRaisesRegex(RuntimeError, "version unique index is missing"):
                self.repository.validate_schema()
        finally:
            with self.repository.connection_factory(register_types=False) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "CREATE UNIQUE INDEX memory_items_scope_identity_version_uidx "
                        "ON memory_items (tenant_id, department_id, user_id, agent_id, "
                        "type, entity_id, attribute, version) NULLS NOT DISTINCT"
                    )

    def test_legacy_key_backfill_accepts_unambiguous_key(self):
        with self.repository.connection_factory(register_types=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "CREATE TEMP TABLE memory_items ("
                    "id text, memory_key text NOT NULL, type text NOT NULL, "
                    "entity_id text, attribute text)"
                )
                cursor.execute(
                    "INSERT INTO memory_items (id, memory_key, type) "
                    "VALUES ('legacy-1', 'customer:customer_A:industry', 'customer')"
                )
                self.repository._backfill_legacy_identity(cursor)
                cursor.execute(
                    "SELECT entity_id, attribute FROM memory_items WHERE id='legacy-1'"
                )
                self.assertEqual(("customer_A", "industry"), cursor.fetchone())

    def test_legacy_key_backfill_rejects_ambiguous_key(self):
        with self.repository.connection_factory(register_types=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "CREATE TEMP TABLE memory_items ("
                    "id text, memory_key text NOT NULL, type text NOT NULL, "
                    "entity_id text, attribute text)"
                )
                cursor.execute(
                    "INSERT INTO memory_items (id, memory_key, type) "
                    "VALUES ('legacy-ambiguous', 'customer:customer_A:industry:extra', 'customer')"
                )
                with self.assertRaisesRegex(RuntimeError, "Cannot safely backfill"):
                    self.repository._backfill_legacy_identity(cursor)

    def test_legacy_key_backfill_rejects_type_mismatch(self):
        with self.repository.connection_factory(register_types=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "CREATE TEMP TABLE memory_items ("
                    "id text, memory_key text NOT NULL, type text NOT NULL, "
                    "entity_id text, attribute text)"
                )
                cursor.execute(
                    "INSERT INTO memory_items (id, memory_key, type) "
                    "VALUES ('legacy-mismatch', 'string:customer_A:industry', 'customer')"
                )
                with self.assertRaisesRegex(RuntimeError, "Cannot safely backfill"):
                    self.repository._backfill_legacy_identity(cursor)

    def test_embedding_dimension_mismatch_fails_at_startup(self):
        with self.assertRaisesRegex(RuntimeError, "dimension mismatch"):
            create_postgres_repository(
                self.dsn, embedding_dimension=self.DIMENSION + 1,
                initialize=False,
            )

    def test_postgres_submit_is_idempotent_and_claimable(self):
        system = build_memory_system(
            repository=self.repository,
            extractor=StructuredMemoryExtractor(),
            embedding_service=TestEmbeddingService(dimension=self.DIMENSION),
            text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
            async_mode=False,
        )
        request = MemorySubmitRequest(
            principal=MemoryPrincipal(self.user_id, self.tenant_id, self.user_id, "sales_agent"),
            scope=self.scope(), idempotency_key=self.suffix,
            source=MemorySource("postgres-test", self.suffix),
            observations=[MemoryObservation("generic", {"value": 1})],
        )
        first = system.submit(request)
        second = system.submit(request)
        self.assertEqual(first.event_id, second.event_id)
        claimed = self.repository.claim_events("worker-test", 10, 30)
        self.assertEqual([first.event_id], [event.event_id for event in claimed])
        self.assertEqual(MemoryEventStatus.PROCESSING, claimed[0].status)

    def test_postgres_expired_lease_can_be_reclaimed(self):
        system = build_memory_system(
            repository=self.repository,
            extractor=StructuredMemoryExtractor(),
            embedding_service=TestEmbeddingService(dimension=self.DIMENSION),
            text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
            async_mode=False,
        )
        request = MemorySubmitRequest(
            principal=MemoryPrincipal(self.user_id, self.tenant_id, self.user_id, "sales_agent"),
            scope=self.scope(), idempotency_key=self.suffix,
            source=MemorySource("lease-test", self.suffix),
            observations=[MemoryObservation("generic", {"value": 1})],
        )
        response = system.submit(request)
        first = self.repository.claim_events("worker-a", 1, 1)[0]
        with self.repository.connection_factory(register_types=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE memory_events SET lease_until=now()-interval '1 second' "
                    "WHERE event_id=%s", (response.event_id,)
                )
        reclaimed = self.repository.claim_events("worker-b", 1, 30)
        self.assertEqual(response.event_id, reclaimed[0].event_id)
        self.assertEqual("worker-b", reclaimed[0].locked_by)

    def test_event_create_query_and_status_update(self):
        event = MemoryEvent(
            trace_id=self.suffix, task_id=self.suffix, agent_id="sales_agent",
            user_id=self.user_id, tenant_id=self.tenant_id,
            department_id="test", source_kind="test", source_id=self.suffix,
            idempotency_key=self.suffix,
            observations=[MemoryObservation("test_input", {"query": "customer"})],
            metadata={},
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

        versions = self.repository.list_versions(self.scope(), self.identity())
        self.assertEqual([1, 2, 3], [item.version for item in versions])
        self.assertEqual(MemoryItemStatus.REPLACED, versions[0].status)
        self.assertEqual(second.id, versions[0].replaced_by_id)
        self.assertEqual(
            {"REPLACES", "DERIVED_FROM", "MERGED_FROM", "CONFLICT_WITH"},
            {relation["relation_type"] for relation in self.repository.list_relations()},
        )

    def test_department_is_part_of_version_scope(self):
        identity = self.identity(attribute="department_budget")
        department_a = self.scope("department-a")
        department_b = self.scope("department-b")
        first = self.make_item(
            identity.memory_key, {"amount": 100}, self.vector(0),
            department_id=department_a.department_id,
        )
        second = self.make_item(
            identity.memory_key, {"amount": 200}, self.vector(1),
            department_id=department_b.department_id,
        )
        self.repository.create_item(first)
        self.repository.create_item(second)
        self.assertEqual(
            {"amount": 100},
            self.repository.find_active_head(department_a, identity).content,
        )
        self.assertEqual(
            {"amount": 200},
            self.repository.find_active_head(department_b, identity).content,
        )

    def test_database_rejects_second_active_head(self):
        identity = self.identity(attribute="active_unique")
        first = self.make_item(identity.memory_key, 100, self.vector(0))
        second = self.make_item(
            identity.memory_key, 120, self.vector(1), version=2
        )
        self.repository.create_item(first)
        with self.assertRaises(UniqueViolation):
            self.repository.create_item(second)

    def test_concurrent_commits_allocate_unique_versions_and_one_active_head(self):
        identity = self.identity(attribute="concurrent_budget")
        scope = self.scope()
        barrier = Barrier(2)
        errors = []
        committed = []
        result_lock = Lock()

        def commit(amount, vector_index):
            item = self.make_item(
                identity.memory_key, amount, self.vector(vector_index)
            )
            try:
                active = self.repository.find_active_head(scope, identity)
                barrier.wait(timeout=5)
                for _ in range(3):
                    relations = (
                        [(active.id, "REPLACES")] if active is not None else []
                    )
                    try:
                        self.repository.commit_resolution(
                            item,
                            expected_active_head_id=(active.id if active else None),
                            relations=relations,
                        )
                        with result_lock:
                            committed.append(item.id)
                        return
                    except ConcurrentMemoryWrite:
                        active = self.repository.find_active_head(scope, identity)
                raise AssertionError("concurrent commit did not stabilize")
            except Exception as error:
                with result_lock:
                    errors.append(error)

        threads = [
            Thread(target=commit, args=(100, 0)),
            Thread(target=commit, args=(120, 1)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(errors)
        self.assertEqual(2, len(committed))
        versions = self.repository.list_versions(scope, identity)
        self.assertEqual([1, 2], [item.version for item in versions])
        self.assertEqual({100, 120}, {item.content for item in versions})
        self.assertEqual(1, sum(
            item.status == MemoryItemStatus.ACTIVE for item in versions
        ))

    def test_sql_retrieve_writes_access_log_without_realtime_counter(self):
        item = self.make_item(
            f"customer:{self.suffix}:industry", "新能源", self.vector(0)
        )
        self.repository.create_item(item)
        system = build_memory_system(
            repository=self.repository,
            extractor=StructuredMemoryExtractor(), async_mode=False,
            embedding_service=TestEmbeddingService(dimension=self.DIMENSION),
            text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
        )
        with redirect_stdout(StringIO()):
            context = system.retrieve(self.retrieve_request("industry"))
        self.assertEqual([item.id], [reference.memory_id for reference in context.references])
        self.assertEqual(0, self.repository.get_item(item.id).access_count)
        with self.repository.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT query FROM memory_access_logs WHERE memory_id=%s", (item.id,)
                )
                self.assertEqual("industry", cursor.fetchone()[0])

    def test_write_pipeline_persists_embedding_metadata(self):
        system = build_memory_system(
            repository=self.repository,
            extractor=StructuredMemoryExtractor(), async_mode=False,
            embedding_service=TestEmbeddingService(dimension=self.DIMENSION),
            text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
        )
        request = MemorySubmitRequest(
            principal=MemoryPrincipal(
                self.user_id, self.tenant_id, self.user_id, "sales_agent"
            ),
            scope=self.scope(), idempotency_key=self.suffix,
            source=MemorySource("test", self.suffix),
            observations=[MemoryObservation("test_input", {})], trace_id=self.suffix,
            metadata={"memory_candidates": [{
                "type": "customer", "entity_id": self.suffix,
                "attribute": "semantic", "content": "customer semantic fact",
                "confidence": 0.9, "business_value": 0.9, "stability": 0.9,
                "explicitness": 0.9, "future_usefulness": 0.9,
            }]},
        )
        with redirect_stdout(StringIO()):
            system.submit(request)
            system._worker.process_once()
        stored = self.repository.find_active_head(
            self.scope(), self.identity(attribute="semantic")
        )
        self.assertEqual(self.vector(0), stored.embedding)
        self.assertEqual("test-embedding", stored.embedding_model)
        self.assertEqual("test", stored.embedding_version)
        self.assertEqual(self.DIMENSION, stored.embedding_dimension)
        self.assertEqual(
            TestEmbeddingService(dimension=self.DIMENSION).space.space_id,
            stored.embedding_space_id,
        )

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
            embedding_space_id=self.TEST_SPACE_ID,
        )
        self.assertEqual(close.id, results[0][0].id)
        self.assertGreater(results[0][1], results[1][1])
        self.assertGreater(results[0][1], 0.99)

    def test_vector_search_does_not_mix_same_dimension_spaces(self):
        identity = self.identity(attribute="space_isolation")
        other_space = EmbeddingSpace("openai", "same-dimension", "v2", self.DIMENSION)
        current = self.make_item(identity.memory_key, "current", self.vector(0))
        other_identity = self.identity(attribute="other_space_fact")
        legacy_space = self.make_item(
            other_identity.memory_key, "other", self.vector(0),
            space_id=other_space.space_id,
        )
        self.repository.create_item(current)
        self.repository.create_item(legacy_space)
        results = self.repository.search_vector(
            self.retrieve_request(query="space", limit=10),
            self.vector(0), self.TEST_SPACE_ID,
        )
        self.assertEqual([current.id], [item.id for item, _ in results])

    def test_durable_event_survives_memory_system_restart(self):
        request = MemorySubmitRequest(
            principal=MemoryPrincipal(self.user_id, self.tenant_id, self.user_id, "sales_agent"),
            scope=self.scope(), idempotency_key=self.suffix,
            source=MemorySource("restart-test", self.suffix),
            observations=[MemoryObservation("customer_fact", "新能源")],
            metadata={"memory_candidates": [{
                "type": "customer", "entity_id": self.suffix, "attribute": "industry",
                "content": "新能源", "confidence": 0.9, "business_value": 0.9,
                "stability": 0.9, "explicitness": 0.9, "future_usefulness": 0.9,
            }]},
        )
        first = build_memory_system(
            repository=self.repository, extractor=StructuredMemoryExtractor(),
            embedding_service=TestEmbeddingService(dimension=self.DIMENSION),
            text_model=StubLLM(), authorization_provider=AllowAllMemoryAuthorizationProvider(),
            async_mode=False,
        )
        response = first.submit(request)
        second = build_memory_system(
            repository=self.repository, extractor=StructuredMemoryExtractor(),
            embedding_service=TestEmbeddingService(dimension=self.DIMENSION),
            text_model=StubLLM(), authorization_provider=AllowAllMemoryAuthorizationProvider(),
            async_mode=False,
        )
        second._worker.process_once()
        self.assertEqual(MemoryEventStatus.PROCESSED, self.repository.get_event(response.event_id).status)


if __name__ == "__main__":
    unittest.main()
