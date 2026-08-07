from datetime import datetime, timedelta, timezone
import unittest

from app.memory.api.models import (
    MemoryObservation, MemoryPrincipal, MemorySource, MemorySubmitRequest,
)
from app.memory.factory import build_memory_system
from app.memory.pipeline.write.extractor import MemoryExtractor, StructuredMemoryExtractor
from app.memory.models.event import MemoryEventStatus
from app.memory.models.scope import MemoryScope
from app.memory.ports.authorization import AllowAllMemoryAuthorizationProvider
from app.memory.test_repository import TestEmbeddingService, TestMemoryRepository


def request(key="source-1"):
    principal = MemoryPrincipal("user", "tenant", "user", "agent")
    return MemorySubmitRequest(
        principal, MemoryScope("tenant", "user", "agent"), key,
        MemorySource("test_source", key), [MemoryObservation("generic", {"x": 1})],
        metadata={"memory_candidates": [{
            "type": "customer", "entity_id": key, "attribute": "name",
            "content": "A", "confidence": 0.9, "business_value": 0.9,
            "stability": 0.9, "explicitness": 0.9, "future_usefulness": 0.9,
        }]},
    )


class TextModel:
    def chat(self, messages, **kwargs):
        return "[]"


class DurableWorkerTest(unittest.TestCase):
    def build(self, repository, extractor=None, authorization=None, sink=None):
        return build_memory_system(
            repository=repository, embedding_service=TestEmbeddingService(),
            extractor=extractor or StructuredMemoryExtractor(), text_model=TextModel(),
            authorization_provider=authorization or AllowAllMemoryAuthorizationProvider(),
            event_sink=sink, async_mode=False,
        )

    def test_duplicate_submit_returns_one_durable_event(self):
        repository = TestMemoryRepository()
        system = self.build(repository)
        first = system.submit(request())
        second = system.submit(request())
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(1, len(repository.events))

    def test_restart_recovery_claims_durable_received_event(self):
        repository = TestMemoryRepository()
        first = self.build(repository)
        response = first.submit(request())
        second = self.build(repository)
        second._worker.process_once()
        self.assertEqual(MemoryEventStatus.PROCESSED, repository.get_event(response.event_id).status)

    def test_expired_processing_lease_is_reclaimed(self):
        repository = TestMemoryRepository()
        system = self.build(repository)
        response = system.submit(request())
        event = repository.get_event(response.event_id)
        event.status = MemoryEventStatus.PROCESSING
        event.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        system._worker.process_once()
        self.assertEqual(MemoryEventStatus.PROCESSED, event.status)
        self.assertEqual(1, event.attempt_count)

    def test_transient_failure_enters_retry_wait_then_succeeds(self):
        class FlakyExtractor(MemoryExtractor):
            calls = 0
            def extract(self, event):
                self.calls += 1
                if self.calls == 1:
                    raise TimeoutError("embedding provider timeout")
                return StructuredMemoryExtractor().extract(event)

        repository = TestMemoryRepository()
        system = self.build(repository, extractor=FlakyExtractor())
        response = system.submit(request())
        system._worker.process_once()
        event = repository.get_event(response.event_id)
        self.assertEqual(MemoryEventStatus.RETRY_WAIT, event.status)
        event.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        system._worker.process_once()
        self.assertEqual(MemoryEventStatus.PROCESSED, event.status)

    def test_write_authorization_denial_is_rejected(self):
        class DenyWrite(AllowAllMemoryAuthorizationProvider):
            def authorize_write_candidate(self, principal, scope, candidate_type):
                raise PermissionError("denied")

        repository = TestMemoryRepository()
        system = self.build(repository, authorization=DenyWrite())
        response = system.submit(request())
        system._worker.process_once()
        self.assertEqual(MemoryEventStatus.REJECTED, repository.get_event(response.event_id).status)

    def test_max_attempts_moves_event_to_dead_letter(self):
        class AlwaysFails(MemoryExtractor):
            def extract(self, event):
                raise TimeoutError("provider unavailable")

        repository = TestMemoryRepository()
        system = self.build(repository, extractor=AlwaysFails())
        system._worker.max_attempts = 1
        response = system.submit(request())
        system._worker.process_once()
        self.assertEqual(MemoryEventStatus.DEAD_LETTER, repository.get_event(response.event_id).status)

    def test_outbox_failure_does_not_change_processed_source_event(self):
        class FailingSink:
            def publish(self, event):
                raise RuntimeError("platform unavailable")

        repository = TestMemoryRepository()
        system = self.build(repository, sink=FailingSink())
        response = system.submit(request())
        system._worker.process_once()
        self.assertEqual(MemoryEventStatus.PROCESSED, repository.get_event(response.event_id).status)
        self.assertGreaterEqual(len(repository.outbox), 1)
        self.assertTrue(all(
            item["status"] == "pending" for item in repository.outbox.values()
        ))

    def test_worker_lifecycle_can_start_and_stop_cleanly(self):
        repository = TestMemoryRepository()
        system = self.build(repository)
        system._worker.start()
        self.assertTrue(system._worker.health()["running"])
        self.assertTrue(system._worker.stop(timeout=2))
        self.assertFalse(system._worker.health()["running"])

    def test_multi_candidate_failure_rolls_back_memory_items(self):
        class FailingRepository(TestMemoryRepository):
            commits = 0
            def commit_resolution(self, *args, **kwargs):
                self.commits += 1
                if self.commits == 2:
                    raise RuntimeError("second candidate failed")
                return super().commit_resolution(*args, **kwargs)

        class TwoCandidates(MemoryExtractor):
            def extract(self, event):
                return [
                    *StructuredMemoryExtractor().extract(event),
                    type(StructuredMemoryExtractor().extract(event)[0])(
                        type="customer", entity_id="other", attribute="name", content="B",
                        source="test", confidence=0.9, business_value=0.9,
                        stability=0.9, explicitness=0.9, future_usefulness=0.9,
                    ),
                ]

        repository = FailingRepository()
        system = self.build(repository, extractor=TwoCandidates())
        response = system.submit(request())
        system._worker.process_once()
        self.assertEqual(MemoryEventStatus.RETRY_WAIT, repository.get_event(response.event_id).status)
        self.assertEqual({}, repository.items)


if __name__ == "__main__":
    unittest.main()
