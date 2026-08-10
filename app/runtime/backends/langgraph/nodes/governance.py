from dataclasses import dataclass
from enum import Enum

from langgraph.types import interrupt

from app.governance.adapters.approval import ApprovalAdapter
from app.governance.adapters.checkpoint import ExecutionCheckpoint


class GovernanceStatus(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass(frozen=True)
class GovernanceContext:
    trace_id: str
    execution_id: str
    agent_id: str
    user_id: str
    tool_name: str | None
    risk_level: str
    policy_context: dict


@dataclass(frozen=True)
class GovernanceDecision:
    status: GovernanceStatus
    reason: str
    approval_id: str | None = None

    def to_dict(self):
        return {
            "status": self.status.value,
            "reason": self.reason,
            "approval_id": self.approval_id,
        }


@dataclass(frozen=True)
class GuardResult:
    risk: str
    action: str
    reason: str

    def to_dict(self):
        return {"risk": self.risk, "action": self.action, "reason": self.reason}


class GuardNode:
    """Input safety boundary; it does not approve or execute Tools."""

    def __init__(self, evaluator=None, emitter=None):
        self.evaluator = evaluator
        self.emitter = emitter

    def __call__(self, state):
        if self.evaluator is not None:
            result = self.evaluator(state)
        else:
            text = str(state.get("input") or "").lower()
            high_risk = any(word in text for word in ("工资", "全部财务", "导出全部"))
            injection = any(
                phrase in text
                for phrase in ("ignore previous instructions", "忽略之前的指令", "绕过安全")
            )
            result = GuardResult(
                risk="high" if high_risk or injection else "low",
                action="require_approval" if high_risk else ("deny" if injection else "allow"),
                reason=("sensitive request" if high_risk else "prompt injection detected" if injection else "no guard finding"),
            )
        if self.emitter is not None:
            self.emitter.emit(
                "guard.checked", "completed", result.to_dict()
            )
        return {"guard_result": result.to_dict()}


class GovernanceGate:
    """Policy decision boundary before ToolNode; no Permission replacement."""

    def __init__(self, evaluator=None, emitter=None):
        self.evaluator = evaluator
        self.emitter = emitter

    def __call__(self, state):
        pending = state.get("pending_tool_call") or {}
        metadata = dict(state.get("metadata") or {})
        guard = dict(state.get("guard_result") or {})
        context = GovernanceContext(
            trace_id=state.get("trace_id", "graph-trace"),
            execution_id=state.get("execution_id", "graph-execution"),
            agent_id=state.get("agent_id", "graph-agent"),
            user_id=metadata.get("user_id", "graph-user"),
            tool_name=pending.get("tool"),
            risk_level=guard.get("risk", "low"),
            policy_context=metadata.get("policy_context", {}),
        )
        if self.evaluator is not None:
            decision = self.evaluator(context)
        elif guard.get("action") == "deny":
            decision = GovernanceDecision(GovernanceStatus.DENY, guard.get("reason", "guard denied"))
        elif guard.get("action") == "require_approval":
            decision = GovernanceDecision(
                GovernanceStatus.REQUIRE_APPROVAL, guard.get("reason", "approval required")
            )
        else:
            decision = GovernanceDecision(GovernanceStatus.ALLOW, "governance allowed")
        if self.emitter is not None:
            self.emitter.emit("governance.checked", "completed", decision.to_dict())
        return {"governance_decision": decision.to_dict()}


class ApprovalInterruptNode:
    """Create an approval request, interrupt the graph, then resume with a decision."""

    def __init__(self, approval_adapter=None, emitter=None, checkpoint_store=None):
        self.approval_adapter = approval_adapter or ApprovalAdapter()
        self.emitter = emitter
        self.checkpoint_store = checkpoint_store

    def __call__(self, state):
        metadata = dict(state.get("metadata") or {})
        pending = dict(state.get("pending_tool_call") or {})
        context = GovernanceContext(
            trace_id=state.get("trace_id", "graph-trace"),
            execution_id=state.get("execution_id", "graph-execution"),
            agent_id=state.get("agent_id", "graph-agent"),
            user_id=metadata.get("user_id", "graph-user"),
            tool_name=pending.get("tool"),
            risk_level=(state.get("guard_result") or {}).get("risk", "high"),
            policy_context=metadata.get("policy_context", {}),
        )
        approval = self.approval_adapter.request_approval(context)
        approval_id = (
            approval.get("approval_id")
            if isinstance(approval, dict)
            else approval.approval_id
        )
        if self.emitter is not None:
            self.emitter.emit(
                "approval.requested", "pending", {"approval_id": approval_id}
            )
        if self.checkpoint_store is not None:
            self.checkpoint_store.save(
                ExecutionCheckpoint(
                    execution_id=context.execution_id,
                    graph_state=dict(state),
                    current_node="approval",
                    pending_action=dict(state.get("_action") or {}) or None,
                    approval_id=approval_id,
                )
            )
        resume = interrupt({
            "approval_id": approval_id,
            "execution_id": context.execution_id,
            "tool_name": context.tool_name,
        })
        approved = bool(
            resume is True
            or resume == "approved"
            or (isinstance(resume, dict) and resume.get("approved") is True)
        )
        if approved and self.emitter is not None:
            self.emitter.emit(
                "execution.resumed", "resumed", {"approval_id": approval_id}
            )
        self.approval_adapter.complete(approval_id, approved)
        decision = GovernanceDecision(
            GovernanceStatus.ALLOW if approved else GovernanceStatus.DENY,
            "approval approved" if approved else "approval denied",
            approval_id,
        )
        if self.emitter is not None:
            self.emitter.emit(
                "approval.completed", "completed", decision.to_dict()
            )
        return {"governance_decision": decision.to_dict()}
