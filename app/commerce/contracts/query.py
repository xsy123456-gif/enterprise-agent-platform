"""Query contracts: Filter, TimeRange, pagination, QueryResult, and the
Freshness / DataQuality / DataProvenance metadata contracts.

These are the typed boundary for every commerce Read Tool.  ``QueryResult`` is
a generic container (``QueryResult[T]``); Read Tools return typed query
results, never Evidence (Evidence is built later by the EvidenceAssembler).
"""

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from app.commerce.contracts.errors import CommerceValidationError

# Filter operators (v1)
OP_EQ = "EQ"
OP_IN = "IN"
OP_RANGE = "RANGE"
OP_GT = "GT"
OP_GTE = "GTE"
OP_LT = "LT"
OP_LTE = "LTE"
FILTER_OPERATORS = frozenset({OP_EQ, OP_IN, OP_RANGE, OP_GT, OP_GTE, OP_LT, OP_LTE})

# Freshness status
FRESHNESS_FRESH = "FRESH"
FRESHNESS_STALE = "STALE"
FRESHNESS_REFRESHED = "REFRESHED"
FRESHNESS_UNKNOWN = "UNKNOWN"
FRESHNESS_STATUSES = frozenset({
    FRESHNESS_FRESH, FRESHNESS_STALE, FRESHNESS_REFRESHED, FRESHNESS_UNKNOWN,
})

# Data quality status
QUALITY_VALID = "VALID"
QUALITY_PARTIAL = "PARTIAL"
QUALITY_STALE = "STALE"
QUALITY_INSUFFICIENT = "INSUFFICIENT"
QUALITY_INVALID = "INVALID"
QUALITY_STATUSES = frozenset({
    QUALITY_VALID, QUALITY_PARTIAL, QUALITY_STALE, QUALITY_INSUFFICIENT, QUALITY_INVALID,
})

# Provenance source type
PROVENANCE_CANONICAL = "CANONICAL"
PROVENANCE_REFRESHED = "REFRESHED_CANONICAL"
PROVENANCE_DERIVED = "DERIVED_CANONICAL"
PROVENANCE_SOURCE_TYPES = frozenset({
    PROVENANCE_CANONICAL, PROVENANCE_REFRESHED, PROVENANCE_DERIVED,
})

T = TypeVar("T")


@dataclass(frozen=True)
class Filter:
    field: str
    operator: str
    value: Any = None

    def __post_init__(self):
        if not self.field:
            raise CommerceValidationError("filter field must not be empty")
        if self.operator not in FILTER_OPERATORS:
            raise CommerceValidationError(f"unknown filter operator: {self.operator}")
        if self.operator == OP_RANGE and not isinstance(self.value, (list, tuple)):
            raise CommerceValidationError("RANGE filter requires a two-element value")

    def to_dict(self) -> dict:
        return {"field": self.field, "operator": self.operator, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict) -> "Filter":
        return cls(field=data["field"], operator=data["operator"], value=data.get("value"))


@dataclass(frozen=True)
class TimeRange:
    start: str | None = None
    end: str | None = None
    timezone: str = "UTC"
    boundary_policy: str = "INCLUSIVE"

    def __post_init__(self):
        if self.start and self.end and self.start > self.end:
            raise CommerceValidationError("time range start must not be after end")

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "timezone": self.timezone,
            "boundary_policy": self.boundary_policy,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TimeRange":
        return cls(
            start=data.get("start"),
            end=data.get("end"),
            timezone=data.get("timezone", "UTC"),
            boundary_policy=data.get("boundary_policy", "INCLUSIVE"),
        )


@dataclass(frozen=True)
class PageRequest:
    cursor: str | None = None
    limit: int = 50

    def __post_init__(self):
        if self.limit < 1:
            raise CommerceValidationError("page limit must be positive")

    def to_dict(self) -> dict:
        return {"cursor": self.cursor, "limit": self.limit}

    @classmethod
    def from_dict(cls, data: dict) -> "PageRequest":
        return cls(cursor=data.get("cursor"), limit=data.get("limit", 50))


@dataclass(frozen=True)
class PageInfo:
    next_cursor: str | None = None
    has_more: bool = False
    returned_count: int = 0

    def to_dict(self) -> dict:
        return {
            "next_cursor": self.next_cursor,
            "has_more": self.has_more,
            "returned_count": self.returned_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PageInfo":
        return cls(
            next_cursor=data.get("next_cursor"),
            has_more=data.get("has_more", False),
            returned_count=data.get("returned_count", 0),
        )


@dataclass(frozen=True)
class FreshnessMetadata:
    status: str = FRESHNESS_UNKNOWN
    observed_at: str | None = None
    last_synced_at: str | None = None
    policy_id: str = ""
    policy_version: str = ""
    age_seconds: float | None = None

    def __post_init__(self):
        if self.status not in FRESHNESS_STATUSES:
            raise CommerceValidationError(f"unknown freshness status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "observed_at": self.observed_at,
            "last_synced_at": self.last_synced_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "age_seconds": self.age_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FreshnessMetadata":
        return cls(
            status=data.get("status", FRESHNESS_UNKNOWN),
            observed_at=data.get("observed_at"),
            last_synced_at=data.get("last_synced_at"),
            policy_id=data.get("policy_id", ""),
            policy_version=data.get("policy_version", ""),
            age_seconds=data.get("age_seconds"),
        )


@dataclass(frozen=True)
class DataQuality:
    status: str = QUALITY_VALID
    completeness: float = 1.0
    missing_fields: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    validator_version: str = ""

    def __post_init__(self):
        object.__setattr__(self, "missing_fields", tuple(self.missing_fields or ()))
        object.__setattr__(self, "issues", tuple(self.issues or ()))
        if self.status not in QUALITY_STATUSES:
            raise CommerceValidationError(f"unknown data quality status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "completeness": self.completeness,
            "missing_fields": list(self.missing_fields),
            "issues": list(self.issues),
            "validator_version": self.validator_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DataQuality":
        return cls(
            status=data.get("status", QUALITY_VALID),
            completeness=data.get("completeness", 1.0),
            missing_fields=tuple(data.get("missing_fields", ())),
            issues=tuple(data.get("issues", ())),
            validator_version=data.get("validator_version", ""),
        )


@dataclass(frozen=True)
class DataProvenance:
    source_type: str = PROVENANCE_CANONICAL
    upstream_platform: str = ""
    connector_id: str = ""
    connector_version: str = ""
    adapter_id: str = ""
    adapter_version: str = ""
    canonical_schema_version: str = ""
    source_sync_id: str = ""
    source_observed_at: str | None = None
    canonical_written_at: str | None = None

    def __post_init__(self):
        if self.source_type not in PROVENANCE_SOURCE_TYPES:
            raise CommerceValidationError(f"unknown provenance source type: {self.source_type}")

    def to_dict(self) -> dict:
        return {
            "source_type": self.source_type,
            "upstream_platform": self.upstream_platform,
            "connector_id": self.connector_id,
            "connector_version": self.connector_version,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "canonical_schema_version": self.canonical_schema_version,
            "source_sync_id": self.source_sync_id,
            "source_observed_at": self.source_observed_at,
            "canonical_written_at": self.canonical_written_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DataProvenance":
        return cls(
            source_type=data.get("source_type", PROVENANCE_CANONICAL),
            upstream_platform=data.get("upstream_platform", ""),
            connector_id=data.get("connector_id", ""),
            connector_version=data.get("connector_version", ""),
            adapter_id=data.get("adapter_id", ""),
            adapter_version=data.get("adapter_version", ""),
            canonical_schema_version=data.get("canonical_schema_version", ""),
            source_sync_id=data.get("source_sync_id", ""),
            source_observed_at=data.get("source_observed_at"),
            canonical_written_at=data.get("canonical_written_at"),
        )


@dataclass(frozen=True)
class QueryResult(Generic[T]):
    request_id: str
    data: tuple[T, ...] = ()
    page: PageInfo = field(default_factory=PageInfo)
    effective_scope: dict = field(default_factory=dict)
    freshness: FreshnessMetadata = field(default_factory=FreshnessMetadata)
    quality: DataQuality = field(default_factory=DataQuality)
    provenance: DataProvenance = field(default_factory=DataProvenance)
    warnings: tuple[str, ...] = ()
    partial: bool = False
    executed_at: str | None = None
    duration_metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "data", tuple(self.data or ()))
        object.__setattr__(self, "warnings", tuple(self.warnings or ()))
        object.__setattr__(self, "effective_scope", dict(self.effective_scope or {}))
        object.__setattr__(self, "duration_metadata", dict(self.duration_metadata or {}))

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "data": [
                item.to_dict() if hasattr(item, "to_dict") else item for item in self.data
            ],
            "page": self.page.to_dict(),
            "effective_scope": dict(self.effective_scope),
            "freshness": self.freshness.to_dict(),
            "quality": self.quality.to_dict(),
            "provenance": self.provenance.to_dict(),
            "warnings": list(self.warnings),
            "partial": self.partial,
            "executed_at": self.executed_at,
            "duration_metadata": dict(self.duration_metadata),
        }


__all__ = [
    "Filter",
    "TimeRange",
    "PageRequest",
    "PageInfo",
    "FreshnessMetadata",
    "DataQuality",
    "DataProvenance",
    "QueryResult",
    "FILTER_OPERATORS",
    "OP_EQ",
    "OP_IN",
    "OP_RANGE",
    "OP_GT",
    "OP_GTE",
    "OP_LT",
    "OP_LTE",
    "FRESHNESS_STATUSES",
    "FRESHNESS_FRESH",
    "FRESHNESS_STALE",
    "FRESHNESS_REFRESHED",
    "FRESHNESS_UNKNOWN",
    "QUALITY_STATUSES",
    "QUALITY_VALID",
    "QUALITY_PARTIAL",
    "QUALITY_STALE",
    "QUALITY_INSUFFICIENT",
    "QUALITY_INVALID",
    "PROVENANCE_SOURCE_TYPES",
    "PROVENANCE_CANONICAL",
    "PROVENANCE_REFRESHED",
    "PROVENANCE_DERIVED",
]
