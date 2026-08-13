"""Haystack Knowledge adapter.

The only package allowed to import Haystack and Qdrant.  Exposes
``HaystackRetrieverAdapter`` which implements ``KnowledgeRetrieverPort``.
"""

from .adapter import HaystackRetrieverAdapter
from .config import HaystackKnowledgeConfig
from .document_store import QdrantStoreManager
from .query_pipeline import QueryPipelineFactory

__all__ = [
    "HaystackRetrieverAdapter",
    "HaystackKnowledgeConfig",
    "QdrantStoreManager",
    "QueryPipelineFactory",
]
