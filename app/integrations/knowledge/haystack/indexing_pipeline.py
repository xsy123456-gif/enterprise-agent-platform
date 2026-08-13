"""Indexing pipeline: SourceDocument -> chunks -> embed -> Qdrant write.

Uses a manual composition (chunk -> dense embed -> sparse embed -> write)
because chunk ids must be stable for idempotency and chunking is a
platform-owned character-window splitter (Chinese-friendly).
"""

from haystack import Document
from haystack.document_stores.types import DuplicatePolicy

from .chunking import split_text
from .config import HaystackKnowledgeConfig
from .document_store import QdrantStoreManager
from .embedders import OllamaDocumentEmbedder
from .jieba_sparse import JiebaSparseDocumentEmbedder


class IndexingPipeline:
    def __init__(self, config: HaystackKnowledgeConfig, store_manager: QdrantStoreManager):
        self.config = config
        self.store_manager = store_manager
        self._dense = None
        self._sparse = None

    @property
    def dense_embedder(self):
        if self._dense is None:
            self._dense = OllamaDocumentEmbedder(
                self.config.ollama_endpoint,
                self.config.ollama_model,
                timeout=self.config.ollama_timeout,
            )
        return self._dense

    @property
    def sparse_embedder(self):
        if self._sparse is None:
            self._sparse = JiebaSparseDocumentEmbedder(
                vocab_size=self.config.sparse_vocab_size
            )
        return self._sparse

    def run(self, document: Document) -> int:
        """Chunk, embed (dense + sparse) and write. Returns written chunk count."""
        chunks = split_text(document.content, document.meta.get("knowledge_type"))
        documents = [
            Document(
                id=f"{document.id}:{index}",
                content=chunk,
                meta=dict(document.meta),
            )
            for index, chunk in enumerate(chunks)
        ]
        if not documents:
            return 0
        documents = self.dense_embedder.run(documents=documents)["documents"]
        documents = self.sparse_embedder.run(documents=documents)["documents"]
        return self.store_manager.store.write_documents(
            documents, policy=DuplicatePolicy.OVERWRITE
        )
