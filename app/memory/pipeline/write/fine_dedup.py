import json
import math


class LLMSemanticDuplicateJudge:
    """Memory-internal judge; it is not an Agent and cannot execute tools."""

    def __init__(self, llm):
        self.llm = llm

    def __call__(self, candidate, existing):
        response = self.llm.chat([
            {
                "role": "system",
                "content": (
                    "Judge whether two memory facts express the same durable fact. "
                    "Return JSON only: {\"duplicate\":true|false}."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({
                    "candidate": candidate.content,
                    "existing": existing.content,
                }, ensure_ascii=False),
            },
        ])
        text = response.strip()
        if text.startswith("```"):
            text = "\n".join(text.splitlines()[1:-1]).strip()
        try:
            result = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError("Memory duplicate judge must return JSON") from error
        if not isinstance(result, dict) or not isinstance(result.get("duplicate"), bool):
            raise ValueError("Memory duplicate judge response is invalid")
        return result["duplicate"]


class MemoryFineDeduplicator:
    def __init__(self, judge=None, merge_threshold=0.90, judge_threshold=0.75):
        self.judge = judge
        self.merge_threshold = merge_threshold
        self.judge_threshold = judge_threshold

    @staticmethod
    def similarity(left, right):
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0

    @staticmethod
    def _space_id(value):
        if hasattr(value, "metadata"):
            return value.metadata.get("embedding_space_id", "legacy-unknown")
        return getattr(value, "embedding_space_id", "legacy-unknown")

    def is_duplicate(self, candidate, existing):
        if existing is None:
            return False
        if (
            self._space_id(candidate) == "legacy-unknown"
            or self._space_id(existing) == "legacy-unknown"
            or self._space_id(candidate) != self._space_id(existing)
        ):
            return False
        score = self.similarity(candidate.embedding, existing.embedding)
        if score >= self.merge_threshold:
            return True
        if score >= self.judge_threshold and self.judge is not None:
            return bool(self.judge(candidate, existing))
        return False
