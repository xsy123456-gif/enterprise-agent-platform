"""Agent message protocol v2 (Phase 14.1).

Extends the Phase 13.6 message contract with task scoping and message types.
``payload_reference`` is a reference (never the payload itself); the payload it
points to must never contain secret / credential / permission.
"""

from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now
from app.platform.agent_collaboration.errors import CollaborationError

MSG_TASK_REQUEST = "TASK_REQUEST"
MSG_TASK_RESPONSE = "TASK_RESPONSE"
MSG_CONTEXT_REQUEST = "CONTEXT_REQUEST"
MSG_CONTEXT_RESPONSE = "CONTEXT_RESPONSE"
MSG_ERROR = "ERROR"
MESSAGE_TYPES = frozenset({
    MSG_TASK_REQUEST, MSG_TASK_RESPONSE, MSG_CONTEXT_REQUEST,
    MSG_CONTEXT_RESPONSE, MSG_ERROR,
})

FORBIDDEN_PAYLOAD_KEYS = ("secret", "credential", "token", "permission", "scope")


@dataclass(frozen=True)
class AgentMessage:
    message_id: str
    task_id: str
    sender_agent: str
    receiver_agent: str
    message_type: str = MSG_TASK_REQUEST
    payload_reference: str = ""
    trace_id: str = ""
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if self.message_type not in MESSAGE_TYPES:
            raise ValueError(f"unknown message type: {self.message_type}")

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "task_id": self.task_id,
            "sender_agent": self.sender_agent,
            "receiver_agent": self.receiver_agent,
            "message_type": self.message_type,
            "payload_reference": self.payload_reference,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
        }


class AgentMessageProtocol:

    def validate(self, message: AgentMessage) -> AgentMessage:
        if not message.message_id:
            raise CollaborationError("message_id is required")
        if not message.task_id:
            raise CollaborationError("task_id is required")
        if not message.sender_agent:
            raise CollaborationError("sender_agent is required")
        if not message.receiver_agent:
            raise CollaborationError("receiver_agent is required")
        if message.sender_agent == message.receiver_agent:
            raise CollaborationError("sender and receiver must differ")
        return message

    def validate_payload(self, payload: dict) -> dict:
        for key in FORBIDDEN_PAYLOAD_KEYS:
            if key in payload:
                raise CollaborationError(
                    f"payload must not contain forbidden key {key!r}"
                )
        return payload


__all__ = [
    "AgentMessage",
    "AgentMessageProtocol",
    "MESSAGE_TYPES",
    "MSG_TASK_REQUEST",
    "MSG_TASK_RESPONSE",
    "MSG_CONTEXT_REQUEST",
    "MSG_CONTEXT_RESPONSE",
    "MSG_ERROR",
    "FORBIDDEN_PAYLOAD_KEYS",
]
