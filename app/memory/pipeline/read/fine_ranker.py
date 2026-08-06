from datetime import datetime, timezone


class MemoryFineRanker:
    def rank(self, candidates):
        now = datetime.now(timezone.utc)
        ranked = []
        for item, similarity, _ in candidates:
            age_days = max((now - item.created_at).total_seconds() / 86400, 0)
            recency = 1 / (1 + age_days / 30)
            frequency = min(item.access_count / 10, 1.0)
            score = (
                0.35 * similarity + 0.25 * item.importance
                + 0.20 * item.confidence + 0.10 * recency + 0.10 * frequency
            )
            ranked.append((item, score))
        return sorted(ranked, key=lambda value: value[1], reverse=True)
