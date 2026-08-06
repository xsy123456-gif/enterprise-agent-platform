from app.memory.models.context import MemoryContext, MemoryReference


class MemoryContextBuilder:
    def build(self, summary, candidates):
        return MemoryContext(
            summary=summary,
            references=[MemoryReference(
                memory_id=item.id, type=item.type, confidence=item.confidence,
                importance=item.importance, created_at=item.created_at,
            ) for item, _ in candidates],
        )
