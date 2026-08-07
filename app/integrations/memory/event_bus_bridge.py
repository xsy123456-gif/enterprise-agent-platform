from app.memory.api.models import (
    MemoryObservation, MemoryPrincipal, MemorySource, MemorySubmitRequest,
)
from app.memory.models.scope import MemoryScope


class PlatformMemoryEventBridge:
    """Translate platform response events into Memory-owned submit contracts."""

    def __init__(self, memory_system):
        self.memory_system = memory_system

    def handle(self, event):
        if getattr(event, "event_type", None) != "response.completed":
            return None
        payload = event.payload
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            raise ValueError("response.completed must include tenant_id")
        user_id = payload["user_id"]
        agent_id = payload["agent_id"]
        scope = MemoryScope(tenant_id, user_id, agent_id, payload.get("department_id"))
        principal = MemoryPrincipal(
            subject_id=payload.get("subject_id") or user_id,
            tenant_id=tenant_id, user_id=user_id, agent_id=agent_id,
        )
        observations = [
            MemoryObservation("user_input", {"task": payload.get("input")}),
            MemoryObservation("assistant_output", payload.get("output")),
        ]
        observations.extend(
            MemoryObservation("tool_result", result)
            for result in (payload.get("tool_results") or [])
        )
        source_id = (
            getattr(event, "event_id", None)
            or payload.get("task_id")
            or payload.get("trace_id")
            or "runtime-event"
        )
        request = MemorySubmitRequest(
            principal=principal, scope=scope,
            idempotency_key=source_id,
            source=MemorySource("agent_response", source_id),
            observations=observations, trace_id=payload.get("trace_id", ""),
            metadata=dict(payload.get("metadata") or {}),
        )
        return self.memory_system.submit(request)
