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
from app.commerce.review_insight.evaluation import (
    BUSINESS_DEFERRED,
    EVAL_INCONSISTENT,
    EVAL_SCHEMA_INVALID,
    EVAL_VALID,
    ExtractionEvaluation,
    ExtractionEvaluationResult,
)
from app.commerce.review_insight.evidence_adapter import (
    EVIDENCE_CODE_PREFIX,
    ReviewInsightEvidenceAdapter,
)
from app.commerce.review_insight.job import ReviewInsightJobManager
from app.commerce.review_insight.metric_source_adapter import (
    MetricSourceAdapter,
    REVIEW_METRICS,
)
from app.commerce.review_insight.repository import (
    CanonicalReviewInsightRepository,
    ReviewInsightNaturalKey,
    ReviewInsightRepositoryPort,
)
from app.commerce.review_insight.service import (
    ReviewInsightProvenance,
    ReviewInsightService,
)
from app.commerce.review_insight.worker import (
    EVENT_DATA_PUBLISHED,
    EVENT_REVIEW_AVAILABLE,
    CanonicalReviewAccess,
    ReviewAccessPort,
    ReviewInsightWorker,
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
    "ReviewInsightNaturalKey",
    "ReviewInsightRepositoryPort",
    "CanonicalReviewInsightRepository",
    "ReviewInsightProvenance",
    "ReviewInsightService",
    "ReviewInsightJobManager",
    "ReviewAccessPort",
    "CanonicalReviewAccess",
    "ReviewInsightWorker",
    "EVENT_DATA_PUBLISHED",
    "EVENT_REVIEW_AVAILABLE",
    "ReviewInsightEvidenceAdapter",
    "EVIDENCE_CODE_PREFIX",
    "MetricSourceAdapter",
    "REVIEW_METRICS",
    "ExtractionEvaluation",
    "ExtractionEvaluationResult",
    "EVAL_VALID",
    "EVAL_SCHEMA_INVALID",
    "EVAL_INCONSISTENT",
    "BUSINESS_DEFERRED",
    "JOB_CREATED",
    "JOB_RUNNING",
    "JOB_PARTIAL",
    "JOB_SUCCEEDED",
    "JOB_FAILED",
    "JOB_CANCELLED",
    "JOB_STATUSES",
    "RESOURCE_REVIEW",
]
