"""Phase 12.5 / 12.6 Memory + Knowledge boundary tests."""

import pytest

from app.commerce.agents.binding import AgentSkillBinding, SkillBindingRegistry
from app.commerce.agents.conversation import ConversationManager
from app.commerce.agents.context import (
    AgentContext,
    AgentKnowledgePort,
    AgentMemoryPort,
    DATA_PRIORITY,
)
from app.commerce.agents.domain import (
    RESPONSE_DIAGNOSTIC,
    AgentDefinition,
    AgentRequest,
)
from app.commerce.agents.manifest import AgentManifest
from app.commerce.agents.router.contract import SkillRoutingResult
from app.commerce.contracts.subject import SUBJECT_STORE, SubjectRef
from app.commerce.diagnostics.plans.ports import TrustedExecutionContext

SUBJECT = SubjectRef(SUBJECT_STORE, "JP01")
TRUSTED = TrustedExecutionContext(tenant_id="company_A")


class _FakeMemory(AgentMemoryPort):
    def __init__(self):
        self.retrieve_calls = 0
        self.submitted = []

    def retrieve(self, query, limit=10):
        self.retrieve_calls += 1
        return ["用户偏好：关注广告ROAS"]

    def submit(self, summary):
        self.submitted.append(summary)


class _FakeKnowledge(AgentKnowledgePort):
    def __init__(self, snippets=("亚马逊退货规则：30天无理由。",)):
        self.snippets = snippets
        self.retrieve_calls = 0

    def retrieve(self, query):
        self.retrieve_calls += 1
        return list(self.snippets)


class _FakeSkillSystem:
    def __init__(self):
        self.calls = []

    def run(self, skill_id, subject, trusted_context=None, fact_executor=None):
        self.calls.append(skill_id)
        from types import SimpleNamespace
        cause = SimpleNamespace(cause_code="ROAS_DECLINE")
        priority = SimpleNamespace(level="P2")
        return SimpleNamespace(diagnostic_result=SimpleNamespace(
            causes=[cause], priority=priority, evidence=()))


class _FakeRouter:
    def __init__(self):
        self.routed = []

    def route(self, request):
        self.routed.append(request.message)
        return SkillRoutingResult(
            selected_skill="advertising_performance_diagnosis", subject=SUBJECT)


def _manager(memory=None, knowledge=None, knowledge_enabled=False):
    definition = AgentDefinition(
        agent_id="a", version="1.0", name="n", description="d")
    manifest = AgentManifest(
        agent_id="a", version="1.0", description="d",
        skills=("advertising_performance_diagnosis",),
        default_skill="advertising_performance_diagnosis",
        required_capabilities=("commerce.metrics.read",))
    bindings = SkillBindingRegistry()
    bindings.register(AgentSkillBinding(
        agent_id="a", skill_id="advertising_performance_diagnosis",
        skill_version="1.0"))
    return ConversationManager(
        agent_definition=definition, manifest=manifest,
        binding_registry=bindings, skill_system=_FakeSkillSystem(),
        router=_FakeRouter(), memory_port=memory, knowledge_port=knowledge,
        knowledge_enabled=knowledge_enabled,
    )


def test_memory_retrieved_before_and_submitted_after():
    memory = _FakeMemory()
    manager = _manager(memory=memory)
    response = manager.handle(
        AgentRequest(request_id="r1", message="广告ROAS怎么样"), TRUSTED, None)
    assert response.response_type == RESPONSE_DIAGNOSTIC
    assert memory.retrieve_calls == 1
    assert len(memory.submitted) == 1
    assert "ROAS" in memory.submitted[0]


def test_memory_is_context_not_business_data():
    # Memory is retrieved but never drives skill selection: the router selected
    # the skill deterministically; memory content is absent from the response.
    memory = _FakeMemory()
    router = _FakeRouter()
    manager = _manager(memory=memory)
    manager.router = router
    response = manager.handle(
        AgentRequest(request_id="r1", message="看看"), TRUSTED, None)
    assert router.routed[0] == "看看"          # routing used only the message
    assert memory.retrieve_calls == 1
    assert "用户偏好" not in response.message   # memory never in the answer body


def test_knowledge_off_by_default():
    knowledge = _FakeKnowledge()
    manager = _manager(knowledge=knowledge, knowledge_enabled=False)
    response = manager.handle(
        AgentRequest(request_id="r1", message="亚马逊退货规则是什么？"),
        TRUSTED, None)
    assert knowledge.retrieve_calls == 0
    assert response.citations == ()


def test_knowledge_attaches_citations_only_when_enabled():
    knowledge = _FakeKnowledge()
    manager = _manager(knowledge=knowledge, knowledge_enabled=True)
    response = manager.handle(
        AgentRequest(request_id="r1", message="亚马逊退货规则是什么？"),
        TRUSTED, None)
    assert knowledge.retrieve_calls == 1
    assert "亚马逊退货规则" in response.citations[0]
    # knowledge is citations only — it never changes the diagnostic result
    assert response.response_type == RESPONSE_DIAGNOSTIC


def test_agent_context_assembly():
    ctx = AgentContext(trusted_context=TRUSTED,
                       memory_snippets=["a"], knowledge_snippets=["b"])
    assert ctx.memory_snippets == ("a",)
    assert ctx.knowledge_snippets == ("b",)
    assert ctx.trusted_context is TRUSTED


def test_data_priority_order():
    assert DATA_PRIORITY == ("commerce_facts", "knowledge", "memory")
    assert DATA_PRIORITY.index("commerce_facts") < DATA_PRIORITY.index("knowledge")
    assert DATA_PRIORITY.index("knowledge") < DATA_PRIORITY.index("memory")
