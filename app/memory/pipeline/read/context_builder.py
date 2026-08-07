from app.memory.models.context import MemoryContext, MemoryReference


class MemoryContextBuilder:
    def build(self, summary, candidates):
        return MemoryContext(
            summary=summary,
            references=[MemoryReference(
                memory_id=item.id, type=item.type,
                entity_id=getattr(item, "entity_id", ""),
                attribute=getattr(item, "attribute", ""),
                content=getattr(item, "content", None),
                confidence=item.confidence,
                importance=item.importance,
                relevance_score=score,
                created_at=item.created_at,
            ) for item, score in candidates],
        )
