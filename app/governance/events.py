from dataclasses import dataclass

from app.governance.models import utc_now


@dataclass
class LifecycleEvent:
    event_type: str
    agent_id: str
    version: str
    operator: str
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = utc_now()

    def to_dict(self):
        return {
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "version": self.version,
            "operator": self.operator,
            "timestamp": self.timestamp,
        }


class EventPublisher:
    def publish(self, event):
        raise NotImplementedError


class EventBusPublisher(EventPublisher):
    def __init__(self, event_bus):
        self.event_bus = event_bus

    def publish(self, event):
        self.event_bus.publish(event)
