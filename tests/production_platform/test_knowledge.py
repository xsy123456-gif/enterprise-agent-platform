"""Phase 15.5 Knowledge Platform tests."""

import pytest

from app.platform.production.errors import KnowledgeAccessDeniedError
from app.platform.production.knowledge import (
    KnowledgeAccessControl,
    KnowledgeAccessPolicy,
    KnowledgeEvaluation,
    KnowledgeEvaluationStore,
    KnowledgeIngestionService,
)


def test_ingestion_creates_draft_and_activates():
    service = KnowledgeIngestionService()
    document = service.ingest(
        document_id="doc1", tenant_id="company_A",
        content="亚马逊退货规则：30天无理由。", source="policy")
    assert document.status == "DRAFT"
    assert document.checksum
    activated = service.activate("doc1")
    assert activated.status == "ACTIVE"


def test_ingestion_checksum_stable():
    service = KnowledgeIngestionService()
    doc_a = service.ingest("doc1", "company_A", "content")
    doc_b = service.ingest("doc2", "company_A", "content")
    assert doc_a.checksum == doc_b.checksum


def test_knowledge_access_fail_closed():
    control = KnowledgeAccessControl([
        KnowledgeAccessPolicy(policy_id="p1", document_id="doc1",
                              agent_id="finance_agent", allowed=True)])
    assert control.check("doc1", "finance_agent") is True
    assert control.check("doc1", "commerce_agent") is False
    with pytest.raises(KnowledgeAccessDeniedError):
        control.authorize("doc1", "commerce_agent")


def test_get_enforces_access():
    control = KnowledgeAccessControl([
        KnowledgeAccessPolicy(policy_id="p1", document_id="doc1",
                              agent_id="finance_agent", allowed=True)])
    service = KnowledgeIngestionService(access_control=control)
    service.ingest("doc1", "company_A", "内容")
    assert service.get("doc1", agent_id="finance_agent") is not None
    with pytest.raises(KnowledgeAccessDeniedError):
        service.get("doc1", agent_id="commerce_agent")


def test_knowledge_evaluation_ranges():
    with pytest.raises(ValueError):
        KnowledgeEvaluation(evaluation_id="e", document_id="d",
                            citation_accuracy=1.5)
    store = KnowledgeEvaluationStore()
    store.record(KnowledgeEvaluation(
        evaluation_id="e", document_id="d", citation_accuracy=0.9,
        retrieval_relevance=0.8, freshness=0.7))
    assert len(store.for_document("d")) == 1
