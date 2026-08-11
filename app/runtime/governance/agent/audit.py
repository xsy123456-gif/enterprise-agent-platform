"""Agent governance evidence emitted through the existing RuntimeEvent plane."""

import uuid

from app.runtime.governance.events import RuntimeEvent


class AgentGovernanceAuditor:
    def __init__(self, event_bus=None, event_store=None):
        self.event_bus = event_bus
        self.event_store = event_store

    def emit(
        self,
        event_type,
        request,
        node,
        *,
        status,
        authorization_id=None,
        context_projection_id=None,
        payload=None,
    ):
        event = RuntimeEvent(
            event_type=event_type,
            execution_id=request.execution_id,
            trace_id=request.trace_id,
            agent_id=node.agent_id,
            agent_version=self._artifact_version(node.artifact_id),
            artifact_id=node.artifact_id,
            artifact_hash=node.artifact_hash,
            backend_type="multi_agent",
            status=status,
            parent_agent_id=request.parent_agent,
            target_agent_id=request.target_agent,
            agent_execution_id=request.agent_execution_id,
            invocation_id=request.invocation_id,
            authorization_id=authorization_id,
            context_projection_id=context_projection_id,
            payload=dict(payload or {}),
        )
        if self.event_store is not None:
            self.event_store.append(event)
        if self.event_bus is not None:
            self.event_bus.publish(event)
        return event

    @staticmethod
    def _artifact_version(artifact_id):
        parts = artifact_id.split(":", 2)
        return parts[1] if len(parts) > 1 and parts[1] else "unknown"


class AgentGovernanceAuditSubscriber:
    """Projects governance RuntimeEvents into the existing AuditRepository port."""

    EVENT_PREFIXES = (
        "agent.authorization.", "agent.context.", "agent.invocation.",
        "agent.result.",
    )

    def __init__(self, repository):
        self.repository = repository

    def handle(self, event):
        if not isinstance(event, RuntimeEvent):
            raise TypeError("event must be RuntimeEvent")
        if not event.event_type.startswith(self.EVENT_PREFIXES):
            return None
        record = {
            "audit_id": str(uuid.uuid4()),
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "execution_id": event.execution_id,
            "trace_id": event.trace_id,
            "parent_agent_id": event.parent_agent_id,
            "target_agent_id": event.target_agent_id,
            "authorization_id": event.authorization_id,
            "context_projection_id": event.context_projection_id,
            "status": event.status,
        }
        self.repository.write(record)
        return record
