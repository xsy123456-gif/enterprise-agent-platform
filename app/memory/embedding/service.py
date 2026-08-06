import math

from app.memory.embedding.models import EmbeddingResult


class EmbeddingDimensionError(ValueError):
    pass


class EmbeddingService:
    """Provider-independent validation boundary for Memory embeddings."""

    def __init__(self, provider, expected_dimension):
        if not isinstance(expected_dimension, int) or expected_dimension < 1:
            raise ValueError("expected_dimension must be a positive integer")
        self.provider = provider
        self.expected_dimension = expected_dimension

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
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("Embedding vector contains a non-finite value")
        return EmbeddingResult(
            vector=vector, model=result.model, version=result.version,
            dimension=result.dimension,
        )
