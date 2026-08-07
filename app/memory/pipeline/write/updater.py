from app.memory.models.item import MemoryItem, MemoryItemStatus
from app.memory.pipeline.write.resolver import Resolution


class MemoryUpdater:
    def __init__(self, repository):
        self.repository = repository

    def persist(self, event, candidate, evaluation, importance, resolution, existing):
        if resolution == Resolution.UPDATE:
            self.repository.create_relation(
                existing.id, event.event_id, "MERGED_FROM"
            )
            return existing, False
        status = MemoryItemStatus.CONFLICT if resolution == Resolution.CONFLICT else MemoryItemStatus.ACTIVE
        item = MemoryItem(
            memory_key=candidate.memory_key, type=candidate.type,
            entity_id=candidate.entity_id, attribute=candidate.attribute,
            content=candidate.content,
            importance=importance, confidence=evaluation.confidence, source=candidate.source,
            tenant_id=event.tenant_id, department_id=event.department_id,
            user_id=event.user_id, agent_id=event.agent_id,
            embedding=candidate.embedding,
            embedding_space_id=candidate.metadata.get(
                "embedding_space_id", "legacy-unknown"
            ),
            embedding_provider=candidate.metadata.get(
                "embedding_provider", "legacy-unknown"
            ),
            embedding_model=candidate.metadata.get("embedding_model"),
            embedding_version=candidate.metadata.get("embedding_version"),
            embedding_dimension=candidate.metadata.get("embedding_dimension"),
            version=1,
            status=status, replaces_id=(existing.id if resolution == Resolution.REPLACE else None),
        )
        relations = [(event.event_id, "DERIVED_FROM")]
        if resolution == Resolution.REPLACE:
            relations.append((existing.id, "REPLACES"))
        elif resolution == Resolution.CONFLICT:
            relations.append((existing.id, "CONFLICT_WITH"))
        self.repository.commit_resolution(
            item,
            expected_active_head_id=(existing.id if existing else None),
            relations=relations,
        )
        return item, True
