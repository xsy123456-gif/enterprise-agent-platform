from copy import deepcopy
from threading import RLock

from app.runtime.governance.events import RuntimeEvent
from app.storage.exceptions import ConflictError
from app.storage.ports.event import EventStore


class InMemoryEventStore(EventStore):
    def __init__(self):
        self._events: list[RuntimeEvent] = []
        self._event_ids: set[str] = set()
        self._lock = RLock()

    def append(self, event: RuntimeEvent) -> None:
        if not isinstance(event, RuntimeEvent):
            raise TypeError("event must be a RuntimeEvent")
        with self._lock:
            if event.event_id in self._event_ids:
                raise ConflictError(f"Event already exists: {event.event_id}")
            self._events.append(deepcopy(event))
            self._event_ids.add(event.event_id)

    def query(
        self,
        execution_id: str | None = None,
        event_type: str | None = None,
    ) -> tuple[RuntimeEvent, ...]:
        with self._lock:
            return tuple(
                deepcopy(event)
                for event in self._events
                if (execution_id is None or event.execution_id == execution_id)
                and (event_type is None or event.event_type == event_type)
            )
