from datetime import datetime, timezone


class MemoryPreRanker:
    def rank(self, candidates):
        now = datetime.now(timezone.utc)
        ranked = []
        for item, similarity in candidates:
            age_days = max((now - item.created_at).total_seconds() / 86400, 0)
            recency = 1 / (1 + age_days / 30)
            score = item.importance + item.confidence + recency
            ranked.append((item, similarity, score))
        return sorted(ranked, key=lambda value: value[2], reverse=True)
