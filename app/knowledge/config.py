"""Knowledge subsystem configuration.

Strategy configuration lives here and is *never* exposed through the public
contract.  Retrieval strategy (embedding models, reranker, backend) is
platform-internal.
"""

from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class KnowledgeConfig:
    backend: str = "haystack"
    qdrant_url: str = "http://localhost:6333"
    collection: str = "knowledge_documents"
    dense_model: str = ""
    sparse_model: str = ""
    reranker: str = ""
    min_top_k: int = 1
    default_top_k: int = 8
    max_top_k: int = 30
    score_threshold: float = 0.0
    timeout_seconds: float = 5.0
    retry_attempts: int = 1
    security_level: str = "public"
    extra: dict = field(default_factory=dict)

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
            backend=env.get("KNOWLEDGE_BACKEND", "haystack"),
            qdrant_url=env.get("KNOWLEDGE_QDRANT_URL", "http://localhost:6333"),
            collection=env.get("KNOWLEDGE_COLLECTION", "knowledge_documents"),
            dense_model=env.get("KNOWLEDGE_DENSE_MODEL", ""),
            sparse_model=env.get("KNOWLEDGE_SPARSE_MODEL", ""),
            reranker=env.get("KNOWLEDGE_RERANKER", ""),
            min_top_k=_int("KNOWLEDGE_MIN_TOP_K", 1),
            default_top_k=_int("KNOWLEDGE_DEFAULT_TOP_K", 8),
            max_top_k=_int("KNOWLEDGE_MAX_TOP_K", 30),
            score_threshold=_float("KNOWLEDGE_SCORE_THRESHOLD", 0.0),
            timeout_seconds=_float("KNOWLEDGE_TIMEOUT", 5.0),
            retry_attempts=_int("KNOWLEDGE_RETRY_ATTEMPTS", 1),
        )

    def clamp_top_k(self, requested):
        if requested is None:
            return self.default_top_k
        return max(self.min_top_k, min(int(requested), self.max_top_k))
