"""Retrieval evaluation metrics (Recall@K, Precision@K, MRR, Hit Rate)."""

from dataclasses import dataclass, field


@dataclass
class RetrievalMetrics:
    recall_at_k: float = 0.0
    precision_at_k: float = 0.0
    mrr: float = 0.0
    hit_rate: float = 0.0


def _recall(retrieved_ids, relevant_ids, k):
    top = retrieved_ids[:k]
    return len(set(top) & set(relevant_ids)) / len(relevant_ids) if relevant_ids else 0.0


def _precision(retrieved_ids, relevant_ids, k):
    top = retrieved_ids[:k]
    return len(set(top) & set(relevant_ids)) / k if k else 0.0


def _reciprocal_rank(retrieved_ids, relevant_ids):
    relevant = set(relevant_ids)
    for index, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant:
            return 1.0 / index
    return 0.0


def evaluate_queries(query_results: dict[str, dict], k: int = 3) -> RetrievalMetrics:
    """``query_results`` maps query -> {"retrieved": [ids], "relevant": [ids]}."""
    recalls, precisions, mrrs, hits = [], [], [], []
    for result in query_results.values():
        retrieved = result.get("retrieved", [])
        relevant = result.get("relevant", [])
        recalls.append(_recall(retrieved, relevant, k))
        precisions.append(_precision(retrieved, relevant, k))
        mrrs.append(_reciprocal_rank(retrieved, relevant))
        hits.append(1.0 if set(retrieved[:k]) & set(relevant) else 0.0)
    n = len(query_results) or 1
    return RetrievalMetrics(
        recall_at_k=sum(recalls) / n,
        precision_at_k=sum(precisions) / n,
        mrr=sum(mrrs) / n,
        hit_rate=sum(hits) / n,
    )


@dataclass
class StrategyComparison:
    dense: RetrievalMetrics = field(default_factory=RetrievalMetrics)
    sparse: RetrievalMetrics = field(default_factory=RetrievalMetrics)
    hybrid: RetrievalMetrics = field(default_factory=RetrievalMetrics)
