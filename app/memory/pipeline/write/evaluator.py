from dataclasses import dataclass


@dataclass(frozen=True)
class Evaluation:
    accepted: bool
    importance: float
    confidence: float


class MemoryEvaluator:
    def __init__(self, threshold=0.45):
        self.threshold = threshold

    def evaluate(self, candidate):
        importance = (
            0.35 * candidate.business_value + 0.25 * candidate.stability
            + 0.20 * candidate.explicitness + 0.20 * candidate.future_usefulness
        )
        return Evaluation(importance >= self.threshold, importance, candidate.confidence)
