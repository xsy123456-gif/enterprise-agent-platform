from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass(frozen=True)
class ToolCallRequest:
    tool_name: str
    arguments: Any
    trace_id: str
    execution_id: str
    agent_id: str
    user_id: str
    agent_version: str | None = None
    tenant_id: str | None = None
    role: str | None = None
    department_id: str | None = None
    capability: str | None = None
    allowed_tools: tuple[str, ...] = ()
    legacy_event_compat: bool = False
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        for name in (
            "tool_name", "trace_id", "execution_id", "agent_id", "user_id",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        if not isinstance(self.allowed_tools, tuple):
            raise TypeError("allowed_tools must be a tuple")


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": dict(self.metadata),
        }
