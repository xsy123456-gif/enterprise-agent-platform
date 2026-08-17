"""Phase 18.2 Execution Plane Convergence tests.

Verify the Employee Agent's Skill execution creates a durable ExecutionRecord in
the single Runtime Foundation execution plane (ExecutionManager).
"""

import uuid

import pytest

from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics.plans import FakeFactQueryExecutor
from app.commerce.skills import (
    DiagnosticSkillExecutionAdapter,
    SkillExecutionContext,
    build_skill_system,
)
from app.runtime.execution import ExecutionManager, ExecutionStatus, InMemoryExecutionStore

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


@pytest.fixture(scope="module")
def skill_system():
    return build_skill_system()


def _adapter(skill_system):
    manager = ExecutionManager(InMemoryExecutionStore())
    return DiagnosticSkillExecutionAdapter(skill_system, execution_manager=manager), manager


def test_skill_execution_creates_execution_record(skill_system):
    adapter, manager = _adapter(skill_system)
    context = SkillExecutionContext(
        execution_id=uuid.uuid4().hex, trace_id="trace-1",
        tenant_id="company_A", agent_id="commerce_operations_agent",
        agent_version="1.0", principal_id="U001",
    )
    result = adapter.execute(
        context, "store_performance_diagnosis", SUBJECT,
        fact_executor=FakeFactQueryExecutor(_facts()),
    )
    assert result.diagnostic_result.status == "COMPLETED"

    record = manager.store.get(context.execution_id)
    assert record is not None
    assert record.status == ExecutionStatus.COMPLETED
    assert record.agent_id == "commerce_operations_agent"
    assert record.tenant_id == "company_A"
    assert record.trace_id == "trace-1"
    assert record.artifact_id


def test_skill_execution_failure_marks_record_failed(skill_system):
    adapter, manager = _adapter(skill_system)
    context = SkillExecutionContext(
        execution_id=uuid.uuid4().hex, trace_id="trace-2",
        tenant_id="company_A", agent_id="commerce_operations_agent",
        agent_version="1.0",
    )
    with pytest.raises(Exception):
        adapter.execute(context, "store_performance_diagnosis", SUBJECT,
                        fact_executor=None)  # missing fact executor -> raises
    record = manager.store.get(context.execution_id)
    assert record.status == ExecutionStatus.FAILED


def test_execution_record_has_unified_identity(skill_system):
    adapter, manager = _adapter(skill_system)
    context = SkillExecutionContext(
        execution_id=uuid.uuid4().hex, trace_id="trace-3",
        tenant_id="company_A", agent_id="commerce_operations_agent",
        agent_version="1.0", principal_id="U001", artifact_id="art-1",
        artifact_hash="h-1",
    )
    adapter.execute(context, "store_performance_diagnosis", SUBJECT,
                    fact_executor=FakeFactQueryExecutor(_facts()))
    record = manager.store.get(context.execution_id)
    assert record.artifact_id == "art-1"
    assert record.artifact_hash == "h-1"
    assert record.user_id == "U001"
