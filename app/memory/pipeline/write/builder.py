import json

from app.memory.events import MemoryDomainEvent
from app.memory.pipeline.write.resolver import Resolution


class WritePipeline:

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

    def prepare(self, event):
        """Phase 1: LLM, embedding, evaluation, resolution — zero durable writes.

        Returns (pending_mutations, domain_events) where each pending mutation is
        (candidate, evaluation, importance, resolution, existing).
        Domain events for memory.created / memory.updated / memory.conflict are
        emitted so they become part of the same Outbox transaction.
        """
        seen = set()
        domain_events = []
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
            evaluation = self.evaluator.evaluate(raw_candidate)
            if not evaluation.accepted:
                continue
            candidate = self.normalizer.normalize(raw_candidate)
            if not self.pre_dedup.accept(event, candidate, seen):
                continue
            self.authorization_provider.authorize_write_candidate(
                event.principal, event.scope, candidate.type
            )
            existing = self.repository.find_active_head(
                event.scope, candidate.identity
            )
            resolution = self.resolver.resolve(candidate, existing)
            if self.fine_dedup.is_duplicate(candidate, existing):
                resolution = Resolution.UPDATE
            importance = self.ranker.rank(candidate)
            pending.append(
                (candidate, evaluation, importance, resolution, existing)
            )
            event_type = (
                "memory.conflict" if resolution == Resolution.CONFLICT
                else "memory.created" if existing is None
                else "memory.updated"
            )
            domain_events.append(MemoryDomainEvent(
                event_type=event_type,
                aggregate_id=event.event_id,
                payload={
                    "trace_id": event.trace_id, "task_id": event.task_id,
                    "agent_id": event.agent_id,
                    "memory_key": candidate.memory_key,
                },
            ))
        return pending, domain_events

    @staticmethod
    def _embedding_text(content):
        if isinstance(content, str):
            return content
        return json.dumps(
            content, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), default=str,
        )
