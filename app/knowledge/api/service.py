"""KnowledgeService — the single public Knowledge API.

Agents see only ``retrieve(request, access_context)``.  ACL resolution, policy
enforcement, audit, trace timing and evidence are all internal.
"""

import time
import uuid

from app.knowledge.access.policy import KnowledgePolicy
from app.knowledge.access.resolver import ScopeResolver
from app.knowledge.audit.evidence import (
    KnowledgeAuditSink,
    KnowledgeRetrievalAuditRecord,
)
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
    query_hash,
)
from app.knowledge.models.request import KnowledgeRetrieveRequest
from app.knowledge.models.result import KnowledgeItem, KnowledgeRetrieveResult
from app.knowledge.ports.retriever import KnowledgeQuery, KnowledgeRetrieverPort


class KnowledgeService:
    """Black-box Knowledge Evidence Service."""

    def __init__(
        self,
        retriever: KnowledgeRetrieverPort,
        config: KnowledgeConfig | None = None,
        resolver: ScopeResolver | None = None,
        policy: KnowledgePolicy | None = None,
        audit_sink: KnowledgeAuditSink | None = None,
        event_bus=None,
    ):
        if retriever is None:
            raise ValueError("KnowledgeService requires a KnowledgeRetrieverPort")
        self.retriever = retriever
        self.config = config or KnowledgeConfig()
        self.resolver = resolver or ScopeResolver()
        self.policy = policy or KnowledgePolicy()
        self.audit_sink = audit_sink
        self.event_bus = event_bus

    async def retrieve(
        self,
        request: KnowledgeRetrieveRequest,
        access_context: KnowledgeAccessContext,
    ) -> KnowledgeRetrieveResult:
        retrieval_id = str(uuid.uuid4())
        started = time.monotonic()
        timing: dict[str, float] = {}
        warnings: list[str] = []

        self._publish(
            "knowledge.retrieval.started",
            {"retrieval_id": retrieval_id, "trace_id": access_context.trace_id},
        )

        if not isinstance(request, KnowledgeRetrieveRequest):
            raise KnowledgeInvalidRequestError("invalid retrieve request")

        # 1. ACL resolution (before any backend call).
        t0 = time.monotonic()
        try:
            effective_filter = self.resolver.resolve(request, access_context)
        except KnowledgeAccessDeniedError as error:
            timing["access_resolve"] = time.monotonic() - t0
            self._emit_denied(retrieval_id, access_context, effective_filter=None)
            self._audit(
                retrieval_id, access_context, request, None, "denied", 0,
                time.monotonic() - started,
            )
            raise
        timing["access_resolve"] = time.monotonic() - t0

        # 2. Policy evaluation (default deny).
        t0 = time.monotonic()
        decision = self.policy.evaluate(access_context, effective_filter)
        timing["policy_evaluate"] = time.monotonic() - t0
        if not decision.allowed:
            self._emit_denied(retrieval_id, access_context, effective_filter)
            self._audit(
                retrieval_id, access_context, request, effective_filter, "denied",
                0, time.monotonic() - started,
            )
            raise KnowledgeAccessDeniedError(decision.reason)

        top_k = self.config.clamp_top_k(request.requested_top_k)
        query = KnowledgeQuery(
            query=request.query,
            effective_filter=effective_filter,
            top_k=top_k,
            trace_id=access_context.trace_id,
            language=request.language,
            score_threshold=self.config.score_threshold,
        )

        # 3. Retrieve.
        t0 = time.monotonic()
        try:
            retrieval = await self.retriever.retrieve(query)
        except KnowledgeTimeoutError:
            self._emit_failed(retrieval_id, access_context)
            raise
        except Exception as error:
            self._emit_failed(retrieval_id, access_context)
            from app.knowledge.errors import KnowledgeUnavailableError

            raise KnowledgeUnavailableError(
                f"knowledge backend unavailable: {type(error).__name__}"
            ) from error
        timing["retrieval"] = time.monotonic() - t0

        # 4. Map + threshold.
        t0 = time.monotonic()
        items = [
            self._to_item(hit)
            for hit in retrieval.hits
            if hit.score >= self.config.score_threshold
        ]
        timing["mapping"] = time.monotonic() - t0

        evidence = RetrievalEvidence(
            retrieval_id=retrieval_id,
            source_type="knowledge",
            document_ids=[item.document_id for item in items],
            chunk_ids=[item.chunk_id for item in items],
            scope=effective_filter.to_dict(),
            scores={item.chunk_id: item.score for item in items},
            content_hashes=[item.content_hash for item in items],
            document_versions=[item.document_version for item in items],
            acl_versions=[
                int(item.metadata.get("acl_version", 1))
                for item in items
            ],
            index_versions=[
                int(item.metadata.get("index_version", 1))
                for item in items
            ],
            execution_id=access_context.execution_id,
            trace_id=access_context.trace_id,
        )

        timing["total"] = time.monotonic() - started
        result = KnowledgeRetrieveResult(
            retrieval_id=retrieval_id,
            items=items,
            query_metadata={
                "query": request.query,
                "top_k": top_k,
                "score_threshold": self.config.score_threshold,
            },
            timing=timing,
            evidence=evidence,
            warnings=warnings,
            reason="ok" if items else "no_relevant_evidence",
        )

        self._audit(
            retrieval_id, access_context, request, effective_filter, "allow",
            len(items), timing["total"],
        )
        if items:
            self._publish(
                "knowledge.retrieval.completed",
                {
                    "retrieval_id": retrieval_id,
                    "trace_id": access_context.trace_id,
                    "result_count": len(items),
                },
            )
        else:
            self._publish(
                "knowledge.retrieval.empty",
                {"retrieval_id": retrieval_id, "trace_id": access_context.trace_id},
            )
        return result

    def _emit_denied(self, retrieval_id, access_context, effective_filter):
        self._publish(
            "knowledge.retrieval.denied",
            {
                "retrieval_id": retrieval_id,
                "trace_id": access_context.trace_id,
                "tenant_id": access_context.tenant_id,
            },
        )

    def _emit_failed(self, retrieval_id, access_context):
        self._publish(
            "knowledge.retrieval.failed",
            {"retrieval_id": retrieval_id, "trace_id": access_context.trace_id},
        )

    def _audit(self, retrieval_id, access_context, request, effective_filter,
               decision, result_count, latency_ms):
        if self.audit_sink is None:
            return
        record = KnowledgeRetrievalAuditRecord(
            retrieval_id=retrieval_id,
            execution_id=access_context.execution_id,
            trace_id=access_context.trace_id,
            user_id=access_context.user_id,
            tenant_id=access_context.tenant_id,
            query_hash=query_hash(request.query),
            requested_scope={
                "knowledge_types": list(request.knowledge_types or []),
                "business_filters": dict(request.business_filters or {}),
            },
            effective_scope=(
                effective_filter.to_dict() if effective_filter is not None else {}
            ),
            result_count=result_count,
            decision=decision,
            latency_ms=round(latency_ms * 1000, 2),
        )
        try:
            self.audit_sink.save(record)
        except Exception:
            # Audit failure must not turn a successful retrieval into a failure.
            pass

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
