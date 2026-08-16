"""ReviewInsight Intelligence Worker (Phase 11).

Event-driven infrastructure that turns raw Reviews into stable, governed,
regenerable ``ReviewInsight`` AI-derived facts.  This package holds the worker
layer only — the canonical ``ReviewInsight`` entity lives in
``app.commerce.domain.review``.
"""

from app.commerce.review_insight.contracts import ReviewExtractorPort
from app.commerce.review_insight.domain import (
    JOB_CANCELLED,
    JOB_CREATED,
    JOB_FAILED,
    JOB_PARTIAL,
    JOB_RUNNING,
    JOB_STATUSES,
    JOB_SUCCEEDED,
    RESOURCE_REVIEW,
    ReviewAvailableEvent,
    ReviewExtractionBatchResult,
    ReviewExtractionResult,
    ReviewInput,
    ReviewInsightJob,
)
from app.commerce.review_insight.errors import (
    ExtractionError,
    ExtractorUnavailableError,
    JobNotFoundError,
    ReviewInsightError,
)

__all__ = [
    "ReviewExtractorPort",
    "ReviewInput",
    "ReviewExtractionResult",
    "ReviewExtractionBatchResult",
    "ReviewInsightJob",
    "ReviewAvailableEvent",
    "ReviewInsightError",
    "ExtractionError",
    "ExtractorUnavailableError",
    "JobNotFoundError",
    "JOB_CREATED",
    "JOB_RUNNING",
    "JOB_PARTIAL",
    "JOB_SUCCEEDED",
    "JOB_FAILED",
    "JOB_CANCELLED",
    "JOB_STATUSES",
    "RESOURCE_REVIEW",
]
