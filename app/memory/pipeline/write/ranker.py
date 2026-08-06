class MemoryRanker:
    def rank(self, candidate):
        return (
            0.25 * candidate.explicitness + 0.25 * candidate.business_value
            + 0.20 * candidate.stability + 0.15 * candidate.frequency
            + 0.15 * candidate.recency
        )
