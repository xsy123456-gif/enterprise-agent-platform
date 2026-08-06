class MemoryReadDeduplicator:
    def deduplicate(self, candidates):
        seen = set()
        result = []
        for item, score in candidates:
            if item.memory_key in seen:
                continue
            seen.add(item.memory_key)
            result.append((item, score))
        return result
