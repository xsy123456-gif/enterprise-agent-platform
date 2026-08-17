"""Phase 18.9 Observability -> Intelligence Evaluation wiring tests."""

import uuid
from unittest.mock import patch

from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics.plans import FakeFactQueryExecutor
from app.commerce.skills import SkillExecutionContext
from app.composition.enterprise import build_enterprise_application
from app.platform.intelligence.evaluation import EvaluationSubscriber
from app.platform.production.observability import AgentMetricSample
from app.runtime.execution import ExecutionStatus
from tests.memory.repository import TestEmbeddingService, TestMemoryRepository

SUBJECT = SubjectRef("STORE", "JP01")


def _facts():
    return {
        ("commerce.metrics.read", "GMV", "JP01"): {"records": [{"value": 1000.0}]},
        ("commerce.metrics.read", "GMV_B", "JP01"): {"records": [{"value": 2000.0}]},
        ("commerce.metrics.read", "ORDERS", "JP01"): {"records": [{"value": 20.0}]},
        ("commerce.metrics.read", "ORDERS_B", "JP01"): {"records": [{"value": 40.0}]},
        ("commerce.metrics.read", "SESSIONS", "JP01"): {"records": [{"value": 1000.0}]},
        ("commerce.metrics.read", "SESSIONS_B", "JP01"): {"records": [{"value": 1000.0}]},
    }


class _StubLLM:
    def chat(self, messages, **kwargs):
        return '{"goal":"g","steps":[]}'


def _sample(**overrides):
    data = dict(
        tenant_id="company_A", agent_id="commerce_operations_agent",
        agent_version="1.0", success=True, latency_ms=10.0,
        execution_id="e1", trace_id="t1",
    )
    data.update(overrides)
    return AgentMetricSample(**data)


# ── Bridge unit ────────────────────────────────────────────

def test_metric_sample_maps_to_evaluation():
    subscriber = EvaluationSubscriber()
    evaluation = subscriber.on_metric_sample(_sample())
    assert evaluation is not None
    assert evaluation.agent_id == "commerce_operations_agent"
    assert evaluation.execution_id == "e1"
    assert evaluation.trace_id == "t1"
    assert evaluation.tenant_id == "company_A"
    assert evaluation.score == 1.0
    assert evaluation.metrics["success"] is True


def test_failed_metric_maps_to_failure_evaluation():
    subscriber = EvaluationSubscriber()
    evaluation = subscriber.on_metric_sample(_sample(success=False))
    assert evaluation.score == 0.0
    assert evaluation.metrics["success"] is False


def test_evaluation_uses_same_execution_id():
    subscriber = EvaluationSubscriber()
    evaluation = subscriber.on_metric_sample(_sample(execution_id="exec-123"))
    assert evaluation.execution_id == "exec-123"


def test_evaluation_failure_is_isolated_and_visible():
    class BrokenEngine:
        def evaluate_execution(self, *args, **kwargs):
            raise RuntimeError("boom")

    subscriber = EvaluationSubscriber(evaluation_engine=BrokenEngine())
    result = subscriber.on_metric_sample(_sample())
    assert result is None
    assert subscriber.errors == ["boom"]


def test_evaluation_payload_contains_no_secrets():
    subscriber = EvaluationSubscriber()
    evaluation = subscriber.on_metric_sample(_sample())
    for forbidden in ("authorization", "api_key", "secret", "credential",
                      "token", "password"):
        assert forbidden not in evaluation.to_dict()


# ── Composition auto-wiring E2E ────────────────────────────

def test_composition_auto_wires_evaluation():
    with patch("app.main.create_llm", return_value=_StubLLM()):
        app = build_enterprise_application(
            "testing",
            memory_repository=TestMemoryRepository(),
            memory_embedding_service=TestEmbeddingService(),
        )

    execution_id = uuid.uuid4().hex
    context = SkillExecutionContext(
        execution_id=execution_id, trace_id="trace-comp", tenant_id="company_A",
        agent_id="commerce_operations_agent", agent_version="1.0",
        principal_id="U001",
    )
    app.commerce.skill_execution.execute(
        context, "store_performance_diagnosis", SUBJECT,
        fact_executor=FakeFactQueryExecutor(_facts()),
    )

    # automatic: no manual collector/evaluator call anywhere
    record = app.commerce.execution_manager.store.get(execution_id)
    assert record.status == ExecutionStatus.COMPLETED

    evaluations = app.intelligence.evaluation_subscriber.evaluations()
    assert evaluations
    evaluation = evaluations[0]
    assert evaluation.execution_id == execution_id
    assert evaluation.trace_id == "trace-comp"
    assert evaluation.score == 1.0
    assert evaluation.metrics["success"] is True
