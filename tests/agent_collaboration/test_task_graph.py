"""Phase 14.2 Task Graph tests."""

import pytest

from app.platform.agent_collaboration.errors import (
    AgentUnavailableError,
    CycleDetectedError,
    DelegationDeniedError,
    MaxDepthExceededError,
)
from app.platform.agent_collaboration.task_graph import (
    AgentTask,
    AgentTaskGraph,
    GraphValidator,
)


def _graph():
    return AgentTaskGraph(
        task_id="g1", root_agent_id="sales_agent",
        tasks=[
            AgentTask(task_id="a", agent_id="sales_agent", goal="分析销售"),
            AgentTask(task_id="b", agent_id="commerce_agent", goal="商品分析",
                      dependencies=("a",)),
            AgentTask(task_id="c", agent_id="marketing_agent", goal="营销分析",
                      dependencies=("a",)),
        ],
    )


def test_graph_topological_order():
    graph = _graph()
    order = graph.execution_order()
    assert order[0] == "a"
    assert set(order[1:]) == {"b", "c"}


def test_graph_rejects_cycle():
    graph = AgentTaskGraph(
        task_id="g1", root_agent_id="a",
        tasks=[
            AgentTask(task_id="a", agent_id="x", dependencies=("b",)),
            AgentTask(task_id="b", agent_id="y", dependencies=("a",)),
        ],
    )
    with pytest.raises(CycleDetectedError):
        GraphValidator().validate(graph)


def test_graph_max_depth():
    graph = AgentTaskGraph(
        task_id="g1", root_agent_id="a",
        tasks=[
            AgentTask(task_id="a", agent_id="x"),
            AgentTask(task_id="b", agent_id="y", dependencies=("a",)),
            AgentTask(task_id="c", agent_id="z", dependencies=("b",)),
            AgentTask(task_id="d", agent_id="w", dependencies=("c",)),
        ],
    )
    with pytest.raises(MaxDepthExceededError):
        GraphValidator(max_agent_depth=3).validate(graph)


def test_graph_agent_existence():
    graph = _graph()
    with pytest.raises(AgentUnavailableError):
        GraphValidator(active_agents={"sales_agent", "commerce_agent"}).validate(graph)


def test_graph_delegation_permission():
    graph = _graph()
    # allow sales->commerce but not sales->marketing
    allowed = {("sales_agent", "commerce_agent")}
    with pytest.raises(DelegationDeniedError):
        GraphValidator(allowed_delegations=allowed).validate(graph)


def test_graph_valid_passes():
    GraphValidator(
        active_agents={"sales_agent", "commerce_agent", "marketing_agent"},
        allowed_delegations={("sales_agent", "commerce_agent"),
                             ("sales_agent", "marketing_agent")},
    ).validate(_graph())
