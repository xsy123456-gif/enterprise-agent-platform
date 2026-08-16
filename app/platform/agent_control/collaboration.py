"""Agent collaboration protocol (Phase 13.6).

Protocol design only — collaboration execution (delegation / workflow /
negotiation / shared context) is deferred to Phase 14.  ``AgentMessageProtocol``
defines and validates the message contract; it never orchestrates agents.
"""

from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now
from app.platform.agent_control.errors import AgentValidationError


@dataclass(frozen=True)
class AgentMessage:
    message_id: str
    from_agent: str
    to_agent: str
    task: str = ""
    context_reference: str = ""
    trace_id: str = ""
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "task": self.task,
            "context_reference": self.context_reference,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
        }


class AgentMessageProtocol:

    def validate(self, message: AgentMessage) -> AgentMessage:
        if not message.message_id:
            raise AgentValidationError("message_id is required")
        if not message.from_agent:
            raise AgentValidationError("from_agent is required")
        if not message.to_agent:
            raise AgentValidationError("to_agent is required")
        if message.from_agent == message.to_agent:
            raise AgentValidationError("from_agent and to_agent must differ")
        if not message.task:
            raise AgentValidationError("task is required")
        return message


__all__ = ["AgentMessage", "AgentMessageProtocol"]
