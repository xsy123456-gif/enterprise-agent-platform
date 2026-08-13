"""KnowledgeService — the single public Knowledge API.

Agents see only ``retrieve(request, access_context)``.  Everything else
(ACL resolution, filter intersection, thresholding, evidence) is internal.
"""

import uuid

from app.knowledge.access.resolver import ScopeResolver
from app.knowledge.config import KnowledgeConfig
from app.knowledge.errors import (
    KnowledgeAccessDeniedError,
    KnowledgeInvalidRequestError,
    KnowledgeTimeoutError,
)
from app.knowledge.models.access import KnowledgeAccessContext
from app.knowledge.models.evidence import (
    Citation,
    RetrievalEvidence,
    content_hash,
)
from app.knowledge.models.request import KnowledgeRetrieveRequest
from app.knowledge.models.result import KnowledgeItem, KnowledgeRetrieveResult
from app.knowledge.ports.retriever import KnowledgeQuery, KnowledgeRetrieverPort


class KnowledgeService:
    """Black-box Knowledge Evidence Service.

    Consumes a trusted ``KnowledgeAccessContext`` (never created by the Agent)
    and an untrusted ``KnowledgeRetrieveRequest``.  ACL runs before retrieval.
    """

    def __init__(
        self,
        retriever: KnowledgeRetrieverPort,
        config: KnowledgeConfig | None = None,
        resolver: ScopeResolver | None = None,
        event_bus=None,
    ):
        if retriever is None:
            raise ValueError("KnowledgeService requires a KnowledgeRetrieverPort")
        self.retriever = retriever
        self.config = config or KnowledgeConfig()
        self.resolver = resolver or ScopeResolver()
        self.event_bus = event_bus

    async def retrieve(
        self,
        request: KnowledgeRetrieveRequest,
        access_context: KnowledgeAccessContext,
    ) -> KnowledgeRetrieveResult:
        retrieval_id = str(uuid.uuid4())
        self._publish(
            "knowledge.retrieval.started",
            {"retrieval_id": retrieval_id, "trace_id": access_context.trace_id},
        )

        if not isinstance(request, KnowledgeRetrieveRequest):
            raise KnowledgeInvalidRequestError("invalid retrieve request")

        # ACL is enforced before any backend call.
        try:
            effective_filter = self.resolver.resolve(request, access_context)
        except KnowledgeAccessDeniedError:
            self._publish(
                "knowledge.retrieval.denied",
                {"retrieval_id": retrieval_id, "trace_id": access_context.trace_id},
            )
            raise

        top_k = self.config.clamp_top_k(request.requested_top_k)

        query = KnowledgeQuery(
            query=request.query,
            effective_filter=effective_filter,
            top_k=top_k,
            trace_id=access_context.trace_id,
            language=request.language,
            score_threshold=self.config.score_threshold,
        )

        try:
            retrieval = await self.retriever.retrieve(query)
        except KnowledgeTimeoutError:
            raise
        except Exception as error:
            # Backend errors never leak native exceptions to the consumer.
            from app.knowledge.errors import KnowledgeUnavailableError

            raise KnowledgeUnavailableError(
                f"knowledge backend unavailable: {type(error).__name__}"
            ) from error

        items = [
            self._to_item(hit)
            for hit in retrieval.hits
            if hit.score >= self.config.score_threshold
        ]

        evidence = RetrievalEvidence(
            retrieval_id=retrieval_id,
            source_type="knowledge",
            document_ids=[item.document_id for item in items],
            chunk_ids=[item.chunk_id for item in items],
            scope=effective_filter.to_dict(),
            scores={item.chunk_id: item.score for item in items},
            content_hashes=[item.content_hash for item in items],
            execution_id=access_context.execution_id,
            trace_id=access_context.trace_id,
        )

        result = KnowledgeRetrieveResult(
            retrieval_id=retrieval_id,
            items=items,
            query_metadata={
                "query": request.query,
                "top_k": top_k,
                "score_threshold": self.config.score_threshold,
            },
            timing=dict(retrieval.timing),
            evidence=evidence,
            reason="ok" if items else "no_relevant_evidence",
        )

        self._publish(
            "knowledge.retrieval.completed",
            {
                "retrieval_id": retrieval_id,
                "trace_id": access_context.trace_id,
                "result_count": len(items),
            },
        )
        return result

    @staticmethod
    def _to_item(hit) -> KnowledgeItem:
        metadata = dict(hit.metadata or {})
        citation_data = metadata.get("citation") or {}
        citation = Citation(
            source_id=citation_data.get("source_id", hit.document_id),
            source_type=citation_data.get("source_type", "unknown"),
            source_name=citation_data.get("source_name", ""),
            document_id=citation_data.get("document_id", hit.document_id),
            document_version=citation_data.get("document_version", ""),
            page=citation_data.get("page"),
            section=citation_data.get("section"),
            uri_reference=citation_data.get("uri_reference"),
        )
        return KnowledgeItem(
            knowledge_id=metadata.get("knowledge_id", hit.chunk_id),
            document_id=hit.document_id,
            chunk_id=hit.chunk_id,
            content=hit.content,
            knowledge_type=metadata.get("knowledge_type", "unknown"),
            source=metadata.get("source", citation.source_name),
            citation=citation,
            score=hit.score,
            metadata=metadata,
            content_hash=content_hash(hit.content),
            document_version=metadata.get("document_version", ""),
        )

    def _publish(self, event_type, payload):
        if self.event_bus is None:
            return
        publish = getattr(self.event_bus, "publish", None)
        if callable(publish):
            publish({"event_type": event_type, **payload})
