"""FactQueryExecutorPort — the abstract fact-access boundary for FACT_QUERY.

Phase 5 does NOT access Repository / QueryService / PostgreSQL.  A diagnostic
plan reads facts through this port, which is invoked with a Runtime-injected
``TrustedExecutionContext``.  The request spec is declarative (no SQL, no raw
tenant/principal/scope); tenant/principal/permission/scope come ONLY from the
trusted context, never from the plan, step params, the spec, or an LLM.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.commerce.contracts.subject import SubjectRef

FACT_QUALITY_VALID = "VALID"
FACT_QUALITY_PARTIAL = "PARTIAL"
FACT_QUALITY_INSUFFICIENT = "INSUFFICIENT"

FRESHNESS_FRESH = "FRESH"
FRESHNESS_STALE = "STALE"
FRESHNESS_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TrustedExecutionContext:
    """Immutable trusted projection of the Platform Runtime / AccessContext.

    This is the *only* source of tenant / principal / organization / scope /
    permission during a plan execution.  Commerce does NOT own the identity or
    authorization fact source; it only consumes this trusted projection.  The
    dataclass is frozen so no plan, step, query or handler can mutate it.
    """

    tenant_id: str
    principal_id: str = ""
    organization_id: str = ""
    scopes: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    trace_id: str = ""
    execution_id: str = ""
    environment: str = ""

    def __post_init__(self):
        object.__setattr__(self, "scopes", tuple(self.scopes or ()))
        object.__setattr__(self, "permissions", tuple(self.permissions or ()))


@dataclass(frozen=True)
class FactQuerySpec:
    query_id: str
    capability: str          # capability requirement (e.g. commerce.metrics.read)
    resource: str = ""       # business query resource hint (not a capability)
    subject: SubjectRef | None = None
    params: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "params", dict(self.params or {}))

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "capability": self.capability,
            "resource": self.resource,
            "subject": self.subject.to_dict() if self.subject else None,
            "params": dict(self.params),
        }


@dataclass(frozen=True)
class FactQueryResult:
    query_id: str
    records: tuple[dict, ...] = ()
    quality: str = FACT_QUALITY_VALID
    freshness: str = FRESHNESS_UNKNOWN
    provenance: dict | None = None

    def __post_init__(self):
        object.__setattr__(self, "records", tuple(dict(r) for r in (self.records or ())))
        if self.provenance is not None:
            object.__setattr__(self, "provenance", dict(self.provenance))


class FactQueryExecutorPort(ABC):
    @abstractmethod
    def execute(self, spec: FactQuerySpec, trusted_context: TrustedExecutionContext) -> FactQueryResult:
        pass


class FakeFactQueryExecutor(FactQueryExecutorPort):
    """In-memory fake: serves facts from a lookup keyed by (capability, subject id).

    Records the trusted context it received so tests can assert that a request
    cannot override it.
    """

    def __init__(self, facts=None):
        self.facts = dict(facts or {})
        self.last_trusted_context = None

    def execute(self, spec, trusted_context):
        self.last_trusted_context = trusted_context
        key = (spec.capability, spec.resource, spec.subject.id if spec.subject else None)
        entry = self.facts.get(key)
        if entry is None:
            return FactQueryResult(query_id=spec.query_id, records=(), quality=FACT_QUALITY_INSUFFICIENT)
        return FactQueryResult(
            query_id=spec.query_id,
            records=tuple(dict(r) for r in entry.get("records", ())),
            quality=entry.get("quality", FACT_QUALITY_VALID),
            freshness=entry.get("freshness", FRESHNESS_FRESH),
        )


__all__ = [
    "FactQueryExecutorPort",
    "FactQuerySpec",
    "FactQueryResult",
    "FakeFactQueryExecutor",
    "TrustedExecutionContext",
    "FACT_QUALITY_VALID",
    "FACT_QUALITY_PARTIAL",
    "FACT_QUALITY_INSUFFICIENT",
    "FRESHNESS_FRESH",
    "FRESHNESS_STALE",
    "FRESHNESS_UNKNOWN",
]
