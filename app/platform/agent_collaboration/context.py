"""Agent context protocol (Phase 14.4).

Multi-agent collaboration needs controlled context, not shared conversation or
memory.  ``AgentContextEnvelope`` carries only task facts + artifact references
+ user goal references; forbidden fields (tenant / permission / credential /
raw memory / private) are rejected.  Every inter-agent context passes through
``AgentContextProvider``.
"""

import uuid
from dataclasses import dataclass, field

from app.core.time import utc_now
from app.platform.agent_collaboration.errors import ContextAccessDeniedError

FORBIDDEN_CONTEXT_KEYS = (
    "tenant_id", "permission", "permissions", "credential", "token", "secret",
    "raw_memory", "private", "private_data",
)


@dataclass(frozen=True)
class AgentContextEnvelope:
    context_id: str
    task_id: str
    source_agent: str
    target_agent: str
    facts: dict = field(default_factory=dict)
    artifacts: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "facts", dict(self.facts or {}))
        object.__setattr__(self, "artifacts", tuple(self.artifacts or ()))
        object.__setattr__(self, "references", tuple(self.references or ()))
        for key in FORBIDDEN_CONTEXT_KEYS:
            if key in self.facts:
                raise ValueError(f"context must not carry forbidden key {key!r}")
        if not self.context_id:
            raise ValueError("context_id is required")
        if not self.task_id:
            raise ValueError("task_id is required")

    def to_dict(self) -> dict:
        return {
            "context_id": self.context_id,
            "task_id": self.task_id,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "facts": dict(self.facts),
            "artifacts": list(self.artifacts),
            "references": list(self.references),
            "created_at": self.created_at,
        }


class AgentContextProvider:

    def __init__(self):
        self._contexts = {}

    def create_context(self, task_id, source_agent, target_agent, facts=None,
                       artifacts=(), references=(), context_id=None) -> AgentContextEnvelope:
        envelope = AgentContextEnvelope(
            context_id=context_id or uuid.uuid4().hex,
            task_id=task_id, source_agent=source_agent, target_agent=target_agent,
            facts=facts, artifacts=artifacts, references=references,
        )
        self._contexts[envelope.context_id] = envelope
        return envelope

    def get_context(self, context_id, requester_agent=None) -> AgentContextEnvelope:
        envelope = self._contexts.get(context_id)
        if envelope is None:
            raise ContextAccessDeniedError(f"unknown context {context_id!r}")
        self.validate_access(envelope, requester_agent)
        return envelope

    def validate_access(self, envelope, requester_agent):
        if requester_agent is None:
            return True
        if requester_agent in (envelope.source_agent, envelope.target_agent):
            return True
        raise ContextAccessDeniedError(
            f"agent {requester_agent!r} cannot access context "
            f"{envelope.context_id!r}"
        )


__all__ = [
    "AgentContextEnvelope",
    "AgentContextProvider",
    "FORBIDDEN_CONTEXT_KEYS",
]
