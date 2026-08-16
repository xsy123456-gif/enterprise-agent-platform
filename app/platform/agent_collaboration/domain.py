"""Agent collaboration domain models (Phase 14.1).

A multi-agent collaboration task, its delegations, and their results.  None of
these carry permission / credential / secret — collaboration is governed by the
control plane, never by the payload.
"""

from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now

# CollaborationTask statuses (§5.1)
TASK_CREATED = "CREATED"
TASK_PLANNING = "PLANNING"
TASK_RUNNING = "RUNNING"
TASK_WAITING_AGENT = "WAITING_AGENT"
TASK_AGGREGATING = "AGGREGATING"
TASK_COMPLETED = "COMPLETED"
TASK_FAILED = "FAILED"
TASK_CANCELLED = "CANCELLED"
TASK_STATUSES = frozenset({
    TASK_CREATED, TASK_PLANNING, TASK_RUNNING, TASK_WAITING_AGENT,
    TASK_AGGREGATING, TASK_COMPLETED, TASK_FAILED, TASK_CANCELLED,
})

# Delegation result status
DELEGATION_SUCCEEDED = "SUCCEEDED"
DELEGATION_FAILED = "FAILED"
DELEGATION_STATUSES = frozenset({DELEGATION_SUCCEEDED, DELEGATION_FAILED})


@dataclass(frozen=True)
class CollaborationTask:
    task_id: str
    root_agent_id: str
    request_id: str = ""
    goal: str = ""
    status: str = TASK_CREATED
    created_at: str = field(default_factory=utc_now)
    completed_at: str = ""

    def __post_init__(self):
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.root_agent_id:
            raise ValueError("root_agent_id is required")
        if self.status not in TASK_STATUSES:
            raise ValueError(f"unknown task status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "root_agent_id": self.root_agent_id,
            "request_id": self.request_id,
            "goal": self.goal,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


@dataclass(frozen=True)
class AgentDelegationRequest:
    delegation_id: str
    task_id: str
    from_agent_id: str
    to_agent_id: str
    goal: str = ""
    input_context_ref: str = ""
    priority: int = 0
    deadline: str = ""
    trace_id: str = ""

    def __post_init__(self):
        if not self.delegation_id:
            raise ValueError("delegation_id is required")
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.from_agent_id:
            raise ValueError("from_agent_id is required")
        if not self.to_agent_id:
            raise ValueError("to_agent_id is required")

    def to_dict(self) -> dict:
        return {
            "delegation_id": self.delegation_id,
            "task_id": self.task_id,
            "from_agent_id": self.from_agent_id,
            "to_agent_id": self.to_agent_id,
            "goal": self.goal,
            "input_context_ref": self.input_context_ref,
            "priority": self.priority,
            "deadline": self.deadline,
            "trace_id": self.trace_id,
        }


@dataclass(frozen=True)
class AgentDelegationResult:
    delegation_id: str
    agent_id: str
    status: str = DELEGATION_SUCCEEDED
    result_reference: str = ""
    summary: str = ""
    completed_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.delegation_id:
            raise ValueError("delegation_id is required")
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if self.status not in DELEGATION_STATUSES:
            raise ValueError(f"unknown delegation status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "delegation_id": self.delegation_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "result_reference": self.result_reference,
            "summary": self.summary,
            "completed_at": self.completed_at,
        }


__all__ = [
    "CollaborationTask",
    "AgentDelegationRequest",
    "AgentDelegationResult",
    "TASK_STATUSES",
    "TASK_CREATED",
    "TASK_PLANNING",
    "TASK_RUNNING",
    "TASK_WAITING_AGENT",
    "TASK_AGGREGATING",
    "TASK_COMPLETED",
    "TASK_FAILED",
    "TASK_CANCELLED",
    "DELEGATION_STATUSES",
    "DELEGATION_SUCCEEDED",
    "DELEGATION_FAILED",
]
