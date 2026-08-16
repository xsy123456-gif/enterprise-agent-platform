"""ReviewInsight service layer (Phase 11.2 + 11.3).

The Service turns canonical ``ReviewExtractionResult`` into ``ReviewInsight``
with full provenance, validates confidence, and persists idempotently.  It does
NOT call an LLM, extract rules, infer causes, or calculate metrics.

``run_job`` orchestrates a full event job: fetch Reviews, call the Extractor,
submit results, and set PARTIAL / SUCCEEDED / FAILED.
"""

import uuid
from dataclasses import dataclass

from app.commerce.domain.review import ReviewInsight
from app.commerce.review_insight.domain import (
    JOB_FAILED,
    JOB_PARTIAL,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    ReviewExtractionBatchResult,
    ReviewExtractionResult,
    ReviewInput,
)
from app.commerce.review_insight.errors import (
    ExtractionError,
    ExtractorUnavailableError,
)
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
                 provenance: ReviewInsightProvenance,
                 review_access=None, extractor=None):
        self.repository = repository
        self.provenance = provenance
        self.review_access = review_access
        self.extractor = extractor

    def run_job(self, job):
        """Fetch -> extract -> submit; enforce PARTIAL / SUCCEEDED / FAILED."""
        if self.review_access is None or self.extractor is None:
            raise ExtractionError("run_job requires review_access and extractor")
        job.status = JOB_RUNNING
        job.total_count = len(job.review_ids)
        try:
            reviews = self.review_access.get_reviews(job.tenant_id, job.review_ids)
            inputs = [
                ReviewInput(
                    review_id=r.review_id,
                    title=r.title,
                    content=r.content,
                    rating=r.rating,
                    language=r.language,
                )
                for r in reviews
            ]
            batch = self.extractor.extract_batch(inputs)
        except ExtractorUnavailableError as error:
            job.status = JOB_FAILED
            job.error_summary = str(error)
            return job
        except Exception as error:  # noqa: BLE001 - every failure is recorded
            job.status = JOB_FAILED
            job.error_summary = f"{type(error).__name__}: {error}"
            return job

        success = 0
        failed = 0
        for result in batch.results:
            try:
                self.submit_extraction_result(job.tenant_id, result)
                success += 1
            except ExtractionError as error:
                failed += 1
                job.error_summary = self._append_error(
                    job.error_summary, f"{result.review_id}: {error}")
        extracted = {r.review_id for r in batch.results}
        failed += len(batch.failed_review_ids)
        failed += sum(
            1 for rid in job.review_ids
            if rid not in extracted and rid not in batch.failed_review_ids
        )
        job.success_count = success
        job.failed_count = failed
        job.status = JOB_PARTIAL if failed else JOB_SUCCEEDED
        return job

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

    @staticmethod
    def _append_error(existing, message):
        return f"{existing}; {message}" if existing else message

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
