import json
from datetime import datetime, timezone

from app.memory.errors import ConcurrentMemoryWrite, MemoryConcurrencyError
from app.memory.events import MemoryDomainEvent
from app.memory.pipeline.write.resolver import Resolution


class WritePipeline:
    MAX_CONCURRENT_WRITE_ATTEMPTS = 3
    STAGES = (
        "EXTRACTING", "EVALUATING", "NORMALIZING", "PRE_DEDUP",
        "RESOLVING", "FINE_DEDUP", "RANKING", "PERSISTING",
    )

    def __init__(self, repository, extractor, embedding_service, evaluator, normalizer, pre_dedup,
                 resolver, fine_dedup, ranker, updater, authorization_provider, event_sink=None):
        self.repository = repository
        self.extractor = extractor
        self.embedding_service = embedding_service
        self.evaluator = evaluator
        self.normalizer = normalizer
        self.pre_dedup = pre_dedup
        self.resolver = resolver
        self.fine_dedup = fine_dedup
        self.ranker = ranker
        self.updater = updater
        self.authorization_provider = authorization_provider
        self.event_sink = event_sink
        self._domain_events = []

    def process(self, event):
        """Two-phase: prepare outside transaction, then commit inside one."""
        self._domain_events = []
        seen = set()
        stage = self.STAGES[0]
        try:
            self._stage(event, stage)
            raw_candidates = self.extractor.extract(event)
            pending = []
            for raw_candidate in raw_candidates:
                embedding = self.embedding_service.embed(
                    self._embedding_text(raw_candidate.content)
                )
                raw_candidate.embedding = embedding.vector
                raw_candidate.metadata.update({
                    "embedding_provider": embedding.provider,
                    "embedding_model": embedding.model,
                    "embedding_version": embedding.version,
                    "embedding_dimension": embedding.dimension,
                    "embedding_space_id": embedding.space_id,
                })
                stage = "EVALUATING"
                self._stage(event, stage)
                evaluation = self.evaluator.evaluate(raw_candidate)
                if not evaluation.accepted:
                    continue
                stage = "NORMALIZING"
                self._stage(event, stage)
                candidate = self.normalizer.normalize(raw_candidate)
                stage = "PRE_DEDUP"
                self._stage(event, stage)
                if not self.pre_dedup.accept(event, candidate, seen):
                    continue
                self.authorization_provider.authorize_write_candidate(
                    event.principal, event.scope, candidate.type
                )
                stage = "RESOLVING"
                self._stage(event, stage)
                existing = self.repository.find_active_head(
                    event.scope, candidate.identity
                )
                resolution = self.resolver.resolve(candidate, existing)
                stage = "FINE_DEDUP"
                self._stage(event, stage)
                if self.fine_dedup.is_duplicate(candidate, existing):
                    resolution = Resolution.UPDATE
                stage = "RANKING"
                self._stage(event, stage)
                importance = self.ranker.rank(candidate)
                pending.append(
                    (candidate, evaluation, importance, resolution, existing)
                )
            stage = "PERSISTING"
            self._stage(event, stage)
            results = self._commit_all(event, pending)
            self.repository.update_processing_task(
                event.event_id, "PERSISTING", "completed"
            )
            return results
        except Exception as error:
            self.repository.update_processing_task(
                event.event_id, stage, "failed", str(error)
            )
            raise

    def _commit_all(self, event, pending):
        transaction = getattr(self.repository, "atomic_write", None)
        ctx = transaction() if transaction else __import__("contextlib").nullcontext()
        with ctx:
            results = []
            for candidate, evaluation, importance, resolution, existing in pending:
                item = created = None
                attempts_before = 0
                for attempt in range(self.MAX_CONCURRENT_WRITE_ATTEMPTS):
                    if attempt > 0:
                        existing = self.repository.find_active_head(
                            event.scope, candidate.identity
                        )
                    try:
                        item, created = self.updater.persist(
                            event, candidate, evaluation, importance,
                            resolution, existing,
                        )
                        break
                    except ConcurrentMemoryWrite as error:
                        if attempt + 1 == self.MAX_CONCURRENT_WRITE_ATTEMPTS:
                            raise MemoryConcurrencyError(
                                "Memory write could not stabilize after "
                                f"{self.MAX_CONCURRENT_WRITE_ATTEMPTS} attempts"
                            ) from error
                results.append(item)
                event_type = (
                    "memory.conflict" if resolution == Resolution.CONFLICT
                    else "memory.created" if created and existing is None
                    else "memory.updated"
                )
                self._domain_events.append(MemoryDomainEvent(
                    event_type=event_type, aggregate_id=event.event_id,
                    payload={"trace_id": event.trace_id, "task_id": event.task_id,
                             "agent_id": event.agent_id, "memory_id": item.id,
                             "memory_key": item.memory_key},
                ))
            return results

    @property
    def domain_events(self):
        return list(self._domain_events)

    def _stage(self, event, stage):
        self.repository.update_processing_task(
            event.event_id, stage, "processing"
        )

    @staticmethod
    def _embedding_text(content):
        if isinstance(content, str):
            return content
        return json.dumps(
            content, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), default=str,
        )

    def _publish(self, event_type, event, metadata):
        domain_event = MemoryDomainEvent(
            event_type=event_type, aggregate_id=event.event_id,
            payload={"trace_id": event.trace_id, "task_id": event.task_id,
                     "agent_id": event.agent_id, **metadata},
        )
        self._domain_events.append(domain_event)
        if self.event_sink:
            self.event_sink.publish(domain_event)
