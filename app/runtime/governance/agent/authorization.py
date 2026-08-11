"""Default-deny Agent authorization and governed Runtime invocation."""

from dataclasses import dataclass, replace

from app.governance.adapters.approval import ApprovalAdapter
from app.runtime.governance.agent.audit import AgentGovernanceAuditor
from app.runtime.governance.agent.context_guard import AgentContextGuard
from app.runtime.governance.agent.models import (
    AgentAuthorizationContext,
    AuthorizationDecision,
    AuthorizationStatus,
)
from app.runtime.governance.agent.policy import AgentInvocationPolicyStore
from app.runtime.governance.agent.result_validator import AgentResultValidator
from app.runtime.multi_agent.contracts import AgentExecutionResult
from app.runtime.multi_agent.executor import AgentRuntimeInvoker
from app.runtime.multi_agent.models import AgentError, AgentResultStatus


class AgentAuthorizationEngine:
    def __init__(self, policy_store=None):
        self.policy_store = policy_store or AgentInvocationPolicyStore()

    def authorize(self, request, context):
        if not isinstance(context, AgentAuthorizationContext):
            raise TypeError("context must be AgentAuthorizationContext")
        if not context.authenticated:
            return self._decision(request, "DENY", "user identity is not authenticated")
        if request.capability not in context.allowed_capabilities:
            return self._decision(
                request, "DENY", "user capability scope does not allow invocation"
            )
        policy = self.policy_store.get(request.parent_agent, request.target_agent)
        if policy is None:
            return self._decision(request, "DENY", "no Agent invocation policy")
        if request.capability not in policy.allowed_capabilities:
            return self._decision(
                request, "DENY", "capability is not allowed", policy.policy_id
            )
        status = "REQUIRE_APPROVAL" if policy.approval_required else "ALLOW"
        reason = "Agent invocation requires approval" if policy.approval_required else "Agent invocation allowed"
        return self._decision(request, status, reason, policy.policy_id)

    def policy_for(self, request):
        return self.policy_store.get(request.parent_agent, request.target_agent)

    @staticmethod
    def _decision(request, status, reason, policy_id=None):
        return AuthorizationDecision(
            status=AuthorizationStatus(status),
            reason=reason,
            source_agent_id=request.parent_agent,
            target_agent_id=request.target_agent,
            policy_id=policy_id,
        )


@dataclass(frozen=True)
class AgentApprovalContext:
    execution_id: str
    agent_id: str
    tool_name: str | None
    risk_level: str


class AgentGovernanceGate:
    def __init__(self, authorization_engine, approval_adapter=None, auditor=None,
                 execution_manager=None):
        self.authorization_engine = authorization_engine
        self.approval_adapter = approval_adapter or ApprovalAdapter()
        self.auditor = auditor or AgentGovernanceAuditor()
        self.execution_manager = execution_manager

    def evaluate(self, request, node, context):
        if request.target_agent != node.agent_id:
            raise ValueError("Governance target does not match Agent node")
        if request.target_artifact_id != node.artifact_id:
            raise ValueError("Governance Artifact ID mismatch")
        if request.target_artifact_hash != node.artifact_hash:
            raise ValueError("Governance Artifact hash mismatch")
        decision = self.authorization_engine.authorize(request, context)
        policy = self.authorization_engine.policy_for(request)
        if decision.status is AuthorizationStatus.REQUIRE_APPROVAL:
            approval = self.approval_adapter.request_approval(AgentApprovalContext(
                execution_id=request.execution_id,
                agent_id=request.target_agent,
                tool_name=None,
                risk_level=policy.risk_level,
            ))
            approval_id = (
                approval.get("approval_id") if isinstance(approval, dict)
                else approval.approval_id
            )
            decision = replace(decision, approval_id=approval_id)
            if self.execution_manager is not None:
                self.execution_manager.transition(
                    request.execution_id,
                    "waiting_governance",
                    current_node=node.agent_id,
                    authorization_id=decision.authorization_id,
                )
        self.auditor.emit(
            "agent.authorization.checked", request, node,
            status=decision.status.value.lower(),
            authorization_id=decision.authorization_id,
            payload={
                "decision": decision.status.value,
                "risk_level": policy.risk_level if policy else "unknown",
            },
        )
        if decision.status is AuthorizationStatus.DENY:
            self.auditor.emit(
                "agent.authorization.denied", request, node, status="denied",
                authorization_id=decision.authorization_id,
                payload={"decision": decision.status.value},
            )
        return decision, policy


class GovernedAgentRuntimeInvoker(AgentRuntimeInvoker):
    """Governance wrapper; the wrapped invoker remains the only executor."""

    def __init__(
        self,
        invoker,
        governance_gate,
        principal_provider,
        context_guard=None,
        result_validator=None,
        auditor=None,
    ):
        if not isinstance(invoker, AgentRuntimeInvoker):
            raise TypeError("invoker must implement AgentRuntimeInvoker")
        if not callable(principal_provider):
            raise TypeError("principal_provider must be callable")
        self.invoker = invoker
        self.governance_gate = governance_gate
        self.principal_provider = principal_provider
        self.context_guard = context_guard or AgentContextGuard()
        self.result_validator = result_validator or AgentResultValidator()
        self.auditor = auditor or governance_gate.auditor
        self.validations = {}

    def invoke(self, node, request):
        principal = self.principal_provider(request)
        decision, policy = self.governance_gate.evaluate(request, node, principal)
        if decision.status is not AuthorizationStatus.ALLOW:
            return self._blocked_result(node, request, decision)
        guarded = self.context_guard.guard(request.context_envelope, policy)
        safe_request = replace(request, context_envelope=guarded.envelope)
        self.auditor.emit(
            "agent.context.projected", safe_request, node, status="completed",
            authorization_id=decision.authorization_id,
            context_projection_id=guarded.context_projection_id,
            payload={"removed_field_count": len(guarded.removed_fields)},
        )
        self.auditor.emit(
            "agent.invocation.started", safe_request, node, status="started",
            authorization_id=decision.authorization_id,
            context_projection_id=guarded.context_projection_id,
        )
        result = self.invoker.invoke(node, safe_request)
        validation = self.result_validator.validate(result, safe_request, node)
        self.validations[request.invocation_id] = validation
        self.auditor.emit(
            "agent.invocation.completed", safe_request, node, status="completed",
            authorization_id=decision.authorization_id,
            context_projection_id=guarded.context_projection_id,
        )
        self.auditor.emit(
            "agent.result.validated", safe_request, node, status="completed",
            authorization_id=decision.authorization_id,
            context_projection_id=guarded.context_projection_id,
            payload={"trust_level": validation.trust_level.value,
                     "issue_count": len(validation.issues)},
        )
        return result

    @staticmethod
    def _blocked_result(node, request, decision):
        code = (
            "AGENT_APPROVAL_REQUIRED"
            if decision.status is AuthorizationStatus.REQUIRE_APPROVAL
            else "AGENT_INVOCATION_DENIED"
        )
        return AgentExecutionResult(
            execution_id=request.execution_id,
            agent_execution_id=request.agent_execution_id,
            agent_id=node.agent_id,
            agent_version=AgentGovernanceAuditor._artifact_version(node.artifact_id),
            artifact_id=node.artifact_id,
            artifact_hash=node.artifact_hash,
            status=AgentResultStatus.DENIED,
            output={},
            errors=(AgentError(
                code=code,
                category="governance",
                message=decision.reason,
                retryable=False,
                details_ref=(
                    f"approval://{decision.approval_id}"
                    if decision.approval_id else None
                ),
            ),),
            metadata={"authorization_id": decision.authorization_id},
        )
