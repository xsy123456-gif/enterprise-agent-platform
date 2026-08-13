"""Query pipeline construction.

Standard pipeline per the Knowledge design:

    Query -> Dense Embedding + Sparse Embedding -> QdrantHybridRetriever

Sparse embedding uses the real fastembed BM25 embedder (not a placeholder).
"""

from haystack import Pipeline
from haystack_integrations.components.retrievers.qdrant import (
    QdrantHybridRetriever,
)

from .config import HaystackKnowledgeConfig
from .document_store import QdrantStoreManager
from .embedders import OllamaTextEmbedder
from .jieba_sparse import JiebaSparseTextEmbedder


class QueryPipelineFactory:
    def __init__(self, config: HaystackKnowledgeConfig, store_manager: QdrantStoreManager):
        self.config = config
        self.store_manager = store_manager
        self._pipeline = None

    @property
    def pipeline(self) -> Pipeline:
        if self._pipeline is None:
            self._pipeline = self._build()
        return self._pipeline

    def _build(self) -> Pipeline:
        pipeline = Pipeline()
        pipeline.add_component(
            "dense_embedder",
            OllamaTextEmbedder(
                self.config.ollama_endpoint,
                self.config.ollama_model,
                timeout=self.config.ollama_timeout,
            ),
        )
        pipeline.add_component(
            "sparse_embedder",
            JiebaSparseTextEmbedder(vocab_size=self.config.sparse_vocab_size),
        )
        pipeline.add_component(
            "retriever",
            QdrantHybridRetriever(document_store=self.store_manager.store),
        )
        pipeline.connect("dense_embedder.embedding", "retriever.query_embedding")
        pipeline.connect(
            "sparse_embedder.sparse_embedding", "retriever.query_sparse_embedding"
        )
        return pipeline
