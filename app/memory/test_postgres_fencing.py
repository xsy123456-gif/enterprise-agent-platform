"""PostgreSQL integration tests for Group-1 correctness guarantees.

Requires MEMORY_TEST_DATABASE_URL env var pointing to a real PostgreSQL 16+
instance with pgvector extension.

Run:  MEMORY_TEST_DATABASE_URL=postgresql://... python -m pytest tests/memory/integration/ -v
"""

import os
import uuid
import unittest
from datetime import datetime, timedelta, timezone
from threading import Barrier, Lock, Thread

from app.memory.api.models import (
    MemoryObservation, MemoryPrincipal, MemoryRetrieveRequest, MemorySource,
    MemorySubmitRequest,
)
from app.memory.embedding.models import EmbeddingSpace
from app.memory.errors import ConcurrentMemoryWrite
from app.memory.events import MemoryDomainEvent
from app.memory.factory import build_memory_system
from app.memory.models.event import MemoryEvent, MemoryEventStatus
from app.memory.models.identity import MemoryIdentity
from app.memory.models.item import MemoryItem, MemoryItemStatus
from app.memory.models.scope import MemoryScope
from app.memory.pipeline.write.extractor import StructuredMemoryExtractor
from app.memory.ports.authorization import AllowAllMemoryAuthorizationProvider
from app.memory.storage.postgres import create_postgres_repository
from app.memory.test_repository import TestEmbeddingService


@unittest.skipUnless(
    os.getenv("MEMORY_TEST_DATABASE_URL"),
    "MEMORY_TEST_DATABASE_URL is not configured",
)
class MemoryIntegrationTest(unittest.TestCase):
    DIMENSION = int(os.getenv("MEMORY_TEST_EMBEDDING_DIMENSION", "1024"))

    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["MEMORY_TEST_DATABASE_URL"]
        cls.repository = create_postgres_repository(
            cls.dsn, embedding_dimension=cls.DIMENSION, initialize=True,
        )

    def setUp(self):
        self.suffix = uuid.uuid4().hex
        self.user_id = f"mit-{self.suffix}"
        self.tenant_id = f"mit-{self.suffix}"

    def tearDown(self):
        with self.repository.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM memory_access_logs WHERE user_id=%s", (self.user_id,))
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
                cursor.execute("DELETE FROM memory_outbox WHERE aggregate_id LIKE %s",
                               (f"%{self.user_id}%",))
                cursor.execute("DELETE FROM memory_events WHERE user_id=%s", (self.user_id,))

    def scope(self):
        return MemoryScope(self.tenant_id, self.user_id, "agent-1")

    # ── Concurrent claim ──────────────────────────────────────────

    def test_two_workers_concurrent_claim_get_different_events(self):
        ev1 = MemoryEvent(
            trace_id=self.suffix, task_id="t1", agent_id="a", user_id=self.user_id,
            tenant_id=self.tenant_id, department_id=None, source_kind="test",
            source_id=f"{self.suffix}-1", idempotency_key=f"{self.suffix}-1",
            observations=[MemoryObservation("x", "y")], metadata={},
        )
        ev2 = MemoryEvent(
            trace_id=self.suffix, task_id="t2", agent_id="a", user_id=self.user_id,
            tenant_id=self.tenant_id, department_id=None, source_kind="test",
            source_id=f"{self.suffix}-2", idempotency_key=f"{self.suffix}-2",
            observations=[MemoryObservation("x", "y")], metadata={},
        )
        self.repository.save_event(ev1)
        self.repository.save_event(ev2)
        w1 = self.repository.claim_events("w-A", 1, 30)
        w2 = self.repository.claim_events("w-B", 1, 30)
        self.assertEqual(1, len(w1))
        self.assertEqual(1, len(w2))
        self.assertNotEqual(w1[0].event_id, w2[0].event_id)
        self.assertNotEqual(w1[0].lock_token, w2[0].lock_token)

    # ── Stale worker token rejected ───────────────────────────────

    def test_stale_worker_token_rejected(self):
        ev = MemoryEvent(
            trace_id=self.suffix, task_id="t", agent_id="a", user_id=self.user_id,
            tenant_id=self.tenant_id, department_id=None, source_kind="test",
            source_id=f"{self.suffix}-stale", idempotency_key=f"{self.suffix}-stale",
            observations=[MemoryObservation("x", "y")], metadata={},
        )
        self.repository.save_event(ev)
        claimed = self.repository.claim_events("w-A", 1, 30)
        self.assertEqual(1, len(claimed))
        ev = claimed[0]
        ev.status = "processed"
        ev.processed_at = datetime.now(timezone.utc)
        with self.assertRaises(ConcurrentMemoryWrite):
            self.repository.commit_event_result(ev, "w-B", [], ev.lock_token)

    # ── Expired lease commit rejected ─────────────────────────────

    def test_expired_lease_commit_rejected(self):
        ev = MemoryEvent(
            trace_id=self.suffix, task_id="t", agent_id="a", user_id=self.user_id,
            tenant_id=self.tenant_id, department_id=None, source_kind="test",
            source_id=f"{self.suffix}-exp", idempotency_key=f"{self.suffix}-exp",
            observations=[MemoryObservation("x", "y")], metadata={},
        )
        self.repository.save_event(ev)
        claimed = self.repository.claim_events("w-A", 1, 2)
        ev = claimed[0]
        with self.repository.connection_factory(register_types=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE memory_events SET lease_until=now()-interval '1 second' "
                    "WHERE event_id=%s", (ev.event_id,)
                )
        ev.status = "processed"
        ev.processed_at = datetime.now(timezone.utc)
        with self.assertRaises(ConcurrentMemoryWrite):
            self.repository.commit_event_result(ev, "w-A", [], ev.lock_token)

    # ── Lease renewal ─────────────────────────────────────────────

    def test_lease_renewal(self):
        ev = MemoryEvent(
            trace_id=self.suffix, task_id="t", agent_id="a", user_id=self.user_id,
            tenant_id=self.tenant_id, department_id=None, source_kind="test",
            source_id=f"{self.suffix}-rnw", idempotency_key=f"{self.suffix}-rnw",
            observations=[MemoryObservation("x", "y")], metadata={},
        )
        self.repository.save_event(ev)
        claimed = self.repository.claim_events("w-A", 1, 30)
        ev = claimed[0]
        ok = self.repository.renew_lease(ev.event_id, "w-A", ev.lock_token, 30)
        self.assertTrue(ok)
        ok_bad = self.repository.renew_lease(ev.event_id, "w-B", ev.lock_token, 30)
        self.assertFalse(ok_bad)

    # ── PROCESSING CHECK constraint ───────────────────────────────

    def test_processing_check_not_null(self):
        ev = MemoryEvent(
            trace_id=self.suffix, task_id="t", agent_id="a", user_id=self.user_id,
            tenant_id=self.tenant_id, department_id=None, source_kind="test",
            source_id=f"{self.suffix}-chk", idempotency_key=f"{self.suffix}-chk",
            observations=[MemoryObservation("x", "y")], metadata={},
        )
        self.repository.save_event(ev)
        with self.repository.connection_factory(register_types=False) as connection:
            with connection.cursor() as cursor:
                with self.assertRaises(Exception):
                    cursor.execute(
                        "UPDATE memory_events SET status='processing', "
                        "locked_by=NULL, lock_token='tok', lease_until=now() "
                        "WHERE event_id=%s", (ev.event_id,),
                    )

    # ── RETRY_WAIT CHECK constraint ───────────────────────────────

    def test_retry_wait_check_not_null(self):
        ev = MemoryEvent(
            trace_id=self.suffix, task_id="t", agent_id="a", user_id=self.user_id,
            tenant_id=self.tenant_id, department_id=None, source_kind="test",
            source_id=f"{self.suffix}-rwchk", idempotency_key=f"{self.suffix}-rwchk",
            observations=[MemoryObservation("x", "y")], metadata={},
        )
        self.repository.save_event(ev)
        claimed = self.repository.claim_events("w-A", 1, 30)
        ev = claimed[0]
        ev.status = "retry_wait"
        ev.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=60)
        ev.error = "err"
        ev.error_code = "code"
        self.repository.commit_event_result(ev, "w-A", [], ev.lock_token)
        stored = self.repository.get_event(ev.event_id)
        self.assertEqual("retry_wait", stored.status)
        self.assertIsNotNone(stored.next_attempt_at)

    # ── Transaction rollback ──────────────────────────────────────

    def test_rollback_on_mutation_failure(self):
        system = build_memory_system(
            repository=self.repository,
            extractor=StructuredMemoryExtractor(),
            embedding_service=TestEmbeddingService(dimension=self.DIMENSION),
            text_model=type("L", (), {"chat": lambda s, m, **kw: "compressed"})(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
            async_mode=False,
        )
        scope = self.scope()
        identity = MemoryIdentity("customer", f"{self.suffix}-rb", "name")
        request = MemorySubmitRequest(
            principal=MemoryPrincipal(self.user_id, self.tenant_id, self.user_id, "agent-1"),
            scope=scope, idempotency_key=f"{self.suffix}-rb",
            source=MemorySource("test", f"{self.suffix}-rb"),
            observations=[MemoryObservation("fact", "x")],
            metadata={"memory_candidates": [
                {"type": "customer", "entity_id": f"{self.suffix}-rb",
                 "attribute": "name", "content": "A", "confidence": 0.9,
                 "business_value": 0.9, "stability": 0.9,
                 "explicitness": 0.9, "future_usefulness": 0.9},
                {"type": "customer", "entity_id": "bad", "attribute": "name",
                 "content": {}, "confidence": 0.9,  # will fail — no content
                 "business_value": 0.9, "stability": 0.9,
                 "explicitness": 0.9, "future_usefulness": 0.9},
            ]},
        )
        response = system.write(request)
        system._worker.process_once()
        ev = self.repository.get_event(response.event_id)
        self.assertEqual(MemoryEventStatus.RETRY_WAIT, ev.status)
        items = self.repository.list_versions(scope, identity)
        self.assertEqual(0, len(items), "rollback: no items persisted on failure")

    # ── Memory + Inbox + Outbox atomic commit ─────────────────────

    def test_memory_inbox_outbox_atomic_commit(self):
        system = build_memory_system(
            repository=self.repository,
            extractor=StructuredMemoryExtractor(),
            embedding_service=TestEmbeddingService(dimension=self.DIMENSION),
            text_model=type("L", (), {"chat": lambda s, m, **kw: "compressed"})(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
            async_mode=False,
        )
        scope = self.scope()
        request = MemorySubmitRequest(
            principal=MemoryPrincipal(self.user_id, self.tenant_id, self.user_id, "agent-1"),
            scope=scope, idempotency_key=f"{self.suffix}-atom",
            source=MemorySource("test", f"{self.suffix}-atom"),
            observations=[MemoryObservation("fact", "atomic-test")],
            metadata={"memory_candidates": [{
                "type": "customer", "entity_id": f"{self.suffix}-atom",
                "attribute": "budget", "content": "atomic", "confidence": 0.9,
                "business_value": 0.9, "stability": 0.9,
                "explicitness": 0.9, "future_usefulness": 0.9,
            }]},
        )
        response = system.write(request)
        system._worker.process_once()
        ev = self.repository.get_event(response.event_id)
        self.assertEqual(MemoryEventStatus.PROCESSED, ev.status)

        identity = MemoryIdentity("customer", f"{self.suffix}-atom", "budget")
        items = self.repository.list_versions(scope, identity)
        self.assertEqual(1, len(items), "Memory item persisted")
        self.assertEqual("atomic", items[0].content)

        with self.repository.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM memory_outbox "
                    "WHERE aggregate_id=%s", (response.event_id,)
                )
                count = cursor.fetchone()[0]
        self.assertGreaterEqual(count, 1,
                                "at least one outbox event for the inbox event")

    # ── Two publishers concurrent claim ───────────────────────────

    def test_two_publishers_concurrent_claim(self):
        de1 = MemoryDomainEvent(event_id=f"ob-{self.suffix}-1", event_type="t1",
                                aggregate_id=f"agg-{self.suffix}", payload={})
        de2 = MemoryDomainEvent(event_id=f"ob-{self.suffix}-2", event_type="t2",
                                aggregate_id=f"agg-{self.suffix}", payload={})
        self.repository.add_outbox(de1)
        self.repository.add_outbox(de2)
        p1 = self.repository.claim_outbox(1, "pub-A", 30)
        p2 = self.repository.claim_outbox(1, "pub-B", 30)
        self.assertEqual(1, len(p1))
        self.assertEqual(1, len(p2))
        ids = {p1[0]["id"], p2[0]["id"]}
        self.assertEqual(2, len(ids), "publishers got different records")

    # ── Expired outbox reclaim ────────────────────────────────────

    def test_expired_outbox_reclaim(self):
        de = MemoryDomainEvent(
            event_id=f"ob-{self.suffix}-exp", event_type="t",
            aggregate_id=f"agg-{self.suffix}", payload={},
        )
        self.repository.add_outbox(de)
        first = self.repository.claim_outbox(1, "pub-old", 1)
        old_token = first[0]["lock_token"]
        old_owner = first[0]["locked_by"]
        old_id = first[0]["id"]
        with self.repository.connection_factory(register_types=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE memory_outbox SET lease_until=now()-interval '1 second' "
                    "WHERE id=%s", (old_id,)
                )
        reclaimed = self.repository.claim_outbox(1, "pub-new", 30)
        self.assertEqual(1, len(reclaimed))
        self.assertEqual(old_id, reclaimed[0]["id"])
        self.assertEqual("pub-new", reclaimed[0]["locked_by"])
        self.assertNotEqual(old_owner, reclaimed[0]["locked_by"])
        self.assertNotEqual(old_token, reclaimed[0]["lock_token"])

    # ── Stale publisher finalize rejected ─────────────────────────

    def test_stale_publisher_mark_published_rejected(self):
        de = MemoryDomainEvent(
            event_id=f"ob-{self.suffix}-cas", event_type="t",
            aggregate_id=f"agg-{self.suffix}", payload={},
        )
        self.repository.add_outbox(de)
        claimed = self.repository.claim_outbox(1, "pub-A", 30)
        lock_token = claimed[0]["lock_token"]
        with self.assertRaises(ConcurrentMemoryWrite):
            self.repository.mark_outbox_published(
                f"ob-{self.suffix}-cas", "pub-B", lock_token,
            )

    def test_stale_publisher_retry_rejected(self):
        de = MemoryDomainEvent(
            event_id=f"ob-{self.suffix}-retry-cas", event_type="t",
            aggregate_id=f"agg-{self.suffix}", payload={},
        )
        self.repository.add_outbox(de)
        claimed = self.repository.claim_outbox(1, "pub-A", 30)
        lock_token = claimed[0]["lock_token"]
        with self.assertRaises(ConcurrentMemoryWrite):
            self.repository.retry_outbox(
                f"ob-{self.suffix}-retry-cas", "err",
                datetime.now(timezone.utc), "pub-A", "wrong-token",
            )

    def test_stale_publisher_dead_letter_rejected(self):
        de = MemoryDomainEvent(
            event_id=f"ob-{self.suffix}-dl-cas", event_type="t",
            aggregate_id=f"agg-{self.suffix}", payload={},
        )
        self.repository.add_outbox(de)
        claimed = self.repository.claim_outbox(1, "pub-A", 30)
        with self.assertRaises(ConcurrentMemoryWrite):
            self.repository.dead_letter_outbox(
                f"ob-{self.suffix}-dl-cas", "fatal", "pub-B", "wrong-token",
            )


if __name__ == "__main__":
    unittest.main()
