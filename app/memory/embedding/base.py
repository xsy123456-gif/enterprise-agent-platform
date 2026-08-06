from abc import ABC, abstractmethod


class EmbeddingProviderError(RuntimeError):
    pass


class BaseEmbedding(ABC):
    @abstractmethod
    def embed(self, text):
        """Return an EmbeddingResult for text without applying Memory policy."""
