class MemoryCandidateFusion:
    """Deduplicates SQL/vector candidates and normalizes their relevance scores."""

    def fuse(self, sql_candidates, vector_candidates):
        merged = {}
        for item, score in sql_candidates:
            entry = merged.setdefault(item.id, {"item": item, "sql": 0.0, "vector": None})
            entry["sql"] = max(entry["sql"], min(max(float(score), 0.0), 1.0))
        for item, score in vector_candidates:
            entry = merged.setdefault(item.id, {"item": item, "sql": 0.0, "vector": None})
            normalized = min(max((float(score) + 1.0) / 2.0, 0.0), 1.0)
            entry["vector"] = max(entry["vector"] or 0.0, normalized)
        candidates = []
        for entry in merged.values():
            semantic_score = max(entry["sql"] * 0.90, entry["vector"] or 0.0)
            candidates.append((entry["item"], semantic_score))
        return sorted(candidates, key=lambda value: value[1], reverse=True)
