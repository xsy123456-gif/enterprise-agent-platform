"""Knowledge backend integrations.

Backend adapters (Haystack, ...) live here and are the only place third-party
RAG/vector-store dependencies may be imported.
"""

from .haystack import (
    HaystackIngestionAdapter,
    HaystackKnowledgeConfig,
    HaystackRetrieverAdapter,
    IndexingPipeline,
    QdrantStoreManager,
    QueryPipelineFactory,
)

__all__ = [
    "HaystackRetrieverAdapter",
    "HaystackIngestionAdapter",
    "HaystackKnowledgeConfig",
    "QdrantStoreManager",
    "IndexingPipeline",
    "QueryPipelineFactory",
]
