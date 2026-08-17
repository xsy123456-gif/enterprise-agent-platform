"""Phase 14.7 Evaluation + Hardening + Enterprise Multi-Agent E2E."""

import pytest

from app.platform.agent_collaboration.aggregator import (
    AgentResultAggregator,
    AgentResultItem,
)
from app.platform.agent_collaboration.audit import (
    CollaborationAuditLogger,
    OP_AGENT_COMPLETED,
    OP_AGENT_DELEGATED,
    OP_TASK_CREATED,
)
from app.platform.agent_collaboration.context import AgentContextProvider
from app.platform.agent_collaboration.delegation import DelegationExecutor
from app.platform.agent_collaboration.domain import CollaborationTask
from app.platform.agent_collaboration.evaluation import (
    CollaborationEvaluation,
    CollaborationEvaluationStore,
)
from app.platform.agent_collaboration.governance import (
    AgentCollaborationPolicy,
    CollaborationAccessControl,
)
from app.platform.agent_collaboration.orchestrator import MultiAgentOrchestrator
from app.platform.agent_collaboration.task_graph import (
    AgentTask,
    AgentTaskGraph,
    GraphValidator,
)


class _Runner:
    def __init__(self, outcomes=None):
        self.outcomes = outcomes or {}
        self.calls = []

    def __call__(self, agent_id, goal, context_ref):
        self.calls.append((agent_id, goal, context_ref))
        return self.outcomes.get(agent_id, {"summary": f"{agent_id} 完成 {goal}"})


def _control():
    return CollaborationAccessControl([
        AgentCollaborationPolicy(policy_id="p1", source_agent="sales_agent",
                                 target_agent="commerce_agent", allowed=True),
        AgentCollaborationPolicy(policy_id="p2", source_agent="sales_agent",
                                 target_agent="marketing_agent", allowed=True),
    ])


def test_enterprise_multi_agent_e2e():
    outcomes = {
        "sales_agent": {"summary": "Q3销售整体下滑20%"},
        "commerce_agent": {"summary": "库存不足导致断货"},
        "marketing_agent": {"summary": "广告流量下降"},
    }
    runner = _Runner(outcomes)
    control = _control()
    delegator = DelegationExecutor(runner, access_control=control)
    orchestrator = MultiAgentOrchestrator(delegator)
    context = AgentContextProvider()
    audit = CollaborationAuditLogger()
    evaluation = CollaborationEvaluationStore()

    task = CollaborationTask(task_id="t1", root_agent_id="sales_agent",
                             goal="为什么Q3销售下降")
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
    GraphValidator(
        active_agents={"sales_agent", "commerce_agent", "marketing_agent"},
        allowed_delegations=control.allowed_delegations(),
    ).validate(graph)

    # context sharing (controlled)
    envelope = context.create_context(
        task_id="t1", source_agent="sales_agent", target_agent="commerce_agent",
        facts={"sales_drop": "20%"}, references=("user_goal",))

    # execute
    audit.record("t1", "sales_agent", OP_TASK_CREATED)
    results = orchestrator.execute(task, graph)
    for node, _ in results:
        audit.record("t1", node.agent_id, OP_AGENT_COMPLETED)

    # aggregate
    items = [
        AgentResultItem(agent_id=node.agent_id, summary=result.summary,
                        confidence=0.8, topic=node.agent_id)
        for node, result in results
    ]
    aggregated = AgentResultAggregator().aggregate("t1", items)
    assert len(aggregated.agent_results) == 3
    assert "库存不足" in aggregated.summary
    assert "广告流量下降" in aggregated.summary

    # evaluate
    evaluation.record(CollaborationEvaluation(
        evaluation_id="e1", task_id="t1", collaboration_success=True,
        delegation_efficiency=0.9, agent_overuse_rate=0.1,
        context_efficiency=0.8, cost_efficiency=0.7))
    assert evaluation.summary().success_rate == 1.0

    # audit trail
    assert any(r.operation == OP_TASK_CREATED for r in audit.list())
    assert any(r.operation == OP_AGENT_COMPLETED for r in audit.list())


def test_e2e_governance_denies_unauthorized_delegation():
    runner = _Runner()
    delegator = DelegationExecutor(runner, access_control=_control())
    orchestrator = MultiAgentOrchestrator(delegator)
    task = CollaborationTask(task_id="t1", root_agent_id="finance_agent")
    graph = AgentTaskGraph(
        task_id="g1", root_agent_id="finance_agent",
        tasks=[AgentTask(task_id="b", agent_id="commerce_agent", goal="x")],
    )
    from app.platform.agent_collaboration.errors import DelegationDeniedError
    with pytest.raises(DelegationDeniedError):
        orchestrator.execute(task, graph)


def test_evaluation_validation_ranges():
    with pytest.raises(ValueError):
        CollaborationEvaluation(evaluation_id="e", task_id="t",
                                delegation_efficiency=1.5)


def test_audit_never_contains_secret():
    audit = CollaborationAuditLogger()
    record = audit.record("t1", "sales_agent", OP_AGENT_DELEGATED)
    for forbidden in ("secret", "credential", "token", "private", "context_raw"):
        assert forbidden not in record.to_dict()
        assert not hasattr(record, forbidden)
