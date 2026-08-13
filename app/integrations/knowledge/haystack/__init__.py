"""Haystack Knowledge adapter.

The only package allowed to import Haystack and Qdrant.  Exposes the retrieval
adapter (``KnowledgeRetrieverPort``) and the ingestion adapter
(``KnowledgeIngestionPort``).
"""

from .adapter import HaystackRetrieverAdapter
from .config import HaystackKnowledgeConfig
from .document_store import QdrantStoreManager
from .indexing_pipeline import IndexingPipeline
from .ingestion_adapter import HaystackIngestionAdapter
from .query_pipeline import QueryPipelineFactory

__all__ = [
    "HaystackRetrieverAdapter",
    "HaystackIngestionAdapter",
    "HaystackKnowledgeConfig",
    "QdrantStoreManager",
    "IndexingPipeline",
    "QueryPipelineFactory",
]
