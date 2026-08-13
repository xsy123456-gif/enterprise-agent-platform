"""Haystack retriever adapter — the only place Haystack/Qdrant may appear.

Implements ``KnowledgeRetrieverPort`` so the Knowledge core never imports
Haystack or Qdrant.  Backend exceptions are mapped to platform errors here.
"""

from app.knowledge.errors import KnowledgeUnavailableError
from app.knowledge.ports.retriever import KnowledgeQuery, KnowledgeRetrieval, KnowledgeRetrieverPort

from .config import HaystackKnowledgeConfig
from .document_store import QdrantStoreManager
from .filters import build_filter
from .mapper import document_to_hit
from .query_pipeline import QueryPipelineFactory


class HaystackRetrieverAdapter(KnowledgeRetrieverPort):
    def __init__(
        self,
        config: HaystackKnowledgeConfig | None = None,
        store_manager: QdrantStoreManager | None = None,
        pipeline_factory: QueryPipelineFactory | None = None,
    ):
        self.config = config or HaystackKnowledgeConfig()
        self.store_manager = store_manager or QdrantStoreManager(self.config)
        self.pipeline_factory = pipeline_factory or QueryPipelineFactory(
            self.config, self.store_manager
        )

    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeRetrieval:
        filter_dict = build_filter(query.effective_filter, self.config)
        try:
            result = self.pipeline_factory.pipeline.run(
                {
                    "dense_embedder": {"text": query.query},
                    "sparse_embedder": {"text": query.query},
                    "retriever": {
                        "filters": filter_dict,
                        "top_k": query.top_k,
                        "score_threshold": query.score_threshold or None,
                    },
                }
            )
        except KnowledgeUnavailableError:
            raise
        except Exception as error:
            # Native Qdrant/embedding errors never leak to the consumer.
            raise KnowledgeUnavailableError(
                f"knowledge backend unavailable: {type(error).__name__}"
            ) from error

        documents = result.get("retriever", {}).get("documents", [])
        hits = [document_to_hit(document) for document in documents]
        return KnowledgeRetrieval(hits=hits, timing={})

    def health(self):
        return self.store_manager.health()
