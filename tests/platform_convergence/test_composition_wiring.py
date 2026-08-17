"""Phase 18.8 Composition auto-wiring E2E.

Proves that ``build_enterprise_application`` wires the observability subscriber
automatically, and that a real Commerce Agent skill execution produces a Trace
and Metrics with the same execution_id as the ExecutionRecord — with no manual
collector call anywhere.
"""

import uuid
from unittest.mock import patch

from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics.plans import FakeFactQueryExecutor
from app.commerce.skills import SkillExecutionContext
from app.composition.enterprise import build_enterprise_application
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


def test_composition_auto_wires_observability():
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

    # automatic wiring: no manual collector call anywhere
    record = app.commerce.execution_manager.store.get(execution_id)
    assert record is not None
    assert record.status == ExecutionStatus.COMPLETED

    trace = app.production.trace.trace("trace-comp")
    assert trace is not None
    assert trace.execution_id == execution_id

    samples = app.production.metrics.samples("commerce_operations_agent")
    assert samples
    assert samples[0].execution_id == execution_id
    assert samples[0].success is True
