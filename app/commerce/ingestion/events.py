"""Sync domain events (commerce.sync.completed / commerce.data.published)."""

EVENT_SYNC_COMPLETED = "commerce.sync.completed"
EVENT_DATA_PUBLISHED = "commerce.data.published"


class SyncEvents:
    """Records sync events; optionally forwards to the platform EventBus."""

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.published = []

    def publish(self, event_type, payload):
        event = {"event_type": event_type, **payload}
        self.published.append(event)
        if self.event_bus is not None:
            from app.events.models import Event
            self.event_bus.publish(Event(event_type, dict(payload)))
        return event

    def completed_events(self):
        return [e for e in self.published if e["event_type"] == EVENT_SYNC_COMPLETED]

    def published_events(self):
        return [e for e in self.published if e["event_type"] == EVENT_DATA_PUBLISHED]


__all__ = ["SyncEvents", "EVENT_SYNC_COMPLETED", "EVENT_DATA_PUBLISHED"]
