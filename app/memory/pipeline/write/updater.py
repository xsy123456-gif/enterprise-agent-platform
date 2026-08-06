from app.memory.models.item import MemoryItem, MemoryItemStatus
from app.memory.pipeline.write.resolver import Resolution


class MemoryUpdater:
    def __init__(self, repository):
        self.repository = repository

    def persist(self, event, candidate, evaluation, importance, resolution, existing):
        if resolution == Resolution.UPDATE:
            return existing, False
        version = existing.version + 1 if existing else 1
        status = MemoryItemStatus.CONFLICT if resolution == Resolution.CONFLICT else MemoryItemStatus.ACTIVE
        item = MemoryItem(
            memory_key=candidate.memory_key, type=candidate.type, content=candidate.content,
            importance=importance, confidence=evaluation.confidence, source=candidate.source,
            tenant_id=event.tenant_id, department_id=event.department_id,
            user_id=event.user_id, agent_id=event.agent_id, version=version,
            status=status, replaces_id=(existing.id if resolution == Resolution.REPLACE else None),
        )
        self.repository.create_item(item)
        if resolution == Resolution.REPLACE:
            self.repository.link_replacement(existing.id, item.id)
        return item, True
