from abc import ABC, abstractmethod
from typing import Any, Mapping


class AuditRepository(ABC):
    """Immutable audit record persistence boundary."""

    @abstractmethod
    def write(self, record: Mapping[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def query(self, **filters: Any) -> tuple[dict[str, Any], ...]:
        raise NotImplementedError

    @abstractmethod
    def export(self) -> tuple[dict[str, Any], ...]:
        raise NotImplementedError
