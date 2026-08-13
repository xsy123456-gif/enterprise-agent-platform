"""Knowledge backend integrations.

Backend adapters (Haystack, ...) live here and are the only place third-party
RAG/vector-store dependencies may be imported.
"""

from .haystack import (
    HaystackKnowledgeConfig,
    HaystackRetrieverAdapter,
    QdrantStoreManager,
    QueryPipelineFactory,
)

__all__ = [
    "HaystackRetrieverAdapter",
    "HaystackKnowledgeConfig",
    "QdrantStoreManager",
    "QueryPipelineFactory",
]
