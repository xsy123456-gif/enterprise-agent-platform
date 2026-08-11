from app.governance.adapters import InMemoryExecutionCheckpointStore
from app.runtime.multi_agent import (
    AgentExecutionGraph,
    AgentGraphEdge,
    AgentRuntimeInvoker,
    ParallelGraphExecutor,
)
from app.runtime.recovery import (
    AgentRetryPolicy,
    FailureEscalationBoundary,
    RecoveryAction,
    RecoveryManager,
    GraphRecoveryPolicy,
)
from app.storage.providers.memory import InMemoryEventStore
from tests.runtime.recovery.helpers import node, request, result


class RecordingEscalation(FailureEscalationBoundary):
    def __init__(self):
        self.events = []

    def request(self, event):
        self.events.append(event)
        return event


def test_first_failure_second_attempt_success_with_checkpoint_and_events():
    agent_node = node()
    invocation = request(agent_node)
    calls = []
    checkpoints = InMemoryExecutionCheckpointStore()
    events = InMemoryEventStore()
    manager = RecoveryManager(
        checkpoint_store=checkpoints, event_store=events, sleeper=lambda _: None
    )

    def invoke():
        calls.append(1)
        if len(calls) == 1:
            return result(
                agent_node, invocation, "failed", "LLM_TIMEOUT", retryable=True
            )
        return result(agent_node, invocation)

    outcome = manager.execute(
        agent_node, invocation, invoke, AgentRetryPolicy(max_attempts=2)
    )

    assert len(calls) == 2
    assert [item.status.value for item in outcome.attempts] == ["FAILED", "SUCCESS"]
    assert outcome.action is RecoveryAction.RESUME
    checkpoint = checkpoints.load_checkpoint("execution-1")
    assert checkpoint.failed_agent_execution_id == invocation.agent_execution_id
    assert checkpoint.failed_node == "finance"
    assert checkpoint.retry_attempt == 1
    event_types = [item.event_type for item in events.query("execution-1")]
    assert event_types == [
        "agent.failure.detected", "agent.retry.requested",
        "agent.retry.started", "agent.retry.completed",
    ]


def test_retry_exhaustion_requests_human_escalation():
    agent_node = node()
    invocation = request(agent_node)
    escalation = RecordingEscalation()
    manager = RecoveryManager(escalation_boundary=escalation)

    outcome = manager.execute(
        agent_node,
        invocation,
        lambda: result(agent_node, invocation, "failed", "LLM_TIMEOUT", retryable=True),
        AgentRetryPolicy(max_attempts=1, fallback_strategy="ESCALATE"),
    )

    assert outcome.action is RecoveryAction.ESCALATE
    assert len(escalation.events) == 1
    assert escalation.events[0].failure_id == outcome.failures[0].failure_id
    assert "stack" not in escalation.events[0].to_dict()


def test_permission_failure_is_never_retried():
    agent_node = node()
    invocation = request(agent_node)
    calls = []
    outcome = RecoveryManager().execute(
        agent_node,
        invocation,
        lambda: calls.append(1) or result(
            agent_node, invocation, "denied", "PERMISSION_DENIED", "policy"
        ),
        AgentRetryPolicy(max_attempts=3),
    )
    assert len(calls) == 1
    assert outcome.action is RecoveryAction.STOP


def test_raw_exception_is_normalized_without_secret_or_traceback():
    agent_node = node()
    invocation = request(agent_node)
    outcome = RecoveryManager().execute(
        agent_node,
        invocation,
        lambda: (_ for _ in ()).throw(
            RuntimeError("password=secret\nTraceback private")
        ),
        AgentRetryPolicy(max_attempts=1),
    )
    payload = outcome.result.to_dict()
    assert payload["errors"][0]["message"] == "Agent Runtime execution failed"
    assert "secret" not in str(payload)
    assert "Traceback" not in str(payload)


class RecoveringInvoker(AgentRuntimeInvoker):
    def __init__(self, fail_once_agent=None, permanent_failure=None):
        self.fail_once_agent = fail_once_agent
        self.permanent_failure = permanent_failure
        self.calls = []

    def invoke(self, agent_node, invocation):
        self.calls.append(agent_node.agent_id)
        count = self.calls.count(agent_node.agent_id)
        if agent_node.agent_id == self.permanent_failure:
            return result(
                agent_node, invocation, "failed", "PERMANENT_FAILURE"
            )
        if agent_node.agent_id == self.fail_once_agent and count == 1:
            return result(
                agent_node, invocation, "failed", "LLM_TIMEOUT", retryable=True
            )
        return result(agent_node, invocation)


def sequential_graph():
    nodes = tuple(node(agent_id) for agent_id in ("sales", "finance", "risk"))
    return AgentExecutionGraph(
        "recovery-graph", "execution-1", "supervisor", nodes,
        (AgentGraphEdge("sales", "finance"), AgentGraphEdge("finance", "risk")),
    )


def invocations(graph):
    return tuple(request(agent_node, graph.execution_id) for agent_node in graph.nodes)


def test_checkpoint_retry_resumes_failed_agent_then_continues_downstream():
    graph = sequential_graph()
    invoker = RecoveringInvoker(fail_once_agent="finance")
    checkpoints = InMemoryExecutionCheckpointStore()
    recovery = RecoveryManager(checkpoint_store=checkpoints)
    executor = ParallelGraphExecutor(
        invoker, recovery_manager=recovery,
        retry_policy=AgentRetryPolicy(max_attempts=2),
    )

    aggregate = executor.execute_aggregated(graph, invocations(graph))

    assert invoker.calls == ["sales", "finance", "finance", "risk"]
    assert aggregate.status == "completed"
    assert checkpoints.load_checkpoint("execution-1").failed_node == "finance"


def test_partial_failure_still_blocks_dependent_agent_without_retry():
    graph = sequential_graph()
    invoker = RecoveringInvoker(permanent_failure="finance")
    executor = ParallelGraphExecutor(
        invoker, recovery_manager=RecoveryManager(),
        retry_policy=AgentRetryPolicy(max_attempts=2),
    )
    aggregate = executor.execute_aggregated(graph, invocations(graph))
    assert aggregate.status == "partial_failed"
    assert aggregate.failed_agents == ("finance",)
    assert aggregate.skipped_agents == ("risk",)
    assert invoker.calls == ["sales", "finance"]


def test_recovery_outcomes_are_tracked_by_agent_execution_identity():
    graph = sequential_graph()
    executor = ParallelGraphExecutor(
        RecoveringInvoker(), recovery_manager=RecoveryManager()
    )
    requests = invocations(graph)
    executor.execute(graph, requests)
    assert set(executor.recovery_outcomes) == {
        item.agent_execution_id for item in requests
    }


def test_graph_policy_can_skip_failed_agent_and_continue_downstream():
    graph = sequential_graph()
    invoker = RecoveringInvoker(permanent_failure="finance")
    executor = ParallelGraphExecutor(
        invoker,
        recovery_manager=RecoveryManager(),
        retry_policy=AgentRetryPolicy(max_attempts=1),
        graph_recovery_policy=GraphRecoveryPolicy(
            failure_strategy={"finance": "SKIP"},
            continue_on_partial_failure=True,
        ),
    )
    aggregate = executor.execute_aggregated(graph, invocations(graph))
    assert invoker.calls == ["sales", "finance", "risk"]
    assert aggregate.status == "partial_failed"
    assert aggregate.skipped_agents == ("finance",)
