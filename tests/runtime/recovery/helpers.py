from app.runtime.multi_agent import (
    AgentError,
    AgentExecutionResult,
    AgentInvocationRequest,
    AgentNode,
    AgentResultStatus,
)


def node(agent_id="finance"):
    return AgentNode(
        agent_id=agent_id,
        artifact_id=f"{agent_id}:1.0:langgraph:artifact",
        artifact_hash=agent_id[0] * 64,
        capability=f"{agent_id}.analysis",
    )


def request(agent_node=None, execution_id="execution-1"):
    agent_node = agent_node or node()
    return AgentInvocationRequest(
        execution_id=execution_id, parent_agent="supervisor",
        target_agent=agent_node.agent_id, capability=agent_node.capability,
        input={"customer": "A"}, trace_id="trace-1",
        target_artifact_id=agent_node.artifact_id,
        target_artifact_hash=agent_node.artifact_hash,
    )


def result(agent_node=None, invocation=None, status="completed", code=None,
           category="runtime", retryable=False):
    agent_node = agent_node or node()
    invocation = invocation or request(agent_node)
    errors = () if code is None else (AgentError(
        code=code, category=category, message="Normalized failure",
        retryable=retryable, details_ref="trace://trace-1/error",
    ),)
    return AgentExecutionResult(
        execution_id=invocation.execution_id,
        agent_execution_id=invocation.agent_execution_id,
        agent_id=agent_node.agent_id,
        agent_version="1.0",
        artifact_id=agent_node.artifact_id,
        artifact_hash=agent_node.artifact_hash,
        status=AgentResultStatus(status),
        output={} if status != "completed" else {"agent": agent_node.agent_id},
        errors=errors,
    )
