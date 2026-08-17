"""Phase 18.11 Knowledge Convergence tests.

Verify the Management Plane -> Projection -> Serving Plane relationship: the
Employee Agent retrieves knowledge through the Serving Plane (with ACL + version
semantics), never through management objects directly.
"""

from unittest.mock import patch

from app.composition.enterprise import build_enterprise_application
from app.composition.knowledge import (
    ServingKnowledgeAgentAdapter,
    build_knowledge_wiring,
)
from app.platform.production.knowledge import (
    KnowledgeAccessControl,
    KnowledgeAccessPolicy,
)
from tests.memory.repository import TestEmbeddingService, TestMemoryRepository


class _StubLLM:
    def chat(self, messages, **kwargs):
        return '{"goal":"g","steps":[]}'


def test_management_activation_projects_to_serving():
    wiring = build_knowledge_wiring()
    wiring.management.ingest("doc1", "company_A", "亚马逊退货规则：30天无理由。")
    assert wiring.serving.retrieve("退货", "company_A", "finance_agent") == []
    wiring.management.activate("doc1")
    result = wiring.serving.retrieve("退货", "company_A", "finance_agent")
    assert result == ["亚马逊退货规则：30天无理由。"]


def test_agent_uses_serving_port():
    wiring = build_knowledge_wiring()
    wiring.management.ingest("doc1", "company_A", "亚马逊退货规则：30天无理由。")
    wiring.management.activate("doc1")
    adapter = ServingKnowledgeAgentAdapter(
        wiring.serving, tenant_id="company_A", agent_id="finance_agent")
    assert adapter.retrieve("退货") == ["亚马逊退货规则：30天无理由。"]


def test_serving_acl_remains_enforced():
    control = KnowledgeAccessControl([KnowledgeAccessPolicy(
        policy_id="p1", document_id="doc1", agent_id="finance_agent",
        allowed=True)])
    wiring = build_knowledge_wiring(access_control=control)
    wiring.management.ingest("doc1", "company_A", "财务制度：预算审批。")
    wiring.management.activate("doc1")
    # authorized agent retrieves; unauthorized agent gets nothing
    assert wiring.serving.retrieve("预算", "company_A", "finance_agent")
    assert wiring.serving.retrieve("预算", "company_A", "commerce_agent") == []


def test_tenant_isolation_in_serving():
    wiring = build_knowledge_wiring()
    wiring.management.ingest("doc1", "company_A", "机密制度。")
    wiring.management.activate("doc1")
    assert wiring.serving.retrieve("机密", "company_B", "finance_agent") == []


def test_version_semantics():
    wiring = build_knowledge_wiring()
    wiring.management.ingest("doc1", "company_A", "v1 内容", version="1.0")
    wiring.management.activate("doc1", "1.0")
    assert wiring.serving.retrieve("v1", "company_A", "a") == ["v1 内容"]
    # register v2 (inactive) -> still v1
    wiring.management.ingest("doc1", "company_A", "v2 内容", version="2.0")
    assert wiring.serving.retrieve("v2", "company_A", "a") == []
    assert wiring.serving.retrieve("v1", "company_A", "a") == ["v1 内容"]
    # activate v2 -> serving switches to v2
    wiring.management.activate("doc1", "2.0")
    assert wiring.serving.retrieve("v2", "company_A", "a") == ["v2 内容"]


def test_composition_wires_knowledge_planes():
    with patch("app.main.create_llm", return_value=_StubLLM()):
        app = build_enterprise_application(
            "testing",
            memory_repository=TestMemoryRepository(),
            memory_embedding_service=TestEmbeddingService(),
        )
    app.production.knowledge_management.ingest(
        "doc1", "company_A", "亚马逊退货规则。")
    app.production.knowledge_management.activate("doc1")
    adapter = ServingKnowledgeAgentAdapter(
        app.production.knowledge_serving, tenant_id="company_A",
        agent_id="finance_agent")
    assert adapter.retrieve("退货") == ["亚马逊退货规则。"]
