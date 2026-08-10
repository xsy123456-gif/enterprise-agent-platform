from abc import ABC
from dataclasses import FrozenInstanceError

import pytest

from app.runtime.multi_agent import (
    AgentExecutionGraph,
    AgentExecutionGraphStatus,
    AgentExecutionRecord,
    AgentExecutionStatus,
    AgentGraphEdge,
    AgentNode,
    AgentRuntimeInvoker,
    SupervisorGraphRuntime,
)


def node(agent_id, artifact_hash):
    return AgentNode(
        agent_id=agent_id,
        artifact_id=f"{agent_id}:1.0:langgraph:{artifact_hash[:8]}",
        artifact_hash=artifact_hash,
        capability=f"{agent_id}_analysis",
        input_contract={"type": "object"},
        output_contract={"type": "object"},
        execution_policy={"timeout_seconds": 30},
    )


def test_agent_graph_creation_round_trip_preserves_artifact_identity():
    sales = node("sales_agent", "a" * 64)
    finance = node("finance_agent", "b" * 64)
    graph = AgentExecutionGraph(
        graph_id="customer-risk-analysis",
        execution_id="execution-1",
        root_agent="supervisor",
        nodes=(sales, finance),
        edges=(
            AgentGraphEdge("supervisor", "sales_agent"),
            AgentGraphEdge("sales_agent", "finance_agent"),
        ),
    )

    restored = AgentExecutionGraph.from_dict(graph.to_dict())

    assert restored == graph
    assert restored.status is AgentExecutionGraphStatus.CREATED
    assert restored.get_node("finance_agent").artifact_id == finance.artifact_id
    assert restored.get_node("finance_agent").artifact_hash == "b" * 64


def test_agent_graph_rejects_unknown_agents_and_cycles():
    sales = node("sales_agent", "a" * 64)
    with pytest.raises(ValueError, match="unknown Agents"):
        AgentExecutionGraph(
            "graph", "execution", "supervisor", (sales,),
            (AgentGraphEdge("sales_agent", "unknown_agent"),),
        )
    with pytest.raises(ValueError, match="acyclic"):
        AgentExecutionGraph(
            "graph", "execution", "supervisor", (sales,),
            (
                AgentGraphEdge("supervisor", "sales_agent"),
                AgentGraphEdge("sales_agent", "supervisor"),
            ),
        )


def test_agent_execution_record_is_immutable_and_has_controlled_lifecycle():
    record = AgentExecutionRecord(
        execution_id="execution-1",
        agent_id="sales_agent",
        artifact_id="sales:1",
        artifact_hash="a" * 64,
        capability="customer_analysis",
        parent_agent_id="supervisor",
    )

    running = record.transition(AgentExecutionStatus.RUNNING)
    completed = running.transition(AgentExecutionStatus.COMPLETED)

    assert record.status is AgentExecutionStatus.CREATED
    assert completed.status is AgentExecutionStatus.COMPLETED
    assert AgentExecutionRecord.from_dict(completed.to_dict()) == completed
    with pytest.raises(ValueError, match="Invalid Agent execution transition"):
        completed.transition(AgentExecutionStatus.RUNNING)
    with pytest.raises(FrozenInstanceError):
        record.agent_id = "finance_agent"


def test_group_one_defines_ports_without_adding_an_executor_or_scheduler():
    assert issubclass(AgentRuntimeInvoker, ABC)
    assert issubclass(SupervisorGraphRuntime, ABC)
    assert AgentRuntimeInvoker.__abstractmethods__ == {"invoke"}
    assert SupervisorGraphRuntime.__abstractmethods__ == {"execute"}
