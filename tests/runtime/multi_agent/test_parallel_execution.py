import threading
import time

from app.runtime.multi_agent import (
    AgentExecutionResult,
    AgentInvocationRequest,
    AgentNode,
    AgentResultStatus,
    AgentRuntimeInvoker,
    AgentGraphEdge,
    AgentExecutionGraph,
    ParallelGraphExecutor,
)


def setup_graph():
    nodes = tuple(
        AgentNode(
            agent_id=agent_id,
            artifact_id=f"{agent_id}:1.0:langgraph:{agent_id}",
            artifact_hash=agent_id[0] * 64,
            capability=f"{agent_id}.analysis",
        ) for agent_id in ("sales", "finance", "risk")
    )
    return AgentExecutionGraph(
        graph_id="risk-graph", execution_id="execution-1", root_agent="supervisor",
        nodes=nodes,
        edges=(
            AgentGraphEdge("supervisor", "sales"),
            AgentGraphEdge("supervisor", "finance"),
            AgentGraphEdge("sales", "risk"),
            AgentGraphEdge("finance", "risk"),
        ),
    )


def requests(graph):
    return tuple(
        AgentInvocationRequest(
            execution_id=graph.execution_id,
            parent_agent="supervisor",
            target_agent=node.agent_id,
            capability=node.capability,
            input={"customer": "A"},
            trace_id="trace-1",
            target_artifact_id=node.artifact_id,
            target_artifact_hash=node.artifact_hash,
        ) for node in graph.nodes
    )


def result(request, node, status=AgentResultStatus.COMPLETED):
    return AgentExecutionResult(
        execution_id=request.execution_id,
        agent_execution_id=request.agent_execution_id,
        agent_id=node.agent_id,
        agent_version="1.0",
        artifact_id=node.artifact_id,
        artifact_hash=node.artifact_hash,
        status=status,
        output={"agent": node.agent_id},
    )


class RecordingInvoker(AgentRuntimeInvoker):
    def __init__(self, failed=None):
        self.failed = failed
        self.calls = []
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()
        self.fanout_started = threading.Barrier(2)

    def invoke(self, node, request):
        with self.lock:
            self.calls.append(node.agent_id)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        if node.agent_id in {"sales", "finance"}:
            self.fanout_started.wait(timeout=2)
            time.sleep(0.01)
        with self.lock:
            self.active -= 1
        status = AgentResultStatus.FAILED if node.agent_id == self.failed else AgentResultStatus.COMPLETED
        return result(request, node, status)


def test_parallel_executor_fanout_runs_concurrently_and_joins():
    graph = setup_graph()
    invoker = RecordingInvoker()
    executor = ParallelGraphExecutor(invoker)
    outputs = executor.execute(graph, requests(graph))

    assert [item.agent_id for item in outputs] == ["sales", "finance", "risk"]
    assert invoker.max_active >= 2
    assert invoker.calls[-1] == "risk"
    assert executor.last_plan.parallel_groups[-1] == ("execution-1:risk",)


def test_parallel_executor_aggregates_fan_in_results():
    graph = setup_graph()
    aggregate = ParallelGraphExecutor(RecordingInvoker()).execute_aggregated(
        graph, requests(graph)
    )
    assert aggregate.status == "completed"
    assert set(aggregate.outputs) == {"sales", "finance", "risk"}
    assert len(aggregate.agent_sources) == 3


def test_failure_blocks_only_dependent_nodes_and_reports_partial_failure():
    graph = setup_graph()
    executor = ParallelGraphExecutor(RecordingInvoker(failed="sales"))
    aggregate = executor.execute_aggregated(graph, requests(graph))

    assert aggregate.status == "partial_failed"
    assert aggregate.failed_agents == ("sales",)
    assert aggregate.skipped_agents == ("risk",)
    assert "finance" in aggregate.outputs


def test_executor_requires_the_runtime_invoker_port():
    try:
        ParallelGraphExecutor(object())
    except TypeError as error:
        assert "AgentRuntimeInvoker" in str(error)
    else:
        raise AssertionError("raw objects must not execute Agents")


def test_executor_does_not_call_missing_agent_directly():
    graph = setup_graph()
    invoker = RecordingInvoker()
    executor = ParallelGraphExecutor(invoker)
    try:
        executor.execute(graph, requests(graph)[:-1])
    except ValueError as error:
        assert "Missing invocation" in str(error)
    else:
        raise AssertionError("missing invocation must be rejected")
