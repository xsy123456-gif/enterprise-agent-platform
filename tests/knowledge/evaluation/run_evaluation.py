"""Knowledge retrieval quality evaluation (real Ollama + Qdrant + FastEmbed).

Run manually::

    python -m tests.knowledge.evaluation.run_evaluation

Compares Dense / Sparse / Hybrid on a small Chinese e-commerce dataset and
reports Recall@K, Precision@K, MRR, Hit Rate.  This is the evidence base for
the BM25-Chinese quality decision (BLOCKER-02).
"""

import json

from haystack import Document
from haystack_integrations.components.retrievers.qdrant import (
    QdrantEmbeddingRetriever,
    QdrantHybridRetriever,
    QdrantSparseEmbeddingRetriever,
)

from app.integrations.knowledge.haystack.document_store import QdrantStoreManager
from app.integrations.knowledge.haystack.embedders import (
    OllamaDocumentEmbedder,
    OllamaTextEmbedder,
)
from app.integrations.knowledge.haystack.jieba_sparse import (
    JiebaSparseDocumentEmbedder,
    JiebaSparseTextEmbedder,
)
from app.integrations.knowledge.haystack.config import HaystackKnowledgeConfig
from app.knowledge.evaluation.metrics import evaluate_queries

COLLECTION = "knowledge_eval"

DOCUMENTS = [
    ("doc-return", "日本站商品退货期限为30天，自签收之日起计算。超过30天不支持退货。"),
    ("doc-exchange", "换货期限为15天，商品须保持未使用状态并保留原包装。"),
    ("doc-refund", "退款将在7个工作日内原路退回。"),
    ("doc-charger", "这款充电器支持100V到240V宽电压，全球通用。"),
    ("doc-cotton", "这件衣服是纯棉材质，洗涤后可能有1到3厘米的轻微缩水。"),
    ("doc-size", "尺寸不合适可以免费申请换货一次。"),
    ("doc-ads", "广告ACOS突然升高，先检查竞价设置、关键词匹配和广告预算。"),
    ("doc-shipping", "标准配送时效为3到5个工作日。"),
]

QUERIES = [
    ("日本站买了15天还能退货吗", ["doc-return"]),
    ("衣服洗了会缩水吗", ["doc-cotton"]),
    ("充电器支持100V吗", ["doc-charger"]),
    ("退款多久能到账", ["doc-refund"]),
    ("广告ACOS高了应该先查什么", ["doc-ads"]),
    ("尺寸不合适怎么办", ["doc-size"]),
    ("多久能送到", ["doc-shipping"]),
]


def main():
    config = HaystackKnowledgeConfig(
        collection=COLLECTION,
        ollama_endpoint="http://172.25.192.1:11434",
        ollama_model="bge-m3",
        embedding_dim=1024,
    )
    store_manager = QdrantStoreManager(config)
    store = store_manager.store

    dense_doc = OllamaDocumentEmbedder(config.ollama_endpoint, config.ollama_model)
    sparse_doc = JiebaSparseDocumentEmbedder(vocab_size=config.sparse_vocab_size)
    dense_text = OllamaTextEmbedder(config.ollama_endpoint, config.ollama_model)
    sparse_text = JiebaSparseTextEmbedder(vocab_size=config.sparse_vocab_size)

    # Ingest
    docs = []
    for doc_id, content in DOCUMENTS:
        docs.append(Document(id=doc_id, content=content, meta={"document_id": doc_id}))
    docs = dense_doc.run(documents=docs)["documents"]
    docs = sparse_doc.run(documents=docs)["documents"]
    store.write_documents(docs, policy="overwrite")

    dense_retriever = QdrantEmbeddingRetriever(document_store=store)
    sparse_retriever = QdrantSparseEmbeddingRetriever(document_store=store)
    hybrid_retriever = QdrantHybridRetriever(document_store=store)

    def retrieve(retriever, query, *, sparse=False, hybrid=False):
        query_embedding = dense_text.run(query)["embedding"]
        if hybrid:
            query_sparse = sparse_text.run(query)["sparse_embedding"]
            out = retriever.run(query_embedding=query_embedding, query_sparse_embedding=query_sparse, top_k=3)
        elif sparse:
            query_sparse = sparse_text.run(query)["sparse_embedding"]
            out = retriever.run(query_sparse_embedding=query_sparse, top_k=3)
        else:
            out = retriever.run(query_embedding=query_embedding, top_k=3)
        return [d.id for d in out["documents"]]

    dense_results, sparse_results, hybrid_results = {}, {}, {}
    for query, relevant in QUERIES:
        dense_results[query] = {"retrieved": retrieve(dense_retriever, query), "relevant": relevant}
        sparse_results[query] = {"retrieved": retrieve(sparse_retriever, query, sparse=True), "relevant": relevant}
        hybrid_results[query] = {"retrieved": retrieve(hybrid_retriever, query, hybrid=True), "relevant": relevant}

    report = {
        "dense": evaluate_queries(dense_results).__dict__,
        "sparse": evaluate_queries(sparse_results).__dict__,
        "hybrid": evaluate_queries(hybrid_results).__dict__,
        "sparse_details": sparse_results,
        "hybrid_details": hybrid_results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
