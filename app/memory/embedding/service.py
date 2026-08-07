import math

from app.memory.embedding.models import EmbeddingResult, EmbeddingSpace


class EmbeddingDimensionError(ValueError):
    pass


class EmbeddingService:
    """Provider-independent validation boundary for Memory embeddings."""

    def __init__(self, provider, expected_dimension, space=None):
        if not isinstance(expected_dimension, int) or expected_dimension < 1:
            raise ValueError("expected_dimension must be a positive integer")
        self.provider = provider
        self.expected_dimension = expected_dimension
        if space is not None and not isinstance(space, EmbeddingSpace):
            raise TypeError("space must be an EmbeddingSpace")
        if space is not None and space.dimension != expected_dimension:
            raise EmbeddingDimensionError(
                "Configured embedding space dimension does not match storage"
            )
        self.space = space

    def embed(self, text):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Embedding text must not be empty")
        result = self.provider.embed(text)
        if not isinstance(result, EmbeddingResult):
            raise TypeError("Embedding provider must return EmbeddingResult")
        vector = [float(value) for value in result.vector]
        if result.dimension != len(vector):
            raise EmbeddingDimensionError(
                "Embedding provider dimension metadata does not match its vector"
            )
        if result.dimension != self.expected_dimension:
            raise EmbeddingDimensionError(
                f"Expected embedding dimension {self.expected_dimension}, "
                f"got {result.dimension} from {result.model}"
            )
        if self.space is not None and result.space_id != self.space.space_id:
            raise ValueError(
                "Embedding provider returned a vector from a different space"
            )
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("Embedding vector contains a non-finite value")
        return EmbeddingResult(
            vector=vector, space=result.space,
        )
