class Resolution:
    CREATE = "create"
    UPDATE = "update"
    REPLACE = "replace"
    CONFLICT = "conflict"


class MemoryResolver:
    def resolve(self, candidate, existing):
        if existing is None:
            return Resolution.CREATE
        if existing.content == candidate.content:
            return Resolution.UPDATE
        if candidate.metadata.get("conflict"):
            return Resolution.CONFLICT
        return (
            Resolution.REPLACE
            if candidate.confidence >= existing.confidence
            else Resolution.CONFLICT
        )
