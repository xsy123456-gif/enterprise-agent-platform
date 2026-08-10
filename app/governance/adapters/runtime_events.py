from app.runtime.governance.events import RuntimeEvent


class RuntimeGovernanceEmitter:
    """Publishes canonical governance evidence to the existing bus and store."""

    def __init__(self, context, event_bus=None, event_store=None):
        self.context = context
        self.event_bus = event_bus
        self.event_store = event_store

    def emit(self, event_type, status, payload=None):
        event = RuntimeEvent(
            event_type=event_type,
            execution_id=self.context.execution_id,
            trace_id=self.context.trace_id,
            agent_id=self.context.agent_id,
            agent_version=self.context.agent_version,
            artifact_id=self.context.artifact_id,
            artifact_hash=self.context.artifact_hash,
            backend_type=self.context.backend_type,
            status=status,
            payload=dict(payload or {}),
        )
        if self.event_store is not None:
            self.event_store.append(event)
        if self.event_bus is not None:
            self.event_bus.publish(event)
        return event
