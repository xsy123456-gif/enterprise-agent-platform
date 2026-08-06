from app.events.models import Event


class MemoryEventPublisher:
    def __init__(self, event_bus):
        self.event_bus = event_bus

    def __call__(self, event_type, payload_or_event, metadata=None):
        if metadata is None:
            payload = dict(payload_or_event)
        else:
            event = payload_or_event
            payload = {
                "trace_id": event.trace_id, "task_id": event.task_id,
                "agent_id": event.agent_id, "user_id": event.user_id,
                "tenant_id": event.tenant_id, **metadata,
            }
        self.event_bus.publish(Event(event_type, payload))
