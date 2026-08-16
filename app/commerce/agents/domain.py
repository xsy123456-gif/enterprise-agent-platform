"""Employee Agent domain models (Phase 12.1).

An Agent is the business *entry point* — not an execution engine, not a prompt,
not a permission holder.  It is defined as a role (``AgentDefinition``), its
capabilities are declared in a ``AgentManifest``, and a running interaction is
represented by ``AgentSession`` / ``AgentRequest`` / ``AgentResponse``.

Security: none of these models carry ``tenant_id`` / ``principal_id`` /
``role`` / ``permission`` / ``scope`` — those are injected by the Runtime as the
``TrustedExecutionContext`` and can never be set by a request.
"""

from dataclasses import dataclass, field
from typing import Any

from app.commerce.domain.base import utc_now

# Agent lifecycle (§6) — mirrors the frozen Skill lifecycle.
AGENT_DRAFT = "DRAFT"
AGENT_VALIDATED = "VALIDATED"
AGENT_ACTIVE = "ACTIVE"
AGENT_DEPRECATED = "DEPRECATED"
AGENT_DISABLED = "DISABLED"
AGENT_STATUSES = frozenset({
    AGENT_DRAFT, AGENT_VALIDATED, AGENT_ACTIVE, AGENT_DEPRECATED, AGENT_DISABLED,
})

# AgentSession states (§5.4)
SESSION_CREATED = "CREATED"
SESSION_ACTIVE = "ACTIVE"
SESSION_WAITING = "WAITING"
SESSION_COMPLETED = "COMPLETED"
SESSION_FAILED = "FAILED"
SESSION_CLOSED = "CLOSED"
SESSION_STATUSES = frozenset({
    SESSION_CREATED, SESSION_ACTIVE, SESSION_WAITING,
    SESSION_COMPLETED, SESSION_FAILED, SESSION_CLOSED,
})

# AgentResponse types (§5.6)
RESPONSE_ANSWER = "ANSWER"
RESPONSE_DIAGNOSTIC = "DIAGNOSTIC"
RESPONSE_CLARIFICATION = "CLARIFICATION"
RESPONSE_ERROR = "ERROR"
RESPONSE_TYPES = frozenset({
    RESPONSE_ANSWER, RESPONSE_DIAGNOSTIC, RESPONSE_CLARIFICATION, RESPONSE_ERROR,
})


@dataclass(frozen=True)
class AgentDefinition:
    """An employee role definition.

    Forbidden fields (by design): prompt / tools / permissions / runtime_state /
    conversation.  Capabilities belong to the ``AgentManifest``.
    """

    agent_id: str
    version: str
    name: str
    description: str
    domain: str = ""
    owner: str = ""
    status: str = AGENT_DRAFT
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if not self.name:
            raise ValueError("agent name is required")
        if not self.description:
            raise ValueError("agent description is required")
        if self.status not in AGENT_STATUSES:
            raise ValueError(f"unknown agent status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "owner": self.owner,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentDefinition":
        return cls(
            agent_id=data["agent_id"],
            version=data["version"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            domain=data.get("domain", ""),
            owner=data.get("owner", ""),
            status=data.get("status", AGENT_DRAFT),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )


@dataclass(frozen=True)
class AgentSession:
    """A running interaction instance (what is executing).

    Carries no ``tenant_id`` / ``principal_id``; if scoping is needed it must
    come from the ``TrustedExecutionContext``.
    """

    session_id: str
    agent_id: str
    conversation_id: str = ""
    status: str = SESSION_CREATED
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.session_id:
            raise ValueError("session_id is required")
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if self.status not in SESSION_STATUSES:
            raise ValueError(f"unknown session status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "conversation_id": self.conversation_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentSession":
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            conversation_id=data.get("conversation_id", ""),
            status=data.get("status", SESSION_CREATED),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )


@dataclass(frozen=True)
class AgentRequest:
    """User input to an agent.

    Forbidden: tenant_id / principal_id / role / permission / scope — a request
    can never forge identity or scope.
    """

    request_id: str
    session_id: str = ""
    message: str = ""
    attachments: tuple[str, ...] = ()
    trace_id: str = ""

    def __post_init__(self):
        object.__setattr__(self, "attachments", tuple(self.attachments or ()))
        if not self.request_id:
            raise ValueError("request_id is required")

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "message": self.message,
            "attachments": list(self.attachments),
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentRequest":
        return cls(
            request_id=data["request_id"],
            session_id=data.get("session_id", ""),
            message=data.get("message", ""),
            attachments=tuple(data.get("attachments", ())),
            trace_id=data.get("trace_id", ""),
        )


@dataclass(frozen=True)
class AgentResponse:
    """Final output of an agent interaction."""

    response_id: str
    session_id: str = ""
    response_type: str = RESPONSE_ANSWER
    message: str = ""
    diagnostic_result: Any = None
    evidence: tuple = ()
    citations: tuple = ()
    next_actions: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "evidence", tuple(self.evidence or ()))
        object.__setattr__(self, "citations", tuple(self.citations or ()))
        object.__setattr__(self, "next_actions", tuple(self.next_actions or ()))
        if not self.response_id:
            raise ValueError("response_id is required")
        if self.response_type not in RESPONSE_TYPES:
            raise ValueError(f"unknown response type: {self.response_type}")

    def to_dict(self) -> dict:
        return {
            "response_id": self.response_id,
            "session_id": self.session_id,
            "response_type": self.response_type,
            "message": self.message,
            "diagnostic_result": (
                self.diagnostic_result.to_dict()
                if hasattr(self.diagnostic_result, "to_dict")
                else self.diagnostic_result
            ),
            "evidence": [
                e.to_dict() if hasattr(e, "to_dict") else e for e in self.evidence
            ],
            "citations": list(self.citations),
            "next_actions": list(self.next_actions),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentResponse":
        return cls(
            response_id=data["response_id"],
            session_id=data.get("session_id", ""),
            response_type=data.get("response_type", RESPONSE_ANSWER),
            message=data.get("message", ""),
            diagnostic_result=data.get("diagnostic_result"),
            evidence=tuple(data.get("evidence", ())),
            citations=tuple(data.get("citations", ())),
            next_actions=tuple(data.get("next_actions", ())),
        )


__all__ = [
    "AgentDefinition",
    "AgentSession",
    "AgentRequest",
    "AgentResponse",
    "AGENT_STATUSES",
    "AGENT_DRAFT",
    "AGENT_VALIDATED",
    "AGENT_ACTIVE",
    "AGENT_DEPRECATED",
    "AGENT_DISABLED",
    "SESSION_STATUSES",
    "SESSION_CREATED",
    "SESSION_ACTIVE",
    "SESSION_WAITING",
    "SESSION_COMPLETED",
    "SESSION_FAILED",
    "SESSION_CLOSED",
    "RESPONSE_TYPES",
    "RESPONSE_ANSWER",
    "RESPONSE_DIAGNOSTIC",
    "RESPONSE_CLARIFICATION",
    "RESPONSE_ERROR",
]
