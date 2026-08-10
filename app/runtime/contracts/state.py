from dataclasses import asdict, dataclass, field, is_dataclass, replace
from typing import Any


def serialize_value(value):
    if hasattr(value, "to_dict"):
        return serialize_value(value.to_dict())
    if is_dataclass(value):
        return serialize_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    return value


@dataclass
class AgentRuntimeState:
    """Serializable, backend-neutral state exchanged by Runtime Contract v1."""

    task_id: str
    trace_id: str
    tenant_id: str
    agent_id: str
    agent_version: str
    current_node: str | None = None
    status: str = "created"
    messages: list[Any] = field(default_factory=list)
    plan: Any | None = None
    memory_context: Any | None = None
    tool_results: list[Any] = field(default_factory=list)
    response: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_id: str | None = None
    user_id: str | None = None
    department_id: str | None = None
    permission_context: dict[str, Any] = field(default_factory=dict)
    policy_context: dict[str, Any] = field(default_factory=dict)
    authorization_result: Any | None = None
    audit_context: dict[str, Any] = field(default_factory=dict)
    request_context: dict[str, Any] = field(default_factory=dict)
    memory_policy: Any | None = None

    def __post_init__(self):
        for name in ("task_id", "trace_id", "tenant_id", "agent_id", "agent_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.status, str) or not self.status:
            raise ValueError("status is required")

    def apply_patch(self, state_patch):
        if not isinstance(state_patch, dict):
            raise TypeError("state_patch must be a mapping")
        fields = self.__dataclass_fields__
        unknown = set(state_patch) - set(fields)
        if unknown:
            raise ValueError(f"Unknown runtime state fields: {sorted(unknown)}")
        candidate = replace(self, **state_patch)
        for name in fields:
            setattr(self, name, getattr(candidate, name))
        return self

    def patched(self, state_patch):
        candidate = replace(self)
        return candidate.apply_patch(state_patch)

    def to_dict(self):
        return serialize_value({
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "current_node": self.current_node,
            "status": self.status,
            "messages": self.messages,
            "plan": self.plan,
            "memory_context": self.memory_context,
            "tool_results": self.tool_results,
            "response": self.response,
            "metadata": self.metadata,
            "execution_id": self.execution_id,
            "user_id": self.user_id,
            "department_id": self.department_id,
            "permission_context": self.permission_context,
            "policy_context": self.policy_context,
            "authorization_result": self.authorization_result,
            "audit_context": self.audit_context,
            "request_context": self.request_context,
            "memory_policy": self.memory_policy,
        })

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))
