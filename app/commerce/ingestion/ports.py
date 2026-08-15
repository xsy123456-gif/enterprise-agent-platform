"""Connector / Adapter ports.

Connector = transport only (raw source DTOs).  Adapter = semantic mapping only.
A Connector must never write Canonical; an Adapter must never call HTTP.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.commerce.ingestion.envelope import CanonicalMutation, SourceRecordEnvelope

SYNC_FULL_SNAPSHOT = "FULL_SNAPSHOT"
SYNC_INCREMENTAL = "INCREMENTAL"
SYNC_MODES = frozenset({SYNC_FULL_SNAPSHOT, SYNC_INCREMENTAL})


@dataclass(frozen=True)
class FetchRequest:
    resource: str
    mode: str
    cursor: str | None = None
    lookback: int = 0
    limit: int = 100


@dataclass(frozen=True)
class FetchResult:
    envelopes: tuple[SourceRecordEnvelope, ...] = ()
    next_cursor: str | None = None
    complete: bool = True

    def __post_init__(self):
        object.__setattr__(self, "envelopes", tuple(self.envelopes or ()))


class ConnectorPort(ABC):
    @abstractmethod
    def fetch(self, request: FetchRequest) -> FetchResult:
        pass


class AdapterMappingError(Exception):
    """An adapter could not map a source record (-> quarantine)."""


class AdapterPort(ABC):
    @abstractmethod
    def adapt(self, envelope: SourceRecordEnvelope) -> list[CanonicalMutation]:
        pass


__all__ = [
    "ConnectorPort",
    "AdapterPort",
    "AdapterMappingError",
    "FetchRequest",
    "FetchResult",
    "SYNC_FULL_SNAPSHOT",
    "SYNC_INCREMENTAL",
    "SYNC_MODES",
]
