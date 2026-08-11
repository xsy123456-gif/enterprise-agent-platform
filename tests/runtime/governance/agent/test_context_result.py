import pytest

from app.runtime.governance.agent import (
    AgentContextGuard,
    AgentResultValidator,
    TrustLevel,
)
from app.runtime.multi_agent import AgentContractValidationError
from tests.runtime.governance.agent.helpers import (
    envelope, node, policy, request, result,
)


def test_context_guard_keeps_only_policy_approved_fields():
    guarded = AgentContextGuard().guard(envelope(), policy())
    assert guarded.envelope.shared_facts == {"customer_id": "A"}
    assert guarded.envelope.task_context == {"goal": "assess risk"}
    assert guarded.envelope.upstream_results == {}
    assert guarded.envelope.evidence_refs
    assert guarded.envelope.provenance
    assert "shared_facts.segment" in guarded.removed_fields


@pytest.mark.parametrize("field", [
    "permission_context", "memory_context", "audit_context", "runtime_state",
    "graph_state", "api_key", "secret", "authorization",
])
def test_context_guard_rejects_mutated_forbidden_context(field):
    context = envelope()
    context.shared_facts[field] = {"unsafe": True}
    with pytest.raises(AgentContractValidationError, match="forbidden"):
        AgentContextGuard().guard(context, policy())


def test_context_guard_handles_no_context():
    guarded = AgentContextGuard().guard(None, policy())
    assert guarded.envelope is None


def test_verified_result_requires_identity_provenance_and_evidence():
    agent_node = node()
    invocation = request(agent_node)
    validation = AgentResultValidator().validate(
        result(agent_node, invocation), invocation, agent_node
    )
    assert validation.trust_level is TrustLevel.VERIFIED
    assert validation.issues == ()


def test_result_without_evidence_is_partial():
    agent_node = node()
    invocation = request(agent_node)
    validation = AgentResultValidator().validate(
        result(agent_node, invocation, evidence=False), invocation, agent_node
    )
    assert validation.trust_level is TrustLevel.PARTIAL
    assert "missing_evidence" in validation.issues


def test_result_without_provenance_is_unverified():
    agent_node = node()
    invocation = request(agent_node)
    validation = AgentResultValidator().validate(
        result(agent_node, invocation, provenance=False), invocation, agent_node
    )
    assert validation.trust_level is TrustLevel.UNVERIFIED
    assert "missing_provenance" in validation.issues


def test_wrong_artifact_is_unverified():
    invocation = request()
    validation = AgentResultValidator().validate(
        result(invocation=invocation), invocation, node("risk")
    )
    assert validation.trust_level is TrustLevel.UNVERIFIED
    assert "invalid_artifact_hash" in validation.issues


def test_wrong_execution_identity_is_unverified():
    agent_node = node()
    expected = request(agent_node)
    other = request(agent_node)
    validation = AgentResultValidator().validate(
        result(agent_node, other), expected, agent_node
    )
    assert validation.trust_level is TrustLevel.UNVERIFIED
    assert "invalid_agent_execution_id" in validation.issues
