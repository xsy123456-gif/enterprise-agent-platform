"""Knowledge retrieval quality evaluation (real Ollama + Qdrant + jieba sparse).

Run manually::

    python -m tests.knowledge.evaluation.run_evaluation

Compares Dense / Sparse / Hybrid on a Chinese e-commerce dataset and reports
Recall@K, Precision@K, MRR, Hit Rate.  This is the evidence base for the
Chinese sparse quality decision.
"""

import json

from haystack import Document
from haystack_integrations.components.retrievers.qdrant import (
    QdrantEmbeddingRetriever,
    QdrantHybridRetriever,
    QdrantSparseEmbeddingRetriever,
)

from app.integrations.knowledge.haystack.config import HaystackKnowledgeConfig
from app.integrations.knowledge.haystack.document_store import QdrantStoreManager
from app.integrations.knowledge.haystack.embedders import (
    OllamaDocumentEmbedder,
    OllamaTextEmbedder,
)
from app.integrations.knowledge.haystack.jieba_sparse import (
    JiebaSparseDocumentEmbedder,
    JiebaSparseTextEmbedder,
)
from app.knowledge.evaluation.metrics import evaluate_queries

COLLECTION = "knowledge_eval"

DOCUMENTS = [
    ("doc-return", "日本站商品退货期限为30天，自签收之日起计算。超过30天不支持退货。"),
    ("doc-exchange", "换货期限为15天，商品须保持未使用状态并保留原包装。"),
    ("doc-refund", "退款将在7个工作日内原路退回。"),
    ("doc-charger", "这款充电器支持100V到240V宽电压，全球通用。"),
    ("doc-cotton", "这件衣服是纯棉材质，洗涤后可能有1到3厘米的轻微缩水。"),
    ("doc-size", "尺寸不合适可以免费申请换货一次。"),
    ("doc-ads-sop", "广告ACOS突然升高，先检查竞价设置、关键词匹配和广告预算。"),
    ("doc-shipping", "标准配送时效为3到5个工作日。"),
    ("doc-battery", "这款电池循环寿命约500次，正常使用约两年。"),
    ("doc-warranty", "电子产品整机保修期为一年，非人为损坏免费维修。"),
    ("doc-coupon", "优惠券在结算页面输入券码使用，部分商品不参与活动。"),
    ("doc-invoice", "电子发票在订单完成后自动开具，可在线下载。"),
    ("doc-listing", "商品上架需要提供产品名称、规格参数、实拍图片和质检报告。"),
    ("doc-ad-rule", "广告素材不得含有绝对化用语，如最、第一、顶级等。"),
    ("doc-review-rule", "禁止诱导好评或虚假评价，违规将下架处理。"),
    ("doc-payment", "支持信用卡、借记卡和第三方支付，跨境订单收取手续费。"),
    ("doc-package", "易碎商品使用防震包装，包装箱需粘贴易碎标识。"),
    ("doc-service-sop", "客服收到投诉先安抚情绪，记录订单号，按流程升级处理。"),
    ("doc-publish-sop", "商品发布先填写基础信息，再上传图片，最后提交审核。"),
    ("doc-refund-sop", "退款处理先核实订单状态，再发起退款，最后通知客户。"),
]

QUERIES = [
    ("日本站买了15天还能退货吗", ["doc-return"]),
    ("衣服洗了会缩水吗", ["doc-cotton"]),
    ("充电器支持100V吗", ["doc-charger"]),
    ("退款多久能到账", ["doc-refund"]),
    ("广告ACOS高了应该先查什么", ["doc-ads-sop"]),
    ("尺寸不合适怎么办", ["doc-size"]),
    ("多久能送到", ["doc-shipping"]),
    ("电池能用多久", ["doc-battery"]),
    ("商品保修多久", ["doc-warranty"]),
    ("优惠券怎么用", ["doc-coupon"]),
    ("商品上架需要什么材料", ["doc-listing"]),
    ("客服接到投诉怎么处理", ["doc-service-sop"]),
]


def _config():
    return HaystackKnowledgeConfig(
        collection=COLLECTION,
        ollama_endpoint="http://172.25.192.1:11434",
        ollama_model="bge-m3",
        embedding_dim=1024,
    )


def _build_store():
    return QdrantStoreManager(_config()).store


def _embedders():
    config = _config()
    return (
        OllamaDocumentEmbedder(config.ollama_endpoint, config.ollama_model),
        JiebaSparseDocumentEmbedder(vocab_size=config.sparse_vocab_size),
        OllamaTextEmbedder(config.ollama_endpoint, config.ollama_model),
        JiebaSparseTextEmbedder(vocab_size=config.sparse_vocab_size),
    )


def _ingest(store):
    dense_doc, sparse_doc, _, _ = _embedders()
    docs = [
        Document(id=doc_id, content=content, meta={"document_id": doc_id})
        for doc_id, content in DOCUMENTS
    ]
    docs = dense_doc.run(documents=docs)["documents"]
    docs = sparse_doc.run(documents=docs)["documents"]
    store.write_documents(docs, policy="overwrite")


def _retrieve_hybrid(store, query):
    _, _, dense_text, sparse_text = _embedders()
    query_embedding = dense_text.run(query)["embedding"]
    query_sparse = sparse_text.run(query)["sparse_embedding"]
    retriever = QdrantHybridRetriever(document_store=store)
    out = retriever.run(
        query_embedding=query_embedding, query_sparse_embedding=query_sparse, top_k=3
    )
    return [d.id for d in out["documents"]]


def _retrieve_dense(store, query):
    _, _, dense_text, _ = _embedders()
    query_embedding = dense_text.run(query)["embedding"]
    out = QdrantEmbeddingRetriever(document_store=store).run(
        query_embedding=query_embedding, top_k=3
    )
    return [d.id for d in out["documents"]]


def _retrieve_sparse(store, query):
    _, _, _, sparse_text = _embedders()
    query_sparse = sparse_text.run(query)["sparse_embedding"]
    out = QdrantSparseEmbeddingRetriever(document_store=store).run(
        query_sparse_embedding=query_sparse, top_k=3
    )
    return [d.id for d in out["documents"]]


def main():
    store = _build_store()
    _ingest(store)

    dense_results, sparse_results, hybrid_results = {}, {}, {}
    for query, relevant in QUERIES:
        dense_results[query] = {"retrieved": _retrieve_dense(store, query), "relevant": relevant}
        sparse_results[query] = {"retrieved": _retrieve_sparse(store, query), "relevant": relevant}
        hybrid_results[query] = {"retrieved": _retrieve_hybrid(store, query), "relevant": relevant}

    report = {
        "dense": evaluate_queries(dense_results).__dict__,
        "sparse": evaluate_queries(sparse_results).__dict__,
        "hybrid": evaluate_queries(hybrid_results).__dict__,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
