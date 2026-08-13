"""Phase 5 audit / trace / evidence / event tests (no backend required)."""

import unittest

from app.knowledge import (
    InMemoryKnowledgeAuditSink,
    KnowledgeAccessContext,
    KnowledgeAccessDeniedError,
    KnowledgeConfig,
    KnowledgeRetrieveRequest,
    KnowledgeService,
    KnowledgeQuery,
    KnowledgeRetrieval,
    KnowledgeRetrieverPort,
    RetrievalHit,
)


class _EventRecorder:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


def _hit():
    return RetrievalHit(
        chunk_id="doc-1:v1:1:0",
        document_id="doc-1",
        content="机密内容：日本站退货期限30天",
        score=0.9,
        metadata={
            "document_version": "2026.08",
            "acl_version": 3,
            "index_version": 2,
            "knowledge_type": "policy",
            "citation": {"source_id": "P1", "source_type": "policy",
                         "document_version": "2026.08", "page": "17"},
        },
    )


class _HitRetriever(KnowledgeRetrieverPort):
    def __init__(self, hits=None):
        self.hits = hits or []

    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeRetrieval:
        return KnowledgeRetrieval(hits=self.hits, timing={"retrieval": 0.01})


def _ctx():
    return KnowledgeAccessContext(
        tenant_id="tenant_A", user_id="u1", role="sales",
        authorized_store_ids=("JP01",), authorized_regions=("JP",),
        authorized_knowledge_scopes=("policy",), security_clearance="public",
    )


class AuditTraceTest(unittest.IsolatedAsyncioTestCase):
    def _service(self, hits=None):
        sink = InMemoryKnowledgeAuditSink()
        events = _EventRecorder()
        service = KnowledgeService(
            _HitRetriever(hits), config=KnowledgeConfig(),
            audit_sink=sink, event_bus=events,
        )
        return service, sink, events

    async def test_retrieval_produces_audit_evidence_and_events(self):
        service, sink, events = self._service([_hit()])
        result = await service.retrieve(KnowledgeRetrieveRequest(query="退货"), _ctx())
        self.assertEqual(1, len(result.items))
        self.assertIsNotNone(result.evidence)
        self.assertEqual(["doc-1"], result.evidence.document_ids)
        self.assertEqual(["2026.08"], result.evidence.document_versions)
        self.assertEqual([3], result.evidence.acl_versions)
        self.assertEqual([2], result.evidence.index_versions)
        self.assertEqual(1, len(sink.records))
        types = [e["event_type"] for e in events.events]
        self.assertIn("knowledge.retrieval.started", types)
        self.assertIn("knowledge.retrieval.completed", types)

    async def test_empty_retrieval_emits_empty_event(self):
        service, sink, events = self._service([])
        result = await service.retrieve(KnowledgeRetrieveRequest(query="无"), _ctx())
        self.assertEqual("no_relevant_evidence", result.reason)
        types = [e["event_type"] for e in events.events]
        self.assertIn("knowledge.retrieval.empty", types)

    async def test_denied_emits_denied_and_no_evidence(self):
        service, sink, events = self._service([_hit()])
        with self.assertRaises(KnowledgeAccessDeniedError):
            await service.retrieve(
                KnowledgeRetrieveRequest(query="x", business_filters={"store_ids": ["JP99"]}),
                _ctx(),
            )
        types = [e["event_type"] for e in events.events]
        self.assertIn("knowledge.retrieval.denied", types)
        self.assertNotIn("knowledge.retrieval.completed", types)

    async def test_audit_record_has_no_content(self):
        service, sink, events = self._service([_hit()])
        await service.retrieve(KnowledgeRetrieveRequest(query="退货"), _ctx())
        record = sink.records[0]
        serialized = str(record.to_dict())
        self.assertNotIn("机密内容", serialized)
        self.assertNotIn("退货期限30天", serialized)

    async def test_event_payload_has_no_content(self):
        service, sink, events = self._service([_hit()])
        await service.retrieve(KnowledgeRetrieveRequest(query="退货"), _ctx())
        for event in events.events:
            self.assertNotIn("机密内容", str(event))

    async def test_trace_timing_recorded(self):
        service, sink, events = self._service([_hit()])
        result = await service.retrieve(KnowledgeRetrieveRequest(query="退货"), _ctx())
        self.assertIn("access_resolve", result.timing)
        self.assertIn("policy_evaluate", result.timing)
        self.assertIn("retrieval", result.timing)
        self.assertIn("total", result.timing)


class FailingSink:
    def save(self, record):
        raise RuntimeError("audit backend down")


class AuditFailureIsolationTest(unittest.IsolatedAsyncioTestCase):
    async def test_audit_failure_does_not_block_retrieval(self):
        service = KnowledgeService(
            _HitRetriever([_hit()]),
            config=KnowledgeConfig(),
            audit_sink=FailingSink(),
        )
        result = await service.retrieve(
            KnowledgeRetrieveRequest(query="退货"), _ctx()
        )
        self.assertEqual(1, len(result.items))


if __name__ == "__main__":
    unittest.main()
