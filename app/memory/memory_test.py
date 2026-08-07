"""Group-1 remaining corrections verification — self-contained seal test.

No dependency on tests.memory_repository — the in-memory test double is
defined inline so the test can live inside the memory package.

Real PostgreSQL tests (CHECK, lease fencing, outbox fencing) live in
tests/memory/integration/.
"""

import json
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from app.memory.api.models import (
    MemoryObservation, MemoryPrincipal, MemoryRetrieveRequest, MemorySource,
    MemorySubmitRequest,
)
from app.memory.errors import ConcurrentMemoryWrite, MemoryError
from app.memory.factory import build_memory_system
from app.memory.models.event import MemoryEventStatus
from app.memory.models.scope import MemoryScope
from app.memory.pipeline.write.extractor import MemoryCandidate, StructuredMemoryExtractor
from app.memory.ports.authorization import AllowAllMemoryAuthorizationProvider


# ── self-contained in-memory repository (no external test dependency) ──

class _InMemoryRepository:
    """Row state tracked independently of Python event/outbox objects."""

    def __init__(self):
        self.embedding_dimension = 3
        self.events = {}
        self._event_state = {}
        self.items = {}
        self.relations = []
        self.access_logs = []
        self.outbox = {}
        self._tx_active = False
        self._tx_snapshot = None

    def _es(self, event_id):
        return self._event_state.setdefault(event_id, {})

    @contextmanager
    def atomic_write(self):
        if self._tx_active:
            yield
            return
        self._tx_active = True
        import copy
        self._tx_snapshot = (copy.deepcopy(self.items), copy.deepcopy(self.relations))
        try:
            yield
        except Exception as exc:
            self.items, self.relations = self._tx_snapshot
            if isinstance(exc, MemoryError):
                raise
            from app.memory.errors import MemoryStorageError
            raise MemoryStorageError(
                f"Repository atomic write failed: {exc}"
            ) from exc
        finally:
            self._tx_active = False
            self._tx_snapshot = None

    def save_event(self, event):
        for stored in self.events.values():
            if getattr(stored, "idempotency_key", None) == getattr(event, "idempotency_key", None) and \
               getattr(stored, "idempotency_key", None) is not None:
                return stored
        self.events[event.event_id] = event
        st = self._es(event.event_id)
        st["status"] = event.status
        return event

    def get_event(self, event_id):
        return self.events.get(event_id)

    def update_event(self, event):
        self.events[event.event_id] = event
        st = self._es(event.event_id)
        st["status"] = event.status
        return event

    def claim_events(self, worker_id, limit, lease_seconds):
        import uuid
        now = datetime.now(timezone.utc)
        claimed = []
        for event in list(self.events.values()):
            st = self._es(event.event_id)
            status = st.get("status", event.status)
            claimable = status in {"received", "retry_wait"} and (
                event.next_attempt_at is None or event.next_attempt_at <= now
            )
            expired = (
                status == "processing"
                and st.get("lease_until")
                and st["lease_until"] <= now
            )
            if (claimable or expired) and len(claimed) < limit:
                st["status"] = "processing"
                st["locked_by"] = worker_id
                st["lock_token"] = str(uuid.uuid4())
                st["lease_until"] = now + timedelta(seconds=lease_seconds)
                event.status = "processing"
                event.locked_by = worker_id
                event.lock_token = st["lock_token"]
                event.lease_until = st["lease_until"]
                event.attempt_count += 1
                event.error = None
                event.error_code = None
                claimed.append(event)
        return claimed

    def renew_lease(self, event_id, worker_id, lock_token, lease_seconds):
        st = self._es(event_id)
        if (
            st.get("status") == "processing"
            and st.get("locked_by") == worker_id
            and st.get("lock_token") == lock_token
            and st.get("lease_until")
            and st["lease_until"] > datetime.now(timezone.utc)
        ):
            st["lease_until"] = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
            event = self.events.get(event_id)
            if event:
                event.lease_until = st["lease_until"]
            return True
        return False

    def commit_event_result(self, event, worker_id, domain_events, lock_token):
        st = self._es(event.event_id)
        if not self.events.get(event.event_id):
            raise ConcurrentMemoryWrite("event not found")
        if (st.get("status") != "processing"
                or st.get("locked_by") != worker_id
                or st.get("lock_token") != lock_token
                or not st.get("lease_until")
                or st["lease_until"] <= datetime.now(timezone.utc)):
            raise ConcurrentMemoryWrite("ownership lost")
        status = event.status
        if status == "processed":
            event.error = None
            event.error_code = None
            event.next_attempt_at = None
        st["status"] = status
        st.pop("locked_by", None)
        st.pop("lock_token", None)
        st.pop("lease_until", None)
        event.locked_by = None
        event.lease_until = None
        event.lock_token = None
        return self.finalize_event(event, domain_events)

    def finalize_event(self, event, domain_events):
        self.update_event(event)
        for de in domain_events:
            self.add_outbox(de)

    def add_outbox(self, event):
        self.outbox.setdefault(event.event_id, {
            "id": event.event_id, "event_type": event.event_type,
            "aggregate_id": event.aggregate_id, "payload": event.payload,
            "status": "pending", "attempt_count": 0,
            "lock_token": None, "locked_by": None, "lease_until": None,
        })

    def claim_outbox(self, limit, worker_id=None, lease_seconds=30):
        import uuid
        now = datetime.now(timezone.utc)
        claimed = []
        for item in list(self.outbox.values()):
            claimable = item["status"] == "pending"
            expired = (
                item["status"] == "processing"
                and item.get("lease_until")
                and item["lease_until"] <= now
            )
            if (claimable or expired) and len(claimed) < limit:
                item["status"] = "processing"
                item["locked_by"] = worker_id
                item["lock_token"] = str(uuid.uuid4())
                item["lease_until"] = now + timedelta(seconds=lease_seconds)
                item["attempt_count"] += 1
                claimed.append(item)
        return claimed

    def mark_outbox_published(self, outbox_id, worker_id, lock_token):
        item = self.outbox.get(outbox_id)
        if not item:
            raise ConcurrentMemoryWrite("Outbox CAS mark_published: record not found")
        if (item["status"] != "processing"
                or item.get("locked_by") != worker_id
                or item.get("lock_token") != lock_token
                or not item.get("lease_until")
                or item["lease_until"] <= datetime.now(timezone.utc)):
            raise ConcurrentMemoryWrite("Outbox CAS mark_published: ownership lost")
        item["status"] = "published"
        return True

    def retry_outbox(self, outbox_id, error, next_attempt_at, worker_id, lock_token):
        item = self.outbox.get(outbox_id)
        if not item:
            raise ConcurrentMemoryWrite("Outbox CAS retry: record not found")
        if (item["status"] != "processing"
                or item.get("locked_by") != worker_id
                or item.get("lock_token") != lock_token
                or not item.get("lease_until")
                or item["lease_until"] <= datetime.now(timezone.utc)):
            raise ConcurrentMemoryWrite("Outbox CAS retry: ownership lost")
        item["status"] = "pending"
        item["last_error"] = error
        item["available_at"] = next_attempt_at
        return True

    def dead_letter_outbox(self, outbox_id, error, worker_id, lock_token):
        item = self.outbox.get(outbox_id)
        if not item:
            raise ConcurrentMemoryWrite("Outbox CAS dead_letter: record not found")
        if (item["status"] != "processing"
                or item.get("locked_by") != worker_id
                or item.get("lock_token") != lock_token
                or not item.get("lease_until")
                or item["lease_until"] <= datetime.now(timezone.utc)):
            raise ConcurrentMemoryWrite("Outbox CAS dead_letter: ownership lost")
        item["status"] = "dead_letter"
        item["last_error"] = error
        return True

    def create_item(self, item, relations=None):
        self.items[item.id] = item
        for target_id, relation_type in relations or []:
            self.create_relation(item.id, target_id, relation_type)
        return item

    def commit_resolution(self, item, expected_active_head_id, relations=None):
        current = self.find_active_head(item.scope, item.identity)
        current_id = current.id if current else None
        if current_id != expected_active_head_id:
            raise ConcurrentMemoryWrite("ACTIVE head changed")
        item.version = self.get_latest_version(item.scope, item.identity) + 1
        return self.create_item(item, relations=relations)

    def merge_observation(self, item, evaluation):
        stored = self.items.get(item.id)
        if not stored:
            raise ConcurrentMemoryWrite("item gone")
        stored.observation_count += 1
        stored.last_observed_at = datetime.now(timezone.utc)
        stored.updated_at = datetime.now(timezone.utc)
        stored.confidence = max(stored.confidence, evaluation.confidence)
        stored.importance = max(stored.importance, evaluation.importance)
        return stored

    def find_active_head(self, scope, identity):
        for item in self.items.values():
            if (item.scope == scope and item.identity == identity
                    and item.status == "active"):
                return item
        return None

    def get_latest_version(self, scope, identity):
        versions = [item.version for item in self.items.values()
                     if item.scope == scope and item.identity == identity]
        return max(versions, default=0)

    def get_item(self, memory_id):
        return self.items.get(memory_id)

    def search(self, request, query_embedding=None, embedding_space_id=None):
        candidates = []
        for item in self.items.values():
            if item.status != "active" or item.tenant_id != request.scope.tenant_id:
                continue
            if item.user_id != request.scope.user_id or item.agent_id != request.scope.agent_id:
                continue
            if request.types and item.type not in request.types:
                continue
            text = f"{item.memory_key} {json.dumps(item.content, ensure_ascii=False)}".lower()
            query_lower = request.query.lower().strip()
            if not query_lower:
                candidates.append((item, 1.0))
                continue
            keywords = [k.lower() for k in request.query.split() if k.strip()]
            if not keywords:
                keywords = [query_lower]
            score = sum(k in text for k in keywords) / len(keywords)
            if score == 0:
                import re
                cjk_bigrams = re.findall(r"[\u4e00-\u9fff]{2}", query_lower)
                if cjk_bigrams:
                    cjk_hits = sum(b in text for b in cjk_bigrams)
                    score = cjk_hits / max(1, len(cjk_bigrams))
            if score > 0:
                candidates.append((item, score))
        return candidates

    search_sql = search
    search_vector = search
    link_replacement = lambda *a: None

    def create_relation(self, source_id, target_id, relation_type):
        self.relations.append({
            "source_id": source_id, "target_id": target_id,
            "relation_type": relation_type,
        })

    list_relations = lambda *a, **kw: []
    list_versions = lambda self, scope, identity: sorted([
        i for i in self.items.values()
        if i.scope == scope and i.identity == identity
    ], key=lambda i: i.version)

    def record_access(self, memory_id, request):
        self.access_logs.append({"memory_id": memory_id})
        item = self.items.get(memory_id)
        if item:
            item.access_count += 1
            item.last_accessed_at = datetime.now(timezone.utc)

    def update_processing_task(self, event_id, stage, status, error=None):
        pass


class _InMemoryEmbeddingService:
    def __init__(self, dimension=3):
        self.dimension = dimension
        self.space = type("Space", (), {"space_id": "test", "provider": "test",
                         "model": "test", "version": "test"})()
        self._idx = 0

    def embed(self, text):
        vector = [0.0] * self.dimension
        self._idx = (self._idx + 1) % self.dimension
        vector[self._idx] = 1.0
        return type("Result", (), {
            "vector": vector, "space": self.space,
            "provider": "test", "model": "test",
            "version": "test", "dimension": self.dimension,
            "space_id": "test",
        })()


class StubLLM:
    def chat(self, messages, **kwargs):
        return "compressed memory context"


# ── Seal test: write("张三是工程师") → worker → read → assert "工程师" ──

class MemorySealTest(unittest.TestCase):

    def test_write_chinese_fact_and_read_it_back(self):
        repo = _InMemoryRepository()
        system = build_memory_system(
            repository=repo,
            embedding_service=_InMemoryEmbeddingService(),
            extractor=StructuredMemoryExtractor(),
            text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
            async_mode=False,
        )
        principal = MemoryPrincipal("user-1", "tenant-1", "user-1", "agent-1")
        scope = MemoryScope("tenant-1", "user-1", "agent-1")

        write_request = MemorySubmitRequest(
            principal=principal, scope=scope,
            idempotency_key="seal-1",
            source=MemorySource("test", "seal-1"),
            observations=[MemoryObservation("fact", "张三是工程师")],
            metadata={"memory_candidates": [{
                "type": "person", "entity_id": "张三", "attribute": "职业",
                "content": "工程师", "confidence": 0.9,
                "business_value": 0.9, "stability": 0.9,
                "explicitness": 1.0, "future_usefulness": 0.9,
            }]},
        )
        response = system.write(write_request)
        self.assertTrue(response.accepted)

        system._worker.process_once()
        event = repo.get_event(response.event_id)
        self.assertEqual("processed", event.status)
        self.assertIsNotNone(event.processed_at)
        self.assertIsNone(event.error)
        self.assertIsNone(event.next_attempt_at)

        # Verify Memory item was persisted with correct content
        self.assertGreaterEqual(len(repo.items), 1)
        found = False
        for item in repo.items.values():
            content_str = json.dumps(item.content, ensure_ascii=False)
            if "工程师" in content_str and item.type == "person":
                self.assertEqual("person", item.type)
                self.assertEqual("person:张三:职业", item.memory_key)
                found = True
                break
        self.assertTrue(found, "seal test: expected persisted Memory item with 工程师")

        # Read back via the pipeline with natural Chinese query
        read_request = MemoryRetrieveRequest(
            principal=principal, scope=scope,
            query="张三的职业是什么？", types=["person"],
        )
        context = system.read(read_request) if hasattr(system, "read") else system.retrieve(read_request)
        self.assertIsNotNone(context.summary)
        records = getattr(context, "records", getattr(context, "references", []))
        self.assertGreaterEqual(len(records), 1,
                                "read back must find the persisted memory item")
        found_engineer = False
        for rec in records:
            content_str = json.dumps(rec.content, ensure_ascii=False) if rec.content is not None else ""
            if "工程师" in content_str:
                found_engineer = True
                break
        self.assertTrue(found_engineer,
                        "seal test: read('张三的职业是什么？') must find '工程师'")

    def test_processed_event_clears_error_and_next_attempt(self):
        repo = _InMemoryRepository()
        system = build_memory_system(
            repository=repo, embedding_service=_InMemoryEmbeddingService(),
            extractor=StructuredMemoryExtractor(), text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
            async_mode=False,
        )
        principal = MemoryPrincipal("u", "t", "u", "a")
        scope = MemoryScope("t", "u", "a")
        request = MemorySubmitRequest(
            principal=principal, scope=scope,
            idempotency_key="clr-1",
            source=MemorySource("test", "clr-1"),
            observations=[MemoryObservation("fact", "x")],
            metadata={"memory_candidates": [{
                "type": "fact", "entity_id": "e", "attribute": "a",
                "content": "x", "confidence": 0.9,
                "business_value": 0.9, "stability": 0.9,
                "explicitness": 1.0, "future_usefulness": 0.9,
            }]},
        )
        resp = system.write(request)
        system._worker.process_once()
        ev = repo.get_event(resp.event_id)
        self.assertEqual("processed", ev.status)
        self.assertIsNone(ev.error)
        self.assertIsNone(ev.error_code)
        self.assertIsNone(ev.next_attempt_at)

    def test_retry_wait_persists_error_and_next_attempt(self):
        repo = _InMemoryRepository()

        class FailingExtractor(StructuredMemoryExtractor):
            def extract(self, ev):
                raise TimeoutError("upstream timeout")

        system = build_memory_system(
            repository=repo, embedding_service=_InMemoryEmbeddingService(),
            extractor=FailingExtractor(), text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
            async_mode=False,
        )
        principal = MemoryPrincipal("u", "t", "u", "a")
        scope = MemoryScope("t", "u", "a")
        request = MemorySubmitRequest(
            principal=principal, scope=scope,
            idempotency_key="rw-1",
            source=MemorySource("test", "rw-1"),
            observations=[MemoryObservation("fact", "x")],
            metadata={"memory_candidates": [{
                "type": "fact", "entity_id": "e", "attribute": "a",
                "content": "x", "confidence": 0.9,
                "business_value": 0.9, "stability": 0.9,
                "explicitness": 1.0, "future_usefulness": 0.9,
            }]},
        )
        resp = system.write(request)
        system._worker.process_once()
        ev = repo.get_event(resp.event_id)
        self.assertEqual("retry_wait", ev.status)
        self.assertIsNotNone(ev.next_attempt_at)
        self.assertIsNotNone(ev.error)
        self.assertIsNotNone(ev.error_code)

    def test_rejected_persists_error_code_and_processed_at(self):
        repo = _InMemoryRepository()

        class DenyWriteAuth(AllowAllMemoryAuthorizationProvider):
            def authorize_write_candidate(self, p, s, ct):
                raise PermissionError("nope")

        system = build_memory_system(
            repository=repo, embedding_service=_InMemoryEmbeddingService(),
            extractor=StructuredMemoryExtractor(), text_model=StubLLM(),
            authorization_provider=DenyWriteAuth(), async_mode=False,
        )
        principal = MemoryPrincipal("u", "t", "u", "a")
        scope = MemoryScope("t", "u", "a")
        request = MemorySubmitRequest(
            principal=principal, scope=scope,
            idempotency_key="rj-1",
            source=MemorySource("test", "rj-1"),
            observations=[MemoryObservation("fact", "x")],
            metadata={"memory_candidates": [{
                "type": "fact", "entity_id": "e", "attribute": "a",
                "content": "x", "confidence": 0.9,
                "business_value": 0.9, "stability": 0.9,
                "explicitness": 1.0, "future_usefulness": 0.9,
            }]},
        )
        resp = system.write(request)
        system._worker.process_once()
        ev = repo.get_event(resp.event_id)
        self.assertEqual("rejected", ev.status)
        self.assertEqual("authorization_denied", ev.error_code)
        self.assertIsNotNone(ev.error)
        self.assertIsNotNone(ev.processed_at)

    def test_lease_expired_prevents_commit_even_before_reclaim(self):
        repo = _InMemoryRepository()
        system = build_memory_system(
            repository=repo, embedding_service=_InMemoryEmbeddingService(),
            extractor=StructuredMemoryExtractor(), text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
            async_mode=False,
        )
        principal = MemoryPrincipal("u", "t", "u", "a")
        scope = MemoryScope("t", "u", "a")
        request = MemorySubmitRequest(
            principal=principal, scope=scope,
            idempotency_key="exp-1",
            source=MemorySource("test", "exp-1"),
            observations=[MemoryObservation("fact", "x")],
            metadata={"memory_candidates": [{
                "type": "fact", "entity_id": "e", "attribute": "a",
                "content": "x", "confidence": 0.9,
                "business_value": 0.9, "stability": 0.9,
                "explicitness": 1.0, "future_usefulness": 0.9,
            }]},
        )
        resp = system.write(request)
        ev = repo.get_event(resp.event_id)
        st = repo._es(ev.event_id)
        st["status"] = "processing"
        st["locked_by"] = "w"
        st["lock_token"] = "tok"
        st["lease_until"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        ev.status = "processed"
        ev.processed_at = datetime.now(timezone.utc)
        ev.locked_by = "w"
        ev.lock_token = "tok"

        with self.assertRaises(ConcurrentMemoryWrite):
            repo.commit_event_result(ev, "w", [], "tok")

    def test_outbox_expired_reclaim_actually_takes_ownership(self):
        repo = _InMemoryRepository()
        import uuid
        now = datetime.now(timezone.utc)
        repo.outbox["ob-1"] = {
            "id": "ob-1", "status": "processing",
            "locked_by": "old-pub", "lock_token": "old-tok",
            "lease_until": now - timedelta(seconds=1),
            "attempt_count": 1,
        }
        records = repo.claim_outbox(1, "new-pub", 30)
        self.assertEqual(1, len(records), "expired processing must be reclaimed")
        rec = records[0]
        self.assertEqual("processing", rec["status"])
        self.assertEqual("new-pub", rec["locked_by"])
        self.assertNotEqual("old-tok", rec["lock_token"])
        self.assertGreater(rec["lease_until"], now)

    def test_outbox_cas_rejected_without_ownership(self):
        repo = _InMemoryRepository()
        repo.outbox["ob-1"] = {
            "id": "ob-1", "status": "processing",
            "locked_by": "pub-A", "lock_token": "tok-A",
            "lease_until": datetime.now(timezone.utc) + timedelta(seconds=30),
            "attempt_count": 1,
        }
        with self.assertRaises(ConcurrentMemoryWrite):
            repo.mark_outbox_published("ob-1", "pub-B", "tok-A")
        self.assertEqual("processing", repo.outbox["ob-1"]["status"])

        with self.assertRaises(ConcurrentMemoryWrite):
            repo.retry_outbox("ob-1", "err", datetime.now(timezone.utc), "pub-B", "tok-A")
        self.assertEqual("processing", repo.outbox["ob-1"]["status"])

        with self.assertRaises(ConcurrentMemoryWrite):
            repo.dead_letter_outbox("ob-1", "fatal", "pub-B", "tok-A")
        self.assertEqual("processing", repo.outbox["ob-1"]["status"])

    def test_commit_event_result_conditional_writes_per_status(self):
        repo = _InMemoryRepository()

        def setup_processing():
            import uuid
            from app.memory.models.event import MemoryEvent
            ev = MemoryEvent(
                trace_id="t", task_id="t", agent_id="a", user_id="u",
                tenant_id="tn", department_id=None, source_kind="sk",
                source_id="si", idempotency_key="ik", observations=[],
                metadata={},
            )
            repo.events[ev.event_id] = ev
            st = repo._es(ev.event_id)
            st["status"] = "processing"
            st["locked_by"] = "w"
            st["lock_token"] = "tok"
            st["lease_until"] = datetime.now(timezone.utc) + timedelta(seconds=30)
            ev.status = "processing"
            ev.locked_by = "w"
            ev.lock_token = "tok"
            ev.lease_until = st["lease_until"]
            ev.attempt_count = 2
            ev.error = "old-error"
            ev.error_code = "old-code"
            ev.next_attempt_at = datetime.now(timezone.utc)
            return ev

        # PROCESSED clears error/next_attempt
        ev = setup_processing()
        ev.status = "processed"
        ev.processed_at = datetime.now(timezone.utc)
        repo.commit_event_result(ev, "w", [], "tok")
        stored = repo.get_event(ev.event_id)
        self.assertEqual("processed", stored.status)
        self.assertIsNone(stored.error)
        self.assertIsNone(stored.error_code)
        self.assertIsNone(stored.next_attempt_at)
        self.assertIsNotNone(stored.processed_at)

        # RETRY_WAIT persists error/next_attempt
        ev = setup_processing()
        ev.status = "retry_wait"
        ev.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=60)
        ev.error = "transient"
        ev.error_code = "provider_error"
        repo.commit_event_result(ev, "w", [], "tok")
        stored = repo.get_event(ev.event_id)
        self.assertEqual("retry_wait", stored.status)
        self.assertEqual("transient", stored.error)
        self.assertEqual("provider_error", stored.error_code)
        self.assertIsNotNone(stored.next_attempt_at)

        # REJECTED persists error/processed_at
        ev = setup_processing()
        ev.status = "rejected"
        ev.processed_at = datetime.now(timezone.utc)
        ev.error = "bad-input"
        ev.error_code = "validation_failed"
        repo.commit_event_result(ev, "w", [], "tok")
        stored = repo.get_event(ev.event_id)
        self.assertEqual("rejected", stored.status)
        self.assertEqual("bad-input", stored.error)
        self.assertEqual("validation_failed", stored.error_code)
        self.assertIsNotNone(stored.processed_at)


if __name__ == "__main__":
    unittest.main()
