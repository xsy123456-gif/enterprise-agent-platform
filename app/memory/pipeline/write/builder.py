import json

from app.memory.pipeline.write.resolver import Resolution


class WritePipeline:
    STAGES = (
        "EXTRACTING", "EVALUATING", "NORMALIZING", "PRE_DEDUP",
        "RESOLVING", "FINE_DEDUP", "RANKING", "PERSISTING",
    )

    def __init__(self, repository, extractor, embedding_service, evaluator, normalizer, pre_dedup,
                 resolver, fine_dedup, ranker, updater, governance, event_publisher=None):
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
        self.governance = governance
        self.event_publisher = event_publisher

    def process(self, event):
        stage = self.STAGES[0]
        try:
            self._stage(event, stage)
            raw_candidates = self.extractor.extract(event)
            results = []
            for raw_candidate in raw_candidates:
                embedding = self.embedding_service.embed(
                    self._embedding_text(raw_candidate.content)
                )
                raw_candidate.embedding = embedding.vector
                raw_candidate.metadata.update({
                    "embedding_model": embedding.model,
                    "embedding_version": embedding.version,
                    "embedding_dimension": embedding.dimension,
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
                if not self.pre_dedup.accept(event, candidate):
                    continue
                self.governance.check_write(event, candidate)
                existing = self.repository.find_latest(event.scope, candidate.identity)
                stage = "RESOLVING"
                self._stage(event, stage)
                resolution = self.resolver.resolve(candidate, existing)
                stage = "FINE_DEDUP"
                self._stage(event, stage)
                if self.fine_dedup.is_duplicate(candidate, existing):
                    resolution = Resolution.UPDATE
                stage = "RANKING"
                self._stage(event, stage)
                importance = self.ranker.rank(candidate)
                stage = "PERSISTING"
                self._stage(event, stage)
                item, created = self.updater.persist(
                    event, candidate, evaluation, importance, resolution, existing
                )
                results.append(item)
                event_type = (
                    "memory.conflict" if resolution == Resolution.CONFLICT
                    else "memory.created" if created and existing is None
                    else "memory.updated"
                )
                self._publish(
                    event_type, event,
                    {"memory_id": item.id, "memory_key": item.memory_key},
                )
            self.repository.update_processing_task(
                event.event_id, "PERSISTING", "completed"
            )
            return results
        except Exception as error:
            self.repository.update_processing_task(
                event.event_id, stage, "failed", str(error)
            )
            raise

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
        if self.event_publisher:
            self.event_publisher(event_type, event, metadata)
