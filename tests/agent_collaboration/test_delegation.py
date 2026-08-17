"""Phase 14.3 Delegation Runtime tests."""

import pytest

from app.platform.agent_collaboration.delegation import DelegationExecutor
from app.platform.agent_collaboration.domain import (
    CollaborationTask,
    AgentDelegationRequest,
)
from app.platform.agent_collaboration.errors import DelegationDeniedError
from app.platform.agent_collaboration.orchestrator import MultiAgentOrchestrator
from app.platform.agent_collaboration.task_graph import AgentTask, AgentTaskGraph


class _Runner:
    def __init__(self, outcomes=None):
        self.outcomes = outcomes or {}
        self.calls = []

    def __call__(self, agent_id, goal, context_ref):
        self.calls.append((agent_id, goal, context_ref))
        return self.outcomes.get(agent_id, {"summary": f"{agent_id} 完成 {goal}"})


class _DenyControl:
    def authorize(self, from_agent, to_agent):
        raise DelegationDeniedError(f"{from_agent} -> {to_agent} denied")


def test_delegation_executor_success():
    runner = _Runner()
    executor = DelegationExecutor(runner)
    request = AgentDelegationRequest(
        delegation_id="d1", task_id="t1", from_agent_id="sales_agent",
        to_agent_id="commerce_agent", goal="分析销量")
    result = executor.execute(request)
    assert result.status == "SUCCEEDED"
    assert result.agent_id == "commerce_agent"
    assert runner.calls[0][0] == "commerce_agent"


def test_delegation_executor_denied():
    executor = DelegationExecutor(_Runner(), access_control=_DenyControl())
    request = AgentDelegationRequest(
        delegation_id="d1", task_id="t1", from_agent_id="finance_agent",
        to_agent_id="commerce_agent", goal="x")
    with pytest.raises(DelegationDeniedError):
        executor.execute(request)


def test_delegation_failure_returns_failed_result():
    def broken(agent_id, goal, context):
        raise RuntimeError("boom")
    executor = DelegationExecutor(broken)
    result = executor.execute(AgentDelegationRequest(
        delegation_id="d1", task_id="t1", from_agent_id="sales_agent",
        to_agent_id="commerce_agent", goal="x"))
    assert result.status == "FAILED"
    assert "boom" in result.summary


def test_orchestrator_runs_in_dependency_order():
    runner = _Runner({
        "sales_agent": {"summary": "销售整体下滑"},
        "commerce_agent": {"summary": "库存不足"},
        "marketing_agent": {"summary": "广告流量下降"},
    })
    orchestrator = MultiAgentOrchestrator(DelegationExecutor(runner))
    graph = AgentTaskGraph(
        task_id="g1", root_agent_id="sales_agent",
        tasks=[
            AgentTask(task_id="a", agent_id="sales_agent", goal="整体分析"),
            AgentTask(task_id="b", agent_id="commerce_agent", goal="商品分析",
                      dependencies=("a",)),
            AgentTask(task_id="c", agent_id="marketing_agent", goal="营销分析",
                      dependencies=("a",)),
        ],
    )
    task = CollaborationTask(task_id="t1", root_agent_id="sales_agent")
    results = orchestrator.execute(task, graph)
    assert [node.task_id for node, _ in results] == ["a", "b", "c"]
    # dependency context threaded into dependent task
    commerce_call = [c for c in runner.calls if c[0] == "commerce_agent"][0]
    assert "销售整体下滑" in commerce_call[2]
