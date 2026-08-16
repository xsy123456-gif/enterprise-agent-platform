"""ReviewInsight service layer (Phase 11.2).

The Service turns canonical ``ReviewExtractionResult`` into ``ReviewInsight``
with full provenance, validates confidence, and persists idempotently.  It does
NOT call an LLM, extract rules, infer causes, or calculate metrics.
"""

import uuid
from dataclasses import dataclass

from app.commerce.domain.review import ReviewInsight
from app.commerce.review_insight.domain import (
    ReviewExtractionBatchResult,
    ReviewExtractionResult,
)
from app.commerce.review_insight.errors import ExtractionError
from app.commerce.review_insight.repository import (
    ReviewInsightNaturalKey,
    ReviewInsightRepositoryPort,
)


@dataclass(frozen=True)
class ReviewInsightProvenance:
    """Extraction provenance stamped by the Service (never by a provider)."""

    extractor_id: str
    extractor_version: str
    model_provider: str = ""
    model_version: str = ""
    prompt_version: str = ""
    knowledge_policy_version: str = ""
    knowledge_context_version: str = ""


class ReviewInsightService:

    def __init__(self, repository: ReviewInsightRepositoryPort,
                 provenance: ReviewInsightProvenance):
        self.repository = repository
        self.provenance = provenance

    def submit_extraction_result(self, tenant_id, result: ReviewExtractionResult) -> ReviewInsight:
        """Validate, then idempotently persist one extraction result."""
        self._validate(result)
        natural_key = ReviewInsightNaturalKey(
            result.review_id, self.provenance.extractor_id,
            self.provenance.extractor_version,
        )
        if self.repository.exists(tenant_id, natural_key):
            return self._find_existing(tenant_id, natural_key)
        return self.repository.save(tenant_id, self._to_insight(result))

    def submit_batch(self, tenant_id, batch: ReviewExtractionBatchResult) -> list[ReviewInsight]:
        insights = []
        for result in batch.results:
            insights.append(self.submit_extraction_result(tenant_id, result))
        return insights

    def _find_existing(self, tenant_id, natural_key):
        for insight in self.repository.list_by_review(tenant_id, natural_key.review_id):
            if (insight.extractor_id == natural_key.extractor_id
                    and insight.extractor_version == natural_key.extractor_version):
                return insight
        return None

    def _validate(self, result):
        if result.confidence is not None and not (0.0 <= result.confidence <= 1.0):
            raise ExtractionError(
                f"confidence {result.confidence!r} out of range [0, 1] "
                f"for review {result.review_id!r}"
            )

    def _to_insight(self, result):
        return ReviewInsight(
            review_insight_id=uuid.uuid4().hex,
            review_id=result.review_id,
            sentiment=result.sentiment,
            topics=result.topics,
            issues=result.issues,
            strengths=result.strengths,
            intent=result.intent,
            severity=result.severity,
            confidence=result.confidence,
            model_provider=self.provenance.model_provider,
            model_version=self.provenance.model_version,
            extractor_id=self.provenance.extractor_id,
            extractor_version=self.provenance.extractor_version,
            prompt_version=self.provenance.prompt_version,
            knowledge_policy_version=self.provenance.knowledge_policy_version,
            knowledge_context_version=self.provenance.knowledge_context_version,
        )


__all__ = ["ReviewInsightProvenance", "ReviewInsightService"]
