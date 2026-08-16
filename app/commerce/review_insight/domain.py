"""ReviewInsight worker domain models (Phase 11).

These models live in the worker layer, distinct from the canonical
``ReviewInsight`` entity (``app.commerce.domain.review``).  Extraction inputs
and results are canonical and provider-neutral; provenance is stamped by the
Service, never by a Provider.  None of these carry cause / impact / priority /
recommendation / action.
"""

from dataclasses import dataclass, field

# ReviewInsightJob statuses (§8)
JOB_CREATED = "CREATED"
JOB_RUNNING = "RUNNING"
JOB_PARTIAL = "PARTIAL"
JOB_SUCCEEDED = "SUCCEEDED"
JOB_FAILED = "FAILED"
JOB_CANCELLED = "CANCELLED"
JOB_STATUSES = frozenset({
    JOB_CREATED, JOB_RUNNING, JOB_PARTIAL, JOB_SUCCEEDED, JOB_FAILED,
    JOB_CANCELLED,
})

RESOURCE_REVIEW = "REVIEW"


@dataclass(frozen=True)
class ReviewInput:
    """A raw review slice handed to an extractor (no content in events)."""

    review_id: str
    title: str = ""
    content: str = ""
    rating: float = 0.0
    language: str = ""

    def __post_init__(self):
        if not self.review_id:
            raise ValueError("review_id is required")

    def to_dict(self) -> dict:
        return {
            "review_id": self.review_id,
            "title": self.title,
            "content": self.content,
            "rating": self.rating,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewInput":
        return cls(
            review_id=data["review_id"],
            title=data.get("title", ""),
            content=data.get("content", ""),
            rating=data.get("rating", 0.0),
            language=data.get("language", ""),
        )


@dataclass(frozen=True)
class ReviewExtractionResult:
    """Canonical, provider-neutral extraction output for one review."""

    review_id: str
    sentiment: str = ""
    topics: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    strengths: tuple[str, ...] = ()
    intent: str = ""
    severity: str = ""
    confidence: float | None = None

    def __post_init__(self):
        object.__setattr__(self, "topics", tuple(self.topics or ()))
        object.__setattr__(self, "issues", tuple(self.issues or ()))
        object.__setattr__(self, "strengths", tuple(self.strengths or ()))

    def to_dict(self) -> dict:
        return {
            "review_id": self.review_id,
            "sentiment": self.sentiment,
            "topics": list(self.topics),
            "issues": list(self.issues),
            "strengths": list(self.strengths),
            "intent": self.intent,
            "severity": self.severity,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewExtractionResult":
        return cls(
            review_id=data["review_id"],
            sentiment=data.get("sentiment", ""),
            topics=tuple(data.get("topics", ())),
            issues=tuple(data.get("issues", ())),
            strengths=tuple(data.get("strengths", ())),
            intent=data.get("intent", ""),
            severity=data.get("severity", ""),
            confidence=data.get("confidence"),
        )


@dataclass(frozen=True)
class ReviewExtractionBatchResult:
    """Batch output: per-review results + failed ids + provider metadata."""

    results: tuple[ReviewExtractionResult, ...] = ()
    failed_review_ids: tuple[str, ...] = ()
    provider_meta: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "results", tuple(self.results or ()))
        object.__setattr__(self, "failed_review_ids", tuple(self.failed_review_ids or ()))
        object.__setattr__(self, "provider_meta", dict(self.provider_meta or {}))

    def to_dict(self) -> dict:
        return {
            "results": [r.to_dict() for r in self.results],
            "failed_review_ids": list(self.failed_review_ids),
            "provider_meta": dict(self.provider_meta),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewExtractionBatchResult":
        return cls(
            results=tuple(ReviewExtractionResult.from_dict(r)
                          for r in data.get("results", ())),
            failed_review_ids=tuple(data.get("failed_review_ids", ())),
            provider_meta=data.get("provider_meta", {}),
        )


@dataclass
class ReviewInsightJob:
    """Job lifecycle record (§8).  Mutable: status advances as the worker runs."""

    job_id: str
    tenant_id: str
    event_id: str
    review_ids: tuple[str, ...]
    extractor_id: str
    extractor_version: str
    status: str = JOB_CREATED
    total_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    retry_count: int = 0
    trace_id: str = ""

    def __post_init__(self):
        object.__setattr__(self, "review_ids", tuple(self.review_ids or ()))
        if self.status not in JOB_STATUSES:
            raise ValueError(f"unknown job status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "tenant_id": self.tenant_id,
            "event_id": self.event_id,
            "review_ids": list(self.review_ids),
            "extractor_id": self.extractor_id,
            "extractor_version": self.extractor_version,
            "status": self.status,
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "retry_count": self.retry_count,
            "trace_id": self.trace_id,
        }


@dataclass(frozen=True)
class ReviewAvailableEvent:
    """Event contract for ``commerce.review.available``.

    Carries review ids only — never review content.
    """

    event_id: str
    tenant_id: str
    resource: str = RESOURCE_REVIEW
    review_ids: tuple[str, ...] = ()
    sync_run_id: str = ""
    published_at: str = ""

    def __post_init__(self):
        object.__setattr__(self, "review_ids", tuple(self.review_ids or ()))

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "resource": self.resource,
            "review_ids": list(self.review_ids),
            "sync_run_id": self.sync_run_id,
            "published_at": self.published_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewAvailableEvent":
        return cls(
            event_id=data["event_id"],
            tenant_id=data["tenant_id"],
            resource=data.get("resource", RESOURCE_REVIEW),
            review_ids=tuple(data.get("review_ids", ())),
            sync_run_id=data.get("sync_run_id", ""),
            published_at=data.get("published_at", ""),
        )


__all__ = [
    "ReviewInput",
    "ReviewExtractionResult",
    "ReviewExtractionBatchResult",
    "ReviewInsightJob",
    "ReviewAvailableEvent",
    "JOB_CREATED",
    "JOB_RUNNING",
    "JOB_PARTIAL",
    "JOB_SUCCEEDED",
    "JOB_FAILED",
    "JOB_CANCELLED",
    "JOB_STATUSES",
    "RESOURCE_REVIEW",
]
