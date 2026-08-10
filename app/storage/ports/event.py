from abc import ABC, abstractmethod

from app.runtime.governance.events import RuntimeEvent


class EventStore(ABC):
    """Append-only persistence boundary for runtime evidence events."""

    @abstractmethod
    def append(self, event: RuntimeEvent) -> None:
        raise NotImplementedError

    @abstractmethod
    def query(
        self,
        execution_id: str | None = None,
        event_type: str | None = None,
    ) -> tuple[RuntimeEvent, ...]:
        raise NotImplementedError
