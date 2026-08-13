"""QdrantDocumentStore management for the Haystack adapter."""

from .config import HaystackKnowledgeConfig


class QdrantStoreManager:
    """Lazily create and hold the single QdrantDocumentStore + QdrantClient."""

    def __init__(self, config: HaystackKnowledgeConfig):
        self.config = config
        self._store = None
        self._client = None

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

    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=self.config.qdrant_url)
        return self._client

    def set_acl_metadata(self, document_id: str, full_meta: dict) -> None:
        """Atomically replace the metadata for all chunks of a document.

        Uses Qdrant ``set_payload`` with a filter selector — a single
        server-side operation.  ``full_meta`` must contain every field that
        must survive (Qdrant replaces the ``meta`` payload key wholesale).
        """
        from qdrant_client import models

        selector = models.Filter(
            must=[
                models.FieldCondition(
                    key="meta.document_id",
                    match=models.MatchValue(value=document_id),
                )
            ]
        )
        self.client.set_payload(
            collection_name=self.config.collection,
            payload={"meta": full_meta},
            points=selector,
            wait=True,
        )

    def delete_by_document_id(self, document_id: str) -> int:
        return self.store.delete_by_filter(
            {"field": "meta.document_id", "operator": "==", "value": document_id}
        )

    def count_documents_by_document_id(self, document_id: str) -> int:
        return self.store.count_documents_by_filter(
            {"field": "meta.document_id", "operator": "==", "value": document_id}
        )

    def health(self):
        try:
            count = self.store.count_documents()
            return {"name": "qdrant", "healthy": True, "documents": count}
        except Exception as error:
            return {"name": "qdrant", "healthy": False, "error": str(error)}
