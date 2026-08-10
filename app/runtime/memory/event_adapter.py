from dataclasses import dataclass, field
from typing import Any

from app.memory.api.models import (
    MemoryObservation,
    MemoryPrincipal,
    MemorySource,
)
from app.memory.api.public_models import MemoryWriteRequest
from app.memory.models.scope import MemoryScope
from app.runtime.governance.events import RuntimeEvent


@dataclass(frozen=True)
class MemoryContext:
    user_id: str
    tenant_id: str
    agent_id: str
    execution_id: str
    trace_id: str
    permission_context: dict[str, Any] = field(default_factory=dict)
    policy_context: dict[str, Any] = field(default_factory=dict)
    department_id: str | None = None
    subject_id: str | None = None


@dataclass(frozen=True)
class MemoryEvent:
    event_type: str
    execution_id: str
    agent_id: str
    user_id: str
    content: Any
    metadata: dict[str, Any] = field(default_factory=dict)
    context: MemoryContext | None = None


class MemoryEventAdapter:
    """Translate canonical Runtime evidence into Memory public contracts."""

    RESPONSE_COMPLETED = "response.completed"

    def adapt(self, event: RuntimeEvent) -> MemoryEvent:
        if not isinstance(event, RuntimeEvent):
            raise TypeError("event must be a canonical RuntimeEvent")
        if event.event_type != self.RESPONSE_COMPLETED:
            raise ValueError(f"Unsupported Memory source event: {event.event_type}")
        payload = dict(event.payload)
        required = ("tenant_id", "user_id")
        missing = [name for name in required if not payload.get(name)]
        if missing:
            raise ValueError(
                f"response.completed missing Memory identity: {', '.join(missing)}"
            )
        context = MemoryContext(
            user_id=payload["user_id"],
            tenant_id=payload["tenant_id"],
            agent_id=event.agent_id,
            execution_id=event.execution_id,
            trace_id=event.trace_id,
            permission_context=dict(payload.get("permission_context") or {}),
            policy_context=dict(payload.get("policy_context") or {}),
            department_id=payload.get("department_id"),
            subject_id=payload.get("subject_id"),
        )
        return MemoryEvent(
            event_type=event.event_type,
            execution_id=event.execution_id,
            agent_id=event.agent_id,
            user_id=context.user_id,
            content=payload.get("output"),
            metadata={
                "input": payload.get("input"),
                "tool_results": list(payload.get("tool_results") or []),
                **dict(payload.get("metadata") or {}),
            },
            context=context,
        )

    def to_write_request(self, event: MemoryEvent) -> MemoryWriteRequest:
        context = event.context
        if context is None:
            raise ValueError("MemoryEvent requires governed MemoryContext")
        observations = []
        if event.metadata.get("input") is not None:
            observations.append(
                MemoryObservation("user_input", event.metadata["input"])
            )
        if event.content is not None:
            observations.append(MemoryObservation("assistant_output", event.content))
        observations.extend(
            MemoryObservation("tool_result", result)
            for result in event.metadata.get("tool_results", [])
        )
        if not observations:
            raise ValueError("response.completed contains no Memory observations")
        principal = MemoryPrincipal(
            subject_id=context.subject_id or context.user_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            agent_id=context.agent_id,
        )
        return MemoryWriteRequest(
            principal=principal,
            scope=MemoryScope(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                agent_id=context.agent_id,
                department_id=context.department_id,
            ),
            idempotency_key=event.execution_id,
            source=MemorySource("agent_response", event.execution_id),
            observations=observations,
            trace_id=context.trace_id,
            metadata={
                **event.metadata,
                "execution_id": context.execution_id,
                "permission_context": context.permission_context,
                "policy_context": context.policy_context,
            },
        )
