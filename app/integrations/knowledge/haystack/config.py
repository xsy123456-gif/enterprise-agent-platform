"""Haystack adapter configuration.

All retrieval strategy (embedding models, collection, security levels) is
adapter-internal and never leaks into the platform contract.
"""

from dataclasses import dataclass, field
import os

SECURITY_LEVELS = ("public", "internal", "confidential", "restricted")


@dataclass(frozen=True)
class HaystackKnowledgeConfig:
    qdrant_url: str = "http://localhost:6333"
    collection: str = "knowledge_documents"
    embedding_dim: int = 1024
    use_sparse_embeddings: bool = True
    similarity: str = "cosine"
    ollama_endpoint: str = "http://localhost:11434"
    ollama_model: str = "bge-m3"
    ollama_timeout: float = 30.0
    sparse_vocab_size: int = 10000
    security_levels: tuple[str, ...] = SECURITY_LEVELS

    @classmethod
    def from_environment(cls, environ=None):
        env = dict(os.environ if environ is None else environ)

        def _int(key, default):
            try:
                return int(env[key])
            except (KeyError, ValueError):
                return default

        def _float(key, default):
            try:
                return float(env[key])
            except (KeyError, ValueError):
                return default

        return cls(
            qdrant_url=env.get("KNOWLEDGE_QDRANT_URL", "http://localhost:6333"),
            collection=env.get("KNOWLEDGE_COLLECTION", "knowledge_documents"),
            embedding_dim=_int("KNOWLEDGE_EMBEDDING_DIMENSION", 1024),
            use_sparse_embeddings=env.get(
                "KNOWLEDGE_USE_SPARSE", "true"
            ).lower() not in {"false", "0", "no"},
            similarity=env.get("KNOWLEDGE_SIMILARITY", "cosine"),
            ollama_endpoint=env.get(
                "KNOWLEDGE_EMBEDDING_ENDPOINT", "http://localhost:11434"
            ),
            ollama_model=env.get("KNOWLEDGE_DENSE_MODEL", "bge-m3"),
            ollama_timeout=_float("KNOWLEDGE_EMBEDDING_TIMEOUT", 30.0),
            sparse_vocab_size=_int("KNOWLEDGE_SPARSE_VOCAB_SIZE", 10000),
        )

    def allowed_levels(self, clearance: str) -> list[str]:
        levels = list(self.security_levels)
        try:
            index = levels.index(clearance)
        except ValueError:
            return ["public"]
        return levels[: index + 1]
