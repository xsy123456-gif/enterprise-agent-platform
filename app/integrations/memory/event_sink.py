from app.events.models import Event


class PlatformMemoryEventSink:
    """Optional composition-root adapter from Memory events to platform EventBus."""

    def __init__(self, event_bus):
        self.event_bus = event_bus

    def publish(self, event):
        self.event_bus.publish(Event(event.event_type, dict(event.payload)))
