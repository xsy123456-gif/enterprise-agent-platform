import json


class MemoryFineDeduplicator:
    def __init__(self, judge=None, similarity_provider=None):
        self.judge = judge
        self.similarity_provider = similarity_provider

    def similarity(self, left, right):
        if self.similarity_provider is not None:
            return self.similarity_provider(left, right)
        left_tokens = set(json.dumps(left, ensure_ascii=False).lower().split())
        right_tokens = set(json.dumps(right, ensure_ascii=False).lower().split())
        union = left_tokens | right_tokens
        return len(left_tokens & right_tokens) / len(union) if union else 1.0

    def is_duplicate(self, candidate, existing):
        if existing is None:
            return False
        score = self.similarity(candidate.content, existing.content)
        if score > 0.90:
            return True
        if score >= 0.75 and self.judge is not None:
            return bool(self.judge(candidate, existing))
        return False
