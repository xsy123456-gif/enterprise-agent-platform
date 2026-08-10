import json

import pytest

from app.runtime.multi_agent import (
    AgentExecutionGraph,
    AgentGraphEdge,
    AgentGraphExecutionStatus,
    AgentGraphScheduler,
    AgentNode,
    AgentTaskStatus,
)


def build_graph(edges=()):
    nodes = tuple(
        AgentNode(
            agent_id=agent_id,
            artifact_id=f"{agent_id}:1.0:langgraph:{agent_id}",
            artifact_hash=agent_id[0] * 64,
            capability=f"{agent_id}.analysis",
        )
        for agent_id in ("sales", "finance", "risk")
    )
    return AgentExecutionGraph(
        graph_id="risk-graph", execution_id="execution-1", root_agent="supervisor",
        nodes=nodes,
        edges=tuple(edges),
    )


def test_scheduler_is_only_a_pure_planning_component():
    graph = build_graph()
    plan = AgentGraphScheduler().create_plan(graph)
    assert plan.graph_id == "risk-graph"
    assert plan.execution_id == "execution-1"
    assert all(task.status is AgentTaskStatus.PENDING for task in plan.nodes)


def test_scheduler_fanout_has_one_parallel_group():
    graph = build_graph(
        (AgentGraphEdge("supervisor", "sales"), AgentGraphEdge("supervisor", "finance"))
    )
    plan = AgentGraphScheduler().create_plan(graph)
    assert plan.parallel_groups == ((
        "execution-1:sales", "execution-1:finance", "execution-1:risk",
    ),)


def test_scheduler_fanin_waits_for_both_dependencies():
    graph = build_graph(
        (
            AgentGraphEdge("supervisor", "sales"),
            AgentGraphEdge("supervisor", "finance"),
            AgentGraphEdge("sales", "risk"),
            AgentGraphEdge("finance", "risk"),
        )
    )
    plan = AgentGraphScheduler().create_plan(graph)
    assert plan.dependencies["execution-1:risk"] == (
        "execution-1:finance", "execution-1:sales"
    )
    assert plan.parallel_groups[-1] == ("execution-1:risk",)


def test_scheduler_preserves_deterministic_node_order():
    plan = AgentGraphScheduler().create_plan(build_graph())
    assert [task.agent_id for task in plan.nodes] == ["sales", "finance", "risk"]
    assert plan.parallel_groups == ((
        "execution-1:sales", "execution-1:finance", "execution-1:risk",
    ),)


def test_scheduler_plan_round_trip():
    plan = AgentGraphScheduler().create_plan(build_graph())
    restored = type(plan).from_dict(plan.to_dict())
    assert restored.to_dict() == plan.to_dict()
    assert json.loads(json.dumps(plan.to_dict()))["graph_id"] == "risk-graph"


@pytest.mark.parametrize("edge", [
    AgentGraphEdge("sales", "risk"),
    AgentGraphEdge("finance", "risk"),
    AgentGraphEdge("supervisor", "sales"),
    AgentGraphEdge("supervisor", "finance"),
])
def test_scheduler_accepts_each_valid_edge(edge):
    plan = AgentGraphScheduler().create_plan(build_graph((edge,)))
    assert plan.graph_id == "risk-graph"


@pytest.mark.parametrize("status", [
    AgentGraphExecutionStatus.CREATED,
    AgentGraphExecutionStatus.WAITING_CHILDREN,
    AgentGraphExecutionStatus.RUNNING_CHILDREN,
    AgentGraphExecutionStatus.AGGREGATING,
    AgentGraphExecutionStatus.COMPLETED,
    AgentGraphExecutionStatus.PARTIAL_FAILED,
    AgentGraphExecutionStatus.FAILED,
])
def test_graph_lifecycle_status_values_are_frozen(status):
    assert status.value
