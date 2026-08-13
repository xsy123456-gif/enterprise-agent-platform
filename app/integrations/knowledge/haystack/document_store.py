"""QdrantDocumentStore management for the Haystack adapter."""

from .config import HaystackKnowledgeConfig


class QdrantStoreManager:
    """Lazily create and hold the single QdrantDocumentStore."""

    def __init__(self, config: HaystackKnowledgeConfig):
        self.config = config
        self._store = None

    @property
    def store(self):
        if self._store is None:
            from haystack_integrations.document_stores.qdrant import (
                QdrantDocumentStore,
            )

            self._store = QdrantDocumentStore(
                url=self.config.qdrant_url,
                index=self.config.collection,
                embedding_dim=self.config.embedding_dim,
                use_sparse_embeddings=self.config.use_sparse_embeddings,
                similarity=self.config.similarity,
                return_embedding=False,
            )
        return self._store

    def health(self):
        try:
            count = self.store.count_documents()
            return {"name": "qdrant", "healthy": True, "documents": count}
        except Exception as error:
            return {"name": "qdrant", "healthy": False, "error": str(error)}
