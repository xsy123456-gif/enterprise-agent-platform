from app.runtime.governance.agent import (
    AgentAuthorizationContext,
    AgentInvocationPolicy,
    AgentInvocationPolicyStore,
)
from app.runtime.multi_agent import (
    AgentContextEnvelope,
    AgentExecutionResult,
    AgentInvocationRequest,
    AgentNode,
    AgentProvenance,
    AgentResultStatus,
    ContextCorrelation,
    EvidenceReference,
)


def node(agent_id="finance"):
    return AgentNode(
        agent_id=agent_id,
        artifact_id=f"{agent_id}:1.0:langgraph:artifact",
        artifact_hash=agent_id[0] * 64,
        capability=f"{agent_id}.analysis",
    )


def envelope():
    return AgentContextEnvelope(
        shared_facts={"customer_id": "A", "segment": "enterprise"},
        upstream_results={"sales": {"summary": "growth"}},
        evidence_refs=(EvidenceReference("document", "doc-1"),),
        task_context={"goal": "assess risk", "region": "CN"},
        correlation=ContextCorrelation(
            "execution-1", "trace-1", "parent-execution", "invocation-parent"
        ),
        provenance=(AgentProvenance(
            "sales", "1.0", "sales:1.0:langgraph:a", "s" * 64,
            "parent-execution",
        ),),
    )


def request(agent_node=None, context=None):
    agent_node = agent_node or node()
    return AgentInvocationRequest(
        execution_id="execution-1", parent_agent="supervisor",
        target_agent=agent_node.agent_id, capability=agent_node.capability,
        input={"customer": "A"}, trace_id="trace-1",
        target_artifact_id=agent_node.artifact_id,
        target_artifact_hash=agent_node.artifact_hash,
        context_envelope=context,
    )


def policy(agent_node=None, **overrides):
    agent_node = agent_node or node()
    values = {
        "source_agent_id": "supervisor",
        "target_agent_id": agent_node.agent_id,
        "allowed_capabilities": frozenset({agent_node.capability}),
        "allowed_context_fields": frozenset({
            "shared_facts.customer_id", "task_context.goal", "evidence_refs",
            "provenance",
        }),
    }
    values.update(overrides)
    return AgentInvocationPolicy(**values)


def policy_store(agent_node=None, **overrides):
    return AgentInvocationPolicyStore((policy(agent_node, **overrides),))


def principal(authenticated=True):
    return AgentAuthorizationContext(
        "user-1", "tenant-1", authenticated,
        frozenset({"finance.analysis", "risk.analysis"}),
    )


def result(agent_node=None, invocation=None, evidence=True, provenance=True):
    agent_node = agent_node or node()
    invocation = invocation or request(agent_node)
    source = AgentProvenance(
        agent_node.agent_id, "1.0", agent_node.artifact_id,
        agent_node.artifact_hash, invocation.agent_execution_id,
    ) if provenance else None
    return AgentExecutionResult(
        execution_id=invocation.execution_id,
        agent_execution_id=invocation.agent_execution_id,
        agent_id=agent_node.agent_id,
        agent_version="1.0",
        artifact_id=agent_node.artifact_id,
        artifact_hash=agent_node.artifact_hash,
        status=AgentResultStatus.COMPLETED,
        output={"risk": "low"},
        evidence=(EvidenceReference("tool_result", "tool-1"),) if evidence else (),
        provenance=source,
    )
