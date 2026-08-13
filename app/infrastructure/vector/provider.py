class VectorStoreProvider:
    """Qdrant connectivity boundary; no RAG behavior lives here."""

    def __init__(self, url="http://localhost:6333"):
        self.url = url
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError as error:
                raise RuntimeError("qdrant-client is required for Qdrant") from error
            self._client = QdrantClient(url=self.url)
        return self._client

    def health(self):
        try:
            self.client.get_collections()
            return {"name": "vector", "healthy": True}
        except Exception as error:
            return {"name": "vector", "healthy": False, "error": str(error)}
