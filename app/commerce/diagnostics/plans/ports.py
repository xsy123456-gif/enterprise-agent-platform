"""FactQueryExecutorPort — the abstract fact-access boundary for FACT_QUERY.

Phase 5 does NOT access Repository / QueryService / PostgreSQL; a diagnostic
plan reads facts through this port, which a Fake (or, in Phase 6+, a real
Commerce Tool-backed implementation) satisfies.  ``FactQuerySpec`` is a
declarative query (no SQL, no raw filters).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.commerce.contracts.subject import SubjectRef

FACT_QUALITY_VALID = "VALID"
FACT_QUALITY_PARTIAL = "PARTIAL"
FACT_QUALITY_INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class FactQuerySpec:
    query_id: str
    resource: str
    subject: SubjectRef
    params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "resource": self.resource,
            "subject": self.subject.to_dict(),
            "params": dict(self.params),
        }


@dataclass(frozen=True)
class FactQueryResult:
    query_id: str
    records: tuple[dict, ...] = ()
    quality: str = FACT_QUALITY_VALID

    def __post_init__(self):
        object.__setattr__(self, "records", tuple(dict(r) for r in (self.records or ())))


class FactQueryExecutorPort(ABC):
    @abstractmethod
    def execute(self, spec: FactQuerySpec) -> FactQueryResult:
        pass


class FakeFactQueryExecutor(FactQueryExecutorPort):
    """In-memory fake: serves facts from a lookup keyed by (resource, subject id).

    Used for Phase 5 tests and mini plans; never touches Repository / QueryService.
    """

    def __init__(self, facts=None):
        self.facts = dict(facts or {})

    def execute(self, spec):
        key = (spec.resource, spec.subject.id)
        entry = self.facts.get(key)
        if entry is None:
            return FactQueryResult(query_id=spec.query_id, records=(), quality=FACT_QUALITY_INSUFFICIENT)
        return FactQueryResult(
            query_id=spec.query_id,
            records=tuple(dict(r) for r in entry.get("records", ())),
            quality=entry.get("quality", FACT_QUALITY_VALID),
        )


__all__ = [
    "FactQueryExecutorPort",
    "FactQuerySpec",
    "FactQueryResult",
    "FakeFactQueryExecutor",
    "FACT_QUALITY_VALID",
    "FACT_QUALITY_PARTIAL",
    "FACT_QUALITY_INSUFFICIENT",
]
