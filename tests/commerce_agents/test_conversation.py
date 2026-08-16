"""Phase 12.4 Conversation Runtime tests."""

from types import SimpleNamespace

import pytest

from app.commerce.agents.binding import AgentSkillBinding, SkillBindingRegistry
from app.commerce.agents.conversation import (
    ConversationHistory,
    ConversationManager,
)
from app.commerce.agents.domain import (
    RESPONSE_CLARIFICATION,
    RESPONSE_DIAGNOSTIC,
    RESPONSE_ERROR,
    AgentDefinition,
    AgentRequest,
)
from app.commerce.agents.manifest import AgentManifest
from app.commerce.agents.router.contract import SkillRoutingResult
from app.commerce.contracts.subject import SUBJECT_STORE, SubjectRef
from app.commerce.diagnostics.plans.ports import TrustedExecutionContext

SUBJECT = SubjectRef(SUBJECT_STORE, "JP01")
TRUSTED = TrustedExecutionContext(tenant_id="company_A", principal_id="U001")


def _definition():
    return AgentDefinition(
        agent_id="commerce_operations_agent", version="1.0",
        name="Commerce Operations Employee", description="ops",
    )


def _manifest():
    return AgentManifest(
        agent_id="commerce_operations_agent", version="1.0", description="ops",
        skills=("store_performance_diagnosis",),
        default_skill="store_performance_diagnosis",
        required_capabilities=("commerce.metrics.read",),
    )


def _diagnostic():
    cause = SimpleNamespace(cause_code="GMV_DECLINE")
    priority = SimpleNamespace(level="P1")
    return SimpleNamespace(causes=[cause], priority=priority, evidence=())


class _FakeSkillSystem:
    def __init__(self, diagnostic=None, error=None):
        self.diagnostic = diagnostic or _diagnostic()
        self.error = error
        self.calls = []

    def run(self, skill_id, subject, trusted_context=None, fact_executor=None):
        self.calls.append((skill_id, subject))
        if self.error:
            raise self.error
        return SimpleNamespace(diagnostic_result=self.diagnostic)


class _FakeRouter:
    def __init__(self, result=None):
        self.result = result or SkillRoutingResult(
            selected_skill="store_performance_diagnosis", subject=SUBJECT)

    def route(self, request):
        return self.result


def _manager(**kwargs):
    defaults = dict(
        agent_definition=_definition(), manifest=_manifest(),
        binding_registry=_binding_registry(), skill_system=_FakeSkillSystem(),
        router=_FakeRouter(),
    )
    defaults.update(kwargs)
    return ConversationManager(**defaults)


def _binding_registry():
    registry = SkillBindingRegistry()
    registry.register(AgentSkillBinding(
        agent_id="commerce_operations_agent",
        skill_id="store_performance_diagnosis", skill_version="1.0"))
    return registry


# ── History ─────────────────────────────────────────────────

def test_history_append_and_recent():
    history = ConversationHistory()
    history.append("user", "hi")
    history.append("agent", "hello")
    assert len(history) == 2
    assert history.recent(1)[0].content == "hello"
    assert history.turns()[0].role == "user"


# ── Conversation flow ───────────────────────────────────────

def test_handle_returns_diagnostic_response():
    skill_system = _FakeSkillSystem()
    manager = _manager(skill_system=skill_system)
    response = manager.handle(
        AgentRequest(request_id="r1", message="JP01销量下降原因？"),
        TRUSTED, fact_executor=None,
    )
    assert response.response_type == RESPONSE_DIAGNOSTIC
    assert response.diagnostic_result is not None
    assert skill_system.calls == [("store_performance_diagnosis", SUBJECT)]
    assert len(manager.history) == 2


def test_handle_missing_trusted_context():
    manager = _manager()
    response = manager.handle(
        AgentRequest(request_id="r1", message="hi"), None, fact_executor=None)
    assert response.response_type == RESPONSE_ERROR


def test_handle_no_subject_clarification():
    router = _FakeRouter(SkillRoutingResult(selected_skill="", subject=None))
    manager = _manager(router=router)
    response = manager.handle(
        AgentRequest(request_id="r1", message="随便看看"), TRUSTED, None)
    assert response.response_type == RESPONSE_CLARIFICATION


def test_handle_skill_error_returns_typed_error():
    skill_system = _FakeSkillSystem(error=RuntimeError("boom"))
    manager = _manager(skill_system=skill_system)
    response = manager.handle(
        AgentRequest(request_id="r1", message="JP01销量"), TRUSTED, None)
    assert response.response_type == RESPONSE_ERROR
    assert "boom" in response.message


def test_handle_uses_default_skill_when_no_match():
    router = _FakeRouter(SkillRoutingResult(selected_skill="", subject=SUBJECT))
    skill_system = _FakeSkillSystem()
    manager = _manager(router=router, skill_system=skill_system)
    response = manager.handle(
        AgentRequest(request_id="r1", message="看看JP01"), TRUSTED, None)
    assert response.response_type == RESPONSE_DIAGNOSTIC
    assert skill_system.calls == [("store_performance_diagnosis", SUBJECT)]
