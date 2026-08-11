"""Group 2 — data correctness tests.

Covers: observation_count, access_count, idempotent response,
error classification (with specific error_code assertions),
PreDedup, retry observations, concurrent counter tests.
"""

import json
import unittest
from datetime import datetime, timedelta, timezone

from app.memory.api.models import (
    MemoryObservation, MemoryPrincipal, MemoryRetrieveRequest, MemorySource,
    MemorySubmitRequest,
)
from app.memory.errors import (
    classify_error, ConcurrentMemoryWrite, ErrorDisposition,
    MemoryAccessDenied, MemoryConcurrencyError, MemoryInvariantViolation,
    MemoryProviderError, MemoryStorageError, MemoryValidationError,
)
from app.memory.factory import build_memory_system
from app.memory.models.event import MemoryEventStatus
from app.memory.models.identity import MemoryIdentity
from app.memory.models.item import MemoryItemStatus
from app.memory.models.scope import MemoryScope
from app.memory.pipeline.write.extractor import MemoryCandidate, StructuredMemoryExtractor
from app.memory.pipeline.write.resolver import Resolution
from app.memory.ports.authorization import AllowAllMemoryAuthorizationProvider

from tests.memory.test_support import _InMemoryRepository, _InMemoryEmbeddingService, StubLLM


def make_request(key, obs="fact", content="x",
                 entity_id=None, type_id="fact", attribute="a",
                 user="u", tenant="tn", agent="ag"):
    principal = MemoryPrincipal(user, tenant, user, agent)
    scope = MemoryScope(tenant, user, agent)
    return MemorySubmitRequest(
        principal=principal, scope=scope,
        idempotency_key=key,
        source=MemorySource("test", key),
        observations=[MemoryObservation(obs, content)],
        metadata={"memory_candidates": [{
            "type": type_id,
            "entity_id": entity_id or key,
            "attribute": attribute,
            "content": content, "confidence": 0.9,
            "business_value": 0.9, "stability": 0.9,
            "explicitness": 1.0, "future_usefulness": 0.9,
        }]},
    )


# ── Error classifier unit tests ───────────────────────────────────

class ErrorClassifierTest(unittest.TestCase):
    def test_permission_error_is_authorization_denied(self):
        d = classify_error(MemoryAccessDenied("nope"))
        self.assertEqual("authorization_denied", d.code)
        self.assertFalse(d.retryable)

    def test_validation_error_is_validation_failed(self):
        d = classify_error(MemoryValidationError("bad"))
        self.assertEqual("validation_failed", d.code)

    def test_invariant_is_invariant_violation(self):
        d = classify_error(MemoryInvariantViolation("two heads"))
        self.assertEqual("invariant_violation", d.code)

    def test_provider_error(self):
        d = classify_error(MemoryProviderError("timeout"))
        self.assertEqual("provider_error", d.code)
        self.assertTrue(d.retryable)

    def test_storage_error(self):
        d = classify_error(MemoryStorageError("connection reset"))
        self.assertEqual("storage_error", d.code)
        self.assertTrue(d.retryable)

    def test_concurrency_error(self):
        d = classify_error(MemoryConcurrencyError("unstable"))
        self.assertEqual("concurrency_error", d.code)
        self.assertTrue(d.retryable)

    def test_concurrent_memory_write_maps_to_concurrency_error(self):
        d = classify_error(ConcurrentMemoryWrite("CAS failure"))
        self.assertEqual("concurrency_error", d.code)
        self.assertTrue(d.retryable)

    def test_unknown_exception(self):
        d = classify_error(RuntimeError("weird"))
        self.assertEqual("unknown_error", d.code)
        self.assertTrue(d.retryable)


# ── Observation count tests ────────────────────────────────────────

class ObservationCountTest(unittest.TestCase):

    def setUp(self):
        self.repo = _InMemoryRepository()
        self.system = build_memory_system(
            repository=self.repo, embedding_service=_InMemoryEmbeddingService(),
            extractor=StructuredMemoryExtractor(), text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
        )

    def _submit_and_process(self, key, content="工程师", type_id="person",
                            entity_id="张三", attribute="职业"):
        req = make_request(key, obs="fact", content=content,
                           type_id=type_id, entity_id=entity_id, attribute=attribute)
        resp = self.system.write(req)
        self.system.runtime._worker.process_once()
        return resp

    def test_create_sets_observation_count_to_one(self):
        self._submit_and_process("oc-1")
        self.assertEqual(1, list(self.repo.items.values())[0].observation_count)

    def test_create_sets_last_observed_at(self):
        self._submit_and_process("oc-2")
        self.assertIsNotNone(list(self.repo.items.values())[0].last_observed_at)

    def test_repeated_observation_increments_count(self):
        self._submit_and_process("oc-3", content="工程师")
        self._submit_and_process("oc-4", content="工程师",
                                  entity_id="张三", type_id="person", attribute="职业")
        item = list(self.repo.items.values())[0]
        self.assertEqual(1, len(self.repo.items))
        self.assertEqual(2, item.observation_count)

    def test_repeated_observation_updates_last_observed_at(self):
        self._submit_and_process("oc-5", content="工程师")
        t1 = list(self.repo.items.values())[0].last_observed_at
        self._submit_and_process("oc-6", content="工程师",
                                  entity_id="张三", type_id="person", attribute="职业")
        t2 = list(self.repo.items.values())[0].last_observed_at
        self.assertGreater(t2, t1)

    def test_thrice_observation_gives_count_three(self):
        for i in range(3):
            self._submit_and_process(f"oc-{i}", content="工程师",
                                      entity_id="张三", type_id="person", attribute="职业")
        item = list(self.repo.items.values())[0]
        self.assertEqual(1, len(self.repo.items))
        self.assertEqual(3, item.observation_count)

    def test_replace_creates_new_version_with_count_one(self):
        self._submit_and_process("oc-10", content="工程师", type_id="person",
                                  entity_id="张三", attribute="职业")
        old = list(self.repo.items.values())[0]

        principal = MemoryPrincipal("u", "tn", "u", "ag")
        scope = MemoryScope("tn", "u", "ag")
        req = MemorySubmitRequest(
            principal=principal, scope=scope, idempotency_key="oc-11",
            source=MemorySource("test", "oc-11"),
            observations=[MemoryObservation("fact", "产品经理")],
            metadata={"memory_candidates": [{
                "type": "person", "entity_id": "张三", "attribute": "职业",
                "content": "产品经理", "confidence": 0.9,
                "business_value": 0.9, "stability": 0.9,
                "explicitness": 1.0, "future_usefulness": 0.9,
            }]},
        )
        self.system.write(req)
        self.system.runtime._worker.process_once()
        self.assertEqual(2, len(self.repo.items))
        self.assertEqual(1, self.repo.items[old.id].observation_count)

    def test_conflict_does_not_increment_old_count(self):
        self._submit_and_process("oc-12", content="工程师", type_id="person",
                                  entity_id="张三", attribute="职业")
        old = list(self.repo.items.values())[0]
        principal = MemoryPrincipal("u", "tn", "u", "ag")
        scope = MemoryScope("tn", "u", "ag")
        req = MemorySubmitRequest(
            principal=principal, scope=scope, idempotency_key="oc-13",
            source=MemorySource("test", "oc-13"),
            observations=[MemoryObservation("fact", "设计师")],
            metadata={"memory_candidates": [{
                "type": "person", "entity_id": "张三", "attribute": "职业",
                "content": "设计师", "confidence": 0.3,
                "business_value": 0.3, "stability": 0.3,
                "explicitness": 0.3, "future_usefulness": 0.3,
                "metadata": {"conflict": True},
            }]},
        )
        self.system.write(req)
        self.system.runtime._worker.process_once()
        self.assertEqual(1, self.repo.items[old.id].observation_count)

    def test_retry_rollback_does_not_double_count(self):
        """First commit fails → rollback → retry succeeds → count=1, not 2."""
        class FailingRepo(_InMemoryRepository):
            first_commit = [True]

            def commit_resolution(self, item, expected_active_head_id, relations=None):
                if self.first_commit[0]:
                    self.first_commit[0] = False
                    raise RuntimeError("simulated commit failure")
                return super().commit_resolution(item, expected_active_head_id, relations)

        repo = FailingRepo()
        system = build_memory_system(
            repository=repo, embedding_service=_InMemoryEmbeddingService(),
            extractor=StructuredMemoryExtractor(), text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
        )
        req = make_request("oc-rb", content="工程师",
                           entity_id="张三", type_id="person", attribute="职业")
        resp = system.write(req)

        # First attempt: commit fails → retry_wait
        system.runtime._worker.process_once()
        ev = repo.get_event(resp.event_id)
        self.assertEqual("retry_wait", ev.status)

        # Second attempt: retry succeeds
        ev.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        system.runtime._worker.process_once()
        ev = repo.get_event(resp.event_id)
        self.assertEqual("processed", ev.status)

        self.assertGreaterEqual(len(repo.items), 1)
        for item in repo.items.values():
            if item.status == "active":
                self.assertEqual(1, item.observation_count,
                                 "retry+rollback must not double count")


# ── Access count tests ─────────────────────────────────────────────

class AccessCountTest(unittest.TestCase):

    def setUp(self):
        self.repo = _InMemoryRepository()
        self.system = build_memory_system(
            repository=self.repo, embedding_service=_InMemoryEmbeddingService(),
            extractor=StructuredMemoryExtractor(), text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
        )

    def _submit_process(self, key="ak-1", content="工程师", type_id="person",
                        entity_id="user", attribute="job"):
        req = make_request(key, obs="fact", content=content,
                           type_id=type_id, entity_id=entity_id, attribute=attribute)
        self.system.write(req)
        self.system.runtime._worker.process_once()

    def _read(self, query="工程师", types=None):
        principal = MemoryPrincipal("u", "tn", "u", "ag")
        scope = MemoryScope("tn", "u", "ag")
        return self.system.read(MemoryRetrieveRequest(
            principal=principal, scope=scope, query=query,
            types=types or ["person"],
        ))

    def test_first_read_sets_access_count_to_one(self):
        self._submit_process("ak-2")
        self._read()
        self.assertEqual(1, list(self.repo.items.values())[0].access_count)

    def test_first_read_sets_last_accessed_at(self):
        self._submit_process("ak-3")
        self._read()
        self.assertIsNotNone(list(self.repo.items.values())[0].last_accessed_at)

    def test_second_read_increments_count(self):
        self._submit_process("ak-4")
        self._read()
        self._read()
        self.assertEqual(2, list(self.repo.items.values())[0].access_count)

    def test_access_log_is_recorded(self):
        self._submit_process("ak-5")
        self._read()
        self.assertGreaterEqual(len(self.repo.access_logs), 1)


# ── Idempotent submit tests ────────────────────────────────────────

class IdempotentSubmitTest(unittest.TestCase):

    def setUp(self):
        self.repo = _InMemoryRepository()
        self.system = build_memory_system(
            repository=self.repo, embedding_service=_InMemoryEmbeddingService(),
            extractor=StructuredMemoryExtractor(), text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
        )

    def test_duplicate_key_returns_same_event_id(self):
        req = make_request("idem-1")
        r1 = self.system.write(req)
        r2 = self.system.write(req)
        self.assertEqual(r1.event_id, r2.event_id)
        self.assertEqual(1, len(self.repo.events))

    def test_duplicate_returns_processed_status(self):
        req = make_request("idem-2")
        self.system.write(req)
        self.system.runtime._worker.process_once()
        r2 = self.system.write(req)
        self.assertEqual("processed", r2.status)

    def test_duplicate_returns_received_status(self):
        req = make_request("idem-3")
        self.system.write(req)
        r2 = self.system.write(req)
        self.assertEqual("received", r2.status)


# ── Error classification (with specific error_code assertions) ────

class ErrorClassificationTest(unittest.TestCase):

    def setUp(self):
        self.repo = _InMemoryRepository()

    def _build(self, extractor=None, auth=None):
        return build_memory_system(
            repository=self.repo, embedding_service=_InMemoryEmbeddingService(),
            extractor=extractor or StructuredMemoryExtractor(),
            text_model=StubLLM(),
            authorization_provider=auth or AllowAllMemoryAuthorizationProvider(),
        )

    def test_authorization_error_gets_authorization_denied(self):
        class Deny(AllowAllMemoryAuthorizationProvider):
            def authorize_write_candidate(self, p, s, ct):
                raise PermissionError("no-write")
        system = self._build(auth=Deny())
        resp = system.write(make_request("err-auth"))
        system.runtime._worker.process_once()
        ev = self.repo.get_event(resp.event_id)
        self.assertEqual(MemoryEventStatus.REJECTED, ev.status)
        self.assertEqual("authorization_denied", ev.error_code)
        self.assertIsNotNone(ev.processed_at)
        self.assertIsNotNone(ev.error)

    def test_validation_error_gets_validation_failed(self):
        class BadExtractor(StructuredMemoryExtractor):
            def extract(self, ev):
                raise MemoryValidationError("bad input")
        system = self._build(extractor=BadExtractor())
        resp = system.write(make_request("err-val"))
        system.runtime._worker.process_once()
        ev = self.repo.get_event(resp.event_id)
        self.assertEqual(MemoryEventStatus.REJECTED, ev.status)
        self.assertEqual("validation_failed", ev.error_code)

    def test_invariant_error_gets_invariant_violation(self):
        class BadExtractor(StructuredMemoryExtractor):
            def extract(self, ev):
                raise MemoryInvariantViolation("two active heads")
        system = self._build(extractor=BadExtractor())
        resp = system.write(make_request("err-inv"))
        system.runtime._worker.process_once()
        ev = self.repo.get_event(resp.event_id)
        self.assertEqual(MemoryEventStatus.DEAD_LETTER, ev.status)
        self.assertEqual("invariant_violation", ev.error_code)

    def test_provider_error_gets_provider_error_code(self):
        class BadExtractor(StructuredMemoryExtractor):
            def extract(self, ev):
                raise MemoryProviderError("embedding timeout")
        system = self._build(extractor=BadExtractor())
        resp = system.write(make_request("err-prov"))
        system.runtime._worker.process_once()
        ev = self.repo.get_event(resp.event_id)
        self.assertEqual(MemoryEventStatus.RETRY_WAIT, ev.status)
        self.assertEqual("provider_error", ev.error_code)
        self.assertIsNotNone(ev.next_attempt_at)
        self.assertIsNotNone(ev.error)

    def test_storage_error_gets_storage_error_code(self):
        class BadExtractor(StructuredMemoryExtractor):
            def extract(self, ev):
                raise MemoryStorageError("connection reset")
        system = self._build(extractor=BadExtractor())
        resp = system.write(make_request("err-stor"))
        system.runtime._worker.process_once()
        ev = self.repo.get_event(resp.event_id)
        self.assertEqual(MemoryEventStatus.RETRY_WAIT, ev.status)
        self.assertEqual("storage_error", ev.error_code)

    def test_concurrency_error_gets_concurrency_error_code(self):
        class BadExtractor(StructuredMemoryExtractor):
            def extract(self, ev):
                raise MemoryConcurrencyError("unstable write")
        system = self._build(extractor=BadExtractor())
        resp = system.write(make_request("err-conc"))
        system.runtime._worker.process_once()
        ev = self.repo.get_event(resp.event_id)
        self.assertEqual(MemoryEventStatus.RETRY_WAIT, ev.status)
        self.assertEqual("concurrency_error", ev.error_code)

    def test_unknown_error_gets_unknown_error_code(self):
        class BadExtractor(StructuredMemoryExtractor):
            def extract(self, ev):
                raise RuntimeError("something weird")
        system = self._build(extractor=BadExtractor())
        resp = system.write(make_request("err-unk"))
        system.runtime._worker.process_once()
        ev = self.repo.get_event(resp.event_id)
        self.assertEqual(MemoryEventStatus.RETRY_WAIT, ev.status)
        self.assertEqual("unknown_error", ev.error_code)

    def test_processed_clears_error(self):
        system = self._build()
        resp = system.write(make_request("err-clr"))
        system.runtime._worker.process_once()
        ev = self.repo.get_event(resp.event_id)
        self.assertEqual(MemoryEventStatus.PROCESSED, ev.status)
        self.assertIsNone(ev.error)
        self.assertIsNone(ev.error_code)

    def test_retry_exhaustion_preserves_original_code(self):
        class BadExtractor(StructuredMemoryExtractor):
            def extract(self, ev):
                raise MemoryProviderError("timeout")
        system = self._build(extractor=BadExtractor())
        system.runtime._worker.max_attempts = 1
        resp = system.write(make_request("err-exh"))
        system.runtime._worker.process_once()
        ev = self.repo.get_event(resp.event_id)
        self.assertEqual(MemoryEventStatus.DEAD_LETTER, ev.status)
        self.assertEqual("provider_error", ev.error_code,
                         "retry exhaustion must preserve original error code")

    def test_llm_failure_through_real_extractor_gets_provider_error(self):
        class FailingLLM:
            def chat(self, messages, **kwargs):
                raise ConnectionError("LLM endpoint unreachable")
        from app.memory.pipeline.write.extractor import LLMMemoryExtractor
        llm_extractor = LLMMemoryExtractor(FailingLLM())
        repo = _InMemoryRepository()
        system = build_memory_system(
            repository=repo,
            embedding_service=_InMemoryEmbeddingService(),
            extractor=llm_extractor, text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
        )
        resp = system.write(make_request("err-llm"))
        system.runtime._worker.process_once()
        ev = repo.get_event(resp.event_id)
        self.assertEqual(MemoryEventStatus.RETRY_WAIT, ev.status)
        self.assertEqual("provider_error", ev.error_code)
        self.assertIsNotNone(ev.error)

    def test_repository_driver_failure_gets_storage_error(self):
        """Repository raises MemoryStorageError → worker maps to storage_error."""
        class FailingRepo(_InMemoryRepository):
            def commit_resolution(self, *a, **kw):
                raise MemoryStorageError("connection refused")
        repo = FailingRepo()
        system = build_memory_system(
            repository=repo,
            embedding_service=_InMemoryEmbeddingService(),
            extractor=StructuredMemoryExtractor(), text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
        )
        resp = system.write(make_request("err-storage"))
        system.runtime._worker.process_once()
        ev = repo.get_event(resp.event_id)
        self.assertEqual(MemoryEventStatus.RETRY_WAIT, ev.status)
        self.assertEqual("storage_error", ev.error_code)


    def test_find_active_head_invariant_not_rewrapped_as_storage(self):
        """MemoryInvariantViolation from find_active_head stays invariant_violation."""
        class InvariantRepo(_InMemoryRepository):
            def find_active_head(self, scope, identity):
                raise MemoryInvariantViolation("two active heads")
        repo = InvariantRepo()
        system = build_memory_system(
            repository=repo,
            embedding_service=_InMemoryEmbeddingService(),
            extractor=StructuredMemoryExtractor(), text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
        )
        resp = system.write(make_request("err-fah"))
        system.runtime._worker.process_once()
        ev = repo.get_event(resp.event_id)
        self.assertEqual(MemoryEventStatus.DEAD_LETTER, ev.status)
        self.assertEqual("invariant_violation", ev.error_code,
                         "MemoryInvariantViolation must not be rewrapped as storage_error")

    def test_concurrent_write_stays_concurrency_not_storage(self):
        """ConcurrentMemoryWrite from commit path stays concurrency_error."""
        class ConcurrentRepo(_InMemoryRepository):
            def commit_resolution(self, *a, **kw):
                raise ConcurrentMemoryWrite("CAS lost")
        repo = ConcurrentRepo()
        system = build_memory_system(
            repository=repo,
            embedding_service=_InMemoryEmbeddingService(),
            extractor=StructuredMemoryExtractor(), text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
        )
        resp = system.write(make_request("err-cc"))
        system.runtime._worker.process_once()
        ev = repo.get_event(resp.event_id)
        self.assertIn(ev.status, [MemoryEventStatus.RETRY_WAIT, MemoryEventStatus.DEAD_LETTER])
        self.assertEqual("concurrency_error", ev.error_code)


class PreDedupTest(unittest.TestCase):

    def setUp(self):
        self.repo = _InMemoryRepository()

    def _build(self, extractor=None):
        return build_memory_system(
            repository=self.repo, embedding_service=_InMemoryEmbeddingService(),
            extractor=extractor or StructuredMemoryExtractor(),
            text_model=StubLLM(),
            authorization_provider=AllowAllMemoryAuthorizationProvider(),
        )

    def test_same_event_duplicate_candidates_filtered(self):
        class DupExtractor(StructuredMemoryExtractor):
            def extract(self, ev):
                base = super().extract(ev)
                dup = type(base[0])(**{k: v for k, v in base[0].__dict__.items()
                                       if k != "embedding"})
                return [base[0], dup, base[0]]
        system = self._build(extractor=DupExtractor())
        resp = system.write(make_request("pd-1"))
        system.runtime._worker.process_once()
        self.assertEqual("processed", self.repo.get_event(resp.event_id).status)
        self.assertEqual(1, len(self.repo.items))

    def test_same_candidate_in_later_event_not_filtered(self):
        system = self._build()

        obs_calls = [0]
        orig = self.repo.merge_observation
        def counting(*a, **kw):
            obs_calls[0] += 1
            return orig(*a, **kw)
        self.repo.merge_observation = counting

        system.write(make_request("pd-2", content="工程师",
                                  entity_id="张三", type_id="person", attribute="职业"))
        system.runtime._worker.process_once()
        system.write(make_request("pd-3", content="工程师",
                                  entity_id="张三", type_id="person", attribute="职业"))
        system.runtime._worker.process_once()

        self.assertGreaterEqual(obs_calls[0], 1,
                                "second event must reach observation update")


# ── PostgresMemoryRepository atomic_write boundary tests ──────────
# These test the real PostgresMemoryRepository storage wrapping
# using a fake connection_factory — no real PostgreSQL needed.

class AtomicWriteStorageBoundaryTest(unittest.TestCase):
    """Validate that atomic_write() correctly wraps raw DB errors
    while preserving Memory Domain Errors."""

    def _make_repo(self):
        from app.memory.repository.postgres import PostgresMemoryRepository
        return PostgresMemoryRepository(self._fake_factory, embedding_dimension=3)

    def _fake_factory(self, register_types=True):
        return _FakeConnection()

    # ── Test A: ConcurrentMemoryWrite NOT rewrapped ────────────────

    def test_concurrent_memory_write_propagates_unchanged(self):
        repo = self._make_repo()
        with self.assertRaises(ConcurrentMemoryWrite) as ctx:
            with repo.atomic_write():
                raise ConcurrentMemoryWrite("CAS lost")
        d = classify_error(ctx.exception)
        self.assertEqual("concurrency_error", d.code,
                         "ConcurrentMemoryWrite must not become storage_error")

    # ── Test B: raw connection error wrapped as MemoryStorageError ─

    def test_raw_connection_error_wrapped_as_storage(self):
        repo = self._make_repo()
        with self.assertRaises(MemoryStorageError) as ctx:
            with repo.atomic_write():
                raise ConnectionError("connection refused")
        d = classify_error(ctx.exception)
        self.assertEqual("storage_error", d.code)

    # ── Test C: MemoryInvariantViolation not rewrapped ─────────────

    def test_invariant_violation_propagates_unchanged(self):
        repo = self._make_repo()
        with self.assertRaises(MemoryInvariantViolation) as ctx:
            with repo.atomic_write():
                raise MemoryInvariantViolation("two active heads")
        d = classify_error(ctx.exception)
        self.assertEqual("invariant_violation", d.code,
                         "MemoryInvariantViolation must not become storage_error")


class _FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return _FakeCursor()


class _FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, *args):
        pass

    def fetchone(self):
        return None

    @property
    def description(self):
        return []


if __name__ == "__main__":
    unittest.main()
