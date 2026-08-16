"""Knowledge evaluation (Phase 15.5)."""

from dataclasses import dataclass, field

from app.core.time import utc_now


@dataclass(frozen=True)
class KnowledgeEvaluation:
    evaluation_id: str
    document_id: str
    citation_accuracy: float = 0.0
    retrieval_relevance: float = 0.0
    freshness: float = 0.0
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        for name in ("citation_accuracy", "retrieval_relevance", "freshness"):
            value = getattr(self, name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be in [0, 1]")

    def to_dict(self) -> dict:
        return {
            "evaluation_id": self.evaluation_id,
            "document_id": self.document_id,
            "citation_accuracy": self.citation_accuracy,
            "retrieval_relevance": self.retrieval_relevance,
            "freshness": self.freshness,
            "created_at": self.created_at,
        }


class KnowledgeEvaluationStore:

    def __init__(self):
        self._records = []

    def record(self, evaluation: KnowledgeEvaluation):
        self._records.append(evaluation)
        return evaluation

    def for_document(self, document_id):
        return [e for e in self._records if e.document_id == document_id]


__all__ = ["KnowledgeEvaluation", "KnowledgeEvaluationStore"]
