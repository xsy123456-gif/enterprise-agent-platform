"""Hybrid vs Hybrid+Rerank comparison (real LLM reranker).

Run manually::

    python -m tests.knowledge.evaluation.run_rerank_comparison
"""

import json

from app.integrations.knowledge.haystack.llm_reranker import LLMReranker
from app.knowledge.evaluation.metrics import evaluate_queries
from app.llm.factory import create_llm

from .run_evaluation import (
    DOCUMENTS,
    QUERIES,
    _build_store,
    _ingest,
    _retrieve_hybrid,
)


def main():
    store = _build_store()
    _ingest(store)

    reranker = LLMReranker(create_llm())

    baseline, reranked = {}, {}
    for query, relevant in QUERIES:
        retrieved = _retrieve_hybrid(store, query)
        baseline[query] = {"retrieved": retrieved, "relevant": relevant}

        # Rerank the retrieved hits with the LLM reranker.
        from app.knowledge.ports.retriever import RetrievalHit

        hits = [RetrievalHit(chunk_id=doc_id, document_id=doc_id,
                             content=doc_id, score=1.0) for doc_id in retrieved]
        import asyncio

        reordered = asyncio.run(reranker.rerank(query, hits))
        reranked[query] = {
            "retrieved": [h.chunk_id for h in reordered],
            "relevant": relevant,
        }

    report = {
        "hybrid": evaluate_queries(baseline).__dict__,
        "hybrid_plus_rerank": evaluate_queries(reranked).__dict__,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
